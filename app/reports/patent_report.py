# app/reports/patent_report.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import csv

from app.models.signal import ExternalSignal


@dataclass
class PatentReportPaths:
    md_path: Path
    csv_path: Path


def write_patent_report(signal: ExternalSignal, out_dir: Path) -> PatentReportPaths:
    out_dir.mkdir(parents=True, exist_ok=True)

    company_id = str(signal.company_id) if signal.company_id else "unknown"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    md_path = out_dir / f"patent_signal_{company_id}_{ts}.md"
    csv_path = out_dir / f"patent_signal_{company_id}_{ts}.csv"

    md_path.write_text(_render_markdown(signal), encoding="utf-8")
    _write_csv(signal, csv_path)

    return PatentReportPaths(md_path=md_path, csv_path=csv_path)


def _render_markdown(signal: ExternalSignal) -> str:
    meta = signal.metadata or {}
    breakdown = meta.get("score_breakdown") or {}

    lines = []
    lines.append("# Patent Signal (Google Patents)\n")
    lines.append(f"**Company ID:** {signal.company_id}\n")
    lines.append(f"**Source:** {signal.source}\n")
    lines.append(f"**Category:** {signal.category}\n")
    lines.append(f"**Collected (UTC):** {signal.signal_date.isoformat()}\n")

    lines.append("\n## Final Score\n")
    lines.append(f"**{signal.normalized_score:.1f}/100**\n")

    lines.append("\n## Browser Verification\n")
    lines.append(f"- Open: {meta.get('verification_url', '(missing)')}\n")
    lines.append("- Confirm assignee filter + keyword query are present\n")
    lines.append("- Confirm results show AI-related patent matches\n")

    lines.append("\n## Score Breakdown (PDF Rules)\n")
    lines.append("| Component | Score | Max | Rule |\n")
    lines.append("|---|---:|---:|---|\n")
    lines.append(f"| AI Patent Count | {breakdown.get('patent_count_score','?')} | 50 | min(ai_patents × 5, 50) |\n")
    lines.append(f"| Recency (1y) | {breakdown.get('recency_bonus_score','?')} | 20 | min(recent_ai_patents × 2, 20) |\n")
    lines.append(f"| Category Diversity | {breakdown.get('category_diversity_score','?')} | 30 | min(#categories × 10, 30) |\n")
    lines.append(f"| **TOTAL** | **{breakdown.get('total','?')}** | **100** | |\n")

    lines.append("\n## Evidence Fields\n")
    lines.append(f"- Assignee: {meta.get('assignee')}\n")
    lines.append(f"- AI Keywords Used: {meta.get('ai_keywords_used')}\n")
    lines.append(f"- AI Patents (counted): {meta.get('ai_patents')}\n")
    lines.append(f"- Recent AI Patents (1y): {meta.get('recent_ai_patents')}\n")
    lines.append(f"- AI Categories: {meta.get('ai_categories')}\n")
    lines.append(f"- Total Results Estimate: {meta.get('total_results_estimate')}\n")

    lines.append("\n## Sampled Evidence Items (first 25)\n")
    for it in (meta.get("sampled_items") or []):
        lines.append(f"- {it.get('title','(no title)')} | {it.get('priority_date')} | AI={it.get('is_ai_related')} | {it.get('url')}\n")

    return "".join(lines)


def _write_csv(signal: ExternalSignal, csv_path: Path) -> None:
    meta = signal.metadata or {}
    breakdown = meta.get("score_breakdown") or {}

    row = {
        "company_id": str(signal.company_id),
        "signal_date": signal.signal_date.isoformat(),
        "source": str(signal.source),
        "category": str(signal.category),
        "normalized_score": signal.normalized_score,
        "assignee": meta.get("assignee"),
        "verification_url": meta.get("verification_url"),
        "total_results_estimate": meta.get("total_results_estimate"),
        "ai_patents": meta.get("ai_patents"),
        "recent_ai_patents": meta.get("recent_ai_patents"),
        "ai_categories": ",".join(meta.get("ai_categories") or []),
        "patent_count_score": breakdown.get("patent_count_score"),
        "recency_bonus_score": breakdown.get("recency_bonus_score"),
        "category_diversity_score": breakdown.get("category_diversity_score"),
        "total_score": breakdown.get("total"),
    }

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        w.writeheader()
        w.writerow(row)