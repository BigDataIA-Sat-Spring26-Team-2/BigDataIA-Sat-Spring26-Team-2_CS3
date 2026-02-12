"""
Task 5.0a: Evidence-to-Dimension Mapper (PATH A)

Maps 4 external signal scores from Snowflake (CS2 data) into 7 dimension scores
using primary/secondary weight mappings from Table 1.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from decimal import Decimal
import structlog

logger = structlog.get_logger()


class Dimension(str, Enum):
    """7 PE Org-AI-R dimensions"""
    DATA_INFRASTRUCTURE = "data_infrastructure"
    AI_GOVERNANCE = "ai_governance"
    TECHNOLOGY_STACK = "technology_stack"
    TALENT = "talent"
    LEADERSHIP = "leadership"
    USE_CASE_PORTFOLIO = "use_case_portfolio"
    CULTURE = "culture"


class SignalSource(str, Enum):
    """CS2 External Signal Categories"""
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
    """
    Defines how a signal source contributes to dimensions.
    
    Each source has:
    - ONE primary dimension (highest weight, bold in Table 1)
    - Multiple secondary dimensions (supporting contributions)
    """
    source: SignalSource
    primary_dimension: Dimension
    primary_weight: Decimal
    secondary_mappings: Dict[Dimension, Decimal] = field(default_factory=dict)
    reliability: Decimal = Decimal("0.85")  # Signal quality factor


@dataclass
class EvidenceScore:
    """A single signal score with metadata"""
    source: SignalSource
    score: Decimal  # 0-100 (raw_score in old version)
    confidence: Decimal  # 0-1
    raw_value: str = ""
    metadata: Dict = field(default_factory=dict)


@dataclass
class SignalContribution:
    """Documents how a signal contributed to a dimension"""
    source: SignalSource
    weight: Decimal
    signal_score: Decimal
    weighted_contribution: Decimal
    is_primary: bool  # True if this is the primary dimension for this signal


@dataclass
class DimensionScore:
    """Final dimension score with audit trail"""
    dimension: Dimension
    score: Decimal  # 0-100
    confidence: Decimal  # 0-1
    contributions: List[SignalContribution]
    total_weight: Decimal
    method: str  # "weighted_average" or "default"
    
    def get_explanation(self) -> str:
        """Human-readable breakdown"""
        if self.method == "default":
            return f"{self.dimension.value}: No signal data → default score 50.0"
        
        parts = [f"{self.dimension.value} = "]
        for contrib in self.contributions:
            primary_marker = " [PRIMARY]" if contrib.is_primary else ""
            parts.append(
                f"{contrib.source.value}({contrib.signal_score:.1f}) × "
                f"{contrib.weight:.2f}{primary_marker} = {contrib.weighted_contribution:.1f}"
            )
        parts.append(f"→ TOTAL: {self.score:.1f}/100")
        return " + ".join(parts)


class EvidenceMapper:
    """
    Maps CS2 external signals to CS3 dimension scores using primary/secondary weights.
    
    This is PATH A (quantitative) in the Phase 3 scoring architecture.
    """
    
    # Signal-to-Dimension Mappings from Case Study 3 PDF Table 1
    SIGNAL_MAPPINGS: Dict[SignalSource, DimensionMapping] = {
        SignalSource.TECHNOLOGY_HIRING: DimensionMapping(
            source=SignalSource.TECHNOLOGY_HIRING,
            primary_dimension=Dimension.TALENT,  # Bold: 0.70
            primary_weight=Decimal("0.70"),
            secondary_mappings={
                Dimension.TECHNOLOGY_STACK: Decimal("0.20"),
                Dimension.DATA_INFRASTRUCTURE: Decimal("0.10"),
            },
            reliability=Decimal("0.85"),
        ),
        
        SignalSource.INNOVATION_ACTIVITY: DimensionMapping(
            source=SignalSource.INNOVATION_ACTIVITY,
            primary_dimension=Dimension.TECHNOLOGY_STACK,  # Bold: 0.50
            primary_weight=Decimal("0.50"),
            secondary_mappings={
                Dimension.USE_CASE_PORTFOLIO: Decimal("0.30"),
                Dimension.DATA_INFRASTRUCTURE: Decimal("0.20"),
            },
            reliability=Decimal("0.80"),
        ),
        
        SignalSource.DIGITAL_PRESENCE: DimensionMapping(
            source=SignalSource.DIGITAL_PRESENCE,
            primary_dimension=Dimension.DATA_INFRASTRUCTURE,  # Bold: 0.60
            primary_weight=Decimal("0.60"),
            secondary_mappings={
                Dimension.TECHNOLOGY_STACK: Decimal("0.40"),
            },
            reliability=Decimal("0.75"),
        ),
        
        SignalSource.LEADERSHIP_SIGNALS: DimensionMapping(
            source=SignalSource.LEADERSHIP_SIGNALS,
            primary_dimension=Dimension.LEADERSHIP,  # Bold: 0.60
            primary_weight=Decimal("0.60"),
            secondary_mappings={
                Dimension.AI_GOVERNANCE: Decimal("0.25"),
                Dimension.CULTURE: Decimal("0.15"),
            },
            reliability=Decimal("0.85"),
        ),

    SignalSource.SEC_ITEM_1: DimensionMapping(
        source=SignalSource.SEC_ITEM_1,
        primary_dimension=Dimension.USE_CASE_PORTFOLIO,  # Bold: 0.70
        primary_weight=Decimal("0.70"),
        secondary_mappings={
            Dimension.TECHNOLOGY_STACK: Decimal("0.30"),
        },
        reliability=Decimal("0.90"),
    ),
    

    SignalSource.SEC_ITEM_1A: DimensionMapping(
        source=SignalSource.SEC_ITEM_1A,
        primary_dimension=Dimension.AI_GOVERNANCE,  # Bold: 0.80
        primary_weight=Decimal("0.80"),
        secondary_mappings={
            Dimension.DATA_INFRASTRUCTURE: Decimal("0.20"),
        },
        reliability=Decimal("0.90"),
    ),
    
    SignalSource.SEC_ITEM_7: DimensionMapping(
        source=SignalSource.SEC_ITEM_7,
        primary_dimension=Dimension.LEADERSHIP,  # Bold: 0.50
        primary_weight=Decimal("0.50"),
        secondary_mappings={
            Dimension.USE_CASE_PORTFOLIO: Decimal("0.30"),
            Dimension.DATA_INFRASTRUCTURE: Decimal("0.20"),
        },
        reliability=Decimal("0.85"),
    ),
        SignalSource.GLASSDOOR_REVIEWS: DimensionMapping(
        source=SignalSource.GLASSDOOR_REVIEWS,
        primary_dimension=Dimension.CULTURE,  # Bold: 0.80
        primary_weight=Decimal("0.80"),
        secondary_mappings={
            Dimension.TALENT: Decimal("0.10"),
            Dimension.LEADERSHIP: Decimal("0.10"),
        },
        reliability=Decimal("0.70"),
    ),
    
   
    SignalSource.BOARD_COMPOSITION: DimensionMapping(
        source=SignalSource.BOARD_COMPOSITION,
        primary_dimension=Dimension.AI_GOVERNANCE,  # Bold: 0.70
        primary_weight=Decimal("0.70"),
        secondary_mappings={
            Dimension.LEADERSHIP: Decimal("0.30"),
        },
        reliability=Decimal("0.85"),
    ),
    }
    
    DEFAULT_SCORE = Decimal("50.0")
    DEFAULT_CONFIDENCE = Decimal("0.5")
    
    def __init__(self):
        """Initialize the mapper"""
        self._validate_mappings()
    
    def _validate_mappings(self):
        """Verify weights sum to 1.0 for each source"""
        for source, mapping in self.SIGNAL_MAPPINGS.items():
            total = mapping.primary_weight + sum(mapping.secondary_mappings.values())
            if not (Decimal("0.99") <= total <= Decimal("1.01")):
                logger.warning(
                    "mapping_weights_invalid",
                    source=source.value,
                    sum=float(total),
                    expected=1.0
                )
    
    def map_evidence_to_dimensions(
        self,
        evidence_scores: List[EvidenceScore]
    ) -> Dict[Dimension, DimensionScore]:
        """
        Map signal scores to dimension scores using weighted averaging.
        
        Algorithm:
        1. For each dimension, accumulate weighted contributions from signals
        2. Apply reliability and confidence weighting
        3. Calculate final weighted average
        4. Dimensions with no evidence default to 50.0
        """
        logger.info(
            "evidence_mapping_started",
            signal_count=len(evidence_scores),
            sources=[e.source.value for e in evidence_scores]
        )
        
        # Build lookup index
        signals_by_source: Dict[SignalSource, EvidenceScore] = {
            score.source: score for score in evidence_scores
        }
        
        # Calculate each dimension
        dimension_scores = {}
        for dimension in Dimension:
            dim_score = self._calculate_dimension_score(
                dimension,
                signals_by_source
            )
            dimension_scores[dimension] = dim_score
            
            logger.debug(
                "dimension_calculated",
                dimension=dimension.value,
                score=float(dim_score.score),
                method=dim_score.method,
                contribution_count=len(dim_score.contributions)
            )
        
        logger.info(
            "evidence_mapping_completed",
            dimension_scores={
                d.value: float(s.score) 
                for d, s in dimension_scores.items()
            }
        )
        
        return dimension_scores
    
    def _calculate_dimension_score(
        self,
        dimension: Dimension,
        signals_by_source: Dict[SignalSource, EvidenceScore]
    ) -> DimensionScore:
        """
        Calculate dimension score using primary/secondary weighted contributions.
        
        Formula: 
        For each contributing signal:
          effective_score = raw_score × confidence × reliability
          weighted_contribution = effective_score × weight
        
        final_score = Σ(weighted_contributions) / Σ(weights × confidence × reliability)
        """
        contributions = []
        weighted_sum = Decimal("0.0")
        total_weight = Decimal("0.0")
        confidence_sum = Decimal("0.0")
        confidence_weight = Decimal("0.0")
        
        # Check all signal mappings for contributions to this dimension
        for source, mapping in self.SIGNAL_MAPPINGS.items():
            if source not in signals_by_source:
                continue  # Signal not available
            
            evidence = signals_by_source[source]
            
            # Determine if this dimension receives contribution from this signal
            is_primary = (mapping.primary_dimension == dimension)
            weight = None
            
            if is_primary:
                weight = mapping.primary_weight
            elif dimension in mapping.secondary_mappings:
                weight = mapping.secondary_mappings[dimension]
            
            if weight is None:
                continue  # This signal doesn't contribute to this dimension
            
            # Calculate effective score with quality factors
            effective_score = evidence.score * evidence.confidence * mapping.reliability
            effective_weight = weight * evidence.confidence * mapping.reliability
            
            weighted_contribution = effective_score * weight
            
            weighted_sum += weighted_contribution
            total_weight += effective_weight
            
            # Track confidence (weighted by contribution)
            confidence_sum += evidence.confidence * weight
            confidence_weight += weight
            
            contributions.append(SignalContribution(
                source=source,
                weight=weight,
                signal_score=evidence.score,
                weighted_contribution=weighted_contribution,
                is_primary=is_primary
            ))
            
            logger.debug(
                "signal_contribution",
                dimension=dimension.value,
                source=source.value,
                is_primary=is_primary,
                weight=float(weight),
                score=float(evidence.score),
                contribution=float(weighted_contribution)
            )
        
        # Calculate final score
        if not contributions:
            # No evidence for this dimension
            logger.debug(
                "dimension_using_default",
                dimension=dimension.value,
                reason="no_contributing_signals"
            )
            return DimensionScore(
                dimension=dimension,
                score=self.DEFAULT_SCORE,
                confidence=self.DEFAULT_CONFIDENCE,
                contributions=[],
                total_weight=Decimal("0.0"),
                method="default"
            )
        
        # Weighted average
        if total_weight > Decimal("0"):
            final_score = weighted_sum / total_weight
            final_confidence = confidence_sum / confidence_weight if confidence_weight > 0 else self.DEFAULT_CONFIDENCE
        else:
            final_score = self.DEFAULT_SCORE
            final_confidence = self.DEFAULT_CONFIDENCE
        
        # Clamp to [0, 100]
        final_score = max(Decimal("0"), min(Decimal("100"), final_score))
        final_confidence = max(Decimal("0"), min(Decimal("1"), final_confidence))
        
        return DimensionScore(
            dimension=dimension,
            score=final_score,
            confidence=final_confidence,
            contributions=contributions,
            total_weight=total_weight,
            method="weighted_average"
        )
    
    def explain_calculation(
        self,
        dimension_scores: Dict[Dimension, DimensionScore]
    ) -> Dict[str, str]:
        """Generate human-readable explanations"""
        explanations = {}
        for dimension, score in dimension_scores.items():
            explanations[dimension.value] = score.get_explanation()
        return explanations


def example_usage():
    """Example usage with mock data"""
    evidence_scores = [
        EvidenceScore(
            source=SignalSource.TECHNOLOGY_HIRING,
            score=Decimal("53.4"),
            confidence=Decimal("0.95"),
            raw_value="31/79 AI jobs",
        ),
        EvidenceScore(
            source=SignalSource.LEADERSHIP_SIGNALS,
            score=Decimal("7.5"),
            confidence=Decimal("0.55"),
            raw_value="1 exec",
        ),
        EvidenceScore(
            source=SignalSource.DIGITAL_PRESENCE,
            score=Decimal("0.0"),
            confidence=Decimal("0.50"),
            raw_value="0 tech",
        ),
        EvidenceScore(
            source=SignalSource.INNOVATION_ACTIVITY,
            score=Decimal("80.0"),
            confidence=Decimal("0.90"),
            raw_value="17 patents",
        ),
    ]
    
    mapper = EvidenceMapper()
    dimension_scores = mapper.map_evidence_to_dimensions(evidence_scores)
    
    print("DIMENSION SCORES (with Primary/Secondary):")
    print("=" * 70)
    for dimension, score in dimension_scores.items():
        print(f"\n{dimension.value.upper()}: {score.score:.1f}/100")
        print(f"  Method: {score.method}")
        if score.contributions:
            print("  Contributions:")
            for contrib in score.contributions:
                primary_tag = " [PRIMARY]" if contrib.is_primary else " [secondary]"
                print(f"    {contrib.source.value}{primary_tag}: "
                      f"{contrib.signal_score:.1f} × {contrib.weight:.2f} "
                      f"= {contrib.weighted_contribution:.1f}")


if __name__ == "__main__":
    example_usage()