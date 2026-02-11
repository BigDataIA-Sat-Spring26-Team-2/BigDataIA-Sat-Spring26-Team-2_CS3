import argparse
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from uuid import UUID
from pathlib import Path
import structlog
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.pipelines.job_signals import JobSignalCollector
from app.pipelines.tech_signals import TechSignalCollector
from app.pipelines.patent_signals import PatentSignalCollector
from app.reports.patent_report import write_patent_report
from app.models.signal import ExternalSignal
from app.models.signal import SignalCategory, SignalSource

from app.services import signal_service
from app.services.snowflake import get_connection
from app.config import get_settings

logger = structlog.get_logger()

TARGET_COMPANIES = {
	"CAT": {"name": "Caterpillar Inc.", "sector": "Manufacturing", "assignee": "Caterpillar Inc."},
	"DE": {"name": "Deere & Company", "sector": "Manufacturing", "assignee": "Deere & Company"},
	"UNH": {"name": "UnitedHealth Group", "sector": "Healthcare", "assignee": "UnitedHealth Group Incorporated"},
	"HCA": {"name": "HCA Healthcare", "sector": "Healthcare", "assignee": "HCA Healthcare, Inc."},
	"ADP": {"name": "Automatic Data Processing", "sector": "Services", "assignee": "Automatic Data Processing, Inc."},
	"PAYX": {"name": "Paychex Inc.", "sector": "Services", "assignee": "Paychex Inc."},
	"WMT": {"name": "Walmart Inc.", "sector": "Retail", "assignee": "Walmart Apollo Llc"},
	"TGT": {"name": "Target Corporation", "sector": "Retail", "assignee": "Target Brands, Inc"},
	"JPM": {"name": "JPMorgan Chase", "sector": "Financial", "assignee": "Jp Morgan Chase Bank, N.A."},
	"GS": {"name": "Goldman Sachs", "sector": "Financial", "assignee": "Goldman Sachs & Co"},
}


def _fq_table(name: str) -> str:
	s = get_settings()
	return f"{s.SNOWFLAKE_DATABASE}.{s.SNOWFLAKE_SCHEMA}.{name}"


async def get_or_create_company(ticker: str, name: str, sector: str) -> UUID:
	conn = None
	cur = None
	try:
		conn = get_connection()
		cur = conn.cursor()

		cur.execute(
			f"SELECT id FROM {_fq_table('COMPANIES')} WHERE ticker = %s AND is_deleted = FALSE",
			(ticker,),
		)
		row = cur.fetchone()

		if row:
			logger.info("Company found", ticker=ticker, company_id=row[0])
			return UUID(row[0])

		cur.execute(
			f"SELECT id FROM {_fq_table('INDUSTRIES')} WHERE sector = %s LIMIT 1",
			(sector,),
		)
		industry_row = cur.fetchone()

		if not industry_row:
			logger.error("No industry found for sector", sector=sector)
			raise ValueError(f"No industry found for sector: {sector}")

		industry_id = industry_row[0]

		from uuid import uuid4

		company_id = str(uuid4())
		now = datetime.now(timezone.utc)

		cur.execute(
			f"""
			INSERT INTO {_fq_table('COMPANIES')} (
				id, name, ticker, industry_id, position_factor,
				is_deleted, created_at, updated_at
			)
			VALUES (%s, %s, %s, %s, %s, FALSE, %s, %s)
			""",
			(company_id, name, ticker, industry_id, 0.0, now, now),
		)
		conn.commit()

		logger.info("Company created", ticker=ticker, company_id=company_id)
		return UUID(company_id)

	finally:
		if cur:
			cur.close()
		if conn:
			conn.close()


async def collect_job_signals(ticker: str, company_id: UUID, company_name: str) -> Dict:
	logger.info("Collecting job signals", ticker=ticker, company_name=company_name)

	collector = JobSignalCollector()

	search_queries = collector.get_optimized_search_queries(company_name)
	logger.info(
		"search_queries_generated",
		ticker=ticker,
		num_queries=len(search_queries),
		queries=search_queries,
	)

	all_jobs = []
	for query in search_queries:
		try:
			jobs = collector.scrape_jobs_from_multiple_sources(
				search_query=query,
				sources=["linkedin", "indeed", "glassdoor"],
				max_results_per_source=15,
				location="United States",
				hours_old=24 * 30,
			)
			all_jobs.extend(jobs)
			logger.info("query_complete", ticker=ticker, query=query[:80], jobs_found=len(jobs))
		except Exception as e:
			logger.error("query_failed", ticker=ticker, query=query[:80], error=str(e), error_type=type(e).__name__)

	unique_jobs = collector.deduplicate_jobs(all_jobs)

	signal = collector.analyze_job_postings(company_name, unique_jobs)
	signal.company_id = company_id

	signal_service.store_signal(signal)
	signal_service.update_signal_summary(company_id)
	logger.info("Summary updated", ticker=ticker)

	return {
		"ai_jobs": signal.metadata.get("ai_jobs", 0),
		"avg_ai_relevance": signal.metadata.get("avg_ai_relevance", 0.0),
		"normalized_score": signal.normalized_score,
		"total_jobs": signal.metadata.get("total_jobs", 0),
		"total_tech_jobs": signal.metadata.get("total_tech_jobs", 0),
		"by_source": signal.metadata.get("by_source", {}),
	}


async def collect_tech_signals(ticker: str, company_id: UUID, company_name: str) -> Dict:
	"""
	Collect tech/digital presence signals (same as API /collect-tech-signals).
	"""
	logger.info("Collecting tech signals", ticker=ticker, company_name=company_name)

	collector = TechSignalCollector()

	# Same signature you use in the API router
	signal = collector.analyze_digital_presence(company_name=company_name, ticker=ticker)
	signal.company_id = company_id

	signal_service.store_signal(signal)
	signal_service.update_signal_summary(company_id)

	logger.info("Tech signal stored", ticker=ticker, score=signal.normalized_score)

	return {
		"normalized_score": signal.normalized_score,
		"metadata": signal.metadata or {},
	}


async def collect_patent_signal(ticker: str, company_id: UUID, assignee: str):
	logger.info("Collecting patent signal", ticker=ticker, assignee=assignee)

	collector = PatentSignalCollector()

	cutoff = datetime.now(timezone.utc) - timedelta(days=5 * 365)
	after_date = cutoff.strftime("%Y%m%d")

	verification_url = collector.build_verification_url(
		assignee=assignee,
		after_yyyymmdd=after_date,
	)
	logger.info("Patent verification URL", url=verification_url)

	analysis = await collector.analyze(verification_url)

	logger.info(
		"Patent analysis result",
		count=analysis.count,
		recent=analysis.recent,
		categories=analysis.categories,
	)

	signal = collector.score(company_id=company_id, assignee=assignee, analysis=analysis)

	signal_service.store_signal(signal)
	signal_service.update_signal_summary(company_id)

	out_dir = Path("reports/patent_signals") / ticker
	paths = write_patent_report(signal, out_dir)

	logger.info(
		"Patent signal stored + report written",
		ticker=ticker,
		score=signal.normalized_score,
		report_md=str(paths.md_path),
		report_csv=str(paths.csv_path),
	)

	return signal


async def collect_leadership_signals(ticker: str, company_id: UUID, company_name: str) -> Dict:
	logger.info("=== LEADERSHIP SIGNALS START ===", ticker=ticker, company_name=company_name)

	from app.pipelines.leadership_signals import LeadershipSignalCollector

	collector = LeadershipSignalCollector()
	try:
		signal = await collector.analyze_company_leadership(
			company_id=company_id,
			ticker=ticker,
			company_name=company_name,
		)
		signal_service.store_signal(signal)

		logger.info(
			"Leadership signal stored",
			ticker=ticker,
			score=signal.normalized_score,
			executives_analyzed=signal.metadata.get("executives_analyzed", 0),
			ai_executives=signal.metadata.get("ai_executives", 0),
			tier=signal.metadata.get("tier", "Unknown"),
		)

		return {
			"score": signal.normalized_score,
			"executives": signal.metadata.get("executives_analyzed", 0),
			"ai_executives": signal.metadata.get("ai_executives", 0),
			"tier": signal.metadata.get("tier", "Unknown"),
		}
	finally:
		await collector.close()
		logger.info("=== LEADERSHIP SIGNALS COMPLETE ===", ticker=ticker)


async def main(tickers: list[str], signal_types: list[str]):
	logger.info("Starting evidence collection", companies=tickers, signal_types=signal_types)

	stats = {
		"companies_processed": 0,
		"job_signals": {"collected": 0, "total_ai_jobs": 0, "errors": 0},
		"leadership_signals": {"collected": 0, "total_executives": 0, "total_ai_executives": 0, "errors": 0},
		"patent_signals": {"collected": 0, "errors": 0},
		"tech_signals": {"collected": 0, "errors": 0},
		"board_signals": {"collected": 0, "errors": 0},
	}

	collect_job = "job" in signal_types or "all" in signal_types
	collect_leadership = "leadership" in signal_types or "all" in signal_types
	collect_patent = "patent" in signal_types or "all" in signal_types
	collect_tech = "tech" in signal_types or "all" in signal_types
	collect_board = "board" in signal_types or "all" in signal_types

	for ticker in tickers:
		if ticker not in TARGET_COMPANIES:
			logger.warning("Unknown ticker", ticker=ticker)
			continue

		company_info = TARGET_COMPANIES[ticker]
		company_name = company_info["name"]
		sector = company_info["sector"]
		assignee = company_info.get("assignee") or company_name

		logger.info("Processing company", ticker=ticker, name=company_name, sector=sector)

		try:
			company_id = await get_or_create_company(ticker, company_name, sector)

			# JOB
			if collect_job:
				try:
					metrics = await collect_job_signals(ticker, company_id, company_name)
					stats["job_signals"]["collected"] += 1
					stats["job_signals"]["total_ai_jobs"] += metrics.get("ai_jobs", 0)
					logger.info("Job signals collected", ticker=ticker, ai_jobs=metrics.get("ai_jobs", 0))
				except Exception as e:
					stats["job_signals"]["errors"] += 1
					logger.error("Job signals failed", ticker=ticker, error=str(e))

			# LEADERSHIP
			if collect_leadership:
				try:
					leadership_result = await collect_leadership_signals(ticker, company_id, company_name)
					stats["leadership_signals"]["collected"] += 1
					stats["leadership_signals"]["total_executives"] += leadership_result.get("executives", 0)
					stats["leadership_signals"]["total_ai_executives"] += leadership_result.get("ai_executives", 0)
					logger.info("Leadership signals collected", ticker=ticker, score=leadership_result.get("score"))
				except Exception as e:
					stats["leadership_signals"]["errors"] += 1
					logger.error("Leadership signals failed", ticker=ticker, error=str(e))

			# TECH
			if collect_tech:
				try:
					tech_result = await collect_tech_signals(ticker, company_id, company_name)
					stats["tech_signals"]["collected"] += 1
					logger.info("Tech signals collected", ticker=ticker, score=tech_result.get("normalized_score"))
				except Exception as e:
					stats["tech_signals"]["errors"] += 1
					logger.error("Tech signals failed", ticker=ticker, error=str(e))

			# PATENT
			if collect_patent:
				try:
					await collect_patent_signal(ticker, company_id, assignee)
					stats["patent_signals"]["collected"] += 1
					logger.info("Patent signals collected", ticker=ticker)
				except Exception as e:
					stats["patent_signals"]["errors"] += 1
					logger.error("Patent signals failed", ticker=ticker, error=str(e))

			# Update summary (safe to call even if each collector also calls it)
			try:
				signal_service.update_signal_summary(company_id)
				logger.info("Summary updated", ticker=ticker)
			except Exception as e:
				logger.error("Summary update failed", ticker=ticker, error=str(e))

			stats["companies_processed"] += 1
			logger.info("Company complete", ticker=ticker, progress=f"{stats['companies_processed']}/{len(tickers)}")

		except Exception as e:
			logger.error("Company processing failed", ticker=ticker, error=str(e), error_type=type(e).__name__)

	# Print summary
	logger.info("Collection complete", **stats)

	print("\n" + "=" * 70)
	print("EVIDENCE COLLECTION SUMMARY")
	print("=" * 70)
	print(f"Companies Processed: {stats['companies_processed']}/{len(tickers)}")

	if collect_job:
		print("\nJob Signals:")
		print(f"  Collected: {stats['job_signals']['collected']}")
		print(f"  Total AI Jobs: {stats['job_signals']['total_ai_jobs']}")
		print(f"  Errors: {stats['job_signals']['errors']}")

	if collect_leadership:
		print("\nLeadership Signals:")
		print(f"  Collected: {stats['leadership_signals']['collected']}")
		print(f"  Total Executives: {stats['leadership_signals']['total_executives']}")
		print(f"  AI-Relevant Executives: {stats['leadership_signals']['total_ai_executives']}")
		print(f"  Errors: {stats['leadership_signals']['errors']}")

	if collect_tech:
		print("\nTech Signals:")
		print(f"  Collected: {stats['tech_signals']['collected']}")
		print(f"  Errors: {stats['tech_signals']['errors']}")

	if collect_patent:
		print("\nPatent Signals:")
		print(f"  Collected: {stats['patent_signals']['collected']}")
		print(f"  Errors: {stats['patent_signals']['errors']}")

	print("=" * 70)
	# BOARD GOVERNANCE
	if collect_board:
		try:
			from app.pipelines.board_analyzer import BoardCompositionAnalyzer
		
			analyzer = BoardCompositionAnalyzer()
			result = analyzer.analyze_company_governance(ticker)
		
			if result:
			# Convert to signal and store (same pattern as leadership)
				signal = ExternalSignal(
					company_id=company_id,
					category=SignalCategory.AI_GOVERNANCE,
                source=SignalSource.COMPANY_WEBSITE,
                signal_date=datetime.now(timezone.utc),
                raw_value=f"Board governance: {result.governance_score:.1f}/100",
                normalized_score=float(result.governance_score),
                confidence=float(result.confidence),
                metadata={"governance_score": float(result.governance_score), "confidence": float(result.confidence)}
				)
				signal_service.store_signal(signal)
			
				stats["board_signals"]["collected"] += 1
				logger.info("Board signals collected", ticker=ticker, score=result.governance_score)
		except Exception as e:
			stats["board_signals"]["errors"] += 1
			logger.error("Board signals failed", ticker=ticker, error=str(e))


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Collect evidence for target companies")
	parser.add_argument("--companies", default="all", help="Comma-separated tickers or 'all' (default: all)")
	parser.add_argument("--ticker", help="Single ticker to process (alternative to --companies)")
	parser.add_argument(
		"--signals",
		default="all",
		choices=["job", "leadership", "tech", "patent", "all", "board"],
		help="Signal types to collect: job, leadership, tech, patent, or all (default: all)",
	)

	args = parser.parse_args()

	if args.ticker:
		tickers = [args.ticker.strip().upper()]
	elif args.companies == "all":
		tickers = list(TARGET_COMPANIES.keys())
	else:
		tickers = [t.strip().upper() for t in args.companies.split(",")]

	if args.signals == "all":
		signal_types = ["job", "leadership", "tech", "patent"]
	else:
		signal_types = [args.signals]

	asyncio.run(main(tickers, signal_types))
