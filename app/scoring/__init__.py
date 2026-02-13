"""
CS3 Scoring Engine Module

Implements the PE Org-AI-R scoring framework:
- Phase 3 Path A: Evidence Mapper (quantitative) ✅ COMPLETE
- Phase 3 Path B: Rubric Scorer (qualitative) ⚠️ PARTIAL
- Phase 4: Score combination ⏭️ TODO
- Phase 5: VR Calculator ✅ COMPLETE
"""

from app.scoring.evidence_mapper import (
    EvidenceMapper,
    Dimension,
    SignalSource,
    EvidenceScore,
    DimensionScore,
    DimensionMapping,
    SignalContribution,
)

from app.scoring.vr_calculator import (
    VRCalculator,
    VRResult,
)

from app.scoring.talent_concentration import (
    TalentConcentrationCalculator,
    JobAnalysis,
)

# Import utils module
from app.scoring import utils

__all__ = [
    # Evidence Mapper (Path A)
    "EvidenceMapper",
    "Dimension",
    "SignalSource",
    "EvidenceScore",
    "DimensionScore",
    "DimensionMapping",
    "SignalContribution",
    
    # VR Calculator (Phase 5)
    "VRCalculator",
    "VRResult",
    
    # Talent Concentration (Task 5.0e)
    "TalentConcentrationCalculator",
    "JobAnalysis",
    
    # Utils (Task 5.1)
    "utils",
]