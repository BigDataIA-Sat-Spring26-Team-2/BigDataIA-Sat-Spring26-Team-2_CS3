from decimal import Decimal
from typing import Optional, List, Tuple
from uuid import UUID
import re

from app.services.snowflake import get_connection
from app.config import get_settings
from app.models.board import GovernanceSignal, BoardMember


class BoardCompositionAnalyzer:

    AI_EXPERTISE_KEYWORDS = [
        "artificial intelligence", "machine learning", "deep learning",
        "neural network", "natural language processing", "nlp",
        "computer vision", "data science", "predictive analytics",
        "chief data officer", "cdo", "chief ai officer", "caio",
        "chief technology officer", "cto", "chief information officer", "cio",
        "chief digital officer", "chief analytics officer", "cao",
        "ai strategy", "ai transformation", "digital transformation",
        "technology strategy", "innovation strategy", "data strategy"
    ]

    TECH_COMMITTEE_NAMES = [
        "technology committee", "digital committee", "innovation committee",
        "cybersecurity committee", "data committee", "ai committee",
        "technology and cybersecurity committee",
        "information technology committee", "it oversight committee"
    ]

    DATA_OFFICER_TITLES = [
        "chief technology officer", "chief information officer",
        "chief digital officer", "chief data officer", "chief ai officer"
    ]

    EXCLUDE_COMMITTEES = [
        "audit committee", "compensation committee", "nominating committee",
        "governance committee", "executive committee"
    ]

    
    def analyze_company_governance(self, ticker: str) -> Optional[GovernanceSignal]:
        settings = get_settings()
        conn = get_connection()
        cur = conn.cursor()

        try:
            cur.execute(f"""
                SELECT c.id
                FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies c
                WHERE c.ticker = %s AND c.is_deleted = FALSE
            """, (ticker,))

            row = cur.fetchone()
            if not row:
                return None

            company_id = row[0]

            cur.execute(f"""
                SELECT dc.chunk_text
                FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.document_chunks dc
                JOIN {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.documents d
                  ON dc.document_id = d.id
                WHERE d.ticker = %s
                  AND d.filing_type = 'DEF 14A'
                ORDER BY d.filing_date DESC, dc.chunk_index
            """, (ticker,))

            rows = cur.fetchall()
            if not rows:
                return self._default_signal(company_id, ticker)

            text = " ".join(r[0] for r in rows if r[0])

            members = self._extract_board_members(text)
            committees = self._extract_committees(text)

            return self._calculate_governance_score(
                company_id, ticker, text, members, committees
            )

        finally:
            cur.close()
            conn.close()

    
    def _is_valid_name(self, name: str) -> bool:
        if not name or len(name) < 5 or len(name) > 50:
            return False
        if any(c.isdigit() for c in name):
            return False

        bad_words = [
            "committee", "director", "officer", "page", "table",
            "compensation", "audit", "board", "annual", "proxy",
            "corporate", "governance", "executive", "contents"
        ]

        if any(bad in name.lower() for bad in bad_words):
            return False

        return sum(1 for w in name.split() if w[0].isupper()) >= 2

    
    def _extract_board_members(self, text: str) -> List[BoardMember]:
        members: List[BoardMember] = []
        seen = set()

        def add_member(name: str, bio: str):
            name = re.sub(r"\s+", " ", name.strip())
            if name in seen or not self._is_valid_name(name):
                return

            seen.add(name)
            bio_lower = bio.lower()

            ai_hits = [
                kw for kw in self.AI_EXPERTISE_KEYWORDS
                if len(kw.split()) > 1 and kw in bio_lower
            ]

            members.append(
                BoardMember(
                    name=name,
                    title="Director",
                    committees=[],
                    bio=bio[:250],
                    is_independent="independent" in bio_lower,
                    tenure_years=0,
                    has_ai_background=len(ai_hits) > 0,
                    ai_keywords_found=ai_hits
                )
            )

        # PASS 1
        for m in re.finditer(r'Age:\s*\d+\s+Director since:\s*\d{4}', text):
            pre = text[max(0, m.start() - 150):m.start()]
            nm = re.search(
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+[A-Z]',
                pre
            )
            if nm:
                add_member(nm.group(1), text[m.end():m.end() + 400])

        # PASS 2
        for m in re.finditer(
            r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s+)?[A-Z][a-z]+)\s*\(Age\s*\d+\)',
            text
        ):
            add_member(m.group(1), text[m.end():m.end() + 400])

        # PASS 3
        sec = re.search(
            r'(director nominees|board of directors)(.*?)(item \d+|$)',
            text.lower(), re.DOTALL
        )
        if sec:
            block = text[sec.start():sec.end()]
            for m in re.finditer(r'\b([A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+)\b', block):
                add_member(m.group(1), block[m.end():m.end() + 300])

        # PASS 4 (TABLE ROWS)
        table_pattern = (
            r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
            r'\s*\|?\s*\d{2}\s*\|?\s*\d{4}'
        )
        for m in re.finditer(table_pattern, text):
            add_member(m.group(1), text[m.end():m.end() + 300])

        return members

    
    def _extract_committees(self, text: str) -> List[str]:
        found = []
        tl = text.lower()

        for tc in self.TECH_COMMITTEE_NAMES:
            base = tc.replace(" committee", "")
            pattern = rf"\b{re.escape(base)} committee(s)?\b"

            for match in re.finditer(pattern, tl):
                start = max(0, match.start() - 40)
                end = min(len(tl), match.end() + 40)
                context = tl[start:end]

                if not any(excl in context for excl in self.EXCLUDE_COMMITTEES):
                    found.append(tc)

        return list(set(found))

    
    def _has_ai_expertise_text(self, text: str) -> Tuple[bool, int]:
        tl = text.lower()
        count = sum(
            1 for kw in self.AI_EXPERTISE_KEYWORDS
            if len(kw.split()) > 1 and kw in tl
        )
        return count > 0, count

    def _has_data_officer(self, text: str) -> bool:
        tl = text.lower()
        return any(t in tl for t in self.DATA_OFFICER_TITLES)

    def _calculate_governance_score(
        self,
        company_id: str,
        ticker: str,
        text: str,
        members: List[BoardMember],
        committees: List[str]
    ) -> GovernanceSignal:

        score = Decimal("20")
        tl = text.lower()

        has_tech_comm = bool(committees)
        if has_tech_comm:
            score += Decimal("15")

        has_ai, tech_count = self._has_ai_expertise_text(text)
        ai_members = [m.name for m in members if m.has_ai_background]
        if ai_members:
            has_ai = True
            tech_count = len(ai_members)

        if has_ai:
            score += Decimal("20")

        has_data_officer = self._has_data_officer(text)
        if has_data_officer:
            score += Decimal("15")
        if "independent director" in tl or "lead independent director" in tl:
            independent_ratio = Decimal("0.6")
        else:
            independent_ratio = Decimal("0.4")

        if independent_ratio > Decimal("0.5"):
            score += Decimal("10")

        if "risk" in tl and "committee" in tl and "technology" in tl:
            score += Decimal("10")

        if "artificial intelligence" in tl and any(
            k in tl for k in ["strategy", "strategic", "oversight", "priorities"]
        ):
            score += Decimal("10")

        score = min(score, Decimal("100"))

        return GovernanceSignal(
            company_id=UUID(company_id),
            ticker=ticker,
            governance_score=float(score),
            confidence=0.85 if len(members) > 5 else 0.7,
            has_tech_committee=has_tech_comm,
            has_ai_expertise=has_ai,
            has_data_officer=has_data_officer,
            has_risk_tech_oversight="risk" in tl and "technology" in tl,
            has_ai_in_strategy="artificial intelligence" in tl,
            tech_expertise_count=tech_count,
            independent_ratio=float(independent_ratio),
            ai_experts=ai_members,
            relevant_committees=committees,
            board_members=members
        )

    def _default_signal(self, company_id: str, ticker: str) -> GovernanceSignal:
        return GovernanceSignal(
            company_id=UUID(company_id),
            ticker=ticker,
            governance_score=20.0,
            confidence=0.5,
            has_tech_committee=False,
            has_ai_expertise=False,
            has_data_officer=False,
            has_risk_tech_oversight=False,
            has_ai_in_strategy=False,
            tech_expertise_count=0,
            independent_ratio=0.5,
            ai_experts=[],
            relevant_committees=[],
            board_members=[]
        )
