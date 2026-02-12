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
        'leadership': get_leadership_evidence
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
            SELECT category, raw_value, normalized_score, metadata
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals
            WHERE company_id = %s
            ORDER BY created_at DESC
        """, (str(company_id),))
        
        rows = cur.fetchall()
        
        for row in rows:
            category = row[0]
            raw_value = row[1]
            score = float(row[2])
            metadata = json.loads(row[3]) if row[3] else {}
            
            all_scores[category] = score
            
            if category == "digital_presence":

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
            
            elif category == "innovation_activity":

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
    """

    conn = get_connection()
    cur = conn.cursor()
    settings = get_settings()

    evidence_parts = []

    try:
        cur.execute(f"""
            SELECT category, raw_value, normalized_score, metadata
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals
            WHERE company_id = %s
            ORDER BY created_at DESC
        """, (str(company_id),))

        rows = cur.fetchall()

        for row in rows:
            category = row[0]
            metadata = json.loads(row[3]) if row[3] else {}

            if category == "innovation_activity":
                keyword_matches = metadata.get("keyword_matches", {})
                for keywords in keyword_matches.values():
                    evidence_parts.extend(keywords)

            elif category == "digital_presence":
                tech_list = metadata.get("ai_technologies", [])
                for tech in tech_list:
                    evidence_parts.append(tech.get("name", ""))

            elif category == "technology_hiring":
                skills = metadata.get("skills_found", [])
                ml_skills = ["mlops", "mlflow", "sagemaker", "kubeflow", 
                            "tensorflow", "pytorch", "scikit-learn"]
                found_ml = [s for s in skills if s in ml_skills]
                evidence_parts.extend(found_ml)

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

# TO-DO
def get_ai_governance_evidence(company_id: UUID, ticker: str) -> Tuple[str, Dict[str, float]]:
    """
    board_composition - 70%
    leadership_signals - 25%
    """
    _, _ = get_leadership_evidence(company_id, ticker)

    return ("AI governance framework in development", {})


# LEADERSHIP
def get_leadership_evidence(company_id: UUID, ticker: str) -> Tuple[str, Dict[str, float]]:
    conn = get_connection()
    cur = conn.cursor()
    settings = get_settings()
    
    evidence_parts = []
    
    try:
        # Fetch leadership signals
        cur.execute(f"""
            SELECT raw_value, normalized_score, metadata
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals
            WHERE company_id = %s AND category = 'leadership_signals'
            ORDER BY created_at DESC
            LIMIT 1
        """, (str(company_id),))
        
        row = cur.fetchone()
        
        if not row:
            return ("", {})
        
        raw_value = row[0]
        score = float(row[1])
        metadata = json.loads(row[2]) if row[2] else {}
        
        # Add raw value
        evidence_parts.append(raw_value)
        
        # Extract executive titles and indicators
        exec_details = metadata.get("executive_details", [])
        for exec_info in exec_details:
            # Add title
            title = exec_info.get("title", "")
            evidence_parts.append(title)
            
            # Add indicator evidence
            for indicator in exec_info.get("indicators", []):
                evidence = indicator.get("evidence", "")
                evidence_parts.append(evidence)
        
        evidence_text = " ".join(evidence_parts)
        
        # Metrics for quantitative rubric checks
        metrics = {
            "leadership_score": score / 100,  # Normalize to 0-1
            "executive_count": metadata.get("executives_analyzed", 0),
            "ai_executive_count": metadata.get("ai_executives", 0),
        }
        
        return (evidence_text, metrics)
        
    finally:
        cur.close()
        conn.close()