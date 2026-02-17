from uuid import UUID
from typing import Dict, List, Tuple
from app.services.snowflake import get_connection
from app.config import get_settings
import json


def get_dimension_evidence(
    company_id: UUID,
    ticker: str,
    dimension: str
) -> Tuple[str, Dict[str, float]]:

    extractors = {
        'data_infrastructure': get_data_infrastructure_evidence,
        'ai_governance': get_ai_governance_evidence,
        'technology_stack': get_technology_stack_evidence,
        'talent': get_talent_evidence,
        'leadership': get_leadership_evidence,
        'use_case_portfolio': get_use_case_portfolio_evidence,
        'culture': get_culture_evidence,
    }
    
    extractor = extractors.get(dimension)
    if not extractor:
        return ("", {})
    
    return extractor(company_id, ticker)


# DATA INFRASTRUCTURE
def get_data_infrastructure_evidence(company_id: UUID, ticker: str) -> Tuple[str, Dict[str, float]]:
    conn = get_connection()
    cur = conn.cursor()
    settings = get_settings()
    
    evidence_parts = []
    all_scores = {}
    
    try:
        cur.execute(f"""
            SELECT category, source, raw_value, normalized_score, metadata
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals
            WHERE company_id = %s
            ORDER BY created_at DESC
        """, (str(company_id),))

        rows = cur.fetchall()

        for row in rows:
            category = row[0] or ""
            source = row[1] or ""
            raw_value = row[2] or ""
            score = float(row[3]) if row[3] else 0.0
            metadata = json.loads(row[4]) if isinstance(row[4], str) else (row[4] or {})

            all_scores[category or source] = score

            if category == "digital_presence" or source == "tech_stack_scrape":

                evidence_parts.append(raw_value)

                tech_list = metadata.get("ai_technologies", [])
                for tech in tech_list:
                    tech_name = tech.get("name", "")
                    evidence_parts.append(tech_name)

                    tech_category = tech.get("category", "")
                    if tech_category:
                        evidence_parts.append(tech_category)

                categories = metadata.get("categories_found", [])
                evidence_parts.extend(categories)

            elif category == "innovation_activity" or source == "google_patents":

                keyword_matches = metadata.get("keyword_matches", {})
                for cat, keywords in keyword_matches.items():
                    evidence_parts.extend(keywords)
                    evidence_parts.append(f"{cat} infrastructure")

            elif category == "technology_hiring":

                skills = metadata.get("skills_found", [])
                infra_skills = [
                    "spark", "hadoop", "kafka", "airflow",
                    "aws", "azure", "gcp", "cloud",
                    "docker", "kubernetes", "mlops",
                    "sql", "redis", "snowflake", "databricks"
                ]
                found_infra = [s for s in skills if s in infra_skills]
                evidence_parts.extend(found_infra)

            elif source == "sec_item_1a_risk_factors" or category == "sec_item_1a_risk_factors":
                all_scores["sec_item_1a"] = score
                kw_matched = metadata.get("keywords_matched", {})
                evidence_parts.extend(kw_matched.get("tech_obsolescence", []))
                evidence_parts.extend(kw_matched.get("cyber_data", []))

            elif source == "sec_item_7_mda" or category == "sec_item_7_mda":
                all_scores["sec_item_7"] = score
                kw_matched = metadata.get("keywords_matched", {})
                evidence_parts.extend(kw_matched.get("investment", []))
        
        evidence_text = " ".join(evidence_parts)
        
        digital_score = all_scores.get("digital_presence", 0)
        innovation_score = all_scores.get("innovation_activity", 0)
        
        tech_count = len(metadata.get("ai_technologies", []) 
                        if category == "digital_presence" else [])
        
        base_quality = (digital_score / 100) * 0.5 + (innovation_score / 100) * 0.3
        tech_bonus = min(0.2, tech_count * 0.05) 
        
        data_quality_score = base_quality + tech_bonus
        
        modern_platforms = ["snowflake", "databricks", "aws", "azure", "gcp"]
        evidence_lower = evidence_text.lower()
        cloud_count = sum(1 for p in modern_platforms if p in evidence_lower)
        
        cloud_adoption = min(1.0, cloud_count / 3)  
        
        metrics = {
            "data_quality_score": data_quality_score,
            "cloud_adoption": cloud_adoption
        }
        
        return (evidence_text, metrics)
        
    finally:
        cur.close()
        conn.close()

def get_technology_stack_evidence(company_id: UUID, ticker: str) -> Tuple[str, Dict[str, float]]:
    """
    Extract Technology Stack evidence from:
    - innovation_activity (PRIMARY - 50% weight)
    - digital_presence (40% weight)
    - technology_hiring (20% weight)
    - sec_item_1_business (30% weight)
    """

    conn = get_connection()
    cur = conn.cursor()
    settings = get_settings()

    evidence_parts = []

    try:
        cur.execute(f"""
            SELECT category, source, raw_value, normalized_score, metadata
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals
            WHERE company_id = %s
            ORDER BY created_at DESC
        """, (str(company_id),))

        rows = cur.fetchall()

        for row in rows:
            category = row[0] or ""
            source = row[1] or ""
            metadata = json.loads(row[4]) if isinstance(row[4], str) else (row[4] or {})

            if category == "innovation_activity" or source == "google_patents":
                keyword_matches = metadata.get("keyword_matches", {})
                for keywords in keyword_matches.values():
                    evidence_parts.extend(keywords)

            elif category == "digital_presence" or source == "tech_stack_scrape":
                tech_list = metadata.get("ai_technologies", [])
                for tech in tech_list:
                    evidence_parts.append(tech.get("name", ""))

            elif category == "technology_hiring":
                skills = metadata.get("skills_found", [])
                ml_skills = ["mlops", "mlflow", "sagemaker", "kubeflow",
                            "tensorflow", "pytorch", "scikit-learn"]
                found_ml = [s for s in skills if s in ml_skills]
                evidence_parts.extend(found_ml)

            elif source == "sec_item_1_business" or category == "sec_item_1_business":
                kw_matched = metadata.get("keywords_matched", {})
                evidence_parts.extend(kw_matched.get("production", []))
                evidence_parts.extend(kw_matched.get("product", []))

        evidence_text = " ".join(evidence_parts)

        mlops_keywords = ["mlops", "mlflow", "kubeflow", "sagemaker"]
        mlops_count = sum(1 for kw in mlops_keywords if kw in evidence_text.lower())

        metrics = {
            "mlops_maturity": min(1.0, mlops_count / 2)  # mature
        }

        return (evidence_text, metrics)

    finally:
        cur.close()
        conn.close()

# AI GOVERNANCE
def get_ai_governance_evidence(company_id: UUID, ticker: str) -> Tuple[str, Dict[str, float]]:
    """
    Extract AI Governance evidence from:
    - board_composition (PRIMARY - 70% weight)
    - sec_item_1a_risk_factors (25% weight)
    - leadership_signals (5% weight)
    """
    conn = get_connection()
    cur = conn.cursor()
    settings = get_settings()

    evidence_parts = []
    governance_score = 0.0
    risk_score = 0.0
    has_tech_committee = False
    has_ai_expertise = False
    has_data_officer = False

    try:
        cur.execute(f"""
            SELECT category, source, raw_value, normalized_score, metadata
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals
            WHERE company_id = %s
            ORDER BY created_at DESC
        """, (str(company_id),))

        rows = cur.fetchall()

        for row in rows:
            category = row[0] or ""
            source = row[1] or ""
            raw_value = row[2] or ""
            score = float(row[3]) if row[3] else 0.0
            metadata = json.loads(row[4]) if isinstance(row[4], str) else (row[4] or {})

            if source == "board_composition" or category == "board_composition":
                governance_score = score
                evidence_parts.append(raw_value)

                has_tech_committee = metadata.get("has_tech_committee", False)
                has_ai_expertise = metadata.get("has_ai_expertise", False)
                has_data_officer = metadata.get("has_data_officer", False)

                if has_tech_committee:
                    evidence_parts.append("board committee")
                if has_ai_expertise:
                    evidence_parts.append("ai expertise on board")
                if has_data_officer:
                    evidence_parts.append("chief data officer")

                ai_experts = metadata.get("ai_experts", [])
                for expert in ai_experts:
                    if isinstance(expert, str):
                        evidence_parts.append(expert)
                committees = metadata.get("relevant_committees", [])
                evidence_parts.extend(committees)

            elif source == "sec_item_1a_risk_factors" or category == "sec_item_1a_risk_factors":
                risk_score = score
                kw_matched = metadata.get("keywords_matched", {})
                evidence_parts.extend(kw_matched.get("ai_risk", []))
                evidence_parts.extend(kw_matched.get("regulatory", []))
                if kw_matched.get("ai_risk"):
                    evidence_parts.append("risk framework")

            elif category == "leadership_signals" or source == "company_website":
                exec_details = metadata.get("executive_details", [])
                for exec_info in exec_details:
                    title = exec_info.get("title", "").lower()
                    if any(kw in title for kw in ["data", "ai", "digital", "cto", "cio", "cdo"]):
                        evidence_parts.append(exec_info.get("title", ""))

        evidence_text = " ".join(evidence_parts)

        metrics = {
            "governance_score": (governance_score / 100) * 0.7 + (risk_score / 100) * 0.3,
            "has_tech_committee": 1.0 if has_tech_committee else 0.0,
            "has_ai_expertise": 1.0 if has_ai_expertise else 0.0,
            "has_data_officer": 1.0 if has_data_officer else 0.0,
        }

        return (evidence_text, metrics)

    finally:
        cur.close()
        conn.close()


# LEADERSHIP
def get_leadership_evidence(company_id: UUID, ticker: str) -> Tuple[str, Dict[str, float]]:
    """
    Extract Leadership evidence from:
    - leadership_signals (PRIMARY - 60% weight)
    - sec_item_7_mda (50% weight)
    - board_composition (30% weight)
    - glassdoor_reviews (10% weight)
    """
    conn = get_connection()
    cur = conn.cursor()
    settings = get_settings()

    evidence_parts = []
    leadership_score = 0.0
    executive_count = 0
    ai_executive_count = 0

    try:
        cur.execute(f"""
            SELECT category, source, raw_value, normalized_score, metadata
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals
            WHERE company_id = %s
            ORDER BY created_at DESC
        """, (str(company_id),))

        rows = cur.fetchall()

        for row in rows:
            category = row[0] or ""
            source = row[1] or ""
            raw_value = row[2] or ""
            score = float(row[3]) if row[3] else 0.0
            metadata = json.loads(row[4]) if isinstance(row[4], str) else (row[4] or {})

            if category == "leadership_signals" or source == "company_website":
                leadership_score = score
                evidence_parts.append(raw_value)

                exec_details = metadata.get("executive_details", [])
                executive_count = metadata.get("executives_analyzed", 0)
                ai_executive_count = metadata.get("ai_executives", 0)

                for exec_info in exec_details:
                    title = exec_info.get("title", "")
                    evidence_parts.append(title)
                    for indicator in exec_info.get("indicators", []):
                        evidence_parts.append(indicator.get("evidence", ""))

            elif source == "sec_item_7_mda" or category == "sec_item_7_mda":
                evidence_parts.append(raw_value)
                kw_matched = metadata.get("keywords_matched", {})
                evidence_parts.extend(kw_matched.get("strategy", []))
                evidence_parts.extend(kw_matched.get("executive_priority", []))
                evidence_parts.extend(kw_matched.get("investment", []))

            elif source == "board_composition" or category == "board_composition":
                has_ai = metadata.get("has_ai_expertise", False)
                has_officer = metadata.get("has_data_officer", False)
                if has_ai:
                    evidence_parts.append("board ai expertise")
                if has_officer:
                    evidence_parts.append("chief technology officer")
                    evidence_parts.append("chief data officer")

            elif source == "glassdoor_reviews" or source == "glassdoor":
                evidence_parts.append(raw_value)

        evidence_text = " ".join(evidence_parts)

        metrics = {
            "leadership_score": leadership_score / 100,
            "executive_count": float(executive_count),
            "ai_executive_count": float(ai_executive_count),
        }

        return (evidence_text, metrics)

    finally:
        cur.close()
        conn.close()


# TALENT
def get_talent_evidence(company_id: UUID, ticker: str) -> Tuple[str, Dict[str, float]]:
    """
    Extract Talent evidence from:
    - technology_hiring (PRIMARY - 70% weight)
    - glassdoor_reviews (10% weight)
    """
    conn = get_connection()
    cur = conn.cursor()
    settings = get_settings()

    evidence_parts = []
    hiring_score = 0.0
    total_jobs = 0
    ai_jobs = 0

    try:
        cur.execute(f"""
            SELECT category, source, raw_value, normalized_score, metadata
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals
            WHERE company_id = %s
            ORDER BY created_at DESC
        """, (str(company_id),))

        rows = cur.fetchall()

        for row in rows:
            category = row[0] or ""
            source = row[1] or ""
            raw_value = row[2] or ""
            score = float(row[3]) if row[3] else 0.0
            metadata = json.loads(row[4]) if isinstance(row[4], str) else (row[4] or {})

            if category == "technology_hiring":
                hiring_score = score
                evidence_parts.append(raw_value)

                skills = metadata.get("skills_found", [])
                evidence_parts.extend(skills)

                total_jobs = metadata.get("total_jobs", 0)
                ai_jobs = metadata.get("ai_jobs", 0)

                job_titles = metadata.get("job_titles", [])
                evidence_parts.extend(job_titles)

            elif source == "glassdoor_reviews" or source == "glassdoor":
                evidence_parts.append(raw_value)

        evidence_text = " ".join(evidence_parts)

        ai_job_ratio = (ai_jobs / total_jobs) if total_jobs > 0 else 0.0

        metrics = {
            "ai_job_ratio": ai_job_ratio,
            "team_size": float(ai_jobs),
            "hiring_score": hiring_score / 100,
        }

        return (evidence_text, metrics)

    finally:
        cur.close()
        conn.close()


# USE CASE PORTFOLIO
def get_use_case_portfolio_evidence(company_id: UUID, ticker: str) -> Tuple[str, Dict[str, float]]:
    """
    Extract Use Case Portfolio evidence from:
    - sec_item_1_business (PRIMARY - 70% weight)
    - innovation_activity / google_patents (30% weight)
    - sec_item_7_mda (30% weight)
    """
    conn = get_connection()
    cur = conn.cursor()
    settings = get_settings()

    evidence_parts = []
    sec1_score = 0.0
    innovation_score = 0.0
    sec7_score = 0.0
    production_use_cases = 0

    try:
        cur.execute(f"""
            SELECT category, source, raw_value, normalized_score, metadata
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals
            WHERE company_id = %s
            ORDER BY created_at DESC
        """, (str(company_id),))

        rows = cur.fetchall()

        for row in rows:
            category = row[0] or ""
            source = row[1] or ""
            raw_value = row[2] or ""
            score = float(row[3]) if row[3] else 0.0
            metadata = json.loads(row[4]) if isinstance(row[4], str) else (row[4] or {})

            if source == "sec_item_1_business" or category == "sec_item_1_business":
                sec1_score = score
                evidence_parts.append(raw_value)

                kw_matched = metadata.get("keywords_matched", {})
                evidence_parts.extend(kw_matched.get("production", []))
                evidence_parts.extend(kw_matched.get("use_case", []))
                evidence_parts.extend(kw_matched.get("roi", []))
                evidence_parts.extend(kw_matched.get("product", []))

                production_use_cases = metadata.get("keyword_counts", {}).get("use_case", 0)

            elif category == "innovation_activity" or source == "google_patents":
                innovation_score = score
                keyword_matches = metadata.get("keyword_matches", {})
                for keywords in keyword_matches.values():
                    evidence_parts.extend(keywords)

            elif source == "sec_item_7_mda" or category == "sec_item_7_mda":
                sec7_score = score
                kw_matched = metadata.get("keywords_matched", {})
                evidence_parts.extend(kw_matched.get("project", []))
                evidence_parts.extend(kw_matched.get("investment", []))

        evidence_text = " ".join(evidence_parts)

        metrics = {
            "production_use_cases": float(production_use_cases),
            "sec1_score": sec1_score / 100,
            "innovation_score": innovation_score / 100,
        }

        return (evidence_text, metrics)

    finally:
        cur.close()
        conn.close()


# CULTURE
def get_culture_evidence(company_id: UUID, ticker: str) -> Tuple[str, Dict[str, float]]:
    """
    Extract Culture evidence from:
    - glassdoor_reviews (PRIMARY - 80% weight)
    - leadership_signals (15% weight)
    - technology_hiring (5% weight)
    """
    conn = get_connection()
    cur = conn.cursor()
    settings = get_settings()

    evidence_parts = []
    glassdoor_score = 0.0

    try:
        cur.execute(f"""
            SELECT category, source, raw_value, normalized_score, metadata
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals
            WHERE company_id = %s
            ORDER BY created_at DESC
        """, (str(company_id),))

        rows = cur.fetchall()

        for row in rows:
            category = row[0] or ""
            source = row[1] or ""
            raw_value = row[2] or ""
            score = float(row[3]) if row[3] else 0.0
            metadata = json.loads(row[4]) if isinstance(row[4], str) else (row[4] or {})

            if source == "glassdoor_reviews" or source == "glassdoor":
                glassdoor_score = score
                evidence_parts.append(raw_value)

                kw_matched = metadata.get("keywords_matched", {})
                for kws in kw_matched.values():
                    if isinstance(kws, list):
                        evidence_parts.extend(kws)

                avg_rating = metadata.get("avg_rating", 0)
                if avg_rating and float(avg_rating) >= 4.0:
                    evidence_parts.append("innovative")
                    evidence_parts.append("data-driven")

            elif category == "leadership_signals" or source == "company_website":
                exec_details = metadata.get("executive_details", [])
                for exec_info in exec_details:
                    for indicator in exec_info.get("indicators", []):
                        ev = indicator.get("evidence", "").lower()
                        if any(kw in ev for kw in ["culture", "innovation", "transform", "agile"]):
                            evidence_parts.append(indicator.get("evidence", ""))

            elif category == "technology_hiring":
                job_titles = metadata.get("job_titles", [])
                for title in job_titles:
                    if isinstance(title, str):
                        title_lower = title.lower()
                        if any(kw in title_lower for kw in ["innovation", "ai", "machine learning", "data science"]):
                            evidence_parts.append(title)

        evidence_text = " ".join(evidence_parts)

        metrics = {
            "culture_score": glassdoor_score / 100,
        }

        return (evidence_text, metrics)

    finally:
        cur.close()
        conn.close()