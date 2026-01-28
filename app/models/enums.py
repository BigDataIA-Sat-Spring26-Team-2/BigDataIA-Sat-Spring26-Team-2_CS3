from enum import Enum

class AssessmentType(str, Enum):
    SCREENING = "screening"
    DUE_DILIGENCE = "due_diligence"
    QUARTERLY = "quarterly"
    EXIT_PREP = "exit_prep"

class AssessmentStatus(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    SUPERSEDED = "superseded"

class Dimension(str, Enum):
    DATA_INFRASTRUCTURE = "data_infrastructure"
    AI_GOVERNANCE = "ai_governance"
    TECHNOLOGY_STACK = "technology_stack"
    TALENT_SKILLS = "talent_skills"
    LEADERSHIP_VISION = "leadership_vision"
    USE_CASE_PORTFOLIO = "use_case_portfolio"
    CULTURE_CHANGE = "culture_change"
class Sector(str, Enum):
   
    HEALTHCARE = "Healthcare"
    FINANCIAL = "Financial"
    TECHNOLOGY = "Technology"
    ENERGY = "Energy"
    RETAIL = "Retail"
    PROFESSIONAL_SERVICES = "Professional Services"
    MANUFACTURING = "Manufacturing"
