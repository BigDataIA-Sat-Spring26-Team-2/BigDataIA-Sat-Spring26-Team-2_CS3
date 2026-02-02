
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.config import get_settings
from app.services.snowflake import get_connection
from app.pipelines.sec_edgar import SECEdgarPipeline
from app.pipelines.document_parser import DocumentParser
from app.pipelines.chunker import chunk_text

from app.pipelines.sec_edgar import SECEdgarPipeline
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
    """
    Simple helper if you want a pure CIK download (no DB inserts).
    Keeps things predictable while you build out storage features.
    """
    pipeline = _sec_pipeline()

    # use the pipeline's generic downloader (CIK path)
    filings = pipeline.download_filings(
        ticker=None,
        cik=str(cik),
        filing_types=filing_types,
        limit=limit,
        after=after,
    )

    files = [{"filing_type": f.filing_type, "accession_number": f.accession_number, "path": f.path} for f in filings]

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
    """
    End-to-end pipeline:
      1) Validate company exists
      2) Download SEC filings (ticker or CIK)
      3) Parse, hash, dedupe
      4) Insert DOCUMENTS
      5) Chunk + insert DOCUMENT_CHUNKS
      6) Return summary + list of downloaded file paths
    """

    # ============================================
    # PIPELINE START
    # ============================================
    logger.info(
        "sec_pipeline_started",
        company_id=str(company_id),
        ticker=ticker,
        cik=cik,
        filing_types=filing_types,
        limit=limit,
        after=after,
    )

    # ---------- validate inputs ----------
    if not ticker and not cik:
        logger.error(
            "validation_failed",
            company_id=str(company_id),
            error="missing_identifier",
            message="Must provide either ticker or cik"
        )
        raise HTTPException(status_code=400, detail="Provide either ticker or cik")

    if ticker:
        ticker = ticker.upper()

    # ---------- validate company exists + maybe get ticker from DB ----------
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
            logger.error(
                "company_not_found",
                company_id=str(company_id),
                ticker=ticker,
                cik=cik,
            )
            raise HTTPException(status_code=404, detail="Company not found")
        db_ticker = row[0] if row else None
        
        logger.info(
            "company_validated",
            company_id=str(company_id),
            db_ticker=db_ticker,
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    # If ticker not supplied but exists in DB, use it
    if not ticker and db_ticker:
        ticker = str(db_ticker).upper()
        logger.info(
            "ticker_resolved_from_database",
            company_id=str(company_id),
            ticker=ticker,
        )

    # Still no identifier?
    if not ticker and not cik:
        logger.error(
            "no_identifier_available",
            company_id=str(company_id),
            db_ticker=db_ticker,
        )
        raise HTTPException(
            status_code=400,
            detail="No ticker found for this company and cik not provided",
        )

    # ============================================
    # DOWNLOAD PHASE
    # ============================================
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

    # ---------- insert into Snowflake ----------
    inserted_docs = 0
    inserted_chunks = 0
    skipped_duplicates = 0

    files = [{"filing_type": f.filing_type, "accession_number": f.accession_number, "path": f.path} for f in downloaded]

    if not downloaded:
        logger.warning(
            "no_filings_downloaded",
            ticker=ticker,
            cik=cik,
            filing_types=filing_types,
            after=after,
            limit=limit,
        )
        return {
            "company_id": str(company_id),
            "ticker": ticker,
            "cik": cik,
            "downloaded_files": 0,
            "inserted_documents": 0,
            "inserted_chunks": 0,
            "skipped_duplicates": 0,
            "after": after,
            "limit": limit,
            "filing_types": filing_types,
            "files": [],
        }

    # ============================================
    # PROCESSING PHASE
    # ============================================
    logger.info(
        "starting_document_processing",
        ticker=ticker,
        total_filings=len(downloaded),
    )

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        for idx, f in enumerate(downloaded, 1):
            file_path = Path(f.path)
            
            # ============================================
            # FILING START
            # ============================================
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

            # ============================================
            # PARSING PHASE
            # ============================================
            try:
                parsed = parser.parse_filing(
                    file_path=file_path,
                    ticker=(ticker or ""),
                )
                
                # Calculate section statistics
                section_word_counts = {
                    section_name: len(section_content.split())
                    for section_name, section_content in parsed.sections.items()
                } if parsed.sections else {}
                
                total_section_words = sum(section_word_counts.values())
                extraction_efficiency = round((total_section_words / parsed.word_count) * 100, 1) if parsed.word_count > 0 else 0
                
                logger.info(
                    "filing_parsed",
                    ticker=ticker,
                    filing_type=parsed.filing_type,
                    accession_number=f.accession_number,
                    # Document metadata
                    company_ticker=parsed.company_ticker,
                    filing_date=parsed.filing_date.isoformat(),
                    detected_format=parsed.detected_format.value,
                    # Content metrics
                    word_count=parsed.word_count,
                    content_hash=parsed.content_hash[:16] + "...",
                    # Section extraction
                    sections_found=parsed.sections_found,
                    section_names=list(parsed.sections.keys()) if parsed.sections else [],
                    section_word_counts=section_word_counts,
                    total_section_words=total_section_words,
                    extraction_efficiency_percent=extraction_efficiency,
                )
            except Exception as e:
                logger.error(
                    "parsing_failed",
                    ticker=ticker,
                    filing_type=f.filing_type,
                    accession_number=f.accession_number,
                    file_path=str(file_path),
                    error=str(e),
                    error_type=type(e).__name__,
                )
                continue

            # ============================================
            # S3 UPLOAD PHASE
            # ============================================
            s3_key = (
                f"sec/{ticker}/"
                f"{f.filing_type}/"
                f"{f.accession_number}/"
                "full-submission.txt"
            )

            logger.info(
                "uploading_to_s3",
                ticker=ticker,
                filing_type=f.filing_type,
                accession_number=f.accession_number,
                s3_key=s3_key,
                file_size_bytes=file_path.stat().st_size,
                file_size_mb=round(file_path.stat().st_size / (1024 * 1024), 2),
            )

            try:
                s3_uri = upload_file_to_s3(
                    local_path=file_path,
                    s3_key=s3_key,
                )
                
                logger.info(
                    "s3_upload_successful",
                    ticker=ticker,
                    filing_type=f.filing_type,
                    accession_number=f.accession_number,
                    s3_uri=s3_uri,
                )
            except Exception as e:
                logger.error(
                    "s3_upload_failed",
                    ticker=ticker,
                    filing_type=f.filing_type,
                    accession_number=f.accession_number,
                    s3_key=s3_key,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

            # ============================================
            # LOCAL FILE CLEANUP
            # ============================================
            if s3_uri and file_path.exists():
                try:
                    file_path.unlink()
                    logger.info(
                        "local_file_deleted",
                        ticker=ticker,
                        filing_type=f.filing_type,
                        accession_number=f.accession_number,
                        file_path=str(file_path),
                        s3_uri=s3_uri,
                    )
                except Exception as e:
                    logger.warning(
                        "local_file_deletion_failed",
                        ticker=ticker,
                        filing_type=f.filing_type,
                        file_path=str(file_path),
                        error=str(e),
                    )

            # ============================================
            # DEDUPLICATION CHECK
            # ============================================
            cur.execute(f"SELECT 1 FROM {DOCS_TABLE} WHERE content_hash=%s", (parsed.content_hash,))
            if cur.fetchone():
                skipped_duplicates += 1
                logger.info(
                    "duplicate_filing_skipped",
                    ticker=ticker,
                    filing_type=f.filing_type,
                    accession_number=f.accession_number,
                    content_hash=parsed.content_hash[:16] + "...",
                )
                continue

            # ============================================
            # DATABASE INSERT
            # ============================================
            doc_id = str(uuid4())
            now = datetime.now(timezone.utc)

            try:
                cur.execute(
                    f"""
                    INSERT INTO {DOCS_TABLE} (
                        id, company_id, cik, ticker, filing_type, accession_number,
                        file_path, filing_date, content_hash, word_count, created_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
                        now,
                    ),
                )
                inserted_docs += 1
                
                logger.info(
                    "document_inserted",
                    document_id=doc_id,
                    ticker=ticker,
                    filing_type=f.filing_type,
                    accession_number=f.accession_number,
                    word_count=parsed.word_count,
                    s3_uri=s3_uri,
                )
            except Exception as e:
                logger.error(
                    "document_insert_failed",
                    ticker=ticker,
                    filing_type=f.filing_type,
                    accession_number=f.accession_number,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

            # ============================================
            # CHUNKING PHASE (COMMENTED OUT)
            # ============================================
            # logger.info(
            #     "chunking_document",
            #     document_id=doc_id,
            #     ticker=ticker,
            #     filing_type=f.filing_type,
            #     word_count=parsed.word_count,
            #     chunk_size_words=350,
            #     overlap_words=50,
            # )
            # 
            # chunks = chunk_text(parsed.content, chunk_size_words=350, overlap_words=50)
            # 
            # logger.info(
            #     "document_chunked",
            #     document_id=doc_id,
            #     ticker=ticker,
            #     filing_type=f.filing_type,
            #     total_chunks=len(chunks),
            #     total_chunk_words=sum(c.word_count for c in chunks),
            # )
            # 
            # chunk_values = [
            #     (str(uuid4()), doc_id, c.chunk_index, c.text, c.content_hash, c.word_count, now)
            #     for c in chunks
            # ]
            #
            # try:
            #     cur.executemany(
            #         f"""
            #         INSERT INTO {CHUNKS_TABLE} (
            #             id, document_id, chunk_index, chunk_text, content_hash, word_count, created_at
            #         ) VALUES (%s,%s,%s,%s,%s,%s,%s)
            #         """,
            #         chunk_values
            #     )
            #     inserted_chunks += len(chunks)
            #     
            #     logger.info(
            #         "chunks_inserted",
            #         document_id=doc_id,
            #         ticker=ticker,
            #         filing_type=f.filing_type,
            #         chunks_count=len(chunks),
            #     )
            # except Exception as e:
            #     logger.error(
            #         "chunks_insert_failed",
            #         document_id=doc_id,
            #         ticker=ticker,
            #         filing_type=f.filing_type,
            #         chunks_count=len(chunks),
            #         error=str(e),
            #         error_type=type(e).__name__,
            #     )
            #     raise

            # ============================================
            # FILING COMPLETE
            # ============================================
            logger.info(
                "filing_processed_successfully",
                ticker=ticker,
                filing_type=f.filing_type,
                accession_number=f.accession_number,
                document_id=doc_id,
                progress=f"{idx}/{len(downloaded)}",
            )

        # ============================================
        # COMMIT TRANSACTION
        # ============================================
        conn.commit()
        
        logger.info(
            "snowflake_transaction_committed",
            ticker=ticker,
            inserted_documents=inserted_docs,
            inserted_chunks=inserted_chunks,
            skipped_duplicates=skipped_duplicates,
        )

    except HTTPException:
        logger.error(
            "http_exception_in_pipeline",
            ticker=ticker,
            company_id=str(company_id),
        )
        raise
    except Exception as e:
        logger.error(
            "pipeline_failed",
            ticker=ticker,
            company_id=str(company_id),
            error=str(e),
            error_type=type(e).__name__,
            inserted_docs=inserted_docs,
            inserted_chunks=inserted_chunks,
            skipped_duplicates=skipped_duplicates,
        )
        if conn:
            try:
                conn.rollback()
                logger.info("transaction_rolled_back", ticker=ticker)
            except Exception as rollback_error:
                logger.error(
                    "rollback_failed",
                    ticker=ticker,
                    error=str(rollback_error),
                )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SEC pipeline failed: {str(e)}",
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    # ============================================
    # PIPELINE COMPLETE
    # ============================================
    logger.info(
        "sec_pipeline_completed",
        company_id=str(company_id),
        ticker=ticker,
        cik=cik,
        downloaded_files=len(downloaded),
        inserted_documents=inserted_docs,
        inserted_chunks=inserted_chunks,
        skipped_duplicates=skipped_duplicates,
        success_rate=f"{inserted_docs}/{len(downloaded)}" if downloaded else "0/0",
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