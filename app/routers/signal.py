from fastapi import APIRouter, status, Query, BackgroundTasks, HTTPException
from typing import Optional
from uuid import UUID
from pathlib import Path
import subprocess
import structlog
from datetime import datetime, timezone, timedelta  # (kept; used elsewhere in file)

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

from app.pipelines.patent_signals import PatentSignalCollector  # (kept; might be used elsewhere)
from app.reports.patent_report import write_patent_report       # (kept; might be used elsewhere)
from app.services.snowflake import get_connection

from app.pipelines.leadership_signals import LeadershipSignalCollector
from app.services import snowflake
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


# ✅ FIXED: route path is "/collect-patent-signals" (NOT "/signals/collect-patent-signals")
# because router already has prefix="/signals"
@router.post(
    "/collect-patent-signals",
    response_model=QueuedTaskResponse
)
async def collect_patent_signals(
    company_id: UUID = Query(...),
    assignee: str = Query(...),
    years: int = Query(5, ge=1, le=20),
):
    """
    Queue patent signal collection by launching the existing evidence script.
    (No Playwright inside API — Windows safe.)
    """
    ticker = _get_ticker_for_company(company_id)

    project_root = Path(__file__).resolve().parents[2]
    script = project_root / "scripts" / "collect_evidence.py"

    logs_dir = project_root / "reports" / "patent_signals" / ticker
    logs_dir.mkdir(parents=True, exist_ok=True)
    out_log = logs_dir / "worker_stdout.log"
    err_log = logs_dir / "worker_stderr.log"

    # ✅ FIXED: ensure we actually run patent collection
    cmd = [
        "poetry", "run", "python", str(script),
        "--ticker", ticker,
        "--signals", "patent",
    ]

    # Optional: only add if your collect_evidence.py supports these flags
    # cmd += ["--assignee", assignee, "--years", str(years)]

    logger.info(
        "Queueing patent collection",
        ticker=ticker,
        company_id=str(company_id),
        assignee=assignee,
        years=years,
        cmd=cmd
    )

    subprocess.Popen(
        cmd,
        cwd=str(project_root),
        stdout=open(out_log, "a", encoding="utf-8"),
        stderr=open(err_log, "a", encoding="utf-8"),
        creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, "CREATE_NEW_CONSOLE") else 0
    )

    return QueuedTaskResponse(
        status="queued",
        message="Patent signal collection started",
        company_id=company_id,
        ticker=ticker,
        assignee=assignee,
    )


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
