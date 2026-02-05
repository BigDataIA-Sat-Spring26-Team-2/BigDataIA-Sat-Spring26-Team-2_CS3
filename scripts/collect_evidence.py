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
from app.services import signal_service
from app.pipelines.patent_signals import PatentSignalCollector
from app.reports.patent_report import write_patent_report
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
    """
    Get company_id from database or create if doesn't exist.
    
    Returns:
        UUID of the company
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Check if company exists
        cur.execute(
            f"SELECT id FROM {_fq_table('COMPANIES')} WHERE ticker = %s AND is_deleted = FALSE",
            (ticker,)
        )
        row = cur.fetchone()
        
        if row:
            logger.info(f"Company found", ticker=ticker, company_id=row[0])
            return UUID(row[0])
        
        # Company doesn't exist, create it
        # First, get industry_id based on sector
        cur.execute(
            f"SELECT id FROM {_fq_table('INDUSTRIES')} WHERE sector = %s LIMIT 1",
            (sector,)
        )
        industry_row = cur.fetchone()
        
        if not industry_row:
            logger.error(f"No industry found for sector", sector=sector)
            raise ValueError(f"No industry found for sector: {sector}")
        
        industry_id = industry_row[0]
        
        # Create company
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
            (company_id, name, ticker, industry_id, 0.0, now, now)
        )
        conn.commit()
        
        logger.info(f"Company created", ticker=ticker, company_id=company_id)
        return UUID(company_id)
        
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


async def collect_job_signals(ticker: str, company_id: UUID, company_name: str):

    logger.info("Collecting job signals", ticker=ticker, company_name=company_name)
    
    collector = JobSignalCollector()
    
    # Multiple search queries for comprehensive results
    search_queries = collector.get_optimized_search_queries(company_name)
    logger.info(
        "search_queries_generated",
        ticker=ticker,
        num_queries=len(search_queries),
        queries=search_queries
    )
    # search_queries = [
    #     f"{company_name} (machine learning OR ML OR AI) engineer",
    #     f"{company_name} (data scientist OR research scientist OR applied scientist)",
    #     f"{company_name} (computer vision OR NLP OR deep learning)",
    #     f"{company_name} (MLOps OR ML infrastructure OR AI platform)",
    #     f"{company_name} (LLM OR generative AI OR prompt engineer)",
    #     f"{company_name} data engineer (ML OR AI pipeline)",
    # ]
    
    all_jobs = []
    for query in search_queries:
        try:
            jobs = collector.scrape_jobs_from_multiple_sources(
                search_query=query,
                sources=["linkedin", "indeed", "glassdoor"],
                max_results_per_source=15,
                location="United States",
                hours_old=24 * 30
            )
            all_jobs.extend(jobs)
            logger.info(
                "query_complete",
                ticker=ticker,
                query=query[:80],
                jobs_found=len(jobs)
            )
        except Exception as e:
            logger.error(
                "query_failed",
                ticker=ticker,
                query=query[:80],
                error=str(e),
                error_type=type(e).__name__
            )
    
    # Deduplicate
    unique_jobs = collector.deduplicate_jobs(all_jobs)

    jobs_by_source_before = {}
    jobs_by_source_after = {}
    
    for job in all_jobs:
        jobs_by_source_before[job.source] = jobs_by_source_before.get(job.source, 0) + 1
    
    for job in unique_jobs:
        jobs_by_source_after[job.source] = jobs_by_source_after.get(job.source, 0) + 1
    
    logger.info(
        "deduplication_complete",
        ticker=ticker,
        before=len(all_jobs),
        after=len(unique_jobs),
        duplicates_removed=len(all_jobs) - len(unique_jobs),
        before_by_source=jobs_by_source_before,
        after_by_source=jobs_by_source_after
    )
    
    # Analyze
    signal = collector.analyze_job_postings(company_name, unique_jobs)
    signal.company_id = company_id
    
    # Store in database
    signal_service.store_signal(signal)

     # Extract metrics
    ai_jobs = signal.metadata['ai_jobs']
    avg_ai_relevance = signal.metadata.get('avg_ai_relevance', 0.0)
    normalized_score = signal.normalized_score
    by_source = signal.metadata.get('by_source', {})

    logger.info(
        "signal_stored",
        ticker=ticker,
        score=normalized_score,
        avg_ai_relevance=avg_ai_relevance,
        ai_jobs=ai_jobs,
        linkedin_ai_jobs=by_source.get('linkedin', {}).get('ai_jobs', 0) if by_source.get('linkedin') else 0,
        indeed_ai_jobs=by_source.get('indeed', {}).get('ai_jobs', 0) if by_source.get('indeed') else 0,
        linkedin_avg_relevance=by_source.get('linkedin', {}).get('avg_relevance', 0.0) if by_source.get('linkedin') else 0.0,
        indeed_avg_relevance=by_source.get('indeed', {}).get('avg_relevance', 0.0) if by_source.get('indeed') else 0.0,
    )
    
    # Update summary
    signal_service.update_signal_summary(company_id)
    logger.info("Summary updated", ticker=ticker)
    
    return {
        "ai_jobs": ai_jobs,
        "avg_ai_relevance": avg_ai_relevance,
        "normalized_score": normalized_score,
        "total_jobs": signal.metadata.get('total_jobs', 0),
        "total_tech_jobs": signal.metadata.get('total_tech_jobs', 0),
        "by_source": by_source
    }

async def collect_patent_signal(ticker: str, company_id, assignee: str):
    """
    Collect patent signals using Playwright (JS-rendered),
    exactly like the notebook.
    """

    logger = structlog.get_logger()
    logger.info("Collecting patent signal", ticker=ticker, assignee=assignee)

    collector = PatentSignalCollector()

    # Same 5-year cutoff logic as notebook
    cutoff = datetime.now(timezone.utc) - timedelta(days=5 * 365)
    after_date = cutoff.strftime("%Y%m%d")

    # ✅ EXACT SAME URL LOGIC AS NOTEBOOK
    print("DEBUG calling build_verification_url")
    print("  assignee arg =", assignee)
    print("  after_date =", after_date)
    verification_url = collector.build_verification_url(
        assignee=assignee,
        after_yyyymmdd=after_date
    )

    logger.info("Patent verification URL", url=verification_url)

    # ✅ PLAYWRIGHT-BASED SCRAPE (THIS WAS THE MISSING PIECE)
    analysis = await collector.analyze(verification_url)

    logger.info(
        "Patent analysis result",
        count=analysis.count,
        recent=analysis.recent,
        categories=analysis.categories,
    )

    # Score exactly like notebook
    signal = collector.score(company_id=company_id, assignee=assignee, analysis=analysis)


    # Store + update summary
    signal_service.store_signal(signal)
    signal_service.update_signal_summary(company_id)

    # Write report (same pattern as job report)
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


async def main(tickers: list[str]):

    logger = structlog.get_logger()
    logger.info("Starting evidence collection", companies=tickers)

    stats = {
        "companies_processed": 0,
        "errors": 0,
        "total_ai_jobs": 0,
    }

    company_results: List[Dict] = []

    for ticker in tickers:
        if ticker not in TARGET_COMPANIES:
            logger.warning("Unknown ticker", ticker=ticker)
            continue

        company_info = TARGET_COMPANIES[ticker]
        company_name = company_info["name"]
        sector = company_info["sector"]
        assignee = company_info.get("assignee") or company_name

        logger.info(
            "Processing company",
            ticker=ticker,
            name=company_name,
            sector=sector
        )

        try:
            company_id = await get_or_create_company(
                ticker, company_name, sector
            )

            # -------- JOB SIGNALS --------
            metrics = await collect_job_signals(
                ticker, company_id, company_name
            )

            stats["total_ai_jobs"] += metrics["ai_jobs"]

            # -------- PATENT SIGNALS (PLAYWRIGHT) --------
            await collect_patent_signal(
                ticker, company_id, assignee
            )

            stats["companies_processed"] += 1

            company_results.append({
                "ticker": ticker,
                "name": company_name,
                "sector": sector,
                "ai_jobs": metrics["ai_jobs"],
                "total_jobs": metrics["total_jobs"],
                "total_tech_jobs": metrics["total_tech_jobs"],
                "avg_ai_relevance": metrics["avg_ai_relevance"],
                "normalized_score": metrics["normalized_score"],
                "status": "success"
            })

            logger.info(
                "Company complete",
                ticker=ticker,
                ai_jobs=metrics["ai_jobs"],
                progress=f"{stats['companies_processed']}/{len(tickers)}"
            )

        except Exception as e:
            stats["errors"] += 1
            logger.error(
                "Company processing failed",
                ticker=ticker,
                error=str(e),
                error_type=type(e).__name__
            )

            company_results.append({
                "ticker": ticker,
                "name": company_name,
                "sector": sector,
                "status": "failed",
                "error": str(e)
            })

    print_final_report(company_results, stats, tickers)

    logger.info("Collection complete", **stats)
    return stats



def print_final_report(company_results: List[Dict], stats: Dict, tickers: List[str]):
    """
    Print a comprehensive final report with AI relevance scores.
    """
    print("\n" + "="*100)
    print("EVIDENCE COLLECTION - FINAL REPORT")
    print("="*100)
    print(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Companies Processed: {stats['companies_processed']}/{len(tickers)}")
    print(f"Total AI Jobs Found: {stats['total_ai_jobs']}")
    print(f"Errors: {stats['errors']}")
    print("="*100)
    
    print("\nDETAILED RESULTS BY COMPANY")
    print("-"*100)
    print(f"{'Ticker':<8} {'Company Name':<30} {'Sector':<15} {'AI Jobs':<10} {'Tech Jobs':<12} {'Avg Relevance':<15} {'Score':<10}")
    print("-"*100)
    
    # Sort by avg_ai_relevance (descending)
    sorted_results = sorted(
        [r for r in company_results if r["status"] == "success"],
        key=lambda x: x["avg_ai_relevance"],
        reverse=True
    )
    
    for result in sorted_results:
        ticker = result["ticker"]
        name = result["name"][:28]  # Truncate long names
        sector = result["sector"][:13]
        ai_jobs = result["ai_jobs"]
        tech_jobs = result["total_tech_jobs"]
        avg_relevance = result["avg_ai_relevance"]
        score = result["normalized_score"]
        
        print(f"{ticker:<8} {name:<30} {sector:<15} {ai_jobs:<10} {tech_jobs:<12} {avg_relevance:<15.3f} {score:<10.1f}")
    

    failed_results = [r for r in company_results if r["status"] == "failed"]
    if failed_results:
        print("\n" + "-"*100)
        print("FAILED COMPANIES")
        print("-"*100)
        for result in failed_results:
            print(f"{result['ticker']:<8} {result['name']:<30} ERROR: {result.get('error', 'Unknown error')}")
    
    print("\n" + "="*100)
    print("KEY INSIGHTS")
    print("="*100)
    
    if sorted_results:
        # Top 3 by AI relevance
        print("\n TOP 3 COMPANIES BY AI RELEVANCE SCORE:")
        for i, result in enumerate(sorted_results[:3], 1):
            print(f"  {i}. {result['name']:<30} - Avg Relevance: {result['avg_ai_relevance']:.3f} ({result['ai_jobs']} AI jobs)")
        
        # Bottom 3 by AI relevance
        if len(sorted_results) >= 3:
            print("\n BOTTOM 3 COMPANIES BY AI RELEVANCE SCORE:")
            for i, result in enumerate(sorted_results[-3:][::-1], 1):
                print(f"  {i}. {result['name']:<30} - Avg Relevance: {result['avg_ai_relevance']:.3f} ({result['ai_jobs']} AI jobs)")
        
        # Sector analysis
        print("\nAI ADOPTION BY SECTOR:")
        sector_stats = {}
        for result in sorted_results:
            sector = result["sector"]
            if sector not in sector_stats:
                sector_stats[sector] = {
                    "count": 0,
                    "total_relevance": 0.0,
                    "total_ai_jobs": 0
                }
            sector_stats[sector]["count"] += 1
            sector_stats[sector]["total_relevance"] += result["avg_ai_relevance"]
            sector_stats[sector]["total_ai_jobs"] += result["ai_jobs"]
        
        for sector, data in sorted(sector_stats.items(), key=lambda x: x[1]["total_relevance"]/x[1]["count"], reverse=True):
            avg_relevance = data["total_relevance"] / data["count"]
            avg_ai_jobs = data["total_ai_jobs"] / data["count"]
            print(f"  {sector:<15} - Avg Relevance: {avg_relevance:.3f} | Avg AI Jobs: {avg_ai_jobs:.1f} | Companies: {data['count']}")
        
        # Overall statistics
        total_relevance = sum(r["avg_ai_relevance"] for r in sorted_results)
        avg_relevance_all = total_relevance / len(sorted_results) if sorted_results else 0.0
        
        print("\nOVERALL STATISTICS:")
        print(f"  Average AI Relevance Across All Companies: {avg_relevance_all:.3f}")
        print(f"  Highest AI Relevance: {sorted_results[0]['avg_ai_relevance']:.3f} ({sorted_results[0]['name']})")
        print(f"  Lowest AI Relevance: {sorted_results[-1]['avg_ai_relevance']:.3f} ({sorted_results[-1]['name']})")
        print(f"  Total AI-Relevant Jobs Found: {stats['total_ai_jobs']}")
    
    print("\n" + "="*100)
    print("REPORT COMPLETE")
    print("="*100 + "\n")


# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(
#         description="Collect evidence for target companies"
#     )
#     parser.add_argument(
#         "--companies",
#         default="all",
#         help="Comma-separated tickers or 'all'"
#     )
#     parser.add_argument(
#         "--ticker",
#         help="Single ticker to process (alternative to --companies)"
#     )
    
#     args = parser.parse_args()
    
#     # Determine which companies to process
#     if args.ticker:
#         tickers = [args.ticker.strip().upper()]
#     elif args.companies == "all":
#         tickers = list(TARGET_COMPANIES.keys())
#     else:
#         tickers = [t.strip().upper() for t in args.companies.split(",")]
    

#     asyncio.run(main(tickers))


async def collect_leadership_signals(ticker: str, company_id: UUID, company_name: str):
    """Collect leadership signals from company website and news"""
    
    logger.info("=== LEADERSHIP SIGNALS START ===", ticker=ticker, company_name=company_name)
    
    try:
        from app.pipelines.leadership_signals import LeadershipSignalCollector
        
        # Initialize collector
        collector = LeadershipSignalCollector()
        
        # Analyze leadership
        signal = await collector.analyze_company_leadership(
            company_id=company_id,
            ticker=ticker,
            company_name=company_name
        )
        
        # Store in database
        signal_service.store_signal(signal)
        
        # Cleanup
        await collector.close()
        
        logger.info(
            "Leadership signal stored",
            ticker=ticker,
            score=signal.normalized_score,
            executives_analyzed=signal.metadata.get('executives_analyzed', 0),
            ai_executives=signal.metadata.get('ai_executives', 0),
            tier=signal.metadata.get('tier', 'Unknown')
        )
        
        logger.info("=== LEADERSHIP SIGNALS COMPLETE ===", ticker=ticker)
        
        return {
            "score": signal.normalized_score,
            "executives": signal.metadata.get('executives_analyzed', 0),
            "ai_executives": signal.metadata.get('ai_executives', 0),
            "tier": signal.metadata.get('tier', 'Unknown')
        }
        
    except Exception as e:
        logger.error(
            "Leadership signal collection failed",
            ticker=ticker,
            error=str(e),
            error_type=type(e).__name__
        )
        raise


async def main(tickers: list[str], signal_types: list[str]):
    """
    Collect signals for specified companies and signal types.
    
    Args:
        tickers: List of company tickers
        signal_types: List of signal types to collect ('job', 'leadership', or 'all')
    """
    
    logger.info(
        "Starting evidence collection",
        companies=tickers,
        signal_types=signal_types
    )
    
    stats = {
        "companies_processed": 0,
        "job_signals": {
            "collected": 0,
            "total_ai_jobs": 0,
            "errors": 0
        },
        "leadership_signals": {
            "collected": 0,
            "total_executives": 0,
            "total_ai_executives": 0,
            "errors": 0
        }
    }
    
    collect_job = 'job' in signal_types or 'all' in signal_types
    collect_leadership = 'leadership' in signal_types or 'all' in signal_types
    
    for ticker in tickers:
        if ticker not in TARGET_COMPANIES:
            logger.warning("Unknown ticker", ticker=ticker)
            continue
        
        company_info = TARGET_COMPANIES[ticker]
        company_name = company_info["name"]
        sector = company_info["sector"]
        
        logger.info(
            "Processing company",
            ticker=ticker,
            name=company_name,
            sector=sector
        )
        
        try:
            # Get or create company
            company_id = await get_or_create_company(ticker, company_name, sector)
            
            # Collect job signals
            if collect_job:
                try:
                    ai_jobs = await collect_job_signals(ticker, company_id, company_name)
                    stats["job_signals"]["collected"] += 1
                    stats["job_signals"]["total_ai_jobs"] += ai_jobs
                    logger.info("Job signals collected", ticker=ticker, ai_jobs=ai_jobs)
                except Exception as e:
                    stats["job_signals"]["errors"] += 1
                    logger.error("Job signals failed", ticker=ticker, error=str(e))
            
            # Collect leadership signals
            if collect_leadership:
                try:
                    leadership_result = await collect_leadership_signals(
                        ticker, company_id, company_name
                    )
                    stats["leadership_signals"]["collected"] += 1
                    stats["leadership_signals"]["total_executives"] += leadership_result["executives"]
                    stats["leadership_signals"]["total_ai_executives"] += leadership_result["ai_executives"]
                    logger.info(
                        "Leadership signals collected",
                        ticker=ticker,
                        score=leadership_result["score"],
                        tier=leadership_result["tier"]
                    )
                except Exception as e:
                    stats["leadership_signals"]["errors"] += 1
                    logger.error("Leadership signals failed", ticker=ticker, error=str(e))
            
            # Update summary (combines all signal types)
            try:
                signal_service.update_signal_summary(company_id)
                logger.info("Summary updated", ticker=ticker)
            except Exception as e:
                logger.error("Summary update failed", ticker=ticker, error=str(e))
            
            stats["companies_processed"] += 1
            
            logger.info(
                "Company complete",
                ticker=ticker,
                progress=f"{stats['companies_processed']}/{len(tickers)}"
            )
            
        except Exception as e:
            logger.error(
                "Company processing failed",
                ticker=ticker,
                error=str(e),
                error_type=type(e).__name__
            )
    
    # Final summary
    logger.info("Collection complete", **stats)
    
    print("\n" + "="*70)
    print("EVIDENCE COLLECTION SUMMARY")
    print("="*70)
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
        
        if stats['leadership_signals']['total_executives'] > 0:
            ai_penetration = (
                stats['leadership_signals']['total_ai_executives'] /
                stats['leadership_signals']['total_executives'] * 100
            )
            print(f"  AI Penetration Rate: {ai_penetration:.1f}%")
    
    print("="*70)
    
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Collect evidence for target companies"
    )
    parser.add_argument(
        "--companies",
        default="all",
        help="Comma-separated tickers or 'all' (default: all)"
    )
    parser.add_argument(
        "--ticker",
        help="Single ticker to process (alternative to --companies)"
    )
    parser.add_argument(
        "--signals",
        default="all",
        choices=["job", "leadership", "all"],
        help="Signal types to collect: job, leadership, or all (default: all)"
    )
    
    args = parser.parse_args()
    
    # Determine which companies to process
    if args.ticker:
        tickers = [args.ticker.strip().upper()]
    elif args.companies == "all":
        tickers = list(TARGET_COMPANIES.keys())
    else:
        tickers = [t.strip().upper() for t in args.companies.split(",")]
    
    # Determine which signals to collect
    if args.signals == "all":
        signal_types = ["job", "leadership"]
    else:
        signal_types = [args.signals]
    
    asyncio.run(main(tickers, signal_types))
