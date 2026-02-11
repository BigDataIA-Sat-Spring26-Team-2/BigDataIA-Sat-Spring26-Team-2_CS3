import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from uuid import UUID  # ← Import UUID class
from datetime import datetime, timezone
from app.services.signal_service import store_signal
from app.models.signal import ExternalSignal, SignalCategory, SignalSource
from app.services.snowflake import get_connection
from app.config import get_settings

def test_simple_insert():
    # Get a real company_id
    settings = get_settings()
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute(f"""
        SELECT id FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies 
        WHERE ticker = 'JPM' AND is_deleted = FALSE
    """)
    row = cur.fetchone()
    
    if not row:
        print("❌ JPM company not found")
        return
    
    company_id = row[0]  # This is a string from Snowflake
    print(f"✅ Found company: {company_id}")
    
    # Create a simple signal with the ACTUAL company_id
    signal = ExternalSignal(
        company_id=UUID(company_id),  # ✅ Convert string to UUID
        category=SignalCategory.LEADERSHIP_SIGNALS,
        source=SignalSource.COMPANY_WEBSITE,
        signal_date=datetime.now(timezone.utc),
        raw_value="Test signal",
        normalized_score=50.0,
        confidence=0.8,
        metadata={"test": True, "executives": 1}
    )
    
    print(f"\n📤 Inserting signal:")
    print(f"   Signal ID: {signal.id}")
    print(f"   Company ID: {signal.company_id}")
    
    # Store it
    result = store_signal(signal)
    
    print(f"\n✅ Store returned successfully")
    print(f"   Signal ID: {result.id}")
    
    # Verify
    cur.execute(f"""
        SELECT id, company_id, category, normalized_score, metadata
        FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals 
        WHERE id = %s
    """, (str(result.id),))
    
    verify = cur.fetchone()
    if verify:
        print(f"\n✅ VERIFIED in database:")
        print(f"   ID: {verify[0]}")
        print(f"   Company ID: {verify[1]}")
        print(f"   Category: {verify[2]}")
        print(f"   Score: {verify[3]}")
        print(f"   Metadata: {verify[4]}")
    else:
        print(f"\n❌ NOT FOUND in database after insert!")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    test_simple_insert()