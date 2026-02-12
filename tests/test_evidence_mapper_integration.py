"""
Complete Integration Tests for Company-Wise Scoring

Tests the FULL pipeline:
1. Fetch external signals from Snowflake for specific company
2. Run Evidence Mapper (PATH A)
3. Verify dimension scores
4. Test with multiple real companies from your CSV data
"""

import pytest
from decimal import Decimal
from uuid import UUID
import structlog

from app.scoring.evidence_mapper import (
    EvidenceMapper,
    EvidenceScore,
    SignalSource,
    Dimension,
)
from app.services.snowflake import get_connection
from app.config import get_settings

logger = structlog.get_logger()


# ============================================================
# HELPER: Fetch Real External Signals from Snowflake
# ============================================================

def fetch_external_signals_for_company(company_id: UUID) -> list[EvidenceScore]:
    """
    Fetch external signals from Snowflake for a specific company.
    
    This is the REAL data fetch that happens in production.
    """
    settings = get_settings()
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        query = f"""
        SELECT 
            category,
            normalized_score,
            confidence,
            raw_value,
            metadata
        FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals
        WHERE company_id = %s
        ORDER BY signal_date DESC, created_at DESC
        """
        
        cur.execute(query, (str(company_id),))
        rows = cur.fetchall()
        
        if not rows:
            logger.warning("no_signals_found", company_id=str(company_id))
            return []
        
        # Convert to EvidenceScore objects
        evidence_scores = []
        seen_categories = set()
        
        for row in rows:
            category = row[0]
            
            # Take only the most recent score per category
            if category in seen_categories:
                continue
            seen_categories.add(category)
            
            # ⭐ ADD THIS ERROR HANDLING ⭐
            try:
                signal_source = SignalSource(category)
            except ValueError:
                # Skip unknown signal categories (like 'ai_governance' from CS3)
                logger.warning(
                    "skipping_unknown_signal_category",
                    category=category,
                    company_id=str(company_id)
                )
                continue  # Skip this row and move to next
            
            score = row[1]
            confidence = row[2] if row[2] else 0.85
            raw_value = row[3] if row[3] else ""
            metadata = row[4] if row[4] else {}
            
            evidence_scores.append(EvidenceScore(
                source=signal_source,  # ⭐ Use validated signal_source ⭐
                score=Decimal(str(score)),
                confidence=Decimal(str(confidence)),
                raw_value=raw_value,
                metadata=metadata
            ))
        
        logger.info(
            "signals_fetched",
            company_id=str(company_id),
            signal_count=len(evidence_scores),
            categories=[e.source.value for e in evidence_scores]
        )
        
        return evidence_scores
        
    finally:
        cur.close()
        conn.close()

def get_company_ticker(company_id: UUID) -> str:
    """Get company ticker for logging/display"""
    settings = get_settings()
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        query = f"""
        SELECT ticker, name
        FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies
        WHERE id = %s
        """
        cur.execute(query, (str(company_id),))
        row = cur.fetchone()
        return f"{row[0]} ({row[1]})" if row else "UNKNOWN"
    finally:
        cur.close()
        conn.close()


# ============================================================
# INTEGRATION TESTS: Real Company Data
# ============================================================

class TestCompanyWiseScoring:
    """
    Test Evidence Mapper with REAL company data from Snowflake.
    
    These are integration tests that require:
    - Snowflake connection configured
    - external_signals table populated with data
    - Valid company UUIDs
    """
    
    # TODO: Replace these with actual company UUIDs from your database
    # You can get them by querying: SELECT id, ticker FROM companies WHERE ticker IN ('CAT', 'DE', 'UNH', 'WMT');
    CATERPILLAR_ID = UUID("c1a3b2f4-1111-4a8c-9c01-000000000001")
    DEERE_ID = UUID("9a2026f8-ef68-4624-a940-2e86636036ba")
    UNITEDHEALTH_ID = UUID("31715ac6-8556-4f84-89f5-1de9b847ff19")
    WALMART_ID = UUID("c52e8f9d-09a2-4bbc-8c75-a5d3b6834fcf")
    
    @pytest.mark.integration
    def test_caterpillar_scoring(self):
        """
        Test Caterpillar Inc. (CAT) scoring with real data.
        
        Expected from your CSV:
        - technology_hiring: 53.4
        - leadership_signals: 7.5
        - digital_presence: 0.0
        - innovation_activity: 80.0
        """
        company_id = self.CATERPILLAR_ID
        ticker = get_company_ticker(company_id)
        logger.info("testing_company", ticker=ticker)
        
        # Fetch real signals from Snowflake
        evidence_scores = fetch_external_signals_for_company(company_id)
        
        # Should have 4 external signals
        assert len(evidence_scores) > 0, "No signals found for Caterpillar"
        
        # Run Evidence Mapper
        mapper = EvidenceMapper()
        dimension_scores = mapper.map_evidence_to_dimensions(evidence_scores)
        
        # Should return all 7 dimensions
        assert len(dimension_scores) == 7
        
        # Print results for inspection
        print(f"\n{'='*70}")
        print(f"DIMENSION SCORES FOR {ticker}")
        print(f"{'='*70}")
        for dimension, score in dimension_scores.items():
            print(f"{dimension.value:25s}: {score.score:6.1f}/100  "
                  f"(confidence: {score.confidence:.2f}, method: {score.method})")
        
        # Validate expected patterns from CSV data
        talent = dimension_scores[Dimension.TALENT]
        tech_stack = dimension_scores[Dimension.TECHNOLOGY_STACK]
        
        # Talent should be close to tech_hiring score (70% weight)
        assert 45.0 <= talent.score <= 60.0, \
            f"Talent score {talent.score} outside expected range"
        
        # Tech stack should reflect innovation_activity (50% weight) + others
        assert 45.0 <= tech_stack.score <= 65.0, \
            f"Tech stack score {tech_stack.score} outside expected range"
        
        # All scores should be valid
        for dim, score in dimension_scores.items():
            assert 0 <= score.score <= 100, \
                f"{dim.value} score {score.score} out of bounds"
    
    @pytest.mark.integration
    def test_unitedhealth_scoring(self):
        """
        Test UnitedHealth Group (UNH) scoring.
        
        Expected from your CSV:
        - technology_hiring: 92.9
        - leadership_signals: 64.1 (has Chief AI Scientist!)
        - digital_presence: 22.5
        - innovation_activity: 80.0
        """
        company_id = self.UNITEDHEALTH_ID
        ticker = get_company_ticker(company_id)
        
        evidence_scores = fetch_external_signals_for_company(company_id)
        assert len(evidence_scores) > 0, "No signals found for UnitedHealth"
        
        mapper = EvidenceMapper()
        dimension_scores = mapper.map_evidence_to_dimensions(evidence_scores)
        
        print(f"\n{'='*70}")
        print(f"DIMENSION SCORES FOR {ticker}")
        print(f"{'='*70}")
        for dimension, score in dimension_scores.items():
            print(f"{dimension.value:25s}: {score.score:6.1f}/100  "
                  f"(method: {score.method})")
        
        # UNH should have high talent score (92.9 tech hiring)
        talent = dimension_scores[Dimension.TALENT]
        assert talent.score >= 85.0, \
            f"UNH talent score {talent.score} too low (expected ~92.9)"
        
        # UNH should have better leadership score than CAT (64.1 vs 7.5)
        leadership = dimension_scores[Dimension.LEADERSHIP]
        assert leadership.score >= 50.0, \
            f"UNH leadership score {leadership.score} too low"
    
    @pytest.mark.integration
    def test_walmart_scoring(self):
        """
        Test Walmart Inc. (WMT) scoring.
        
        Expected from your CSV:
        - technology_hiring: 88.7
        - leadership_signals: 26.7
        - digital_presence: 65.0 (4 AI technologies detected!)
        - innovation_activity: 80.0
        """
        company_id = self.WALMART_ID
        ticker = get_company_ticker(company_id)
        
        evidence_scores = fetch_external_signals_for_company(company_id)
        assert len(evidence_scores) > 0, "No signals found for Walmart"
        
        mapper = EvidenceMapper()
        dimension_scores = mapper.map_evidence_to_dimensions(evidence_scores)
        
        print(f"\n{'='*70}")
        print(f"DIMENSION SCORES FOR {ticker}")
        print(f"{'='*70}")
        for dimension, score in dimension_scores.items():
            print(f"{dimension.value:25s}: {score.score:6.1f}/100")
        
        # Walmart should have high data infrastructure (digital_presence = 65.0 with 60% weight)
        data_infra = dimension_scores[Dimension.DATA_INFRASTRUCTURE]
        assert data_infra.score >= 55.0, \
            f"WMT data infrastructure {data_infra.score} too low (has 65.0 digital presence)"
        
        # Should have high talent
        talent = dimension_scores[Dimension.TALENT]
        assert talent.score >= 80.0
    
    @pytest.mark.integration
    def test_compare_multiple_companies(self):
        """
        Compare scores across multiple companies to verify they're different.
        
        This ensures we're actually scoring per-company, not using cached/shared data.
        """
        companies = [
            ("CAT", self.CATERPILLAR_ID),
            ("DE", self.DEERE_ID),
            ("UNH", self.UNITEDHEALTH_ID),
            ("WMT", self.WALMART_ID),
        ]
        
        all_scores = {}
        mapper = EvidenceMapper()
        
        for ticker, company_id in companies:
            evidence = fetch_external_signals_for_company(company_id)
            if not evidence:
                pytest.skip(f"No data for {ticker}")
            
            dimensions = mapper.map_evidence_to_dimensions(evidence)
            all_scores[ticker] = {
                dim.value: float(score.score) 
                for dim, score in dimensions.items()
            }
        
        # Print comparison table
        print(f"\n{'='*90}")
        print(f"COMPANY COMPARISON: Dimension Scores")
        print(f"{'='*90}")
        print(f"{'Dimension':<25s} {'CAT':>8s} {'DE':>8s} {'UNH':>8s} {'WMT':>8s}")
        print(f"{'-'*90}")
        
        for dim in Dimension:
            scores = [all_scores.get(t, {}).get(dim.value, 0) for t in ['CAT', 'DE', 'UNH', 'WMT']]
            print(f"{dim.value:<25s} {scores[0]:>8.1f} {scores[1]:>8.1f} {scores[2]:>8.1f} {scores[3]:>8.1f}")
        
        # Verify scores are different across companies
        talent_scores = [all_scores[t]["talent"] for t in all_scores]
        assert len(set(talent_scores)) > 1, \
            "All companies have same talent score - not scoring per company!"


# ============================================================
# HELPER TEST: Get Actual Company IDs from Database
# ============================================================

class TestDatabaseSetup:
    """Helper tests to get company UUIDs for the integration tests above"""
    
    @pytest.mark.setup
    def test_print_company_ids(self):
        """
        Run this FIRST to get the actual UUIDs for your companies.
        Then update the class constants above.
        """
        settings = get_settings()
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            query = f"""
            SELECT id, ticker, name
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies
            WHERE ticker IN ('CAT', 'DE', 'UNH', 'WMT', 'HCA', 'ADP', 'PAYX', 'TGT', 'JPM', 'GS')
            ORDER BY ticker
            """
            cur.execute(query)
            rows = cur.fetchall()
            
            print("\n" + "="*80)
            print("COMPANY UUIDs - Copy these into test class constants:")
            print("="*80)
            for row in rows:
                company_id, ticker, name = row
                print(f'{ticker:5s}_ID = UUID("{company_id}")  # {name}')
            
            # Also check external signals
            print("\n" + "="*80)
            print("EXTERNAL SIGNALS CHECK:")
            print("="*80)
            for row in rows:
                company_id, ticker, name = row
                cur.execute(f"""
                    SELECT COUNT(*), COUNT(DISTINCT category)
                    FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals
                    WHERE company_id = %s
                """, (str(company_id),))
                count_row = cur.fetchone()
                print(f"{ticker:5s}: {count_row[0]:3d} total signals, {count_row[1]} categories")
        
        finally:
            cur.close()
            conn.close()


# ============================================================
# UNIT TESTS: Mock Data (No Snowflake Required)
# ============================================================

class TestEvidenceMapperUnit:
    """
    Unit tests that don't require Snowflake.
    These use mocked data matching your CSV structure.
    """
    
    def test_caterpillar_with_mock_data(self):
        """Test with mock data matching CAT's actual signals"""
        mapper = EvidenceMapper()
        
        # Mock Caterpillar's signals from CSV
        evidence = [
            EvidenceScore(
                source=SignalSource.TECHNOLOGY_HIRING,
                score=Decimal("53.4"),
                confidence=Decimal("0.95"),
                raw_value="31/79 highly AI-relevant jobs",
                metadata={"ai_jobs": 31, "total_jobs": 79}
            ),
            EvidenceScore(
                source=SignalSource.LEADERSHIP_SIGNALS,
                score=Decimal("7.5"),
                confidence=Decimal("0.55"),
                raw_value="1 executives analyzed (no AI background)",
                metadata={"ai_executives": 0}
            ),
            EvidenceScore(
                source=SignalSource.DIGITAL_PRESENCE,
                score=Decimal("0.0"),
                confidence=Decimal("0.50"),
                raw_value="0 AI technologies detected",
                metadata={"ai_technologies": []}
            ),
            EvidenceScore(
                source=SignalSource.INNOVATION_ACTIVITY,
                score=Decimal("80.0"),
                confidence=Decimal("0.90"),
                raw_value="17 AI patents",
                metadata={"ai_patent_count": 17}
            ),
        ]
        
        result = mapper.map_evidence_to_dimensions(evidence)
        
        # Expected calculations (manually verified):
        # Data Infrastructure = (53.4×0.10 + 80.0×0.20 + 0.0×0.60) / 0.90
        #                     = (5.34 + 16.0 + 0.0) / 0.90 = 23.71
        data_infra = result[Dimension.DATA_INFRASTRUCTURE]
        assert 20.0 <= data_infra.score <= 30.0
        
        # Talent = 53.4 × (0.70/0.70) = 53.4 (only one source)
        talent = result[Dimension.TALENT]
        assert abs(talent.score - Decimal("53.4")) < Decimal("0.1")
        
        # Print for verification
        print("\nMOCK CATERPILLAR SCORES:")
        for dim, score in result.items():
            print(f"  {dim.value}: {score.score:.1f}")


# ============================================================
# RUN INSTRUCTIONS
# ============================================================

if __name__ == "__main__":
    print("""
    TEST EXECUTION INSTRUCTIONS:
    ============================
    
    Step 1: Get Company UUIDs
    -------------------------
    pytest tests/test_evidence_mapper_integration.py::TestDatabaseSetup::test_print_company_ids -v -s
    
    This will print the UUIDs. Copy them into the test class constants.
    
    Step 2: Run Unit Tests (No Snowflake Required)
    -----------------------------------------------
    pytest tests/test_evidence_mapper_integration.py::TestEvidenceMapperUnit -v
    
    Step 3: Run Integration Tests (Requires Snowflake)
    ---------------------------------------------------
    pytest tests/test_evidence_mapper_integration.py::TestCompanyWiseScoring -v -s -m integration
    
    Step 4: Compare All Companies
    ------------------------------
    pytest tests/test_evidence_mapper_integration.py::TestCompanyWiseScoring::test_compare_multiple_companies -v -s
    """)