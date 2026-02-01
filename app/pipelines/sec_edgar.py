from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from sec_edgar_downloader import Downloader


@dataclass
class DownloadedFiling:
    filing_type: str
    accession_number: str
    path: str


class SECEdgarPipeline:
    def __init__(self, company_name: str, email: str, download_dir: Path):
        self.dl = Downloader(company_name, email, download_dir)
        self.download_dir = download_dir

    def download_filings(
        self,
        ticker: Optional[str],
        cik: Optional[str],
        filing_types: List[str],
        limit: int,
        after: str,
    ) -> List[DownloadedFiling]:
        downloaded: List[DownloadedFiling] = []

        # Choose identifier folder name used by downloader output
        identifier = ticker if ticker else cik
        if not identifier:
            return downloaded

        for filing_type in filing_types:
            if ticker:
                self.dl.get(filing_type, ticker, limit=limit, after=after)
            else:
                # CIK download supported by library (CIK must be string)
                self.dl.get(filing_type, cik, limit=limit, after=after)

            filing_dir = self.download_dir / "sec-edgar-filings" / identifier / filing_type
            if filing_dir.exists():
                for filing_path in filing_dir.glob("**/full-submission.txt"):
                    accession_number = filing_path.parent.name
                    downloaded.append(
                        DownloadedFiling(
                            filing_type=filing_type,
                            accession_number=accession_number,
                            path=str(filing_path),
                        )
                    )

        return downloaded
