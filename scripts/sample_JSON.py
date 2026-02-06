"""
Export sample evidence for submission.
Run: python scripts/export_sample_evidence.py
Output:
  data/samples/sample_document_1.json
  data/samples/sample_document_2.json
  data/samples/sample_document_3.json
  data/samples/signal_summary_CAT.json  (one per company)
"""

import sys
import json
from pathlib import Path
from datetime import datetime, date

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.services.snowflake import get_connection
from app.config import get_settings


def json_serial(obj):
    from decimal import Decimal
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    raise TypeError(f"Type {type(obj)} not serializable")


def row_to_dict(row, cursor):
    cols = [desc[0] for desc in cursor.description]
    return {k.lower(): v for k, v in zip(cols, row)}


def row_to_dict_upper(row, cols):
    """Use pre-saved column names (uppercase from Snowflake)"""
    return dict(zip(cols, row))


def export_sample_documents(cur, db, schema, out_dir):
    """Export 3 sample parsed documents — one 10-K, one 8-K, one DEF 14A"""

    print("\n=== Exporting 3 Sample Documents ===\n")

    types_wanted = ["10-K", "8-K", "DEF 14A"]
    selected = []

    for ft in types_wanted:
        cur.execute(f"""
            SELECT 
                d.id, d.company_id, d.ticker, d.filing_type,
                d.accession_number, d.filing_date, d.content_hash,
                d.word_count, d.file_path,
                d.sections_extracted, d.sections_stored, d.sections_duplicates,
                d.created_at,
                c.name AS company_name
            FROM {db}.{schema}.documents d
            JOIN {db}.{schema}.companies c ON d.company_id = c.id
            WHERE d.filing_type = %s
            ORDER BY d.word_count DESC
            LIMIT 1
        """, (ft,))

        row = cur.fetchone()
        if row:
            selected.append(row_to_dict(row, cur))

    # If we got fewer than 3, fill with largest remaining docs
    if len(selected) < 3:
        existing_ids = [d["id"] for d in selected]
        placeholders = ",".join(["%s"] * len(existing_ids)) if existing_ids else "''"

        cur.execute(f"""
            SELECT 
                d.id, d.company_id, d.ticker, d.filing_type,
                d.accession_number, d.filing_date, d.content_hash,
                d.word_count, d.file_path,
                d.sections_extracted, d.sections_stored, d.sections_duplicates,
                d.created_at,
                c.name AS company_name
            FROM {db}.{schema}.documents d
            JOIN {db}.{schema}.companies c ON d.company_id = c.id
            {"WHERE d.id NOT IN (" + placeholders + ")" if existing_ids else ""}
            ORDER BY d.word_count DESC
            LIMIT %s
        """, (*existing_ids, 3 - len(selected)))

        for row in cur.fetchall():
            selected.append(row_to_dict(row, cur))

    for idx, doc in enumerate(selected, 1):
        doc_id = doc["id"]

        # Fetch chunks (first 5, text truncated)
        cur.execute(f"""
            SELECT 
                dc.id, dc.chunk_index, dc.chunk_text,
                dc.content_hash, dc.word_count, dc.section
            FROM {db}.{schema}.document_chunks dc
            WHERE dc.document_id = %s
            ORDER BY dc.chunk_index
            LIMIT 5
        """, (doc_id,))

        chunks = []
        for crow in cur.fetchall():
            chunk = row_to_dict(crow, cur)
            # Truncate text for sample
            if chunk.get("chunk_text") and len(chunk["chunk_text"]) > 500:
                chunk["chunk_text"] = chunk["chunk_text"][:500] + "...[truncated]"
            chunks.append(chunk)

        # Fetch total chunk count
        cur.execute(f"""
            SELECT COUNT(*) FROM {db}.{schema}.document_chunks
            WHERE document_id = %s
        """, (doc_id,))
        total_chunks = cur.fetchone()[0]

        sample = {
            "document_metadata": {
                "id": doc["id"],
                "company_id": doc["company_id"],
                "company_name": doc["company_name"],
                "ticker": doc["ticker"],
                "filing_type": doc["filing_type"],
                "accession_number": doc["accession_number"],
                "filing_date": doc["filing_date"],
                "content_hash": doc["content_hash"],
                "word_count": doc["word_count"],
                "file_path": doc["file_path"],
                "sections_extracted": doc["sections_extracted"],
                "sections_stored": doc["sections_stored"],
                "sections_duplicates": doc["sections_duplicates"],
                "created_at": doc["created_at"],
            },
            "total_chunks": total_chunks,
            "sample_chunks": chunks,
            "note": "chunk_text truncated to 500 chars. Full text stored in Snowflake."
        }

        out_path = out_dir / f"sample_document_{idx}.json"
        out_path.write_text(
            json.dumps(sample, indent=2, default=json_serial),
            encoding="utf-8"
        )
        print(f"  {out_path} — {doc['ticker']} {doc['filing_type']} ({doc['word_count']:,} words, {total_chunks} chunks)")


def export_signal_summaries(cur, db, schema, out_dir):
    """Export signal summary JSON for each company"""

    print("\n=== Exporting Signal Summaries ===\n")

    cur.execute(f"""
        SELECT 
            css.company_id, css.ticker, c.name,
            css.technology_hiring_score,
            css.innovation_activity_score,
            css.digital_presence_score,
            css.leadership_signals_score,
            css.composite_score,
            css.signal_count,
            css.last_updated
        FROM {db}.{schema}.company_signal_summaries css
        JOIN {db}.{schema}.companies c ON css.company_id = c.id
        ORDER BY css.composite_score DESC
    """)

    # Store all rows with column names BEFORE cursor gets reused
    summary_cols = [desc[0] for desc in cur.description]
    summary_rows = cur.fetchall()

    for row in summary_rows:
        summary = row_to_dict_upper(row, summary_cols)
        ticker = summary["TICKER"]
        company_id = summary["COMPANY_ID"]

        # Fetch latest signal per category
        cur.execute(f"""
            SELECT 
                es.id, es.category, es.source,
                es.normalized_score, es.confidence,
                es.raw_value, es.signal_date, es.created_at
            FROM {db}.{schema}.external_signals es
            WHERE es.company_id = %s
            AND (es.category, es.created_at) IN (
                SELECT category, MAX(created_at)
                FROM {db}.{schema}.external_signals
                WHERE company_id = %s
                GROUP BY category
            )
            ORDER BY es.normalized_score DESC
        """, (str(company_id), str(company_id)))

        signals = []
        for sr in cur.fetchall():
            signals.append(row_to_dict(sr, cur))

        output = {
            "company": {
                "company_id": summary["COMPANY_ID"],
                "ticker": ticker,
                "name": summary["NAME"],
            },
            "signal_summary": {
                "technology_hiring_score": float(summary["TECHNOLOGY_HIRING_SCORE"] or 0),
                "innovation_activity_score": float(summary["INNOVATION_ACTIVITY_SCORE"] or 0),
                "digital_presence_score": float(summary["DIGITAL_PRESENCE_SCORE"] or 0),
                "leadership_signals_score": float(summary["LEADERSHIP_SIGNALS_SCORE"] or 0),
                "composite_score": float(summary["COMPOSITE_SCORE"] or 0),
                "signal_count": summary["SIGNAL_COUNT"],
                "last_updated": summary["LAST_UPDATED"],
                "weights": {
                    "technology_hiring": 0.30,
                    "innovation_activity": 0.25,
                    "digital_presence": 0.25,
                    "leadership_signals": 0.20,
                }
            },
            "latest_signals": signals
        }

        out_path = out_dir / f"signal_summary_{ticker}.json"
        out_path.write_text(
            json.dumps(output, indent=2, default=json_serial),
            encoding="utf-8"
        )
        print(f"  {out_path} — composite: {float(summary['COMPOSITE_SCORE'] or 0):.1f}, signals: {summary['SIGNAL_COUNT']}")


def main():
    settings = get_settings()
    db = settings.SNOWFLAKE_DATABASE
    schema = settings.SNOWFLAKE_SCHEMA

    conn = get_connection()
    cur = conn.cursor()

    out_dir = Path("data/samples")
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        export_sample_documents(cur, db, schema, out_dir)
        export_signal_summaries(cur, db, schema, out_dir)

        # Print final file listing
        print("\n=== Files Generated ===\n")
        for f in sorted(out_dir.glob("*.json")):
            size = f.stat().st_size
            print(f"  {f} ({size:,} bytes)")

        print(f"\nTotal files: {len(list(out_dir.glob('*.json')))}")
        print("Done.\n")

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()