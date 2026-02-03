from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone
import hashlib

from fastapi import HTTPException, status

from app.config import get_settings
from app.services.snowflake import get_connection
from app.pipelines.sec_edgar import SECEdgarPipeline
from app.pipelines.document_parser import DocumentParser
from app.services.s3_storage import upload_file_to_s3
import structlog

logger = structlog.get_logger()

def _fq(name: str) -> str:
    s = get_settings()
    return f"{s.SNOWFLAKE_DATABASE}.{s.SNOWFLAKE_SCHEMA}.{name}"


COMPANIES_TABLE = _fq("COMPANIES")
DOCS_TABLE = _fq("DOCUMENTS")
CHUNKS_TABLE = _fq("DOCUMENT_CHUNKS")


def _sec_pipeline() -> SECEdgarPipeline:
    """
    Central place to configure SEC downloader identity + output dir.
    Change via env later if needed.
    """
    s = get_settings()

    company_name = getattr(s, "SEC_DOWNLOADER_COMPANY", None) or "PE OrgAIR Team-2"
    email = getattr(s, "SEC_DOWNLOADER_EMAIL", None) or "you@example.com"
    download_dir = Path(getattr(s, "SEC_DOWNLOAD_DIR", None) or "data/raw/sec")

    download_dir.mkdir(parents=True, exist_ok=True)

    return SECEdgarPipeline(
        company_name=company_name,
        email=email,
        download_dir=download_dir,
    )


def download_by_cik(
    cik: str,
    filing_types: List[str],
    after: str,
    limit: int,
) -> Dict[str, Any]:
    pipeline = _sec_pipeline()

    filings = pipeline.download_filings(
        ticker=None,
        cik=str(cik),
        filing_types=filing_types,
        limit=limit,
        after=after,
    )

    files = [
        {"filing_type": f.filing_type, "accession_number": f.accession_number, "path": f.path}
        for f in filings
    ]

    return {
        "cik": cik,
        "downloaded_files": len(filings),
        "after": after,
        "limit": limit,
        "filing_types": filing_types,
        "files": files,
    }


def run_sec_download_for_company(
    company_id: UUID,
    ticker: Optional[str],
    cik: Optional[str],
    filing_types: List[str],
    limit: int,
    after: str,
) -> Dict[str, Any]:

    logger.info(
        "sec_pipeline_started",
        company_id=str(company_id),
        ticker=ticker,
        cik=cik,
        filing_types=filing_types,
        limit=limit,
        after=after,
    )

    if not ticker and not cik:
        logger.error(
            "validation_failed",
            company_id=str(company_id),
            error="missing_identifier",
            message="Must provide either ticker or cik",
        )
        raise HTTPException(status_code=400, detail="Provide either ticker or cik")

    if ticker:
        ticker = ticker.upper()

    logger.info(
        "validating_company",
        company_id=str(company_id),
        ticker=ticker,
        cik=cik,
    )

    conn = None
    cur = None
    db_ticker: Optional[str] = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"SELECT ticker FROM {COMPANIES_TABLE} WHERE id=%s AND is_deleted=FALSE",
            (str(company_id),),
        )
        row = cur.fetchone()
        if not row:
            logger.error("company_not_found", company_id=str(company_id))
            raise HTTPException(status_code=404, detail="Company not found")
        db_ticker = row[0]
        logger.info("company_validated", company_id=str(company_id), db_ticker=db_ticker)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    if not ticker and db_ticker:
        ticker = str(db_ticker).upper()
        logger.info("ticker_resolved_from_database", company_id=str(company_id), ticker=ticker)

    logger.info(
        "starting_sec_download",
        ticker=ticker,
        cik=cik,
        filing_types=filing_types,
        limit=limit,
        after=after,
    )

    pipeline = _sec_pipeline()
    parser = DocumentParser()

    downloaded = pipeline.download_filings(
        ticker=ticker,
        cik=cik,
        filing_types=filing_types,
        limit=limit,
        after=after,
    )

    logger.info(
        "sec_download_completed",
        ticker=ticker,
        cik=cik,
        downloaded_count=len(downloaded),
        filing_types=filing_types,
    )

    inserted_docs = 0
    inserted_chunks = 0
    skipped_duplicates = 0

    files = [
        {"filing_type": f.filing_type, "accession_number": f.accession_number, "path": f.path}
        for f in downloaded
    ]

    logger.info("starting_document_processing", ticker=ticker, total_filings=len(downloaded))

    conn = get_connection()
    cur = conn.cursor()

    try:
        for idx, f in enumerate(downloaded, 1):
            file_path = Path(f.path)

            logger.info(
                "processing_filing",
                ticker=ticker,
                filing_type=f.filing_type,
                accession_number=f.accession_number,
                file_path=str(file_path),
                file_size_bytes=file_path.stat().st_size,
                file_size_mb=round(file_path.stat().st_size / (1024 * 1024), 2),
                progress=f"{idx}/{len(downloaded)}",
                progress_percent=round((idx / len(downloaded)) * 100, 1),
            )

            parsed = parser.parse_filing(file_path=file_path, ticker=ticker or "")

            logger.info(
                "filing_parsed",
                ticker=ticker,
                filing_type=parsed.filing_type,
                accession_number=f.accession_number,
                company_ticker=parsed.company_ticker,
                filing_date=parsed.filing_date.isoformat(),
                detected_format=parsed.detected_format.value,
                word_count=parsed.word_count,
                content_hash=parsed.content_hash[:16] + "...",
                sections_found=parsed.sections_found,
                section_names=list(parsed.sections.keys()) if parsed.sections else [],
            )

            logger.info(
                "checking_for_duplicates",
                ticker=ticker,
                filing_type=f.filing_type,
                accession_number=f.accession_number,
                content_hash=parsed.content_hash[:16] + "...",
            )

            cur.execute(f"SELECT 1 FROM {DOCS_TABLE} WHERE content_hash=%s", (parsed.content_hash,))
            if cur.fetchone():
                skipped_duplicates += 1
                logger.info(
                    "duplicate_filing_skipped",
                    ticker=ticker,
                    filing_type=f.filing_type,
                    accession_number=f.accession_number,
                )
                continue

            s3_key = f"sec/{ticker}/{f.filing_type}/{f.accession_number}/full-submission.txt"
            s3_uri = upload_file_to_s3(file_path, s3_key)
            file_path.unlink()

            # ==================================================
            # SECTION-LEVEL DEDUPLICATION + HYBRID CHUNKING
            # ==================================================
            sections_extracted = len(parsed.sections)
            sections_stored = 0
            sections_duplicates = 0
            section_data = []

            chunk_index = 0

            for section_name, section_content in parsed.sections.items():
                words = section_content.split()

                if len(words) < 5000:
                    chunks = [(chunk_index, section_content)]
                    next_index = chunk_index + 1
                else:
                    chunks = []
                    start = 0
                    idx_c = chunk_index
                    while start < len(words):
                        end = min(start + 1000, len(words))
                        chunks.append((idx_c, " ".join(words[start:end])))
                        idx_c += 1
                        if end == len(words):
                            break
                        start = end - 100
                    next_index = idx_c

                for idx_c, chunk_text in chunks:
                    chunk_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                    chunk_word_count = len(chunk_text.split())

                    cur.execute(
                        f"SELECT 1 FROM {CHUNKS_TABLE} WHERE content_hash=%s",
                        (chunk_hash,),
                    )

                    if cur.fetchone():
                        sections_duplicates += 1
                        continue

                    section_data.append(
                        (
                            str(uuid4()),
                            None,
                            idx_c,
                            chunk_text,
                            chunk_hash,
                            chunk_word_count,
                            None,
                        )
                    )
                    sections_stored += 1

                chunk_index = next_index

            # ============================
            # INSERT DOCUMENT
            # ============================
            doc_id = str(uuid4())
            now = datetime.now(timezone.utc)

            cur.execute(
                f"""
                INSERT INTO {DOCS_TABLE} (
                    id, company_id, cik, ticker, filing_type, accession_number,
                    file_path, filing_date, content_hash, word_count,
                    sections_extracted, sections_stored, sections_duplicates,
                    created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    doc_id,
                    str(company_id),
                    cik,
                    ticker,
                    f.filing_type,
                    f.accession_number,
                    parsed.source_path,
                    parsed.filing_date.date(),
                    parsed.content_hash,
                    parsed.word_count,
                    sections_extracted,
                    sections_stored,
                    sections_duplicates,
                    now,
                ),
            )

            inserted_docs += 1

            if section_data:
                final_sections = [
                    (sid, doc_id, idx_c, txt, h, wc, now)
                    for sid, _, idx_c, txt, h, wc, _ in section_data
                ]

                cur.executemany(
                    f"""
                    INSERT INTO {CHUNKS_TABLE} (
                        id, document_id, chunk_index, chunk_text,
                        content_hash, word_count, created_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    final_sections,
                )

                inserted_chunks += len(final_sections)

            logger.info(
                "filing_processed_successfully",
                ticker=ticker,
                filing_type=f.filing_type,
                accession_number=f.accession_number,
                document_id=doc_id,
                sections_extracted=sections_extracted,
                sections_stored=sections_stored,
                sections_duplicates=sections_duplicates,
            )

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    logger.info(
        "sec_pipeline_completed",
        company_id=str(company_id),
        ticker=ticker,
        cik=cik,
        downloaded_files=len(downloaded),
        inserted_documents=inserted_docs,
        inserted_chunks=inserted_chunks,
        skipped_duplicates=skipped_duplicates,
    )

    return {
        "company_id": str(company_id),
        "ticker": ticker,
        "cik": cik,
        "downloaded_files": len(downloaded),
        "inserted_documents": inserted_docs,
        "inserted_chunks": inserted_chunks,
        "skipped_duplicates": skipped_duplicates,
        "after": after,
        "limit": limit,
        "filing_types": filing_types,
        "files": files,
    }
