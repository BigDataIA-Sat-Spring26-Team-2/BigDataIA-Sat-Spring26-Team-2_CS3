import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.services.snowflake import get_connection
from app.config import get_settings


def fetch_stats():
    settings = get_settings()
    db = settings.SNOWFLAKE_DATABASE
    schema = settings.SNOWFLAKE_SCHEMA

    conn = get_connection()
    cur = conn.cursor()

    lines = []

    def md(text=""):
        lines.append(text)

    try:
        # =============================================
        # HEADER
        # =============================================
        md("# Evidence Collection Report")
        md()
        md("## PE Org-AI-R Platform — Case Study 1 & 2")
        md()
        md("**Authors:** Prachi Pradhan, Samiksh Gupta, Siddharth Shukla")
        md()
        md("**Course:** Big Data and Intelligent Analytics — Northeastern University, Spring 2026")
        md()
        md("---")
        md()

        # =============================================
        # OVERALL SUMMARY
        # =============================================
        cur.execute(f"SELECT COUNT(DISTINCT ticker) FROM {db}.{schema}.documents")
        doc_companies = cur.fetchone()[0]

        cur.execute(f"SELECT COUNT(*) FROM {db}.{schema}.documents")
        doc_count = cur.fetchone()[0]

        cur.execute(f"SELECT COUNT(*) FROM {db}.{schema}.document_chunks")
        chunk_count = cur.fetchone()[0]

        cur.execute(f"SELECT COUNT(*) FROM {db}.{schema}.external_signals")
        signal_count = cur.fetchone()[0]

        cur.execute(f"SELECT COUNT(DISTINCT company_id) FROM {db}.{schema}.external_signals")
        signal_companies = cur.fetchone()[0]

        cur.execute(f"SELECT AVG(composite_score) FROM {db}.{schema}.company_signal_summaries")
        avg_composite = cur.fetchone()[0] or 0

        md("## Summary Statistics")
        md()
        md("| Metric | Value |")
        md("|--------|-------|")
        md(f"| Companies with documents | {doc_companies} |")
        md(f"| Total documents | {doc_count} |")
        md(f"| Total chunks | {chunk_count:,} |")
        md(f"| Companies with signals | {signal_companies} |")
        md(f"| Total signals | {signal_count} |")
        md(f"| Avg composite score | {float(avg_composite):.1f} |")
        md()
        md("---")
        md()

        # =============================================
        # DOCUMENT STATISTICS (sorted by total docs DESC)
        # =============================================
        md("## Documents by Company")
        md()

        cur.execute(f"""
            SELECT 
                d.ticker,
                c.name AS company,
                COUNT(CASE WHEN d.filing_type = '10-K' THEN 1 END) AS ten_k,
                COUNT(CASE WHEN d.filing_type = '10-Q' THEN 1 END) AS ten_q,
                COUNT(CASE WHEN d.filing_type = '8-K' THEN 1 END) AS eight_k,
                COUNT(CASE WHEN d.filing_type = 'DEF 14A' THEN 1 END) AS def14a,
                COUNT(*) AS total_docs
            FROM {db}.{schema}.documents d
            JOIN {db}.{schema}.companies c ON d.company_id = c.id
            GROUP BY d.ticker, c.name
            ORDER BY total_docs DESC
        """)

        rows = cur.fetchall()

        md("| Ticker | Company | 10-K | 10-Q | 8-K | DEF 14A | Total Docs |")
        md("|--------|---------|------|------|-----|---------|------------|")

        t_10k = t_10q = t_8k = t_def = t_total = 0
        for r in rows:
            md(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} |")
            t_10k += r[2]
            t_10q += r[3]
            t_8k += r[4]
            t_def += r[5]
            t_total += r[6]

        md(f"| **Total** | | **{t_10k}** | **{t_10q}** | **{t_8k}** | **{t_def}** | **{t_total}** |")
        md()
        md("---")
        md()

        # =============================================
        # CHUNK STATISTICS (sorted by chunks DESC)
        # =============================================
        md("## Chunks by Company")
        md()

        cur.execute(f"""
            SELECT 
                d.ticker,
                c.name AS company,
                COUNT(DISTINCT d.id) AS total_docs,
                COUNT(dc.id) AS total_chunks,
                COALESCE(SUM(dc.word_count), 0) AS total_words
            FROM {db}.{schema}.documents d
            JOIN {db}.{schema}.companies c ON d.company_id = c.id
            LEFT JOIN {db}.{schema}.document_chunks dc ON d.id = dc.document_id
            GROUP BY d.ticker, c.name
            ORDER BY total_chunks DESC
        """)

        rows = cur.fetchall()

        md("| Ticker | Company | Total Docs | Total Chunks | Total Words |")
        md("|--------|---------|------------|--------------|-------------|")

        tc = tw = td = 0
        for r in rows:
            words = int(r[4] or 0)
            md(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]:,} | {words:,} |")
            td += r[2]
            tc += r[3]
            tw += words

        md(f"| **Total** | | **{td}** | **{tc:,}** | **{tw:,}** |")
        md()
        md("---")
        md()

        # =============================================
        # SECTIONS BY FILING TYPE (sorted by chunk count DESC)
        # =============================================
        md("## Sections Extracted by Filing Type")
        md()

        cur.execute(f"""
            SELECT 
                dc.section,
                d.filing_type,
                COUNT(*) AS chunk_count
            FROM {db}.{schema}.document_chunks dc
            JOIN {db}.{schema}.documents d ON dc.document_id = d.id
            WHERE dc.section IS NOT NULL
            GROUP BY dc.section, d.filing_type
            ORDER BY chunk_count DESC
        """)

        rows = cur.fetchall()

        md("| Section | Filing Type | Chunk Count |")
        md("|---------|-------------|-------------|")
        for r in rows:
            md(f"| {r[0]} | {r[1]} | {r[2]:,} |")
        md()
        md("---")
        md()

        # =============================================
        # SAY SCORES (AI keyword density)
        # =============================================
        md("## Say Scores (AI Rhetoric in SEC Filings)")
        md()
        md("Say Score measures AI keyword density in SEC filing text. Higher = more AI rhetoric.")
        md()

        from app.pipelines.say_score_analyzer import SayScoreAnalyzer
        analyzer = SayScoreAnalyzer()

        tickers = ["CAT", "DE", "UNH", "HCA", "ADP", "PAYX", "WMT", "TGT", "JPM", "GS"]
        say_scores = {}

        for ticker in tickers:
            try:
                score = analyzer.calculate_say_score(ticker)
                say_scores[ticker] = score
            except Exception as e:
                say_scores[ticker] = 0.0

        # Sort by say score DESC
        sorted_say = sorted(say_scores.items(), key=lambda x: x[1], reverse=True)

        md("| Rank | Ticker | Say Score (0-100) |")
        md("|------|--------|-------------------|")
        for rank, (ticker, score) in enumerate(sorted_say, 1):
            md(f"| {rank} | {ticker} | {score:.1f} |")

        md()
        md("---")
        md()

        # =============================================
        # DO SCORES (composite external signals)
        # =============================================
        md("## Do Scores (Actual AI Investment — External Signals)")
        md()
        md("Do Score = composite external signal score. Higher = more actual AI activity.")
        md()

        cur.execute(f"""
            SELECT 
                css.ticker,
                c.name,
                css.technology_hiring_score,
                css.innovation_activity_score,
                css.digital_presence_score,
                css.leadership_signals_score,
                css.composite_score,
                css.signal_count
            FROM {db}.{schema}.company_signal_summaries css
            JOIN {db}.{schema}.companies c ON css.company_id = c.id
            ORDER BY css.composite_score DESC
        """)

        rows = cur.fetchall()
        do_scores = {}

        md("| Rank | Ticker | Company | Hiring (30%) | Innovation (25%) | Digital (25%) | Leadership (20%) | Do Score | Signals |")
        md("|------|--------|---------|-------------|-----------------|--------------|-----------------|----------|---------|")

        for rank, r in enumerate(rows, 1):
            hiring = float(r[2] or 0)
            innov = float(r[3] or 0)
            digital = float(r[4] or 0)
            leader = float(r[5] or 0)
            comp = float(r[6] or 0)
            sigs = r[7] or 0
            do_scores[r[0]] = comp
            md(f"| {rank} | {r[0]} | {r[1]} | {hiring:.1f} | {innov:.1f} | {digital:.1f} | {leader:.1f} | **{comp:.1f}** | {sigs} |")

        md()
        md("---")
        md()

        # =============================================
        # SAY-DO GAP ANALYSIS
        # =============================================
        md("## Say-Do Gap Analysis")
        md()
        md("Gap = Say Score - Do Score. Positive gap means company talks more than it does. Negative gap means company does more than it talks.")
        md()

        gap_data = []
        for ticker in tickers:
            say = say_scores.get(ticker, 0.0)
            do = do_scores.get(ticker, 0.0)
            gap = say - do
            gap_data.append((ticker, say, do, gap))

        # Sort by gap DESC (biggest talkers first)
        gap_data.sort(key=lambda x: x[3], reverse=True)

        md("| Rank | Ticker | Say Score | Do Score | Gap (Say - Do) | Assessment |")
        md("|------|--------|-----------|----------|----------------|------------|")

        for rank, (ticker, say, do, gap) in enumerate(gap_data, 1):
            if gap > 15:
                assessment = "Overstating AI"
            elif gap > 5:
                assessment = "More talk than action"
            elif gap > -5:
                assessment = "Balanced"
            elif gap > -15:
                assessment = "Quiet builder"
            else:
                assessment = "Strong doer"
            md(f"| {rank} | {ticker} | {say:.1f} | {do:.1f} | {gap:+.1f} | {assessment} |")

        md()
        md("---")
        md()

        # =============================================
        # SECTOR ANALYSIS (sorted by avg composite DESC)
        # =============================================
        md("## Sector Analysis")
        md()

        cur.execute(f"""
            SELECT 
                i.sector,
                AVG(css.technology_hiring_score) AS avg_hiring,
                AVG(css.innovation_activity_score) AS avg_innovation,
                AVG(css.digital_presence_score) AS avg_digital,
                AVG(css.leadership_signals_score) AS avg_leadership,
                AVG(css.composite_score) AS avg_composite,
                COUNT(*) AS company_count
            FROM {db}.{schema}.company_signal_summaries css
            JOIN {db}.{schema}.companies c ON css.company_id = c.id
            JOIN {db}.{schema}.industries i ON c.industry_id = i.id
            GROUP BY i.sector
            ORDER BY avg_composite DESC
        """)

        rows = cur.fetchall()

        md("| Rank | Sector | Avg Hiring | Avg Innovation | Avg Digital | Avg Leadership | Avg Composite | Companies |")
        md("|------|--------|-----------|----------------|-------------|----------------|---------------|-----------|")
        for rank, r in enumerate(rows, 1):
            md(f"| {rank} | {r[0]} | {float(r[1] or 0):.1f} | {float(r[2] or 0):.1f} | {float(r[3] or 0):.1f} | {float(r[4] or 0):.1f} | **{float(r[5] or 0):.1f}** | {r[6]} |")

        md()
        md("---")
        md()

        # =============================================
        # LATEST SIGNALS DETAIL (sorted by score DESC)
        # =============================================
        md("## Latest Signals Detail")
        md()

        cur.execute(f"""
            SELECT 
                c.ticker,
                es.category,
                es.source,
                es.normalized_score,
                es.confidence,
                es.raw_value,
                es.signal_date
            FROM {db}.{schema}.external_signals es
            JOIN {db}.{schema}.companies c ON es.company_id = c.id
            WHERE (es.category, es.company_id, es.created_at) IN (
                SELECT category, company_id, MAX(created_at)
                FROM {db}.{schema}.external_signals
                GROUP BY category, company_id
            )
            ORDER BY es.normalized_score DESC
        """)

        rows = cur.fetchall()

        md("| Ticker | Category | Source | Score | Confidence | Raw Value |")
        md("|--------|----------|--------|-------|------------|-----------|")
        for r in rows:
            score = float(r[3])
            conf = float(r[4])
            raw = str(r[5])[:60]
            md(f"| {r[0]} | {r[1]} | {r[2]} | {score:.1f} | {conf:.2f} | {raw} |")

        md()
        md("---")
        md()

        # =============================================
        # TOP / BOTTOM COMPANIES
        # =============================================
        md("## Key Findings")
        md()

        # Top 3 Do Score
        do_sorted = sorted(do_scores.items(), key=lambda x: x[1], reverse=True)
        md("### Top 3 Companies by Do Score (Actual AI Investment)")
        md()
        for i, (ticker, score) in enumerate(do_sorted[:3], 1):
            md(f"{i}. **{ticker}** — Do Score: {score:.1f}")
        md()

        # Bottom 3 Do Score
        md("### Bottom 3 Companies by Do Score")
        md()
        for i, (ticker, score) in enumerate(do_sorted[-3:], 1):
            md(f"{i}. **{ticker}** — Do Score: {score:.1f}")
        md()

        # Top 3 Say Score
        md("### Top 3 Companies by Say Score (AI Rhetoric)")
        md()
        for i, (ticker, score) in enumerate(sorted_say[:3], 1):
            md(f"{i}. **{ticker}** — Say Score: {score:.1f}")
        md()

        # Biggest Say-Do Gaps
        md("### Biggest Say-Do Gaps (Potential Overstaters)")
        md()
        gap_sorted = sorted(gap_data, key=lambda x: x[3], reverse=True)
        for i, (ticker, say, do, gap) in enumerate(gap_sorted[:3], 1):
            md(f"{i}. **{ticker}** — Say: {say:.1f}, Do: {do:.1f}, Gap: {gap:+.1f}")
        md()

        # Biggest Negative Gaps (Quiet Builders)
        md("### Quiet Builders (Do > Say)")
        md()
        gap_sorted_asc = sorted(gap_data, key=lambda x: x[3])
        for i, (ticker, say, do, gap) in enumerate(gap_sorted_asc[:3], 1):
            md(f"{i}. **{ticker}** — Say: {say:.1f}, Do: {do:.1f}, Gap: {gap:+.1f}")
        md()

        md("---")
        md()
        md("*Report generated from Snowflake database and SEC filing analysis.*")

    finally:
        cur.close()
        conn.close()

    # Write to file
    out_dir = Path("reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "evidence_stats.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\nReport written to: {out_path}")
    print(f"Total lines: {len(lines)}")


if __name__ == "__main__":
    fetch_stats()