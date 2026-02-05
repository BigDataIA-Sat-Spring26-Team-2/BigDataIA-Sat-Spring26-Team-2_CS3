from app.pipelines.collectors.website_collector import CompanyWebsiteCollector
from app.models.leadership import ExecutiveProfile

_detector = CompanyWebsiteCollector()

def get_hardcoded_executives(ticker: str):
    """Hardcoded executives for companies with difficult-to-scrape websites"""
    
    # Define executives by ticker
    executives_data = {
        "UNH": [
            ("Michael Pencina", "Chief AI Scientist"),
            ("Sandeep Dadlani", "CEO, Optum Insight"),
        ],
        
        "GS": [
            ("David Solomon", "Chairman and CEO"),
            ("John Waldron", "President and COO"),
            ("Denis Coleman", "Chief Financial Officer"),
            ("Marco Argenti", "Chief Information Officer"),
            ("Atte Lahtiranta", "Chief Technology Officer"),
        ],
        
        "HCA": [
            ("Sam Hazen", "CEO and Director"),
            ("Bill Rutherford", "CFO"),
            ("Michael McAlevey", "Chief Operations Officer"),
            ("Kathleen Whalen", "Chief Information Officer"),
        ],
        
        "PAYX": [
            ("John Gibson", "President and CEO"),
            ("Bob Schrader", "CFO"),
            ("Mark Bottini", "Chief Sales Officer"),
            ("Tom Hammond", "Chief Information Officer"),
            ("Michael Gioja", "SVP of IT Operations and Service Delivery"),
        ],
    }
    
    # Get data for this ticker
    raw_data = executives_data.get(ticker.upper(), [])
    
    if not raw_data:
        return []
    
    executives = []
    
    for name, title in raw_data:
        indicators = _detector._detect_ai(title, "")
        is_ai = _detector._is_ai_relevant_role(title, indicators)

        profile = ExecutiveProfile(
            name=name,
            title=title,
            role_weight=_detector._get_role_weight(title),
            indicators=indicators,
            sources=[
                "Company Website (AI-Relevant)" if is_ai
                else "Company Website (Generic)"
            ]
        )

        profile.calculate_max_score()
        executives.append(profile)

    return executives