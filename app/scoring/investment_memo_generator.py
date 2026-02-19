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

1. **Executive Summary** — 2-3 sentences with a clear BUY / HOLD / PASS recommendation and the Org-AI-R score (primary metric) alongside the V^R score.
2. **Path A vs Path B Comparison** — A Markdown table with columns: Dimension | Path A (Quantitative) | Path B (Qualitative) | Combined | Delta.
3. **Seven-Dimension Deep Dive** — One paragraph per dimension explaining the score drivers.
4. **Industry Context** — Compare the company's V^R score against the H^R (industry baseline). Explain alignment: does the company exceed, meet, or fall short of sector expectations? Use the Org-AI-R score as the primary recommendation driver.
5. **Discrepancy Analysis** — Flag any dimension where |Path A − Path B| > 15 points and explain possible causes.
6. **Risk Factors** — Bullet list of key risks. Include board governance assessment if available (tech committee presence, AI expertise on board, data officer).
7. **Opportunities** — Bullet list of upside catalysts.
8. **Competitive Positioning** — Where this company sits relative to sector peers, using confidence interval and alignment data.

RECOMMENDATION THRESHOLDS (use Org-AI-R score as the primary driver):
- Org-AI-R >= 60  →  BUY  (strong AI readiness, attractive investment)
- Org-AI-R >= 35 and < 60  →  HOLD  (moderate readiness, monitor for improvement)
- Org-AI-R < 35  →  PASS  (weak readiness, significant gaps)

You MUST apply these thresholds consistently. The recommendation in the Executive Summary
and in the JSON summary block must match the threshold the Org-AI-R score falls into.

Use precise numbers from the data provided. Do not fabricate data points.
Keep the total memo under 1500 words.

Also produce a JSON summary block at the very end of your response, fenced with ```json ... ```, containing:
{
  "recommendation": "BUY" | "HOLD" | "PASS",
  "vr_score": <number>,
  "org_air_score": <number>,
  "hr_score": <number>,
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
        full_scores: Dict[str, Any] | None = None,
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
            full_scores: Full Org-AI-R scoring result from ScoringIntegrationService

        Returns:
            (markdown_text, json_summary)
        """
        user_content = self._build_user_prompt(
            ticker, company_name, path_a_scores, path_b_scores, vr_result, evidence_metadata,
            full_scores,
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
                ticker, company_name, path_a_scores, path_b_scores, vr_result,
                full_scores,
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
        full_scores: Dict[str, Any] | None = None,
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

        if full_scores:
            lines += ["", "### Full Scoring Context"]
            lines.append(f"- **H^R (Industry Baseline):** {full_scores.get('hr_score', 'N/A')}")
            lines.append(f"- **Org-AI-R (Final Score):** {full_scores.get('org_air_score', 'N/A')}")
            lines.append(f"- **Alignment (VR vs HR):** {full_scores.get('alignment', 'N/A')}")
            lines.append(f"- **Synergy Score:** {full_scores.get('synergy_score', 'N/A')}")
            lines.append(f"- **Board Governance:** {full_scores.get('board_governance_score', 'N/A')}")
            lines.append(f"- **Confidence Interval:** [{full_scores.get('ci_lower', 'N/A')}, {full_scores.get('ci_upper', 'N/A')}]")
            lines.append(f"- **Confidence:** {full_scores.get('confidence', 'N/A')}")
            lines.append(f"- **Talent Concentration:** {full_scores.get('talent_concentration', 'N/A')}")
            lines.append(f"- **Position Factor:** {full_scores.get('position_factor', 'N/A')}")

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
        full_scores: Dict[str, Any] | None = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Template-based memo when the API call fails."""
        org_air_score = full_scores.get("org_air_score", 0) if full_scores else vr_result.get("vr_score", 0)
        vr_score = vr_result.get("vr_score", 0)

        if org_air_score >= 60:
            rec = "BUY"
        elif org_air_score >= 35:
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

        # Build full scoring context section if available
        full_scoring_section = ""
        if full_scores:
            hr_score = full_scores.get("hr_score", "N/A")
            org_air_score = full_scores.get("org_air_score", "N/A")
            alignment = full_scores.get("alignment", "N/A")
            board_gov = full_scores.get("board_governance_score", "N/A")
            ci_lower = full_scores.get("ci_lower", "N/A")
            ci_upper = full_scores.get("ci_upper", "N/A")
            full_scoring_section = f"""
## Industry Context & Org-AI-R

| Metric | Value |
|--------|-------|
| H^R (Industry Baseline) | {hr_score} |
| Org-AI-R (Final Score) | {org_air_score} |
| Alignment (VR vs HR) | {alignment} |
| Board Governance | {board_gov} |
| Confidence Interval | [{ci_lower}, {ci_upper}] |
"""

        markdown = f"""# Investment Memo: {company_name} ({ticker})

> **Note:** This memo was generated using a template fallback (API unavailable).

## Executive Summary

**Recommendation: {rec}**

{company_name} ({ticker}) received a V^R (Venture Readiness) score of **{vr_score:.1f}/100**{f" and an Org-AI-R score of **{full_scores.get('org_air_score', 'N/A'):.1f}/100**" if full_scores and isinstance(full_scores.get('org_air_score'), (int, float)) else ""}.
The strongest dimension is **{top}** and the weakest is **{bottom}**.

## Path A vs Path B Comparison

{table}
{full_scoring_section}
## Discrepancy Analysis

{"Dimensions with >15-point divergence between Path A and Path B: **" + ", ".join(discrepancies) + "**." if discrepancies else "No significant discrepancies detected (all deltas ≤ 15 points)."}

## Risk Factors

- V^R score indicates {"strong" if vr_score >= 60 else "moderate" if vr_score >= 35 else "limited"} AI readiness
- CV penalty: {vr_result.get("vr_components", {}).get("cv_penalty_amount", "N/A")} points lost to score imbalance
- TC penalty: {vr_result.get("vr_components", {}).get("tc_penalty_amount", "N/A")} points lost to talent concentration risk
{f"- Board governance score: {full_scores.get('board_governance_score', 'N/A')}" if full_scores else ""}

## Opportunities

- Strongest dimension ({top}) can be leveraged as competitive advantage
- Addressing weakest dimension ({bottom}) offers highest marginal improvement

## Competitive Positioning

Sector: {vr_result.get("sector", "N/A")}. Further peer comparison requires additional data.
"""

        json_summary = {
            "recommendation": rec,
            "vr_score": vr_score,
            "org_air_score": full_scores.get("org_air_score") if full_scores else None,
            "hr_score": full_scores.get("hr_score") if full_scores else None,
            "top_strength": top,
            "top_weakness": bottom,
            "discrepancy_flags": discrepancies,
            "fallback": True,
        }

        logger.warning("memo_fallback_used", ticker=ticker, recommendation=rec)
        return markdown, json_summary
