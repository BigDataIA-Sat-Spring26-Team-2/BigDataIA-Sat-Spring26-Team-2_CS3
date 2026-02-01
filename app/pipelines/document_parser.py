from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import pdfplumber
from bs4 import BeautifulSoup


@dataclass
class ParsedDocument:
    company_ticker: str
    filing_type: str
    filing_date: datetime
    content: str
    sections: Dict[str, str]
    source_path: str
    content_hash: str
    word_count: int


class DocumentParser:
    """
    Parse SEC filings from multiple formats and extract key sections.

    CS2 requires PDF + HTML/TXT parsing and extraction of Item 1 / 1A / 7. (Lab 3)
    """

    SECTION_PATTERNS = {
        "item_1": r"(?:ITEM\s*1[.\s]*BUSINESS)",
        "item_1a": r"(?:ITEM\s*1A[.\s]*RISK\s*FACTORS)",
        "item_7": r"(?:ITEM\s*7[.\s]*MANAGEMENT)",
    }

    def parse_filing(self, file_path: Path, ticker: str, filing_type: str) -> ParsedDocument:
        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            content = self._parse_pdf(file_path)
        elif suffix in [".htm", ".html", ".txt"]:
            content = self._parse_html_or_text(file_path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

        cleaned = self._clean_text(content)
        sections = self._extract_sections(cleaned)

        content_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
        word_count = len(cleaned.split())

        # Best-effort filing_date: use file modified time if you don’t have metadata yet
        filing_date = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)

        return ParsedDocument(
            company_ticker=ticker,
            filing_type=filing_type,
            filing_date=filing_date,
            content=cleaned,
            sections=sections,
            source_path=str(file_path),
            content_hash=content_hash,
            word_count=word_count,
        )

    def _parse_pdf(self, file_path: Path) -> str:
        text_parts = []
        with pdfplumber.open(str(file_path)) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                text_parts.append(t)
        return "\n".join(text_parts)

    def _parse_html_or_text(self, file_path: Path) -> str:
        raw = file_path.read_text(errors="ignore")
        # Heuristic: treat as HTML if it looks like HTML
        if "<html" in raw.lower() or "<body" in raw.lower():
            soup = BeautifulSoup(raw, "html.parser")
            return soup.get_text(separator=" ")
        return raw

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _extract_sections(self, text: str) -> Dict[str, str]:
        # Very simple extractor:
        # find start indices of each item pattern, then slice until next item
        matches = []
        upper = text.upper()

        for key, pat in self.SECTION_PATTERNS.items():
            m = re.search(pat, upper)
            if m:
                matches.append((key, m.start()))

        matches.sort(key=lambda x: x[1])
        sections: Dict[str, str] = {}

        for i, (key, start) in enumerate(matches):
            end = matches[i + 1][1] if i + 1 < len(matches) else len(text)
            sections[key] = text[start:end].strip()

        return sections
