import sys
from pathlib import Path
import re
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.snowflake import get_connection
from app.config import get_settings
from app.pipelines.board_analyzer import BoardCompositionAnalyzer


def find_matches_with_context(text: str, keyword: str, max_results: int = 3) -> list:
    """Find keyword with 80 chars context before/after"""
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    matches = []
    
    for match in pattern.finditer(text):
        start = max(0, match.start() - 80)
        end = min(len(text), match.end() + 80)
        snippet = text[start:end].replace('\n', ' ').strip()
        matches.append(snippet)
        
        if len(matches) >= max_results:
            break
    
    return matches


def validate_jpm_detailed():
    
    settings = get_settings()
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(f"""
            SELECT dc.chunk_text
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.document_chunks dc
            JOIN {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.documents d
                ON dc.document_id = d.id
            WHERE d.ticker = 'JPM'
                AND d.filing_type = 'DEF 14A'
            ORDER BY d.filing_date DESC, dc.chunk_index
        """)
        
        rows = cur.fetchall()
        all_text = " ".join([row[0] for row in rows if row[0]])
        text_lower = all_text.lower()
        
        print("\n" + "="*70)
        print("JPM BOARD GOVERNANCE - EVIDENCE VALIDATION")
        print("="*70 + "\n")
        
        print(f"📄 Document Stats:")
        print(f"   Total chunks: {len(rows)}")
        print(f"   Total characters: {len(all_text):,}")
        print()
        
        score = 20
        print(f"Base Score: {score} points\n")
        
        # CHECK 1: Tech Committee
        print("─"*70)
        print("CHECK 1: Technology Committee (0 or +15 points)")
        print("─"*70)
        
        tech_committees = [
            "technology committee", "digital committee", "innovation committee",
            "cybersecurity committee", "data committee", "ai committee",
            "technology and cybersecurity committee",
            "information technology committee", "it oversight committee"
        ]
        
        found_tech_comm = []
        for tc in tech_committees:
            pattern = r'\b' + re.escape(tc) + r'\b'
            matches = list(re.finditer(pattern, text_lower))
            
            for match in matches:
                start = max(0, match.start() - 30)
                end = min(len(text_lower), match.end() + 30)
                context = text_lower[start:end]
                
                exclude_terms = ["audit committee", "compensation committee", "nominating committee"]
                is_excluded = any(excl in context for excl in exclude_terms)
                
                if not is_excluded and tc not in found_tech_comm:
                    found_tech_comm.append(tc)
                    snippets = find_matches_with_context(all_text, tc, max_results=1)
                    if snippets:
                        print(f"✅ Found: '{tc}'")
                        print(f"   Context: ...{snippets[0]}...\n")
        
        if found_tech_comm:
            score += 15
            print(f"→ Tech Committee Exists: +15 | Running Total: {score}\n")
        else:
            print(f"❌ No technology committee found")
            print(f"→ Tech Committee: +0 | Running Total: {score}\n")
        
        # CHECK 2: AI Expertise
        print("─"*70)
        print("CHECK 2: AI/Tech Expertise on Board (0 or +20 points)")
        print("─"*70)
        
        ai_long_phrases = [
            "artificial intelligence", "machine learning", "deep learning",
            "natural language processing", "computer vision", "data science",
            "predictive analytics", "chief data officer", "chief ai officer",
            "chief technology officer", "chief information officer",
            "chief digital officer", "chief analytics officer",
            "ai strategy", "ai transformation", "digital transformation",
            "technology strategy", "innovation strategy", "data strategy",
            "ph.d. computer science"
        ]
        
        found_ai = []
        for phrase in ai_long_phrases:
            if phrase in text_lower:
                count = text_lower.count(phrase)
                found_ai.append((phrase, count))
        
        if found_ai:
            print(f"Found {len(found_ai)} AI expertise indicators:\n")
            for phrase, count in sorted(found_ai, key=lambda x: x[1], reverse=True)[:5]:
                snippets = find_matches_with_context(all_text, phrase, max_results=1)
                if snippets:
                    print(f"  ✅ '{phrase}' ({count}x)")
                    print(f"     ...{snippets[0]}...\n")
            
            if len(found_ai) > 5:
                print(f"  ... and {len(found_ai) - 5} more keyword matches\n")
            
            score += 20
            print(f"→ AI Expertise Found: +20 | Running Total: {score}\n")
        else:
            print(f"❌ No AI expertise keywords found\n")
        
        # CHECK 3: Data Officer
        print("─"*70)
        print("CHECK 3: Data Officer Role - CTO/CDO/CAIO (0 or +15 points)")
        print("─"*70)
        
        officer_titles = [
            "chief technology officer",
            "chief information officer",
            "chief digital officer",
            "chief data officer",
            "chief ai officer"
        ]
        
        found_officers = []
        for title in officer_titles:
            if title in text_lower:
                snippets = find_matches_with_context(all_text, title, max_results=1)
                if snippets:
                    found_officers.append(title)
                    print(f"✅ Found: '{title}'")
                    print(f"   ...{snippets[0]}...\n")
        
        if found_officers:
            score += 15
            print(f"→ Data Officer Role Found: +15 | Running Total: {score}\n")
        else:
            print(f"❌ No data officer titles found (full phrase search)")
            print(f"→ Data Officer: +0 | Running Total: {score}\n")
        
        # CHECK 4: Independent Directors
        print("─"*70)
        print("CHECK 4: Independent Director Ratio >50% (0 or +10 points)")
        print("─"*70)
        
        ind_mentions = text_lower.count("independent director")
        snippets = find_matches_with_context(all_text, "independent director", max_results=2)
        
        print(f"'independent director' mentioned: {ind_mentions}x")
        if snippets:
            for i, snippet in enumerate(snippets, 1):
                print(f"  [{i}] ...{snippet}...")
        
        if ind_mentions > 0:
            score += 10
            print(f"\n→ Independent Ratio Estimated >50%: +10 | Running Total: {score}\n")
        else:
            print(f"\n→ Independent Ratio: +0 | Running Total: {score}\n")
        
        # CHECK 5: Risk Committee + Technology
        print("─"*70)
        print("CHECK 5: Risk Committee with Tech Oversight (0 or +10 points)")
        print("─"*70)
        
        has_risk = "risk committee" in text_lower
        has_tech_kw = "technology" in text_lower
        
        if has_risk:
            risk_snippets = find_matches_with_context(all_text, "risk committee", max_results=1)
            print(f"✅ 'risk committee' found")
            if risk_snippets:
                print(f"   ...{risk_snippets[0]}...")
        else:
            print(f"❌ 'risk committee' not found")
        
        if has_tech_kw:
            tech_snippets = find_matches_with_context(all_text, "technology", max_results=1)
            print(f"✅ 'technology' found")
            if tech_snippets:
                print(f"   ...{tech_snippets[0]}...")
        else:
            print(f"❌ 'technology' not found")
        
        if has_risk and has_tech_kw:
            score += 10
            print(f"\n→ Both Found: +10 | Running Total: {score}\n")
        else:
            print(f"\n→ Risk Tech Oversight: +0 | Running Total: {score}\n")
        
        # CHECK 6: Strategic + AI
        print("─"*70)
        print("CHECK 6: AI in Strategic Priorities (0 or +10 points)")
        print("─"*70)
        
        has_strategic = "strategic" in text_lower
        has_ai_kw = "artificial intelligence" in text_lower
        
        if has_strategic:
            strat_snippets = find_matches_with_context(all_text, "strategic", max_results=1)
            print(f"✅ 'strategic' found")
            if strat_snippets:
                print(f"   ...{strat_snippets[0]}...")
        
        if has_ai_kw:
            ai_snippets = find_matches_with_context(all_text, "artificial intelligence", max_results=1)
            print(f"✅ 'artificial intelligence' found")
            if ai_snippets:
                print(f"   ...{ai_snippets[0]}...")
        
        if has_strategic and has_ai_kw:
            score += 10
            print(f"\n→ Both Found: +10 | Running Total: {score}\n")
        else:
            print(f"\n→ AI in Strategy: +0 | Running Total: {score}\n")
        
        # FINAL
        print("="*70)
        print("FINAL SCORE CALCULATION")
        print("="*70)
        print(f"Calculated Score: {score}/100")
        print(f"Returned Score:   {result.governance_score:.1f}/100")
        
        if abs(score - result.governance_score) < 1:
            print("✅ VALIDATION PASSED - Scores Match")
        else:
            print(f"⚠️ MISMATCH: Difference of {abs(score - result.governance_score):.1f} points")
        
        print("="*70 + "\n")
        
    finally:
        cur.close()
        conn.close()


def test_all_companies():
    
    tickers = ["JPM", "GS", "WMT", "TGT", "UNH", "HCA", "ADP", "PAYX", "CAT", "DE"]
    
    print("\n" + "="*70)
    print("BOARD GOVERNANCE - ALL COMPANIES (CORRECTED)")
    print("="*70 + "\n")
    
    analyzer = BoardCompositionAnalyzer()
    results = []
    
    for ticker in tickers:
        result = analyzer.analyze_company_governance(ticker)
        if result:
            results.append(result)
            
            status = "✅" if result.governance_score > 20 else "⚠️"
            print(f"{status} {ticker:6} | Score: {result.governance_score:5.1f} | "
                  f"Tech Comm: {'✅' if result.has_tech_committee else '❌'} | "
                  f"AI Expert: {'✅' if result.has_ai_expertise else '❌'} | "
                  f"Data Officer: {'✅' if result.has_data_officer else '❌'}")
        else:
            print(f"❌ {ticker:6} | No data found")
    
    if results:
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70 + "\n")
        
        avg_score = sum(r.governance_score for r in results) / len(results)
        companies_with_tech_comm = sum(1 for r in results if r.has_tech_committee)
        companies_with_ai_expert = sum(1 for r in results if r.has_ai_expertise)
        companies_with_officer = sum(1 for r in results if r.has_data_officer)
        
        print(f"Average Governance Score: {avg_score:.1f}/100")
        print(f"Companies with Tech Committee: {companies_with_tech_comm}/{len(results)}")
        print(f"Companies with AI Expertise: {companies_with_ai_expert}/{len(results)}")
        print(f"Companies with Data Officer: {companies_with_officer}/{len(results)}")
        print()


if __name__ == "__main__":
    validate_jpm_detailed()
    print()
    test_all_companies()