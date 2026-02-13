from fastapi import APIRouter, status, Query, BackgroundTasks, HTTPException
from typing import Optional
from uuid import UUID
from pathlib import Path
import structlog
from app.models.enums import SignalSource
from app.schemas.signal_tasks import QueuedTaskResponse
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
from app.reports.patent_report import write_patent_report
from app.services.snowflake import get_connection

from app.pipelines.leadership_signals import LeadershipSignalCollector
from app.pipelines.sec_item_analyzer import SECItem1Analyzer
from datetime import datetime, timezone 

from app.config import get_settings

router = APIRouter(prefix="/signals", tags=["Signals"])
logger = structlog.get_logger()


def _fq_table(name: str) -> str:
    s = get_settings()
    return f"{s.SNOWFLAKE_DATABASE}.{s.SNOWFLAKE_SCHEMA}.{name}"


def _get_ticker_for_company(company_id: UUID) -> str:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            f"SELECT ticker FROM {_fq_table('COMPANIES')} WHERE id = %s AND is_deleted = FALSE",
            (str(company_id),),
        )
        row = cur.fetchone()
        if not row or not row[0]:
            raise ValueError(f"Could not find ticker for company_id={company_id}")
        return row[0]
    finally:
        cur.close()
        conn.close()


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
    """
    collector = JobSignalCollector()

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

    unique_jobs = collector.deduplicate_jobs(all_jobs)
    signal = collector.analyze_job_postings(company_name, unique_jobs)
    signal.company_id = company_id

    stored_signal = signal_service.store_signal(signal)

    if background_tasks:
        background_tasks.add_task(signal_service.update_signal_summary, company_id)
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
    company_id: UUID = Query(...),
    assignee: str = Query(...),
    years: int = Query(5, ge=1, le=20),
    background_tasks: BackgroundTasks = None,
):
    """
    Collect patent signals inline (no queue). Returns ExternalSignal like job/tech.
    """
    try:
        collector = PatentSignalCollector()

        analysis = await collector.analyze_assignee(assignee=assignee, years=years) \
            if hasattr(collector, "analyze_assignee") else None

        if analysis is None:
            # Fallback if your collector expects a verification URL
            verification_url = collector.build_verification_url_for_years(assignee=assignee, years=years) \
                if hasattr(collector, "build_verification_url_for_years") else None

            if verification_url is None:
                # Minimal fallback: replicate your collect_evidence cutoff logic here
                from datetime import datetime, timezone, timedelta
                cutoff = datetime.now(timezone.utc) - timedelta(days=years * 365)
                after_date = cutoff.strftime("%Y%m%d")
                verification_url = collector.build_verification_url(
                    assignee=assignee,
                    after_yyyymmdd=after_date,
                )

            analysis = await collector.analyze(verification_url)

        signal = collector.score(company_id=company_id, assignee=assignee, analysis=analysis)

        stored_signal = signal_service.store_signal(signal)
        out_dir = Path("reports/patent_signals") / str(company_id)
        write_patent_report(stored_signal, out_dir)

        if background_tasks:
            background_tasks.add_task(signal_service.update_signal_summary, company_id)
        else:
            signal_service.update_signal_summary(company_id)

        return stored_signal

    except Exception as e:
        logger.exception("Patent signal collection failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Patent signal collection failed: {str(e)}")


@router.get(
    "/companies/{company_id}/summary",
    response_model=CompanySignalSummary
)
def get_company_signal_summary(company_id: UUID):
    return signal_service.get_signal_summary(company_id)


@router.post(
    "/companies/{company_id}/summary/refresh",
    response_model=CompanySignalSummary
)
def refresh_signal_summary(company_id: UUID):
    return signal_service.update_signal_summary(company_id)


@router.post(
    "/collect-leadership-signals",
    response_model=ExternalSignal,
    status_code=status.HTTP_201_CREATED
)
async def collect_leadership_signals(
    company_id: UUID = Query(...),
    ticker: str = Query(...),
    company_name: str = Query(...),
    background_tasks: BackgroundTasks = None,
):
    """
    Collect leadership commitment signals from external sources.
    """
    import time
    start_time = time.time()

    logger.info("Leadership collection started", ticker=ticker, company=company_name)

    try:
        collector = LeadershipSignalCollector()

        signal = await collector.analyze_company_leadership(
            company_id=company_id,
            ticker=ticker,
            company_name=company_name
        )

        stored_signal = signal_service.store_signal(signal)

        if background_tasks:
            background_tasks.add_task(signal_service.update_signal_summary, company_id)
        else:
            signal_service.update_signal_summary(company_id)

        await collector.close()

        elapsed = time.time() - start_time
        logger.info(
            "Leadership collection complete",
            ticker=ticker,
            score=signal.normalized_score,
            elapsed_seconds=round(elapsed, 2)
        )

        return stored_signal

    except Exception as e:
        logger.error(
            "Leadership collection failed",
            ticker=ticker,
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=500,
            detail=f"Leadership signal collection failed: {str(e)}"
        )
@router.post("/collect-board-signals")
async def collect_board_signals(
    company_id: UUID = Query(...),
    ticker: str = Query(...),
):
    from app.pipelines.board_analyzer import BoardCompositionAnalyzer
    
    analyzer = BoardCompositionAnalyzer()
    result = analyzer.analyze_company_governance(ticker)
    
    if not result:
        raise HTTPException(404, "No board data found")
    
    # Convert to ExternalSignal
    signal = ExternalSignal(
        company_id=company_id,
        category=SignalCategory.AI_GOVERNANCE,  # Maps to AI_GOVERNANCE dimension
        source=SignalSource.COMPANY_WEBSITE,
        signal_date=datetime.now(timezone.utc),
        raw_value=f"Board governance analysis: {result.governance_score:.1f}/100",
        normalized_score=float(result.governance_score),
        confidence=float(result.confidence),
        metadata={
            "has_tech_committee": result.has_tech_committee,
            "has_ai_expertise": result.has_ai_expertise,
            "has_data_officer": result.has_data_officer,
            "independent_ratio": result.independent_ratio,
            "board_members": len(result.board_members),
            "ai_experts": result.ai_experts,
        }
    )
    
    stored = signal_service.store_signal(signal)
    signal_service.update_signal_summary(company_id)
    
    return stored
@router.post(
    "/collect-sec-item1-signals",
    response_model=ExternalSignal,
    status_code=status.HTTP_201_CREATED
)
async def collect_sec_item1_signals(
    company_id: UUID = Query(...),
    ticker: str = Query(...),
    background_tasks: BackgroundTasks = None,
):
    """
    Collect SEC Item 1 (Business section) signals.
    Analyzes use case portfolio from business description.
    """
    from app.pipelines.sec_item_analyzer import SECItem1Analyzer
    conn = get_connection()
    cur = conn.cursor()
    settings = get_settings()
    
    try:
        cur.execute(f"""
            SELECT ticker FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies
            WHERE id = %s AND is_deleted = FALSE
        """, (str(company_id),))
        
        row = cur.fetchone()
        
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Company not found: {company_id}"
            )
        
        db_ticker = row[0]
        
        if db_ticker.upper() != ticker.upper():
            raise HTTPException(
                status_code=400,
                detail=f"Ticker mismatch: company_id has ticker '{db_ticker}', but you provided '{ticker}'"
            )
    finally:
        cur.close()
        conn.close()
    
    logger.info("sec_item1_collection_started", ticker=ticker)
    
    try:
        analyzer = SECItem1Analyzer()
        score, confidence, metadata = analyzer.analyze_business_section(
            company_id=company_id,
            ticker=ticker
        )
        
        # Create signal
        signal = ExternalSignal(
            company_id=company_id,
            category=SignalCategory.USE_CASE_PORTFOLIO,
            source=SignalSource.SEC_ITEM_1_BUSINESS,  
            signal_date=datetime.now(timezone.utc),
            raw_value=f"SEC Item 1 analysis: {metadata.get('use_case_score', 0):.0f} use case mentions",
            normalized_score=float(score),
            confidence=float(confidence),
            metadata=metadata
        )
        
        # Store signal
        stored = signal_service.store_signal(signal)
        
        if background_tasks:
            background_tasks.add_task(signal_service.update_signal_summary, company_id)
        else:
            signal_service.update_signal_summary(company_id)
        
        logger.info("sec_item1_collection_complete", ticker=ticker, score=float(score))
        
        return stored
        
    except Exception as e:
        logger.error("sec_item1_collection_failed", ticker=ticker, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"SEC Item 1 collection failed: {str(e)}"
        )
    
@router.post(
    "/collect-sec-item1a-signals",
    response_model=ExternalSignal,
    status_code=status.HTTP_201_CREATED
)
async def collect_sec_item1a_signals(
    company_id: UUID = Query(...),
    ticker: str = Query(...),
    background_tasks: BackgroundTasks = None,
):
    """Collect SEC Item 1A (Risk Factors) signals for AI Governance."""
    
    # Ticker validation (same as Item 1)
    conn = get_connection()
    cur = conn.cursor()
    settings = get_settings()
    
    try:
        cur.execute(f"""
            SELECT ticker FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies
            WHERE id = %s AND is_deleted = FALSE
        """, (str(company_id),))
        
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, f"Company not found: {company_id}")
        
        if row[0].upper() != ticker.upper():
            raise HTTPException(400, f"Ticker mismatch: expected '{row[0]}', got '{ticker}'")
    finally:
        cur.close()
        conn.close()
    
    try:
        from app.pipelines.sec_item_analyzer import SECItem1AAnalyzer
        
        analyzer = SECItem1AAnalyzer()
        score, confidence, metadata = analyzer.analyze_risk_section(
            company_id=company_id,
            ticker=ticker
        )
        
        signal = ExternalSignal(
            company_id=company_id,
            category=SignalCategory.AI_GOVERNANCE,      
            source=SignalSource.SEC_ITEM_1A_RISK,
            signal_date=datetime.now(timezone.utc),
            raw_value=f"SEC Item 1A: {metadata.get('ai_risk_score', 0):.0f} AI risk mentions",
            normalized_score=float(score),
            confidence=float(confidence),
            metadata=metadata
        )
        
        stored = signal_service.store_signal(signal)
        
        if background_tasks:
            background_tasks.add_task(signal_service.update_signal_summary, company_id)
        else:
            signal_service.update_signal_summary(company_id)
        
        return stored
        
    except Exception as e:
        logger.error("sec_item1a_failed", ticker=ticker, error=str(e))
        raise HTTPException(500, f"SEC Item 1A collection failed: {str(e)}")