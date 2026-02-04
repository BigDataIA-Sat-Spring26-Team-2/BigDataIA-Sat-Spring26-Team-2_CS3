from fastapi import APIRouter, status, Query, BackgroundTasks
from typing import Optional
from uuid import UUID
from app.pipelines.tech_signals import TechSignalCollector
from app.models.signal import (
    ExternalSignal,
    CompanySignalSummary,
    SignalCategory,
)
from app.models.pagination import PaginatedResponse
from app.services import signal_service
from app.pipelines.job_signals import JobSignalCollector

from app.pipelines.patent_signals import PatentSignalCollector


from app.pipelines.leadership_signals import LeadershipSignalCollector
from app.services import snowflake


router = APIRouter(prefix="/signals", tags=["Signals"])


@router.post(
    "/collect-job-signals",
    response_model=ExternalSignal,
    status_code=status.HTTP_201_CREATED
)
async def collect_job_signals(
    company_id: UUID = Query(...),
    company_name: str = Query(...),
    max_results: int = Query(default=20, ge=5, le=50),
    background_tasks: BackgroundTasks = None,
):
    """
    Collect job posting signals for a company.
    
    This scrapes job boards (LinkedIn, Indeed) and calculates AI hiring signal.
    
    Args:
        company_id: Company UUID from database
        company_name: Company name for job search
        max_results: Max results per source (default: 20)
        
    Returns:
        ExternalSignal with AI hiring score
    """
    collector = JobSignalCollector()
    
    # Search queries
    search_queries = [
        f"{company_name} machine learning",
        f"{company_name} data scientist",
        f"{company_name} artificial intelligence",
    ]
    
    all_jobs = []
    for query in search_queries:
        jobs = collector.scrape_jobs_from_multiple_sources(
            search_query=query,
            sources=["linkedin", "indeed"],
            max_results_per_source=max_results,
            location="United States",
            hours_old=24 * 30  # Last 30 days
        )
        all_jobs.extend(jobs)
    
    # Deduplicate
    unique_jobs = collector.deduplicate_jobs(all_jobs)
    
    # Analyze and create signal
    signal = collector.analyze_job_postings(company_name, unique_jobs)
    signal.company_id = company_id
    
    # Store in database
    stored_signal = signal_service.store_signal(signal)
    
    # Update summary in background
    if background_tasks:
        background_tasks.add_task(
            signal_service.update_signal_summary,
            company_id
        )
    else:
        signal_service.update_signal_summary(company_id)
    
    return stored_signal

@router.post(
    "/collect-tech-signals",
    response_model=ExternalSignal,
    status_code=status.HTTP_201_CREATED
)
async def collect_tech_signals(
    company_id: UUID = Query(...),
    company_name: str = Query(...),
    ticker: str = Query(..., description="Ticker used to look up hardcoded COMPANY_SOURCES"),
    background_tasks: BackgroundTasks = None,
):
    collector = TechSignalCollector()

    signal = collector.analyze_digital_presence(company_name=company_name, ticker=ticker)
    signal.company_id = company_id

    stored_signal = signal_service.store_signal(signal)

    if background_tasks:
        background_tasks.add_task(signal_service.update_signal_summary, company_id)
    else:
        signal_service.update_signal_summary(company_id)

    return stored_signal


@router.get(
    "/companies/{company_id}",
    response_model=PaginatedResponse[ExternalSignal]
)
def get_company_signals(
    company_id: UUID,
    category: Optional[SignalCategory] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return signal_service.get_signals_for_company(
        company_id=company_id,
        category=category,
        page=page,
        page_size=page_size,
    )
@router.post(
    "/collect-patent-signals",
    response_model=ExternalSignal,
    status_code=status.HTTP_201_CREATED
)
async def collect_patent_signals(
    company_id: UUID = Query(..., description="Company UUID from DB"),
    assignee: str = Query(..., description="Assignee name to search on Google Patents"),
    max_pages: int = Query(default=2, ge=1, le=10, description="How many results pages to scan (100 results each)"),
    years: int = Query(default=5, ge=1, le=15, description="How many years back to count patents"),
    background_tasks: BackgroundTasks = None,
):
    """
    Collect AI-related patent signals from Google Patents.

    Flow:
    - Search Google Patents by assignee
    - For each result, open patent page
    - Confirm assignee and extract CPC classifications
    - Filter by AI CPC list
    - Score using CS2 rubric and store as INNOVATION_ACTIVITY signal
    """
    collector = PatentSignalCollector(concurrency=5)
    signal = await collector.collect_and_score_google_patents(
        company_id=company_id,
        assignee=assignee,
        max_pages=max_pages,
        results_per_page=100,
        years=years,
    )

    stored_signal = signal_service.store_signal(signal)

    if background_tasks:
        background_tasks.add_task(signal_service.update_signal_summary, company_id)
    else:
        signal_service.update_signal_summary(company_id)

    return stored_signal


@router.get(
    "/companies/{company_id}/summary",
    response_model=CompanySignalSummary
)
def get_company_signal_summary(company_id: UUID):
    """
    Get aggregated signal summary for a company.
    
    Returns composite AI readiness score based on all signal categories.
    
    Args:
        company_id: Company UUID
        
    Returns:
        CompanySignalSummary with scores by category
    """
    return signal_service.get_signal_summary(company_id)


@router.post(
    "/companies/{company_id}/summary/refresh",
    response_model=CompanySignalSummary
)
def refresh_signal_summary(company_id: UUID):
    """
    Recalculate signal summary for a company.
    
    Useful after adding new signals to update the composite score.
    
    Args:
        company_id: Company UUID
        
    Returns:
        Updated CompanySignalSummary
    """

    return signal_service.update_signal_summary(company_id)


    

@router.post(
    "/collect-leadership-signals",
    response_model=ExternalSignal,
    status_code=status.HTTP_201_CREATED
)
async def collect_leadership_signals(
    company_id: UUID = Query(...),
    ticker: str = Query(...),
    background_tasks: BackgroundTasks = None,
):
    """
    Collect leadership commitment signals from existing SEC filings.
    """
    import time
    from app.config import get_settings
    from fastapi import HTTPException
    
    start_time = time.time()
    
    print(f"\n{'='*60}")
    print(f"🔍 Starting leadership collection for {ticker}")
    print(f"{'='*60}\n")
    
    settings = get_settings()
    
    # Fetch document chunks from Snowflake
    print(f"[1] Connecting to Snowflake...")
    conn = snowflake.get_connection()
    cur = conn.cursor()
    print(f"[1] ✅ Connected ({time.time() - start_time:.2f}s)")
    
    try:
        # Count total chunks
        print(f"\n[2] Counting chunks...")
        count_query = f"""
        SELECT COUNT(*) 
        FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.document_chunks dc
        JOIN {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.documents d
            ON dc.document_id = d.id
        WHERE d.company_id = %s AND d.ticker = %s
        """
        cur.execute(count_query, (str(company_id), ticker))
        total_chunks = cur.fetchone()[0]
        print(f"[2] ✅ Found {total_chunks} total chunks ({time.time() - start_time:.2f}s)")
        
        if total_chunks == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No document chunks found for {ticker}. Run SEC EDGAR pipeline first."
            )
        
        # Fetch chunks with section info
        # COALESCE handles both old chunks (section=NULL) and new chunks (section='item_1_business')
        print(f"\n[3] Fetching chunks (stratified by filing type)...")
        query = f"""
        WITH ranked_chunks AS (
            SELECT 
                dc.chunk_text, 
                d.filing_type,
                COALESCE(dc.section, 'unknown') as section,
                d.filing_date,
                ROW_NUMBER() OVER (PARTITION BY d.filing_type ORDER BY d.filing_date DESC, dc.chunk_index) as rn
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.document_chunks dc
            JOIN {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.documents d
                ON dc.document_id = d.id
            WHERE d.company_id = %s 
              AND d.ticker = %s
        )
        SELECT chunk_text, filing_type, section
        FROM ranked_chunks
        WHERE rn <= 50
        ORDER BY filing_type, rn
        """
        
        cur.execute(query, (str(company_id), ticker))
        rows = cur.fetchall()
        print(f"[3] ✅ Fetched {len(rows)} chunks ({time.time() - start_time:.2f}s)")
        
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No chunks returned for {ticker}"
            )
        
        chunks = [
            {
                'chunk_text': row[0],
                'filing_type': row[1],
                'section': row[2]  # Will be actual section or 'unknown'
            }
            for row in rows
        ]
        
        # Show sample
        print(f"    Sample:")
        print(f"    - Filing: {chunks[0]['filing_type']}")
        print(f"    - Section: {chunks[0]['section']}")
        print(f"    - Text: {len(chunks[0]['chunk_text'])} chars")
        
        # Show section distribution
        section_counts = {}
        for chunk in chunks:
            section = chunk['section']
            section_counts[section] = section_counts.get(section, 0) + 1
        
        print(f"\n    Section distribution:")
        for section, count in sorted(section_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"      {section}: {count} chunks")
        
        # ✅ ADD THIS - Filing type distribution
        filing_counts = {}
        for chunk in chunks:
            ft = chunk['filing_type']
            filing_counts[ft] = filing_counts.get(ft, 0) + 1
        
        print(f"\n    Filing type distribution:")
        for ft, count in sorted(filing_counts.items()):
            print(f"      {ft}: {count} chunks")
        
    finally:
        cur.close()
        conn.close()
        print(f"[3] Connection closed ({time.time() - start_time:.2f}s)")
    
    # Analyze
    print(f"\n[4] Analyzing with LeadershipSignalCollector...")
    collector = LeadershipSignalCollector()
    signal = await collector.analyze_company_leadership(
        company_id=company_id,
        ticker=ticker,
        document_chunks=chunks
    )
    print(f"[4] ✅ Analysis complete ({time.time() - start_time:.2f}s)")
    print(f"    Score: {signal.normalized_score:.1f}/100")
    print(f"    Evidence: {signal.metadata.get('evidence_count')} pieces")
    
    # Store
    print(f"\n[5] Storing signal...")
    stored_signal = signal_service.store_signal(signal)
    print(f"[5] ✅ Stored ({time.time() - start_time:.2f}s)")
    
    # Update summary
    print(f"\n[6] Updating summary...")
    if background_tasks:
        background_tasks.add_task(
            signal_service.update_signal_summary,
            company_id
        )
        print(f"[6] Summary queued (background) ({time.time() - start_time:.2f}s)")
    else:
        signal_service.update_signal_summary(company_id)
        print(f"[6] ✅ Summary updated ({time.time() - start_time:.2f}s)")
    
    total_time = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"✅ COMPLETE in {total_time:.2f}s")
    print(f"{'='*60}\n")
    
    return stored_signal

