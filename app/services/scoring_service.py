"""
app/services/scoring_service.py

Service layer that orchestrates company-wise scoring.
Fetches data from Snowflake and runs Evidence Mapper per company.
"""

import structlog
from uuid import UUID
from decimal import Decimal
from typing import Dict, List, Optional, Any

from app.scoring.evidence_mapper import (
    EvidenceMapper,
    EvidenceScore,
    SignalSource,
    Dimension,
    DimensionScore,
)
from app.services.snowflake import get_connection
from app.config import get_settings

logger = structlog.get_logger()


class ScoringService:
    """
    Service for calculating dimension scores per company.
    
    This is the main entrypoint for Phase 3 PATH A scoring.
    """
    
    def __init__(self):
        self.mapper = EvidenceMapper()
        self.settings = get_settings()
    
    def score_company(
        self, 
        company_id: UUID,
        include_audit_trail: bool = False
    ) -> Dict[str, Any]:
        """
        Calculate dimension scores for a specific company.
        
        Args:
            company_id: UUID of the company to score
            include_audit_trail: If True, include detailed calculation breakdown
        
        Returns:
            {
                "company_id": str,
                "ticker": str,
                "dimension_scores": {...},
                "metadata": {...},
                "audit_trail": {...}  # if requested
            }
        """
        logger.info("scoring_company_started", company_id=str(company_id))
        
        # Step 1: Fetch company info
        company_info = self._get_company_info(company_id)
        if not company_info:
            raise ValueError(f"Company {company_id} not found")
        
        # Step 2: Fetch external signals from Snowflake
        evidence_scores = self._fetch_external_signals(company_id)
        
        if not evidence_scores:
            logger.warning(
                "no_signals_found",
                company_id=str(company_id),
                ticker=company_info["ticker"]
            )
            # Return default scores
            return self._create_default_response(company_info)
        
        # Step 3: Run Evidence Mapper (PATH A)
        dimension_scores = self.mapper.map_evidence_to_dimensions(evidence_scores)
        
        # Step 4: Build response
        response = {
            "company_id": str(company_id),
            "ticker": company_info["ticker"],
            "company_name": company_info["name"],
            "dimension_scores": self._format_dimension_scores(dimension_scores),
            "metadata": {
                "signal_count": len(evidence_scores),
                "signal_sources": [e.source.value for e in evidence_scores],
                "scoring_method": "path_a_quantitative",
                "path_b_included": False,  # Not implemented yet
            }
        }
        
        if include_audit_trail:
            response["audit_trail"] = {
                "raw_signals": self._format_evidence_scores(evidence_scores),
                "explanations": self.mapper.explain_calculation(dimension_scores),
                "contribution_breakdown": self._build_contribution_breakdown(dimension_scores)
            }
        
        logger.info(
            "scoring_company_completed",
            company_id=str(company_id),
            ticker=company_info["ticker"],
            dimension_scores={
                d.value: float(s.score) 
                for d, s in dimension_scores.items()
            }
        )
        
        return response
    
    def score_multiple_companies(
        self,
        company_ids: List[UUID]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Score multiple companies in batch.
        
        Returns:
            Dictionary mapping company_id -> scoring result
        """
        results = {}
        
        for company_id in company_ids:
            try:
                result = self.score_company(company_id)
                results[str(company_id)] = result
            except Exception as e:
                logger.error(
                    "company_scoring_failed",
                    company_id=str(company_id),
                    error=str(e)
                )
                results[str(company_id)] = {
                    "error": str(e),
                    "status": "failed"
                }
        
        return results
    
    def compare_companies(
        self,
        company_ids: List[UUID],
        dimensions: Optional[List[Dimension]] = None
    ) -> Dict[str, Any]:
        """
        Score multiple companies and return comparison table.
        
        Args:
            company_ids: List of companies to compare
            dimensions: Specific dimensions to compare (default: all 7)
        
        Returns:
            Comparison table with scores
        """
        if dimensions is None:
            dimensions = list(Dimension)
        
        # Score all companies
        results = self.score_multiple_companies(company_ids)
        
        # Build comparison table
        comparison = {
            "dimensions": [d.value for d in dimensions],
            "companies": {}
        }
        
        for company_id_str, result in results.items():
            if "error" in result:
                continue
            
            ticker = result["ticker"]
            comparison["companies"][ticker] = {
                "company_id": company_id_str,
                "company_name": result["company_name"],
                "scores": {
                    dim.value: result["dimension_scores"][dim.value]["score"]
                    for dim in dimensions
                }
            }
        
        return comparison
    
    # ========================================
    # Private Helper Methods
    # ========================================
    
    def _get_company_info(self, company_id: UUID) -> Optional[Dict[str, str]]:
        """Fetch basic company info from companies table"""
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            query = f"""
            SELECT id, ticker, name
            FROM {self.settings.SNOWFLAKE_DATABASE}.{self.settings.SNOWFLAKE_SCHEMA}.companies
            WHERE id = %s AND is_deleted = FALSE
            """
            cur.execute(query, (str(company_id),))
            row = cur.fetchone()
            
            if not row:
                return None
            
            return {
                "id": row[0],
                "ticker": row[1],
                "name": row[2]
            }
        finally:
            cur.close()
            conn.close()
    
    def _fetch_external_signals(self, company_id: UUID) -> List[EvidenceScore]:
        """
        Fetch external signals from Snowflake for specific company.
        
        This is the KEY method that makes scoring company-specific.
        """
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            query = f"""
            SELECT 
                category,
                normalized_score,
                confidence,
                raw_value,
                metadata,
                signal_date,
                created_at
            FROM {self.settings.SNOWFLAKE_DATABASE}.{self.settings.SNOWFLAKE_SCHEMA}.external_signals
            WHERE company_id = %s
            ORDER BY signal_date DESC, created_at DESC
            """
            
            cur.execute(query, (str(company_id),))
            rows = cur.fetchall()
            
            logger.debug(
                "signals_fetched_from_snowflake",
                company_id=str(company_id),
                row_count=len(rows)
            )
            
            # Convert to EvidenceScore objects
            # Take most recent score per category
            evidence_by_category = {}
            
            for row in rows:
                category = row[0]
                
                if category in evidence_by_category:
                    continue  # Already have most recent
                
                score = row[1]
                confidence = row[2] if row[2] else 0.85
                raw_value = row[3] if row[3] else ""
                metadata = row[4] if row[4] else {}
                
                evidence_by_category[category] = EvidenceScore(
                    source=SignalSource(category),
                    score=Decimal(str(score)),
                    confidence=Decimal(str(confidence)),
                    raw_value=raw_value,
                    metadata=metadata
                )
            
            return list(evidence_by_category.values())
            
        finally:
            cur.close()
            conn.close()
    
    def _format_dimension_scores(
        self,
        dimension_scores: Dict[Dimension, DimensionScore]
    ) -> Dict[str, Dict[str, Any]]:
        """Format dimension scores for API response"""
        return {
            dimension.value: {
                "score": float(score.score),
                "confidence": float(score.confidence),
                "method": score.method,
                "contribution_count": len(score.contributions)
            }
            for dimension, score in dimension_scores.items()
        }
    
    def _format_evidence_scores(
        self,
        evidence_scores: List[EvidenceScore]
    ) -> List[Dict[str, Any]]:
        """Format evidence scores for audit trail"""
        return [
            {
                "source": e.source.value,
                "score": float(e.score),
                "confidence": float(e.confidence),
                "raw_value": e.raw_value,
                "metadata": e.metadata
            }
            for e in evidence_scores
        ]
    
    def _build_contribution_breakdown(
        self,
        dimension_scores: Dict[Dimension, DimensionScore]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Build detailed contribution breakdown for audit trail"""
        breakdown = {}
        
        for dimension, score in dimension_scores.items():
            breakdown[dimension.value] = [
                {
                    "source": contrib.source.value,
                    "weight": float(contrib.weight),
                    "signal_score": float(contrib.signal_score),
                    "weighted_contribution": float(contrib.weighted_contribution)
                }
                for contrib in score.contributions
            ]
        
        return breakdown
    
    def _create_default_response(
        self,
        company_info: Dict[str, str]
    ) -> Dict[str, Any]:
        """Create response with default scores when no signals available"""
        default_scores = {
            dimension.value: {
                "score": 50.0,
                "confidence": 0.5,
                "method": "default_no_signals",
                "contribution_count": 0
            }
            for dimension in Dimension
        }
        
        return {
            "company_id": company_info["id"],
            "ticker": company_info["ticker"],
            "company_name": company_info["name"],
            "dimension_scores": default_scores,
            "metadata": {
                "signal_count": 0,
                "signal_sources": [],
                "scoring_method": "default",
                "warning": "No external signals found for this company"
            }
        }


# ========================================
# Example Usage
# ========================================

def example_score_single_company():
    """Example: Score a single company"""
    service = ScoringService()
    
    # Replace with actual UUID from your database
    company_id = UUID("550e8400-e29b-41d4-a716-446655440000")
    
    result = service.score_company(
        company_id,
        include_audit_trail=True
    )
    
    print(f"\nScoring Result for {result['ticker']}:")
    print("=" * 70)
    for dim_name, dim_data in result["dimension_scores"].items():
        print(f"{dim_name:25s}: {dim_data['score']:6.1f}/100  "
              f"(confidence: {dim_data['confidence']:.2f})")


def example_compare_companies():
    """Example: Compare multiple companies"""
    service = ScoringService()
    
    company_ids = [
        UUID("550e8400-e29b-41d4-a716-446655440000"),  # CAT
        UUID("660e8400-e29b-41d4-a716-446655440001"),  # UNH
        UUID("770e8400-e29b-41d4-a716-446655440002"),  # WMT
    ]
    
    comparison = service.compare_companies(company_ids)
    
    print("\nCompany Comparison:")
    print("=" * 90)
    print(f"{'Dimension':<25s}", end="")
    for ticker in comparison["companies"].keys():
        print(f"{ticker:>12s}", end="")
    print()
    print("-" * 90)
    
    for dim in comparison["dimensions"]:
        print(f"{dim:<25s}", end="")
        for ticker, data in comparison["companies"].items():
            score = data["scores"][dim]
            print(f"{score:>12.1f}", end="")
        print()


if __name__ == "__main__":
    example_score_single_company()
    # example_compare_companies()