import argparse
import asyncio
from datetime import datetime, timezone
from uuid import UUID
from pathlib import Path
import structlog
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
from app.pipelines.job_signals import JobSignalCollector
from app.services import signal_service
from app.services.snowflake import get_connection
from app.config import get_settings

logger = structlog.get_logger()

TARGET_COMPANIES = {
    "CAT": {"name": "Caterpillar Inc.", "sector": "Manufacturing"},
    "DE": {"name": "Deere & Company", "sector": "Manufacturing"},
    "UNH": {"name": "UnitedHealth Group", "sector": "Healthcare"},
    "HCA": {"name": "HCA Healthcare", "sector": "Healthcare"},
    "ADP": {"name": "Automatic Data Processing", "sector": "Services"},
    "PAYX": {"name": "Paychex Inc.", "sector": "Services"},
    "WMT": {"name": "Walmart Inc.", "sector": "Retail"},
    "TGT": {"name": "Target Corporation", "sector": "Retail"},
    "JPM": {"name": "JPMorgan Chase", "sector": "Financial"},
    "GS": {"name": "Goldman Sachs", "sector": "Financial"},
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
    search_queries = [
        f"{company_name} machine learning",
        f"{company_name} data scientist",
        f"{company_name} artificial intelligence",
    ]
    
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
            logger.info(f"Query results", query=query, jobs_found=len(jobs))
        except Exception as e:
            logger.error(f"Job scraping failed", query=query, error=str(e))
    
    # Deduplicate
    unique_jobs = collector.deduplicate_jobs(all_jobs)
    logger.info("Deduplication complete", 
                ticker=ticker, 
                before=len(all_jobs), 
                after=len(unique_jobs))
    
    # Analyze
    signal = collector.analyze_job_postings(company_name, unique_jobs)
    signal.company_id = company_id
    
    # Store in database
    signal_service.store_signal(signal)
    logger.info("Signal stored", 
                ticker=ticker, 
                score=signal.normalized_score,
                ai_jobs=signal.metadata['ai_jobs'])
    
    # Update summary
    signal_service.update_signal_summary(company_id)
    logger.info("Summary updated", ticker=ticker)
    
    return signal.metadata['ai_jobs']


async def main(tickers: list[str]):

    logger.info("Starting evidence collection", companies=tickers)
    
    stats = {
        "companies_processed": 0,
        "total_ai_jobs": 0,
        "errors": 0,
    }
    
    for ticker in tickers:
        if ticker not in TARGET_COMPANIES:
            logger.warning("Unknown ticker", ticker=ticker)
            continue
        
        company_info = TARGET_COMPANIES[ticker]
        company_name = company_info["name"]
        sector = company_info["sector"]
        
        logger.info("Processing company", 
                   ticker=ticker, 
                   name=company_name, 
                   sector=sector)
        
        try:
            # Get or create company
            company_id = await get_or_create_company(ticker, company_name, sector)
            
            # Collect job signals
            ai_jobs = await collect_job_signals(ticker, company_id, company_name)
            
            stats["companies_processed"] += 1
            stats["total_ai_jobs"] += ai_jobs
            
            logger.info("Company complete", 
                       ticker=ticker, 
                       ai_jobs=ai_jobs,
                       progress=f"{stats['companies_processed']}/{len(tickers)}")
            
        except Exception as e:
            logger.error("Company processing failed", 
                        ticker=ticker, 
                        error=str(e),
                        error_type=type(e).__name__)
            stats["errors"] += 1
    
    # Final summary
    logger.info("Collection complete", **stats)
    
    print("\n" + "="*70)
    print("Evidence Collection Summary")
    print("="*70)
    print(f"Companies Processed: {stats['companies_processed']}/{len(tickers)}")
    print(f"Total AI Jobs Found: {stats['total_ai_jobs']}")
    print(f"Errors: {stats['errors']}")
    print("="*70)
    
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Collect evidence for target companies"
    )
    parser.add_argument(
        "--companies",
        default="all",
        help="Comma-separated tickers or 'all'"
    )
    parser.add_argument(
        "--ticker",
        help="Single ticker to process (alternative to --companies)"
    )
    
    args = parser.parse_args()
    
    # Determine which companies to process
    if args.ticker:
        tickers = [args.ticker.strip().upper()]
    elif args.companies == "all":
        tickers = list(TARGET_COMPANIES.keys())
    else:
        tickers = [t.strip().upper() for t in args.companies.split(",")]
    

    asyncio.run(main(tickers))