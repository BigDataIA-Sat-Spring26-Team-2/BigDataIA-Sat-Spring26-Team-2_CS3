from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
from enum import Enum

import pdfplumber
from bs4 import BeautifulSoup


class DocumentFormat(str, Enum):
    PDF = "pdf"
    HTML = "html"


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
    detected_format: DocumentFormat
    sections_found: int


class DocumentParser:
    """
    Extracts ONLY AI-relevant sections from SEC filings.
    
    AI-RELEVANT SECTIONS:
    - Item 1 (Business): AI strategy, technology stack
    - Item 1A (Risk Factors): Technology/cyber risks
    - Item 2 (MD&A): Recent AI developments
    - Item 7 (MD&A): R&D spending on AI
    - Item 8.01 (8-K): AI announcements
    - Executive Compensation (DEF-14A): Tech incentives
    """
    
    AI_RELEVANT_PATTERNS = {
        # 10-K/10-Q patterns - VERY FLEXIBLE
        "item_1_business": [
            r'Item\s*1\.\s*Business',
            r'ITEM\s*1\.\s*BUSINESS',
        ],
        "item_1a_risk_factors": [
            r'Item\s*1A\.\s*Risk\s*Factors',
            r'ITEM\s*1A\.\s*RISK\s*FACTORS',
        ],
        "item_2_mda": [
            r'Item\s*2\.\s*(?:Management|Properties)',
            r'ITEM\s*2\.\s*(?:MANAGEMENT|PROPERTIES)',
        ],
        "item_7_mda": [
            r'Item\s*7\.\s*Management',
            r'ITEM\s*7\.\s*MANAGEMENT',
        ],
        
        # 8-K patterns
        "item_8_01_other": [
            r'Item\s*8\.01',
            r'ITEM\s*8\.01',
        ],
        
        # DEF-14A patterns
        "executive_compensation": [
            r'Executive\s*Compensation',
            r'EXECUTIVE\s*COMPENSATION',
            r'Compensation\s*Discussion',
            r'COMPENSATION\s*DISCUSSION',
        ],
    }
    
    # Filing type detection patterns - 8-K FIRST to avoid misclassification
    FILING_TYPE_PATTERNS = {
        "8-K": [r'\b8-K\b', r'CURRENT REPORT'],
        "10-K": [r'\b10-K\b', r'ANNUAL REPORT'],
        "10-Q": [r'\b10-Q\b', r'QUARTERLY REPORT'],
        "DEF-14A": [r'DEF 14A', r'PROXY STATEMENT', r'SCHEDULE 14A'],
    }
    
    def parse_filing(
        self,
        file_path: Path,
        ticker: str = "UNKNOWN",
        filing_type_hint: Optional[str] = None
    ) -> ParsedDocument:
        """
        Parse ANY SEC filing and extract AI-relevant sections.
        
        Args:
            file_path: Path to SEC filing
            ticker: Company ticker (optional, defaults to "UNKNOWN")
            filing_type_hint: Optional type hint (e.g., "10-Q", "8-K")
        
        Returns:
            ParsedDocument with clean text and AI-relevant sections
        """
        # Step 1: Detect format
        doc_format = self._detect_format(file_path)
        
        # Step 2: Extract text based on format
        if doc_format == DocumentFormat.PDF:
            raw_text = self._extract_from_pdf(file_path)
        else:
            raw_text = self._extract_from_html(file_path)
        
        # Step 3: Clean text
        clean_text = self._clean_text(raw_text)
        
        # Step 4: Get filing type from path (source of truth)
        filing_type_from_path = self._extract_filing_type_from_path(file_path)
        
        # Use hint if provided, otherwise use path, fallback to detection
        if filing_type_hint:
            filing_type = filing_type_hint
        elif filing_type_from_path != "UNKNOWN":
            filing_type = filing_type_from_path
        else:
            filing_type = self._detect_filing_type(clean_text[:10000])
        
        # Step 5: Extract AI-relevant sections
        sections = self._extract_ai_relevant_sections(clean_text)
        
        # Step 6: Build result
        return ParsedDocument(
            company_ticker=ticker,
            filing_type=filing_type,
            filing_date=datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc),
            content=clean_text,
            sections=sections,
            source_path=str(file_path),
            content_hash=hashlib.sha256(clean_text.encode("utf-8")).hexdigest(),
            word_count=len(clean_text.split()),
            detected_format=doc_format,
            sections_found=len(sections)
        )
    
    def _detect_format(self, file_path: Path) -> DocumentFormat:
        """Detect if PDF or HTML"""
        if file_path.suffix.lower() == ".pdf":
            return DocumentFormat.PDF
        return DocumentFormat.HTML
    
    def _extract_filing_type_from_path(self, file_path: Path) -> str:
        """Extract filing type from file path structure"""
        # Path structure: .../ticker/filing_type/accession/file
        # Example: .../AAPL/DEF 14A/0001308179-25-000008/full-submission.txt
        parts = file_path.parts
        if len(parts) >= 3:
            filing_type = parts[-3]  # Get filing type folder name
            return filing_type
        return "UNKNOWN"
    
    def _detect_filing_type(self, text: str) -> str:
        """Detect filing type from document content"""
        text_upper = text.upper()
        
        for filing_type, patterns in self.FILING_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_upper):
                    return filing_type
        
        return "UNKNOWN"
    
    def _extract_from_pdf(self, file_path: Path) -> str:
        """Extract text from PDF"""
        try:
            text_parts = []
            with pdfplumber.open(str(file_path)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
            return "\n".join(text_parts)
        except Exception:
            return ""
    
    def _extract_from_html(self, file_path: Path) -> str:
        """Extract text from HTML - REMOVES ALL TAGS"""
        try:
            with open(file_path, 'r', errors='ignore') as f:
                raw = f.read()
            
            soup = BeautifulSoup(raw, "html.parser")
            
            # Remove noise tags
            for tag in soup(["script", "style", "head", "meta", "link"]):
                tag.decompose()
            
            # Get clean text (removes ALL HTML tags)
            return soup.get_text(separator=" ")
        except Exception:
            return ""
    
    def _clean_text(self, text: str) -> str:
        """Clean text for pattern matching"""
        import html
        
        # Decode ALL HTML entities (&#160; &#8211; etc.)
        text = html.unescape(text)
        
        # Common replacements
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('\xa0', ' ')  # non-breaking space
        
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[_]{3,}', ' ', text)
        
        return text.strip()
    
    def _extract_ai_relevant_sections(self, text: str) -> Dict[str, str]:
        """
        Extract ONLY AI-relevant sections.
        Skip Table of Contents matches - get actual section content.
        
        Returns:
            Dict of section_name -> section_text
        """
        found_sections = []
        
        # Try all AI-relevant patterns
        for key, pattern_list in self.AI_RELEVANT_PATTERNS.items():
            for pattern in pattern_list:
                # Find ALL matches
                matches = list(re.finditer(pattern, text, re.IGNORECASE))
                
                if matches:
                    # Skip TOC: Look for match that has substantial content after it
                    # (TOC entries are followed by other Items, real sections have content)
                    for match in matches:
                        start = match.start()
                        # Check next 500 chars - if it's mostly "Item X" references, it's TOC
                        sample = text[start:start+500]
                        item_count = len(re.findall(r'Item\s+\d', sample))
                        
                        # Real section: < 3 Item references in next 500 chars
                        # TOC: many Item references
                        if item_count < 3:
                            found_sections.append((key, start, match.group(0)))
                            break
                    break  # Found this section, move to next
        
        # Sort by position in document
        found_sections.sort(key=lambda x: x[1])
        
        # Extract text between sections
        sections = {}
        for i, (key, start, header) in enumerate(found_sections):
            # Find end of section
            if i + 1 < len(found_sections):
                end = found_sections[i + 1][1]
            else:
                # Last section: take max 50K words (~250K chars)
                end = min(start + 250000, len(text))
            
            section_text = text[start:end].strip()
            
            # Only include substantial sections (>200 words)
            if len(section_text.split()) > 200:
                sections[key] = section_text
        
        return sections