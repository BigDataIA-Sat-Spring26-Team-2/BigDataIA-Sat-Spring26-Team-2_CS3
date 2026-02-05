# app/pipelines/patent_signals.py
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Set, Dict, Optional
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

from app.models.signal import ExternalSignal
from app.models.enums import SignalCategory, SignalSource


# ==========
# AI DEFINITION (CPC-based, notebook-consistent)
# ==========
AI_CPC_CODES = [
    "G06N20/00",
    "G06N5/00",
    "G06N7/00",
    "G06N3/04",
]

# Keywords are used only for category/explainability (NOT for filtering)
CATEGORY_RULES: Dict[str, List[str]] = {
    "machine_learning": ["machine learning", "ml model", "training"],
    "deep_learning": ["deep learning", "neural network", "cnn", "rnn", "transformer"],
    "nlp": ["natural language processing", "nlp", "language model", "llm"],
    "computer_vision": ["computer vision", "image", "object detection", "segmentation"],
    "predictive_analytics": ["prediction", "forecast", "probability", "predictive model"],
    "reinforcement_learning": ["reinforcement learning", "policy gradient", "q-learning"],
}


@dataclass
class PatentItem:
    title: str
    snippet: str
    url: str
    priority_date: Optional[datetime]


@dataclass
class PatentAnalysis:
    # Canonical fields (these are what your older scoring/debug code expected)
    count: int
    recent: int
    categories: List[str]
    verification_url: str

    # Extra fields that are useful for reporting/UI
    total_results_estimate: int
    ai_patents_count: int
    recent_ai_patents_count: int
    ai_categories: List[str]
    sampled_items: List[Dict]
    keyword_matches: Dict[str, List[str]]


class PatentSignalCollector:
    """
    Google Patents collector (Playwright, JS-rendered).

    AI relevance logic:
      - We FILTER results using CPC codes (G06N...) in the Google Patents query.
      - We then compute:
          * count = total AI patents estimate (from "About X results")
          * recent = number of AI patents within last 1 year (from sampled results)
          * categories = keyword-derived AI subareas for explainability
    """

    def build_verification_url(
        self,
        *,
        assignee: str,
        after_yyyymmdd: str,
        num: int = 100,
        sort: str = "new",
        start: int = 0,
    ) -> str:
        """
        Notebook-consistent working pattern:
          https://patents.google.com/?q=<ENCODED_CPC_OR_LIST>&assignee=<ENCODED_ASSIGNEE>&after=priority:YYYYMMDD&num=100&sort=new&start=0

        Important:
          - We do NOT embed assignee inside q (you saw that break).
          - We encode ONLY q value via quote_plus.
        """
        cpc_parts = [f"CPC=({c})" for c in AI_CPC_CODES]
        q_raw = " OR ".join(cpc_parts)
        q_encoded = quote_plus(q_raw)

        # Make assignee resilient (commas often cause flaky matching)
        assignee_clean = assignee.replace(",", "")
        assignee_encoded = quote_plus(assignee_clean)

        url = (
            "https://patents.google.com/?"
            f"q={q_encoded}"
            f"&assignee={assignee_encoded}"
            f"&after=priority:{after_yyyymmdd}"
            f"&num={num}"
            f"&sort={sort}"
            f"&start={start}"
        )
        return url

    def _parse_priority_date(self, text: str) -> Optional[datetime]:
        m = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
        if not m:
            return None
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return None

    def _extract_categories_and_matches(self, text: str) -> tuple[List[str], Dict[str, List[str]]]:
        t = text.lower()
        categories: Set[str] = set()
        matches: Dict[str, List[str]] = {}

        for cat, kws in CATEGORY_RULES.items():
            hits = [kw for kw in kws if kw in t]
            if hits:
                categories.add(cat)
                matches[cat] = hits

        return sorted(categories), matches

    async def analyze(self, url: str, *, max_items: int = 100) -> PatentAnalysis:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(2500)

            body_text = (await page.inner_text("body")).lower()

            # Best-effort estimate (this is what makes the result reproducible/verifiable in browser)
            total_estimate = 0
            m = re.search(r"about\s+([\d,]+)\s+results", body_text)
            if m:
                total_estimate = int(m.group(1).replace(",", ""))

            # Pull visible result cards (sample)
            items: List[PatentItem] = []
            locator = page.locator("search-result-item")
            n = await locator.count()
            n = min(n, max_items)

            for i in range(n):
                card = locator.nth(i)

                title = ""
                if await card.locator("h3").count():
                    title = (await card.locator("h3").inner_text()).strip()

                snippet = ""
                if await card.locator(".abstract").count():
                    snippet = (await card.locator(".abstract").inner_text()).strip()
                else:
                    snippet = (await card.inner_text()).strip()

                href = ""
                a = card.locator("a").first
                if await a.count():
                    href = await a.get_attribute("href") or ""
                if href.startswith("/"):
                    href = "https://patents.google.com" + href

                priority = self._parse_priority_date(snippet)

                items.append(
                    PatentItem(
                        title=title,
                        snippet=snippet,
                        url=href,
                        priority_date=priority,
                    )
                )

            await browser.close()

        # Cutoffs
        cutoff_5y = datetime.now(timezone.utc) - timedelta(days=5 * 365)
        cutoff_1y = datetime.now(timezone.utc) - timedelta(days=365)

        # Because the query already filters CPC=(G06N...), every result *should* be AI-classed.
        # We still:
        #   - enforce the 5y cutoff via priority_date when available (sampled items)
        #   - compute recency via 1y cutoff (sampled items)
        ai_count_sampled_5y = 0
        recent_ai_sampled = 0
        categories: Set[str] = set()
        keyword_matches_agg: Dict[str, Set[str]] = {}
        sampled: List[Dict] = []

        for it in items:
            combined = f"{it.title}\n{it.snippet}".strip()
            cats, matches = self._extract_categories_and_matches(combined)

            in_5y = True
            in_1y = False
            if it.priority_date:
                in_5y = it.priority_date >= cutoff_5y
                in_1y = it.priority_date >= cutoff_1y

            if in_5y:
                ai_count_sampled_5y += 1
                categories.update(cats)
                if in_1y:
                    recent_ai_sampled += 1

                for k, vs in matches.items():
                    keyword_matches_agg.setdefault(k, set()).update(vs)

            sampled.append(
                {
                    "title": it.title,
                    "url": it.url,
                    "priority_date": it.priority_date.isoformat() if it.priority_date else None,
                    "in_last_5y": in_5y,
                    "in_last_1y": in_1y,
                    "ai_categories": cats,
                }
            )

        keyword_matches = {k: sorted(list(v)) for k, v in keyword_matches_agg.items()}

        # Canonical fields
        count = total_estimate  # browser-verifiable: "About X results"
        recent = recent_ai_sampled
        categories_sorted = sorted(categories)

        return PatentAnalysis(
            count=count,
            recent=recent,
            categories=categories_sorted,
            verification_url=url,
            total_results_estimate=total_estimate,
            ai_patents_count=ai_count_sampled_5y,
            recent_ai_patents_count=recent_ai_sampled,
            ai_categories=categories_sorted,
            sampled_items=sampled[:25],
            keyword_matches=keyword_matches,
        )

    def score(self, *, company_id, assignee: str, analysis: PatentAnalysis, years: int = 5) -> ExternalSignal:
        """
        Scoring (same 50/20/30 breakdown you’ve been using):
          - Patent count: min(ai_patent_count × 5, 50)
          - Recency:      min(recent_ai_patents × 2, 20)
          - Diversity:    min(#categories × 10, 30)
        """
        patent_count_score = min(analysis.count * 5, 50)
        recency_bonus_score = min(analysis.recent * 2, 20)
        category_diversity_score = min(len(analysis.categories) * 10, 30)
        total = patent_count_score + recency_bonus_score + category_diversity_score

        return ExternalSignal(
            company_id=company_id,
            category=SignalCategory.INNOVATION_ACTIVITY,
            source=SignalSource.GOOGLE_PATENTS,
            signal_date=datetime.now(timezone.utc),
            raw_value=f"{analysis.count} AI patents (CPC G06N, last {years}y window)",
            normalized_score=float(round(total, 1)),
            confidence=0.90,
            metadata={
                "assignee": assignee,
                "verification_url": analysis.verification_url,
                "cpc_codes_used": AI_CPC_CODES,
                "total_results_estimate": analysis.total_results_estimate,
                "ai_patent_count": analysis.count,
                "recent_ai_patents": analysis.recent,
                "ai_categories": analysis.categories,
                "keyword_matches": analysis.keyword_matches,
                "sampled_items": analysis.sampled_items,
                "score_breakdown": {
                    "patent_count_score": patent_count_score,
                    "recency_bonus_score": recency_bonus_score,
                    "category_diversity_score": category_diversity_score,
                    "total": round(total, 1),
                },
            },
        )
