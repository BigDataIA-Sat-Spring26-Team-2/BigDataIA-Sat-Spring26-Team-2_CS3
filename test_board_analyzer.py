import sys
from pathlib import Path
import re
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.snowflake import get_connection
from app.config import get_settings
from app.pipelines.board_analyzer import BoardCompositionAnalyzer



def find_matches_with_context(text: str, keyword: str, max_results: int = 2):
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    matches = []

    for match in pattern.finditer(text):
        start = max(0, match.start() - 80)
        end = min(len(text), match.end() + 80)
        snippet = text[start:end].replace("\n", " ").strip()
        matches.append(snippet)

        if len(matches) >= max_results:
            break

    return matches

def explain_analyzer_score(result):
    breakdown = {
        "Base": 20,
        "Tech Committee": 15 if result.has_tech_committee else 0,
        "AI Expertise": 20 if result.has_ai_expertise else 0,
        "Data Officer": 15 if result.has_data_officer else 0,
        "Independent Directors": 10 if result.independent_ratio > 0.5 else 0,
        "Risk + Technology": 10 if result.has_risk_tech_oversight else 0,
        "AI in Strategy": 10 if result.has_ai_in_strategy else 0,
    }

    total = sum(breakdown.values())

    print("\nANALYZER SCORE EXPLANATION")
    print("-" * 70)
    for k, v in breakdown.items():
        print(f"{k:30}: {v}")
    print("-" * 70)
    print(f"TOTAL ANALYZER SCORE: {total}/100\n")

def validate_company_detailed(ticker: str):
    settings = get_settings()
    conn = get_connection()
    cur = conn.cursor()

    analyzer = BoardCompositionAnalyzer()
    result = analyzer.analyze_company_governance(ticker)

    if not result:
        print(f"No data found for {ticker}")
        return

    try:
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
        all_text = " ".join(row[0] for row in rows if row[0])
        text_lower = all_text.lower()

        print("\n" + "=" * 90)
        print(f"{ticker} – BOARD GOVERNANCE DETAILED VALIDATION")
        print("=" * 90 + "\n")

        print(f"Document chunks: {len(rows)}")
        print(f"Total characters: {len(all_text):,}\n")

        score = 20
        print(f"Base score: {score}\n")

        print("CHECK 1: TECHNOLOGY / DIGITAL COMMITTEE (+15)")
        found = False
        for tc in analyzer.TECH_COMMITTEE_NAMES:
            if tc in text_lower:
                found = True
                print(f"  Found '{tc}'")
                for s in find_matches_with_context(all_text, tc):
                    print(f"     ...{s}...")

        if found:
            score += 15
            print(f"→ +15 | Running score: {score}\n")
        else:
            print(" No technology committee found\n")

        print("CHECK 2: AI / TECHNOLOGY EXPERTISE (+20)")
        ai_hits = [kw for kw in analyzer.AI_EXPERTISE_KEYWORDS if kw in text_lower]

        if ai_hits:
            unique_hits = sorted(set(ai_hits))
            print(f"  Found {len(unique_hits)} AI indicators:")
            for kw in unique_hits[:5]:
                print(f"  {kw}")
                for s in find_matches_with_context(all_text, kw, 1):
                    print(f"      ...{s}...")
            score += 20
            print(f"→ +20 | Running score: {score}\n")
        else:
            print(" No AI expertise indicators found\n")

        print("CHECK 3: DATA / TECHNOLOGY OFFICER (+15)")
        found = False
        for title in analyzer.DATA_OFFICER_TITLES:
            if title in text_lower:
                found = True
                print(f" {title}")
                for s in find_matches_with_context(all_text, title, 1):
                    print(f"     ...{s}...")

        if found:
            score += 15
            print(f"→ +15 | Running score: {score}\n")
        else:
            print(" No CTO / CDO / CAIO references\n")

        print("CHECK 4: INDEPENDENT DIRECTORS (+10)")
        if "independent director" in text_lower:
            for s in find_matches_with_context(all_text, "independent director", 2):
                print(f"  ...{s}...")
            score += 10
            print(f"→ +10 | Running score: {score}\n")
        else:
            print("   No independent director references\n")

        print("CHECK 5: RISK COMMITTEE WITH TECH (+10)")
        if "risk" in text_lower and "committee" in text_lower and "technology" in text_lower:
            for s in find_matches_with_context(all_text, "risk committee", 1):
                print(f"  ...{s}...")
            score += 10
            print(f"→ +10 | Running score: {score}\n")
        else:
            print(" Risk + technology oversight not found\n")

        print("CHECK 6: AI IN STRATEGIC CONTEXT (+10)")
        if "artificial intelligence" in text_lower and any(
            k in text_lower for k in ["strategic", "strategy", "oversight", "priorities"]
        ):
            for s in find_matches_with_context(all_text, "artificial intelligence", 1):
                print(f"   ...{s}...")
            score += 10
            print(f"→ +10 | Running score: {score}\n")
        else:
            print("  AI not clearly linked to strategy\n")

        print("=" * 90)
        print("FINAL SCORES")
        print("=" * 90)
        print(f"Final calculated score (authoritative): {score}/100")
        print(f"Analyzer score (model output):          {result.governance_score}/100")

        explain_analyzer_score(result)

        print("=" * 90)
        print("EXTRACTED BOARD MEMBERS")
        print("=" * 90)

        print(f"Total members extracted: {len(result.board_members)}\n")
        for m in result.board_members:
            print(f"• {m.name} | {m.title}")
            print(f"  Independent: {m.is_independent}")
            if m.has_ai_background:
                print(f"AI Keywords: {', '.join(m.ai_keywords_found[:3])}")
            print()

    finally:
        cur.close()
        conn.close()

def run_detailed_reports_for_all_companies():
    tickers = ["JPM", "GS", "WMT", "TGT", "UNH", "HCA", "ADP", "PAYX", "CAT", "DE"]

    for ticker in tickers:
        validate_company_detailed(ticker)

if __name__ == "__main__":
    run_detailed_reports_for_all_companies()