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

class DocumentStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADED = "downloaded"
    PARSED = "parsed"
    CHUNKED = "chunked"
    INDEXED = "indexed"
    FAILED = "failed"

class SignalCategory(str, Enum):
    TECHNOLOGY_HIRING = "technology_hiring"
    INNOVATION_ACTIVITY = "innovation_activity"
    DIGITAL_PRESENCE = "digital_presence"
    LEADERSHIP_SIGNALS = "leadership_signals"
    AI_GOVERNANCE = "ai_governance"
    USE_CASE_PORTFOLIO = "use_case_portfolio"
    CULTURE = "culture"



class SignalSource(str, Enum):
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    GLASSDOOR = "glassdoor"
    COMPANY_WEBSITE = "company_website"
    MULTIPLE = "LinkedIn_Indeed"
    TECH_STACK_SCRAPE="tech_stack_scrape"
    GOOGLE_PATENTS = "google_patents"
    SEC_ITEM_1_BUSINESS = "sec_item_1_business"
    SEC_ITEM_1A_RISK = "sec_item_1a_risk_factors"
    SEC_ITEM_7_MDA = "sec_item_7_mda"
    BOARD_COMPOSITION = "board_composition" 
