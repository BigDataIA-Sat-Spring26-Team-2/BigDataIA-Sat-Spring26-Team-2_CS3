from app.pipelines.collectors.website_collector import CompanyWebsiteCollector
from app.models.leadership import ExecutiveProfile

_detector = CompanyWebsiteCollector()

def get_hardcoded_executives(ticker: str):
    if ticker != "UNH":
        return []

    executives = []

    raw_data = [
        ("Michael Pencina", "Chief AI Scientist"),
        ("Sandeep Dadlani", "CEO, Optum Insight"),
    ]

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
