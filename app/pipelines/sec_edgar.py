from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class DownloadedFiling:
    filing_type: str
    accession_number: str
    path: str


class SECEdgarPipeline:
    """
    Wrapper around sec-edgar-downloader.

    IMPORTANT:
    We do a lazy import of sec_edgar_downloader inside __init__ so that:
    - FastAPI can still start even if the sec-edgar-downloader dependency is broken
    - You get a clear error message only when you actually run the pipeline
    """

    def __init__(self, company_name: str, email: str, download_dir: Path):
        self.download_dir = download_dir

        # ✅ Lazy import: prevents FastAPI startup crash
        try:
            from sec_edgar_downloader import Downloader
        except Exception as e:
            raise RuntimeError(
                "sec-edgar-downloader could not be imported. "
                "This usually happens because of a dependency mismatch (pyrate-limiter). "
                f"Original error: {e}"
            )

        self.dl = Downloader(company_name, email, download_dir)

    def download_filings(
        self,
        ticker: Optional[str],
        cik: Optional[str],
        filing_types: List[str],
        limit: int,
        after: str,
    ) -> List[DownloadedFiling]:
        downloaded: List[DownloadedFiling] = []

        # Folder name used by downloader output
        identifier = ticker if ticker else cik
        if not identifier:
            return downloaded

        identifier = str(identifier)

        for filing_type in filing_types:
            if ticker:
                self.dl.get(filing_type, ticker, limit=limit, after=after)
            else:
                self.dl.get(filing_type, str(cik), limit=limit, after=after)

            filing_dir = self.download_dir / "sec-edgar-filings" / identifier / filing_type
            if filing_dir.exists():
                for filing_path in filing_dir.glob("**/full-submission.txt"):
                    downloaded.append(
                        DownloadedFiling(
                            filing_type=filing_type,
                            accession_number=filing_path.parent.name,
                            path=str(filing_path),
                        )
                    )

        return downloaded

    def download_filings_by_cik(
        self,
        cik: str,
        filing_types: List[str],
        limit: int,
        after: str,
    ) -> List[DownloadedFiling]:
        cik = str(cik)
        return self.download_filings(
            ticker=None,
            cik=cik,
            filing_types=filing_types,
            limit=limit,
            after=after,
        )
