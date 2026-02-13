"""
app/services/scoring_service.py

Service layer that orchestrates company-wise scoring.
Fetches data from Snowflake and runs Evidence Mapper per company.
"""

import structlog
from uuid import UUID
from decimal import Decimal
from typing import Dict, List, Optional, Any

from app.scoring.vr_calculator import VRCalculator, VRResult
from app.scoring.talent_concentration import TalentConcentrationCalculator, JobAnalysis
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
    
    Supports:
    - Phase 3 PATH A: Evidence Mapper (dimension scoring)
    - Phase 5: V^R Calculator (venture readiness)
    """
    
    def __init__(self):
        self.mapper = EvidenceMapper()
        self.vr_calculator = VRCalculator()
        self.tc_calculator = TalentConcentrationCalculator()
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
                "path_b_included": False,
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
    
    def calculate_vr(
        self,
        company_id: UUID,
        include_audit_trail: bool = False
    ) -> Dict[str, Any]:
        """
        Calculate V^R (Venture Readiness) score for a company.
        
        Pipeline:
        1. Get 7 dimension scores (from Evidence Mapper - Path A)
        2. Calculate Talent Concentration from job metadata  
        3. Get company sector
        4. Run V^R calculator
        
        Args:
            company_id: UUID of company
            include_audit_trail: Include calculation details
        
        Returns:
            Dict with vr_score and components
        
        Raises:
            ValueError: Missing required data
        """
        logger.info("vr_calculation_started", company_id=str(company_id))
        
        # Step 1: Get company info
        company_info = self._get_company_info(company_id)
        if not company_info:
            raise ValueError(f"Company {company_id} not found in database")
        
        logger.debug("company_info_fetched", ticker=company_info["ticker"])
        
        # Step 2: Get dimension scores
        dimension_result = self.score_company(company_id, include_audit_trail=False)
        
        # Step 3: Extract dimension scores (handle the dict format from _format_dimension_scores)
        dimension_scores = {}
        for dim_name, dim_data in dimension_result["dimension_scores"].items():
            # dim_data is {"score": 53.4, "confidence": 0.95, "method": "weighted_average", ...}
            dimension_scores[dim_name] = float(dim_data["score"])
        
        logger.debug("dimension_scores_extracted", scores=dimension_scores)
        
        # Step 4: Calculate TC
        tc = self._calculate_talent_concentration(company_id)
        logger.debug("tc_calculated", tc=tc)
        
        # Step 5: Get sector
        sector = self._get_company_sector(company_id)
        logger.debug("sector_fetched", sector=sector)
        
        # Step 6: Calculate V^R
        vr_result = self.vr_calculator.calculate(
            dimension_scores=dimension_scores,
            talent_concentration=tc,
            sector=sector
        )
        
        # Step 7: Build response
        response = {
            "company_id": str(company_id),
            "ticker": company_info["ticker"],
            "company_name": company_info["name"],
            "vr_score": float(vr_result.vr_score),
            "vr_components": {
                "base_score": float(vr_result.weighted_mean),
                "cv": float(vr_result.cv),
                "cv_penalty": float(vr_result.cv_penalty),
                "cv_penalty_amount": float(vr_result.cv_penalty_amount),
                "talent_concentration": float(vr_result.talent_concentration),
                "talent_risk_adj": float(vr_result.talent_risk_adj),
                "tc_penalty_amount": float(vr_result.tc_penalty_amount),
            },
            "dimension_scores": dimension_scores,
            "sector": sector,
            "metadata": {
                "scoring_method": "path_a_quantitative",
                "path_b_included": False,
                "dimension_source": "evidence_mapper"
            }
        }
        
        if include_audit_trail:
            response["audit_trail"] = {
                "vr_summary": vr_result.get_summary(),
                "dimension_weights": {
                    k: float(v) for k, v in vr_result.dimension_weights.items()
                },
                "calculation_steps": {
                    "step_1_weighted_mean": float(vr_result.weighted_mean),
                    "step_2_cv_calculation": {
                        "cv": float(vr_result.cv),
                        "cv_penalty": float(vr_result.cv_penalty),
                        "points_lost": float(vr_result.cv_penalty_amount)
                    },
                    "step_3_tc_calculation": {
                        "tc": float(vr_result.talent_concentration),
                        "tc_adjustment": float(vr_result.talent_risk_adj),
                        "points_lost": float(vr_result.tc_penalty_amount)
                    },
                    "step_4_final_vr": float(vr_result.vr_score)
                }
            }
        
        logger.info(
            "vr_calculation_completed",
            company_id=str(company_id),
            ticker=company_info["ticker"],
            vr_score=float(vr_result.vr_score)
        )
        
        return response
    
    def score_multiple_companies(
        self,
        company_ids: List[UUID]
    ) -> Dict[str, Dict[str, Any]]:
        """Score multiple companies in batch."""
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
        """Score multiple companies and return comparison table."""
        if dimensions is None:
            dimensions = list(Dimension)
        
        results = self.score_multiple_companies(company_ids)
        
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
        
        ⭐ KEY FIX: Only fetches CS2 signals (filters out ai_governance, etc.)
        """
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            # ⭐ CRITICAL FIX: Filter to only CS2 signal categories
            query = f"""
            SELECT 
                category,
                normalized_score,
                confidence,
                raw_value,
                metadata
            FROM {self.settings.SNOWFLAKE_DATABASE}.{self.settings.SNOWFLAKE_SCHEMA}.external_signals
            WHERE company_id = %s
              AND category IN ('technology_hiring', 'innovation_activity', 'digital_presence', 'leadership_signals')
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
            evidence_by_category = {}
            
            for row in rows:
                category = row[0]
                
                if category in evidence_by_category:
                    continue  # Already have most recent
                
                score = row[1]
                confidence = row[2] if row[2] else 0.85
                raw_value = row[3] if row[3] else ""
                metadata = row[4] if row[4] else {}
                
                # Now safe - category is guaranteed to be in SignalSource enum
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
    


    def _fetch_external_signals(self, company_id: UUID) -> List[EvidenceScore]:
        """
        Fetch external signals from Snowflake for specific company.
        
        Only processes signals that exist in SignalSource enum.
        Skips unknown categories with warning log.
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
                metadata
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
            evidence_by_category = {}
            skipped_categories = []
            
            for row in rows:
                category = row[0]
                
                # Skip if already have this category
                if category in evidence_by_category:
                    continue
                
                # ⭐ TRY to convert category to SignalSource enum
                try:
                    signal_source = SignalSource(category)
                except ValueError:
                    # Category not in enum - skip it
                    skipped_categories.append(category)
                    logger.warning(
                        "skipping_unknown_signal_category",
                        category=category,
                        company_id=str(company_id)
                    )
                    continue
                
                score = row[1]
                confidence = row[2] if row[2] else 0.85
                raw_value = row[3] if row[3] else ""
                metadata = row[4] if row[4] else {}
                
                # Now safe - signal_source is validated
                evidence_by_category[category] = EvidenceScore(
                    source=signal_source,  # Use validated enum value
                    score=Decimal(str(score)),
                    confidence=Decimal(str(confidence)),
                    raw_value=raw_value,
                    metadata=metadata
                )
            
            if skipped_categories:
                logger.info(
                    "skipped_categories_summary",
                    company_id=str(company_id),
                    skipped=skipped_categories,
                    reason="not_in_cs2_signal_enum"
                )
            
            return list(evidence_by_category.values())
            
        finally:
            cur.close()
            conn.close()

    def _calculate_talent_concentration(self, company_id: UUID) -> float:
        """
        Calculate TC using YOUR existing TalentConcentrationCalculator.
        
        Raises:
            ValueError: If no job metadata found
        """
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            query = f"""
            SELECT metadata
            FROM {self.settings.SNOWFLAKE_DATABASE}.{self.settings.SNOWFLAKE_SCHEMA}.external_signals
            WHERE company_id = %s
            AND category = 'technology_hiring'
            ORDER BY created_at DESC
            LIMIT 1
            """
            
            cur.execute(query, (str(company_id),))
            row = cur.fetchone()
            
            if not row or not row[0]:
                raise ValueError(
                    f"No technology_hiring metadata found for company {company_id}. "
                    f"TC calculation requires job posting data."
                )
            
            # ⭐ THE FIX: Parse JSON string to dict
            metadata_raw = row[0]
            
            if isinstance(metadata_raw, str):
                # It's a JSON string - parse it!
                metadata = json.loads(metadata_raw)
            elif isinstance(metadata_raw, dict):
                # Already a dict - use as-is
                metadata = metadata_raw
            else:
                raise ValueError(
                    f"Unexpected metadata type: {type(metadata_raw)}. "
                    f"Expected JSON string or dict."
                )
            
            # Now metadata is definitely a dict
            total_jobs = metadata.get("ai_jobs", 0)
            seniority_dist = metadata.get("seniority_distribution", {})
            skills_found = metadata.get("skills_found", [])
            
            if total_jobs == 0:
                raise ValueError(
                    f"No AI jobs found in metadata for company {company_id}."
                )
            
            # Build JobAnalysis for YOUR calculator
            job_analysis = JobAnalysis(
                total_ai_jobs=total_jobs,
                senior_ai_jobs=(
                    seniority_dist.get("senior", 0) + 
                    seniority_dist.get("executive", 0) + 
                    seniority_dist.get("principal", 0)
                ),
                mid_ai_jobs=seniority_dist.get("mid", 0),
                entry_ai_jobs=seniority_dist.get("entry", 0),
                unique_skills=set(skills_found) if skills_found else set()
            )
            
            logger.debug(
                "job_analysis_built",
                company_id=str(company_id),
                total_jobs=job_analysis.total_ai_jobs,
                senior_jobs=job_analysis.senior_ai_jobs,
                skill_count=len(job_analysis.unique_skills)
            )
            
            # Use YOUR existing calculator
            tc_result = self.tc_calculator.calculate_tc(
                job_analysis=job_analysis,
                glassdoor_individual_mentions=0,
                glassdoor_review_count=1
            )
            
            tc_float = float(tc_result)
            
            logger.info(
                "talent_concentration_calculated",
                company_id=str(company_id),
                tc=tc_float,
                components={
                    "leadership_ratio": job_analysis.senior_ai_jobs / job_analysis.total_ai_jobs if job_analysis.total_ai_jobs > 0 else 0,
                    "total_jobs": job_analysis.total_ai_jobs,
                    "unique_skills": len(job_analysis.unique_skills)
                }
            )
            
            return tc_float
            
        finally:
            cur.close()
            conn.close()

    
    def _get_company_sector(self, company_id: UUID) -> str:
        """
        Get company sector from companies table.
        
        Raises:
            ValueError: If company not found or sector is NULL
        """
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            query = f"""
            SELECT sector
            FROM {self.settings.SNOWFLAKE_DATABASE}.{self.settings.SNOWFLAKE_SCHEMA}.companies
            WHERE id = %s AND is_deleted = FALSE
            """
            cur.execute(query, (str(company_id),))
            row = cur.fetchone()
            
            if not row:
                raise ValueError(
                    f"Company {company_id} not found in database."
                )
            
            if not row[0]:
                raise ValueError(
                    f"Company {company_id} has NULL sector. "
                    f"Update companies table with valid sector."
                )
            
            sector = row[0]
            
            logger.debug("company_sector_fetched", company_id=str(company_id), sector=sector)
            
            return sector
            
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
                    "weighted_contribution": float(contrib.weighted_contribution),
                    "is_primary": contrib.is_primary
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