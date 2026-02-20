from typing import Dict, Any
from uuid import UUID
import json
import structlog

from app.models.enums import SignalCategory, SignalSource
from app.services.snowflake import get_connection
from app.config import get_settings

logger = structlog.get_logger()


def calculate_evidence_count(
    category: SignalCategory,
    source: SignalSource,
    metadata: Dict[str, Any]
) -> int:
    """
    Calculate total evidence count by summing all evidence factors.
    
    Each measurable factor in metadata counts as separate evidence.
    
    Args:
        category: Signal category enum
        source: Signal source enum
        metadata: Signal metadata dict
    
    Returns:
        Total number of evidence pieces (minimum 1)

    """
    
    if category == SignalCategory.TECHNOLOGY_HIRING:
        """
        Evidence Factors:
        - ai_jobs: Each AI-relevant job posting = 1 evidence
        - skills_found: Each unique skill = 1 evidence
        """
        ai_jobs = metadata.get('ai_jobs', 0) or metadata.get('total_ai_jobs', 0)
        skills_found = metadata.get('skills_found', [])
        
        evidence_count = 0
        
        # Factor 1: AI jobs
        if ai_jobs > 0:
            evidence_count += int(ai_jobs)
        
        # Factor 2: Unique skills
        if isinstance(skills_found, list) and len(skills_found) > 0:
            evidence_count += len(skills_found)
        
        logger.debug(
            "evidence_count_tech_hiring",
            ai_jobs=ai_jobs,
            skills_count=len(skills_found) if skills_found else 0,
            total_evidence=evidence_count
        )
        
        return max(evidence_count, 1)
    
    elif category == SignalCategory.INNOVATION_ACTIVITY:
        """
        Evidence Factors:
        - ai_patents: Each AI patent = 1 evidence
        - recent_ai_patents: Each recent patent = 1 evidence
        - ai_categories: Each category = 1 evidence
        """
        ai_patents = (
            metadata.get('ai_patents', 0) or 
            metadata.get('ai_patent_count', 0) or
            metadata.get('count', 0)
        )
        recent_ai_patents = metadata.get('recent_ai_patents', 0)
        ai_categories = metadata.get('ai_categories', [])
        
        evidence_count = 0
        
        # Factor 1: Total AI patents
        if ai_patents > 0:
            evidence_count += int(ai_patents)
        
        # Factor 2: Recent patents
        if recent_ai_patents > 0:
            evidence_count += int(recent_ai_patents)
        
        # Factor 3: Patent categories
        if isinstance(ai_categories, list) and len(ai_categories) > 0:
            evidence_count += len(ai_categories)
        
        logger.debug(
            "evidence_count_innovation",
            ai_patents=ai_patents,
            recent_patents=recent_ai_patents,
            categories=len(ai_categories) if ai_categories else 0,
            total_evidence=evidence_count
        )
        
        return max(evidence_count, 1)
    
    elif category == SignalCategory.DIGITAL_PRESENCE:
        """
        Evidence Factors:
        - ai_technologies: Each technology = 1 evidence
        - categories: Each tech category = 1 evidence

        """
        ai_technologies = metadata.get('ai_technologies', [])
        categories = metadata.get('categories', [])
        
        if not ai_technologies:
            ai_technologies = metadata.get('technologies', [])
        
        evidence_count = 0
        
        # Factor 1: Technologies
        if isinstance(ai_technologies, list) and len(ai_technologies) > 0:
            evidence_count += len(ai_technologies)
        
        # Factor 2: Categories
        if isinstance(categories, list) and len(categories) > 0:
            evidence_count += len(categories)
        
        logger.debug(
            "evidence_count_digital",
            technologies=len(ai_technologies) if isinstance(ai_technologies, list) else 0,
            categories=len(categories) if isinstance(categories, list) else 0,
            total_evidence=evidence_count
        )
        
        return max(evidence_count, 1)

    elif (category == SignalCategory.LEADERSHIP_SIGNALS and 
          source not in [SignalSource.SEC_ITEM_7_MDA]):
        """
        Evidence Factors:
        - executives_analyzed: Each executive = 1 evidence
        - raw_score presence: 1 evidence if score exists
        """
        executives_analyzed = metadata.get('executives_analyzed', 0)
        raw_score = metadata.get('raw_score', 0)
        
        if executives_analyzed == 0:
            exec_details = metadata.get('executive_details', [])
            if isinstance(exec_details, list):
                executives_analyzed = len(exec_details)
        
        evidence_count = 0
        
        # Factor 1: Executives
        if executives_analyzed > 0:
            evidence_count += int(executives_analyzed)
        
        # Factor 2: Score existence
        if raw_score > 0:
            evidence_count += 1
        
        logger.debug(
            "evidence_count_leadership_external",
            executives=executives_analyzed,
            has_score=raw_score > 0,
            total_evidence=evidence_count
        )
        
        return max(evidence_count, 1)
    
    elif (category == SignalCategory.LEADERSHIP_SIGNALS and 
          source == SignalSource.SEC_ITEM_7_MDA):
        """
        Evidence Factors:
        - total_keywords_found: Each keyword mention = 1 evidence
        - word_count: Document analyzed = 1 evidence
        
        """
        total_keywords = metadata.get('total_keywords_found', 0)
        word_count = metadata.get('word_count', 0)
        
        evidence_count = 0
        
        # Factor 1: Keywords
        if total_keywords > 0:
            evidence_count += int(total_keywords)
        
        # Factor 2: Document analyzed
        if word_count > 0:
            evidence_count += 1
        
        logger.debug(
            "evidence_count_leadership_sec",
            keywords=total_keywords,
            document_analyzed=word_count > 0,
            total_evidence=evidence_count
        )
        
        return max(evidence_count, 1)
    
    elif category == SignalCategory.USE_CASE_PORTFOLIO:
        """
        Evidence Factors:
        - total_keywords_found: Each AI use case keyword = 1 evidence
        - word_count: Document analyzed = 1 evidence
        
        """
        total_keywords = metadata.get('total_keywords_found', 0)
        word_count = metadata.get('word_count', 0)
        
        evidence_count = 0
        
        # Factor 1: Keywords
        if total_keywords > 0:
            evidence_count += int(total_keywords)
        
        # Factor 2: Document analyzed
        if word_count > 0:
            evidence_count += 1
        
        logger.debug(
            "evidence_count_use_case",
            keywords=total_keywords,
            document_analyzed=word_count > 0,
            total_evidence=evidence_count
        )
        
        return max(evidence_count, 1)
    
    elif (category == SignalCategory.AI_GOVERNANCE and 
          source == SignalSource.SEC_ITEM_1A_RISK):
        """
        Evidence Factors:
        - ai_risk_score: Each keyword group match = evidence
        - word_count: Document analyzed = 1 evidence

        """
        keywords_matched = metadata.get('keywords_matched', {})
        word_count = metadata.get('word_count', 0)
        
        evidence_count = 0
        
        # Factor 1: Keyword matches (count all matches across groups)
        if keywords_matched and isinstance(keywords_matched, dict):
            total_matches = sum(
                len(v) if isinstance(v, list) else 0
                for v in keywords_matched.values()
            )
            evidence_count += total_matches
        
        # Factor 2: Document analyzed
        if word_count > 0:
            evidence_count += 1
        
        logger.debug(
            "evidence_count_governance_sec",
            keyword_matches=total_matches if keywords_matched else 0,
            document_analyzed=word_count > 0,
            total_evidence=evidence_count
        )
        
        return max(evidence_count, 1)

    elif (category == SignalCategory.AI_GOVERNANCE and 
          source == SignalSource.BOARD_COMPOSITION):
        """
        Evidence Factors (each boolean/list item counts separately):
        - has_tech_committee: 1 evidence if True
        - has_ai_expertise: 1 evidence if True
        - has_data_officer: 1 evidence if True
        - ai_experts: Each expert = 1 evidence
        - relevant_committees: Each committee = 1 evidence
        """
        evidence_count = 0
        
        # Boolean indicators (each True = 1 evidence)
        if metadata.get('has_tech_committee'):
            evidence_count += 1
        
        if metadata.get('has_ai_expertise'):
            evidence_count += 1
        
        if metadata.get('has_data_officer'):
            evidence_count += 1
        
        if metadata.get('has_risk_tech_oversight'):
            evidence_count += 1
        
        if metadata.get('has_ai_in_strategy'):
            evidence_count += 1
        
        # AI experts (each expert = 1 evidence)
        ai_experts = metadata.get('ai_experts', [])
        if isinstance(ai_experts, list):
            evidence_count += len(ai_experts)
        
        # Committees (each committee = 1 evidence)
        committees = metadata.get('relevant_committees', [])
        if isinstance(committees, list):
            evidence_count += len(committees)
        
        logger.debug(
            "evidence_count_board",
            boolean_indicators=sum([
                1 if metadata.get('has_tech_committee') else 0,
                1 if metadata.get('has_ai_expertise') else 0,
                1 if metadata.get('has_data_officer') else 0,
                1 if metadata.get('has_risk_tech_oversight') else 0,
                1 if metadata.get('has_ai_in_strategy') else 0,
            ]),
            ai_experts=len(ai_experts) if isinstance(ai_experts, list) else 0,
            committees=len(committees) if isinstance(committees, list) else 0,
            total_evidence=evidence_count
        )
        
        return max(evidence_count, 1)
    
    elif category == SignalCategory.CULTURE:
        """
        Evidence Factors:
        - keywords_matched: Each keyword match = 1 evidence
        - Fallback: review_count if no keyword matches
        
        """
        keywords_matched = metadata.get('keywords_matched', {})
        review_count = metadata.get('review_count', 0)
        
        evidence_count = 0
        
        # Factor 1: Keyword matches (sum across all categories)
        if keywords_matched and isinstance(keywords_matched, dict):
            for category_name, matches in keywords_matched.items():
                if isinstance(matches, list):
                    evidence_count += len(matches)
        
        # Fallback: use review count if no keyword matches
        if evidence_count == 0 and review_count > 0:
            evidence_count = int(review_count)
        
        logger.debug(
            "evidence_count_culture",
            keyword_matches=evidence_count if keywords_matched else 0,
            review_count=review_count,
            total_evidence=evidence_count
        )
        
        return max(evidence_count, 1)
    

    else:
        logger.debug(
            "evidence_count_default",
            category=category.value if category else "unknown",
            source=source.value if source else "unknown",
            evidence_count=1
        )
        return 1


def get_total_evidence_count(company_id: UUID) -> int:
    """
    Get total evidence count for a company from all signals.
    
    Sums up evidence_count from all latest signals for each category.
    
    Args:
        company_id: Company UUID
    
    Returns:
        Total evidence count across all signal categories

    """
    settings = get_settings()
    conn = None
    cur = None
    
    try:
        conn = get_connection()
        cur = conn.cursor()

        sql = f"""
            SELECT 
                category,
                source,
                metadata,
                normalized_score
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals
            WHERE company_id = %s
            AND (category, created_at) IN (
                SELECT category, MAX(created_at)
                FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals
                WHERE company_id = %s
                GROUP BY category
            )
        """
        
        cur.execute(sql, (str(company_id), str(company_id)))
        rows = cur.fetchall()
        
        total_evidence = 0
        evidence_breakdown = {}
        
        for row in rows:
            category_str = row[0]
            source_str = row[1]
            metadata = row[2]
            score = float(row[3]) if row[3] else 0.0
            
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
            elif metadata is None:
                metadata = {}
            
            # Convert strings to enums
            try:
                category = SignalCategory(category_str)
                source = SignalSource(source_str)
            except ValueError:
                logger.warning(
                    "unknown_category_or_source",
                    category=category_str,
                    source=source_str
                )
                continue
            
            evidence_count = calculate_evidence_count(category, source, metadata)
            
            total_evidence += evidence_count
            
            evidence_breakdown[category_str] = {
                "source": source_str,
                "evidence_count": evidence_count,
                "score": score
            }
            
            logger.debug(
                "category_evidence",
                company_id=str(company_id),
                category=category_str,
                evidence_count=evidence_count
            )
        
        logger.info(
            "total_evidence_calculated",
            company_id=str(company_id),
            total_evidence=total_evidence,
            categories=len(evidence_breakdown),
            breakdown=evidence_breakdown
        )
        
        return max(total_evidence, 1)
        
    except Exception as e:
        logger.error(
            "evidence_count_error",
            company_id=str(company_id),
            error=str(e)
        )

        return 7  
    
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_evidence_breakdown(company_id: UUID) -> Dict[str, Dict]:
    """
    Get detailed evidence breakdown by category.
    
    Args:
        company_id: Company UUID
    
    Returns:
        Dict with evidence count and details per category
    
    """
    settings = get_settings()
    conn = None
    cur = None
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        sql = f"""
            SELECT 
                category,
                source,
                metadata,
                normalized_score,
                confidence,
                raw_value
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals
            WHERE company_id = %s
            AND (category, created_at) IN (
                SELECT category, MAX(created_at)
                FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals
                WHERE company_id = %s
                GROUP BY category
            )
        """
        
        cur.execute(sql, (str(company_id), str(company_id)))
        rows = cur.fetchall()
        
        breakdown = {}
        
        for row in rows:
            category_str = row[0]
            source_str = row[1]
            metadata = row[2]
            score = float(row[3]) if row[3] else 0.0
            confidence = float(row[4]) if row[4] else 0.0
            raw_value = row[5]
            
            # Parse metadata
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}
            elif metadata is None:
                metadata = {}
            
            # Calculate or use stored evidence count
            try:
                category = SignalCategory(category_str)
                source = SignalSource(source_str)
                
                evidence_count = calculate_evidence_count(category, source, metadata)
            except ValueError:
                evidence_count = 1
            
            # Extract details for reporting
            details = extract_evidence_details(category_str, metadata)
            
            breakdown[category_str] = {
                "source": source_str,
                "evidence_count": evidence_count,
                "score": score,
                "confidence": confidence,
                "raw_value": raw_value,
                "details": details
            }
        
        return breakdown
        
    except Exception as e:
        logger.error("evidence_breakdown_error", company_id=str(company_id), error=str(e))
        return {}
    
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def extract_evidence_details(category: str, metadata: Dict) -> Dict:
    """
    Extract human-readable evidence details from metadata.
    
    Args:
        category: Category string
        metadata: Signal metadata
    
    Returns:
        Dict with breakdown of evidence factors
    """
    if category == "technology_hiring":
        return {
            "ai_jobs": metadata.get('ai_jobs', 0),
            "skills_found": len(metadata.get('skills_found', []))
        }
    
    elif category == "innovation_activity":
        return {
            "ai_patents": metadata.get('ai_patents', 0),
            "recent_ai_patents": metadata.get('recent_ai_patents', 0),
            "ai_categories": len(metadata.get('ai_categories', []))
        }
    
    elif category == "digital_presence":
        ai_tech = metadata.get('ai_technologies', []) or metadata.get('technologies', [])
        return {
            "ai_technologies": len(ai_tech) if isinstance(ai_tech, list) else 0,
            "categories": len(metadata.get('categories', []))
        }
    
    elif category == "leadership_signals":
        return {
            "executives_analyzed": metadata.get('executives_analyzed', 0),
            "keywords_found": metadata.get('total_keywords_found', 0)
        }
    
    elif category == "ai_governance":
        if metadata.get('has_tech_committee') is not None:
            # Board composition
            return {
                "has_tech_committee": 1 if metadata.get('has_tech_committee') else 0,
                "has_ai_expertise": 1 if metadata.get('has_ai_expertise') else 0,
                "has_data_officer": 1 if metadata.get('has_data_officer') else 0,
                "ai_experts": len(metadata.get('ai_experts', [])),
                "committees": len(metadata.get('relevant_committees', []))
            }
        else:
            # SEC filing
            keywords = metadata.get('keywords_matched', {})
            total = sum(len(v) if isinstance(v, list) else 0 for v in keywords.values())
            return {
                "keyword_matches": total
            }
    
    elif category == "culture":
        keywords = metadata.get('keywords_matched', {})
        total = sum(len(v) if isinstance(v, list) else 0 for v in keywords.values())
        return {
            "keyword_matches": total,
            "review_count": metadata.get('review_count', 0)
        }
    
    elif category == "use_case_portfolio":
        return {
            "keywords_found": metadata.get('total_keywords_found', 0)
        }
    
    return {}