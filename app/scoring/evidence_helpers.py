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
        'data_infrastructure': get_data_infrastructure_evidence
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
