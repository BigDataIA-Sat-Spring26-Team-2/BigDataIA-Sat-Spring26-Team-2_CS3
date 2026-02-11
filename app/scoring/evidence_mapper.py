from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from decimal import Decimal


class Dimension(str, Enum):

    DATA_INFRASTRUCTURE = "data_infrastructure"
    AI_GOVERNANCE = "ai_governance"
    TECHNOLOGY_STACK = "technology_stack"
    TALENT = "talent"
    LEADERSHIP = "leadership"
    USE_CASE_PORTFOLIO = "use_case_portfolio"
    CULTURE = "culture"


class SignalSource(str, Enum):

    TECHNOLOGY_HIRING = "technology_hiring"
    INNOVATION_ACTIVITY = "innovation_activity"
    DIGITAL_PRESENCE = "digital_presence"
    LEADERSHIP_SIGNALS = "leadership_signals"
    
    SEC_ITEM_1 = "sec_item_1_business"
    SEC_ITEM_1A = "sec_item_1a_risk_factors"
    SEC_ITEM_7 = "sec_item_7_mda"
    
    GLASSDOOR_REVIEWS = "glassdoor_reviews"
    BOARD_COMPOSITION = "board_composition"


@dataclass
class DimensionMapping:
    source: SignalSource
    primary_dimension: Dimension
    primary_weight: Decimal
    secondary_mappings: Dict[Dimension, Decimal] = field(default_factory=dict)
    reliability: Decimal = Decimal("0.8")


@dataclass
class EvidenceScore:
    source: SignalSource
    raw_score: Decimal  # 0-100
    confidence: Decimal  # 0-1
    evidence_count: int
    metadata: Dict = field(default_factory=dict)


@dataclass
class DimensionScore:
    dimension: Dimension
    score: Decimal
    contributing_sources: List[SignalSource]
    total_weight: Decimal
    confidence: Decimal


SIGNAL_TO_DIMENSION_MAP: Dict[SignalSource, DimensionMapping] = {
    
  
    
    SignalSource.TECHNOLOGY_HIRING: DimensionMapping(
        source=SignalSource.TECHNOLOGY_HIRING,
        primary_dimension=Dimension.TALENT,
        primary_weight=Decimal("0.70"),
        secondary_mappings={
            Dimension.TECHNOLOGY_STACK: Decimal("0.20"),
            Dimension.DATA_INFRASTRUCTURE: Decimal("0.10"),
           
        },
        reliability=Decimal("0.85"),
    ),
    

    SignalSource.INNOVATION_ACTIVITY: DimensionMapping(
        source=SignalSource.INNOVATION_ACTIVITY,
        primary_dimension=Dimension.TECHNOLOGY_STACK,
        primary_weight=Decimal("0.50"),
        secondary_mappings={
            Dimension.USE_CASE_PORTFOLIO: Decimal("0.30"),
            Dimension.DATA_INFRASTRUCTURE: Decimal("0.20"),
        },
        reliability=Decimal("0.80"),
    ),
        SignalSource.DIGITAL_PRESENCE: DimensionMapping(
        source=SignalSource.DIGITAL_PRESENCE,
        primary_dimension=Dimension.DATA_INFRASTRUCTURE,
        primary_weight=Decimal("0.60"),
        secondary_mappings={
            Dimension.TECHNOLOGY_STACK: Decimal("0.40"),
        },
        reliability=Decimal("0.75"),
    ),
     SignalSource.LEADERSHIP_SIGNALS: DimensionMapping(
        source=SignalSource.LEADERSHIP_SIGNALS,
        primary_dimension=Dimension.LEADERSHIP,
        primary_weight=Decimal("0.60"),
        secondary_mappings={
            Dimension.AI_GOVERNANCE: Decimal("0.25"),
            Dimension.CULTURE: Decimal("0.15"),
        },
        reliability=Decimal("0.85"),
    ),
    
       SignalSource.SEC_ITEM_1: DimensionMapping(
        source=SignalSource.SEC_ITEM_1,
        primary_dimension=Dimension.USE_CASE_PORTFOLIO,
        primary_weight=Decimal("0.70"),
        secondary_mappings={
            Dimension.TECHNOLOGY_STACK: Decimal("0.30"),
        },
        reliability=Decimal("0.90"),
    ),

    SignalSource.SEC_ITEM_1A: DimensionMapping(
        source=SignalSource.SEC_ITEM_1A,
        primary_dimension=Dimension.AI_GOVERNANCE,
        primary_weight=Decimal("0.80"),
        secondary_mappings={
            Dimension.DATA_INFRASTRUCTURE: Decimal("0.20"),
        },
        reliability=Decimal("0.90"),
    ),
    SignalSource.SEC_ITEM_7: DimensionMapping(
        source=SignalSource.SEC_ITEM_7,
        primary_dimension=Dimension.LEADERSHIP,
        primary_weight=Decimal("0.50"),
        secondary_mappings={
            Dimension.USE_CASE_PORTFOLIO: Decimal("0.30"),
            Dimension.DATA_INFRASTRUCTURE: Decimal("0.20"),
        },
        reliability=Decimal("0.85"),
    ),

    SignalSource.GLASSDOOR_REVIEWS: DimensionMapping(
        source=SignalSource.GLASSDOOR_REVIEWS,
        primary_dimension=Dimension.CULTURE,
        primary_weight=Decimal("0.80"),
        secondary_mappings={
            Dimension.TALENT: Decimal("0.10"),
            Dimension.LEADERSHIP: Decimal("0.10"),
        },
        reliability=Decimal("0.70"),
    ),
    
    # Row 9: Board composition [NEW]
    SignalSource.BOARD_COMPOSITION: DimensionMapping(
        source=SignalSource.BOARD_COMPOSITION,
        primary_dimension=Dimension.AI_GOVERNANCE,
        primary_weight=Decimal("0.70"),
        secondary_mappings={
            Dimension.LEADERSHIP: Decimal("0.30"),
        },
        reliability=Decimal("0.85"),
    ),
}
class EvidenceMapper:
    """Maps CS2 evidence to 7 VR dimensions."""
    
    def __init__(self):
        self.mappings = SIGNAL_TO_DIMENSION_MAP
    
    def map_evidence_to_dimensions(
        self,
        evidence_scores: List[EvidenceScore],
    ) -> Dict[Dimension, DimensionScore]:
        """
        Convert CS2 evidence scores to 7 dimension scores.
        
        Algorithm:
        1. Initialize accumulators for each dimension
        2. For each evidence source:
           a. Look up its mapping
           b. Add weighted contribution to primary dimension
           c. Add weighted contributions to secondary dimensions
        3. Calculate weighted average for each dimension
        4. Dimensions with NO evidence default to 50.0
        
        Args:
            evidence_scores: List of scores from CS2 + CS3 sources
            
        Returns:
            Dict mapping each Dimension to its aggregated score
        """
        
        # STEP 1: Initialize accumulators for all 7 dimensions
        dimension_sums: Dict[Dimension, Decimal] = {d: Decimal(0) for d in Dimension}
        dimension_weights: Dict[Dimension, Decimal] = {d: Decimal(0) for d in Dimension}
        dimension_sources: Dict[Dimension, List[SignalSource]] = {d: [] for d in Dimension}
        
        # STEP 2: Process each evidence score
        for ev in evidence_scores:
            # Look up mapping for this source
            mapping = self.mappings.get(ev.source)
            if not mapping:
                continue  # Skip unknown sources
            
            # Weight the score by confidence and reliability
            effective_score = ev.raw_score * ev.confidence * mapping.reliability
            
            # PRIMARY contribution
            primary_dim = mapping.primary_dimension
            primary_weight = mapping.primary_weight
            
            dimension_sums[primary_dim] += effective_score * primary_weight
            dimension_weights[primary_dim] += primary_weight * ev.confidence * mapping.reliability
            
            if ev.source not in dimension_sources[primary_dim]:
                dimension_sources[primary_dim].append(ev.source)
            
            # SECONDARY contributions
            for sec_dim, sec_weight in mapping.secondary_mappings.items():
                dimension_sums[sec_dim] += effective_score * sec_weight
                dimension_weights[sec_dim] += sec_weight * ev.confidence * mapping.reliability
                
                if ev.source not in dimension_sources[sec_dim]:
                    dimension_sources[sec_dim].append(ev.source)
        
        # STEP 3: Calculate final dimension scores
        result: Dict[Dimension, DimensionScore] = {}
        
        for dim in Dimension:
            total_weight = dimension_weights[dim]
            
            if total_weight > 0:
                # Has evidence - calculate weighted average
                final_score = dimension_sums[dim] / total_weight
                
                # Calculate confidence based on number of sources
                num_sources = len(dimension_sources[dim])
                confidence = min(Decimal("0.5") + Decimal(num_sources) / 10, Decimal("0.95"))
                
            else:
                # NO evidence - default to 50.0
                final_score = Decimal("50.0")
                confidence = Decimal("0.5")
            
            # Bound score to [0, 100]
            final_score = max(Decimal(0), min(Decimal(100), final_score))
            
            result[dim] = DimensionScore(
                dimension=dim,
                score=final_score,
                contributing_sources=dimension_sources[dim],
                total_weight=total_weight,
                confidence=confidence,
            )
        
        return result
    def get_coverage_report(
        self,
        evidence_scores: List[EvidenceScore],
    ) -> Dict[Dimension, Dict]:
        """
        Report which dimensions have evidence and which have gaps.
        
        Returns dict with:
        - has_evidence: bool
        - source_count: int
        - total_weight: float
        - confidence: float
        """
        dimension_scores = self.map_evidence_to_dimensions(evidence_scores)
        
        report = {}
        for dim, score_obj in dimension_scores.items():
            report[dim] = {
                "has_evidence": len(score_obj.contributing_sources) > 0,
                "source_count": len(score_obj.contributing_sources),
                "total_weight": float(score_obj.total_weight),
                "confidence": float(score_obj.confidence),
                "score": float(score_obj.score),
                "sources": [s.value for s in score_obj.contributing_sources],
            }
        
        return report
    def fetch_and_map_company_evidence(self, company_id: str) -> Dict[Dimension, DimensionScore]:
        """
        Fetch all evidence for a company from Snowflake and map to dimensions.
        
        Args:
            company_id: Company UUID
            
        Returns:
            Dict of 7 dimension scores
        """
        from app.services.snowflake import get_connection
        from app.config import get_settings
        
        settings = get_settings()
        conn = get_connection()
        cur = conn.cursor()
        
        evidence_scores: List[EvidenceScore] = []
        
        try:
            # Fetch latest signal per category for this company
            query = f"""
            SELECT 
                es.category,
                es.normalized_score,
                es.confidence,
                es.metadata
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals es
            WHERE es.company_id = %s
            AND (es.category, es.created_at) IN (
                SELECT category, MAX(created_at)
                FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals
                WHERE company_id = %s
                GROUP BY category
            )
            """
            
            cur.execute(query, (company_id, company_id))
            rows = cur.fetchall()
            
            # Convert to EvidenceScore objects
            for row in rows:
                category = row[0]  # e.g., "technology_hiring"
                score = float(row[1])
                confidence = float(row[2])
                metadata = row[3] if row[3] else {}
                
                # Map category to SignalSource enum
                source = self._map_category_to_source(category)
                if not source:
                    continue
                
                evidence_scores.append(EvidenceScore(
                    source=source,
                    raw_score=Decimal(str(score)),
                    confidence=Decimal(str(confidence)),
                    evidence_count=metadata.get('signal_count', 1) if isinstance(metadata, dict) else 1,
                    metadata=metadata if isinstance(metadata, dict) else {}
                ))
            
        finally:
            cur.close()
            conn.close()
        
        # Map to dimensions
        return self.map_evidence_to_dimensions(evidence_scores)
    
    def _map_category_to_source(self, category: str) -> Optional[SignalSource]:
      
        mapping = {
            "technology_hiring": SignalSource.TECHNOLOGY_HIRING,
            "innovation_activity": SignalSource.INNOVATION_ACTIVITY,
            "digital_presence": SignalSource.DIGITAL_PRESENCE,
            "leadership_signals": SignalSource.LEADERSHIP_SIGNALS,
            "ai_governance": SignalSource.BOARD_COMPOSITION,
            # Add SEC sections when available:
            # "sec_item_1_business": SignalSource.SEC_ITEM_1,
            # "sec_item_1a_risk_factors": SignalSource.SEC_ITEM_1A,
            # "sec_item_7_mda": SignalSource.SEC_ITEM_7,
        }
        return mapping.get(category)