"""
CS3 Scoring Engine Module

Implements the PE Org-AI-R scoring framework:
- Phase 3 Path A: Evidence Mapper (quantitative)
- Phase 3 Path B: Rubric Scorer (qualitative)  
- Phase 4: Score combination
- Phase 5: VR Calculator
"""

from app.scoring.evidence_mapper import (
    EvidenceMapper,
    Dimension,
    SignalSource,
    EvidenceScore,
    DimensionScore,
)

# Only import what exists
__all__ = [
    "EvidenceMapper",
    "Dimension",
    "SignalSource",
    "EvidenceScore",
    "DimensionScore",
]

# Future imports (uncomment when these files are created):
# from app.scoring.rubric_scorer import RubricScorer
# from app.scoring.talent_concentration import TalentConcentrationCalculator
# from app.scoring.vr_calculator import VRCalculator