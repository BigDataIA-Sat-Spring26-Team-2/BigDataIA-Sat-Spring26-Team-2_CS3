"""
app/scoring/investment_memo_generator.py

Generates PE-style investment memos using LangChain + Anthropic Claude.
Interprets Path A (quantitative) + Path B (qualitative) scores and V^R result
into actionable insights for AI readiness assessment.
"""

import json
import structlog
from typing import Any, Dict, Tuple

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from app.config import get_settings

logger = structlog.get_logger()

# ──────────────────────────────────────────────
# Rubric dimension definitions (cached at class level)
# ──────────────────────────────────────────────
DIMENSION_DEFINITIONS = {
    "data_infrastructure": "Data collection, storage, quality, and pipeline maturity for AI workloads.",
    "ai_governance": "Policies, ethics frameworks, risk controls, and compliance posture for AI use.",
    "technology_stack": "Cloud platforms, ML frameworks, tooling, and integration readiness.",
    "talent": "AI/ML hiring depth, skill diversity, and workforce development programs.",
    "leadership": "C-suite AI vision, board-level oversight, and strategic commitment signals.",
    "use_case_portfolio": "Breadth and depth of deployed or planned AI use cases across the business.",
    "culture": "Organizational openness to experimentation, innovation culture, and change management.",
}

MAX_EVIDENCE_CHARS = 3000

SYSTEM_PROMPT = """You are a senior private-equity analyst specializing in AI-readiness assessments.
You produce concise, data-driven investment memos that help partners make BUY / HOLD / PASS decisions.

When writing a memo you MUST include ALL of the following sections (use Markdown headings):

1. **Executive Summary** — 2-3 sentences with a clear BUY / HOLD / PASS recommendation and the V^R score.
2. **Path A vs Path B Comparison** — A Markdown table with columns: Dimension | Path A (Quantitative) | Path B (Qualitative) | Combined | Delta.
3. **Seven-Dimension Deep Dive** — One paragraph per dimension explaining the score drivers.
4. **Discrepancy Analysis** — Flag any dimension where |Path A − Path B| > 15 points and explain possible causes.
5. **Risk Factors** — Bullet list of key risks.
6. **Opportunities** — Bullet list of upside catalysts.
7. **Competitive Positioning** — Where this company sits relative to sector peers.

Use precise numbers from the data provided. Do not fabricate data points.
Keep the total memo under 1500 words.

Also produce a JSON summary block at the very end of your response, fenced with ```json ... ```, containing:
{
  "recommendation": "BUY" | "HOLD" | "PASS",
  "vr_score": <number>,
  "top_strength": "<dimension>",
  "top_weakness": "<dimension>",
  "discrepancy_flags": ["<dimension>", ...]
}
"""


def _truncate(text: str, max_chars: int = MAX_EVIDENCE_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…[truncated]"


class InvestmentMemoGenerator:
    """Generates PE-style investment memos via LangChain + ChatAnthropic."""

    def __init__(self):
        settings = get_settings()
        self.model = ChatAnthropic(
            model=settings.CLAUDE_MODEL,
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
            max_tokens=4096,
            temperature=0.3,
        )

    def generate_memo(
        self,
        ticker: str,
        company_name: str,
        path_a_scores: Dict[str, float],
        path_b_scores: Dict[str, Any],
        vr_result: Dict[str, Any],
        evidence_metadata: Dict[str, str] | None = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate an investment memo.

        Args:
            ticker: Company ticker symbol
            company_name: Full company name
            path_a_scores: {dimension: score} from Evidence Mapper
            path_b_scores: {dimension: {score, level, rationale, ...}} from Rubric Scorer
            vr_result: Full V^R calculation result dict
            evidence_metadata: Optional per-dimension evidence text (truncated to 3000 chars)

        Returns:
            (markdown_text, json_summary)
        """
        user_content = self._build_user_prompt(
            ticker, company_name, path_a_scores, path_b_scores, vr_result, evidence_metadata
        )

        try:
            response = self.model.invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_content),
            ])
            markdown_text = response.content
            json_summary = self._extract_json_summary(markdown_text, vr_result)

            logger.info(
                "memo_generated",
                ticker=ticker,
                recommendation=json_summary.get("recommendation"),
                word_count=len(markdown_text.split()),
            )
            return markdown_text, json_summary

        except Exception as exc:
            logger.error("memo_generation_failed", ticker=ticker, error=str(exc))
            # Fallback: template-based memo
            return self._fallback_memo(
                ticker, company_name, path_a_scores, path_b_scores, vr_result
            )

    # ──────────────────────────────────────────
    # Prompt construction
    # ──────────────────────────────────────────

    def _build_user_prompt(
        self,
        ticker: str,
        company_name: str,
        path_a_scores: Dict[str, float],
        path_b_scores: Dict[str, Any],
        vr_result: Dict[str, Any],
        evidence_metadata: Dict[str, str] | None,
    ) -> str:
        lines = [
            f"## Company: {company_name} ({ticker})",
            f"**Sector:** {vr_result.get('sector', 'N/A')}",
            f"**V^R Score:** {vr_result.get('vr_score', 'N/A')}",
            "",
            "### V^R Components",
        ]

        vr_comp = vr_result.get("vr_components", {})
        for key, val in vr_comp.items():
            lines.append(f"- {key}: {val}")

        lines += ["", "### Dimension Scores"]
        lines.append("| Dimension | Path A | Path B | Combined |")
        lines.append("|-----------|--------|--------|----------|")

        for dim, definition in DIMENSION_DEFINITIONS.items():
            pa = path_a_scores.get(dim, "N/A")
            pb_data = path_b_scores.get(dim, {})
            pb = pb_data.get("score", "N/A") if isinstance(pb_data, dict) else "N/A"
            # Combined is in dimension_scores of vr_result
            combined_scores = vr_result.get("dimension_scores", {})
            combined = combined_scores.get(dim, "N/A")
            lines.append(f"| {dim} | {pa} | {pb} | {combined} |")

        lines += ["", "### Dimension Definitions"]
        for dim, definition in DIMENSION_DEFINITIONS.items():
            lines.append(f"- **{dim}**: {definition}")

        if evidence_metadata:
            lines += ["", "### Supporting Evidence"]
            for dim, text in evidence_metadata.items():
                lines.append(f"#### {dim}")
                lines.append(_truncate(text))
                lines.append("")

        return "\n".join(lines)

    # ──────────────────────────────────────────
    # JSON extraction
    # ──────────────────────────────────────────

    @staticmethod
    def _extract_json_summary(
        markdown_text: str, vr_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Pull the fenced JSON block from the model response."""
        try:
            start = markdown_text.rfind("```json")
            end = markdown_text.rfind("```", start + 7)
            if start != -1 and end != -1:
                raw = markdown_text[start + 7 : end].strip()
                return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            pass

        # Couldn't parse — return minimal summary
        return {
            "recommendation": "HOLD",
            "vr_score": vr_result.get("vr_score"),
            "top_strength": None,
            "top_weakness": None,
            "discrepancy_flags": [],
            "parse_warning": "Could not extract JSON summary from model response",
        }

    # ──────────────────────────────────────────
    # Fallback template
    # ──────────────────────────────────────────

    def _fallback_memo(
        self,
        ticker: str,
        company_name: str,
        path_a_scores: Dict[str, float],
        path_b_scores: Dict[str, Any],
        vr_result: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        """Template-based memo when the API call fails."""
        vr_score = vr_result.get("vr_score", 0)

        if vr_score >= 60:
            rec = "BUY"
        elif vr_score >= 35:
            rec = "HOLD"
        else:
            rec = "PASS"

        # Find strongest / weakest
        combined = vr_result.get("dimension_scores", {})
        if combined:
            top = max(combined, key=lambda d: combined[d])
            bottom = min(combined, key=lambda d: combined[d])
        else:
            top = bottom = "N/A"

        # Discrepancies
        discrepancies = []
        for dim in DIMENSION_DEFINITIONS:
            pa = path_a_scores.get(dim)
            pb_data = path_b_scores.get(dim, {})
            pb = pb_data.get("score") if isinstance(pb_data, dict) else None
            if pa is not None and pb is not None and abs(float(pa) - float(pb)) > 15:
                discrepancies.append(dim)

        # Build table
        table_lines = ["| Dimension | Path A | Path B | Combined | Delta |"]
        table_lines.append("|-----------|--------|--------|----------|-------|")
        for dim in DIMENSION_DEFINITIONS:
            pa = path_a_scores.get(dim, "N/A")
            pb_data = path_b_scores.get(dim, {})
            pb = pb_data.get("score", "N/A") if isinstance(pb_data, dict) else "N/A"
            comb = combined.get(dim, "N/A")
            delta = ""
            if isinstance(pa, (int, float)) and isinstance(pb, (int, float)):
                delta = f"{abs(pa - pb):.1f}"
            table_lines.append(f"| {dim} | {pa} | {pb} | {comb} | {delta} |")

        table = "\n".join(table_lines)

        markdown = f"""# Investment Memo: {company_name} ({ticker})

> **Note:** This memo was generated using a template fallback (API unavailable).

## Executive Summary

**Recommendation: {rec}**

{company_name} ({ticker}) received a V^R (Venture Readiness) score of **{vr_score:.1f}/100**.
The strongest dimension is **{top}** and the weakest is **{bottom}**.

## Path A vs Path B Comparison

{table}

## Discrepancy Analysis

{"Dimensions with >15-point divergence between Path A and Path B: **" + ", ".join(discrepancies) + "**." if discrepancies else "No significant discrepancies detected (all deltas ≤ 15 points)."}

## Risk Factors

- V^R score indicates {"strong" if vr_score >= 60 else "moderate" if vr_score >= 35 else "limited"} AI readiness
- CV penalty: {vr_result.get("vr_components", {}).get("cv_penalty_amount", "N/A")} points lost to score imbalance
- TC penalty: {vr_result.get("vr_components", {}).get("tc_penalty_amount", "N/A")} points lost to talent concentration risk

## Opportunities

- Strongest dimension ({top}) can be leveraged as competitive advantage
- Addressing weakest dimension ({bottom}) offers highest marginal improvement

## Competitive Positioning

Sector: {vr_result.get("sector", "N/A")}. Further peer comparison requires additional data.
"""

        json_summary = {
            "recommendation": rec,
            "vr_score": vr_score,
            "top_strength": top,
            "top_weakness": bottom,
            "discrepancy_flags": discrepancies,
            "fallback": True,
        }

        logger.warning("memo_fallback_used", ticker=ticker, recommendation=rec)
        return markdown, json_summary
