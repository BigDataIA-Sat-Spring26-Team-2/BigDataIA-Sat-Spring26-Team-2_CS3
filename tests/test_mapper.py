from decimal import Decimal
from app.scoring.evidence_mapper import EvidenceMapper

# Get JPM's company_id
from app.services.snowflake import get_connection
from app.config import get_settings

settings = get_settings()
conn = get_connection()
cur = conn.cursor()

cur.execute(f"""
    SELECT id FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies
    WHERE ticker = 'JPM' AND is_deleted = FALSE
""")
row = cur.fetchone()
company_id = row[0]

cur.close()
conn.close()

mapper = EvidenceMapper()
dimension_scores = mapper.fetch_and_map_company_evidence(company_id)


print("\n" + "="*70)
print("REAL JPM DIMENSION SCORES (from Snowflake)")
print("="*70 + "\n")

for dim, score_obj in dimension_scores.items():
    print(f"{dim.value:25} | Score: {score_obj.score:6.2f} | "
          f"Sources: {len(score_obj.contributing_sources)} | "
          f"Confidence: {score_obj.confidence:.2f}")

# Coverage report (ONLY ONE - simplified)
print("\n" + "="*70)
print("EVIDENCE COVERAGE")
print("="*70 + "\n")

for dim, score_obj in dimension_scores.items():
    status = "correct" if len(score_obj.contributing_sources) > 0 else "wrong"
    sources = [s.value for s in score_obj.contributing_sources]
    print(f"{status} {dim.value:25} | Sources: {len(sources)} | {sources}")