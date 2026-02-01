from pathlib import Path
from app.pipelines.sec_edgar import SECEdgarPipeline
from app.services.s3_storage import upload_file_to_s3
import structlog

logger = structlog.get_logger()


def collect_sec_documents(ticker: str, after: str):
    pipeline = SECEdgarPipeline(
        company_name="PE-OrgAIR-Platform",
        email="gupta.samik@neu.edu",
        download_dir=Path("data/raw/sec"),
    )

    filings = pipeline.download_filings(
        ticker=ticker,
        cik=None,
        filing_types=["10-K", "8-K", "10-Q", "DEF 14A"],
        limit=5,
        after=after,
    )

    for filing in filings:
        local_path = Path(filing.path)

        s3_key = (
            f"sec/{ticker}/"
            f"{filing.filing_type}/"
            f"{filing.accession_number}/"
            "full-submission.txt"
        )

        logger.info(
            "uploading_sec_filing",
            ticker=ticker,
            filing_type=filing.filing_type,
            accession_number=filing.accession_number,
        )

        s3_uri = upload_file_to_s3(
            local_path=local_path,
            s3_key=s3_key,
        )

        if s3_uri and local_path.exists():
            local_path.unlink()   # deletes the file
            logger.info(
                "local_file_deleted_after_s3_upload",
                local_path=str(local_path),
                s3_uri=s3_uri,
            )

# if __name__ == "__main__":
#     collect_sec_documents("AAPL","2021-01-01")