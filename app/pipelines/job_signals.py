import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict
import pandas as pd
import numpy as np
from jobspy import scrape_jobs

from app.models.signal import (
    ExternalSignal,
    SignalCategory,
    SignalSource,
)

logger = logging.getLogger(__name__)


_SOURCE_TO_JOBSPY_SITE = {
    "linkedin": "linkedin",
    "indeed": "indeed"
}


@dataclass
class JobPosting:
    title: str
    company: str
    location: str
    description: str
    posted_date: str
    source: str
    url: str
    is_ai_related: bool = False
    ai_skills: list = field(default_factory=list)
    seniority_level: str = ""
    ai_relevance_score: float = 0.0 
    
    def __repr__(self):
        return f"JobPosting(title='{self.title}', company='{self.company}', ai_related={self.is_ai_related})"


class JobSignalCollector:
    
    AI_KEYWORDS = [
        "machine learning", "ml engineer", "data scientist",
        "artificial intelligence", "deep learning", "nlp",
        "computer vision", "mlops", "ai engineer",
        "pytorch", "tensorflow", "llm", "large language model",
        "generative ai", "gpt", "neural network", "data science"
    ]
    
    AI_SKILLS = [
        # Programming Languages
        "python", "r", "julia", "scala", "java",
        
        # ML Frameworks
        "pytorch", "tensorflow", "scikit-learn", "keras",
        "xgboost", "lightgbm", "catboost",
        
        # Deep Learning
        "transformers", "huggingface", "bert", "gpt",
        "stable diffusion", "diffusion models", "lstm", "rnn",
        
        # MLOps & Infrastructure
        "mlflow", "kubeflow", "mlops", "sagemaker",
        "vertex ai", "azure ml", "databricks",
        "spark", "hadoop", "kubernetes", "docker",
        "airflow", "prefect",
        
        # NLP
        "nlp", "natural language processing", "spacy",
        "nltk", "langchain", "llama", "openai",
        
        # Computer Vision
        "opencv", "yolo", "rcnn", "computer vision",
        "image recognition", "object detection", "segmentation",
        
        # Vector Databases & RAG
        "pinecone", "weaviate", "chromadb", "faiss",
        "vector database", "rag", "retrieval augmented",
        "embeddings",
        
        # Cloud Platforms
        "aws", "gcp", "azure", "cloud", "s3",
        
        # Data Engineering
        "sql", "nosql", "mongodb", "postgresql",
        "redis", "kafka", "streaming",
        
        # Statistics & Math
        "statistics", "probability", "linear algebra",
        "optimization", "calculus"
    ]
    
    SENIORITY_KEYWORDS = {
        "entry": ["junior", "entry", "associate", "intern", "graduate", "jr"],
        "mid": ["mid", "intermediate", "professional"],
        "senior": ["senior", "sr", "lead", "staff", "principal engineer"],
        "principal": ["principal", "architect", "distinguished", "fellow"],
        "executive": ["director", "vp", "vice president", "chief", "head of", "manager", "cto", "cdo"]
    }

    AI_TITLE_KEYWORDS = [
        "ai", 
        "ml", 
        "machine learning", 
        "data scientist", 
        "mlops", 
        "artificial intelligence"
    ]

    def __init__(self):
        """Initialize the job signal collector."""
        pass
    
    @staticmethod
    def _safe_str(x) -> str:
        return "" if x is None else str(x)
    
    @staticmethod
    def get_optimized_search_queries(company_name: str) -> List[str]:

        return [
            # Query 1: Core ML/AI Engineering (most common roles)
            # Catches: ML Engineer, Machine Learning Engineer, AI Engineer, AI/ML Engineer
            f"{company_name} (machine learning OR ML OR artificial intelligence OR AI) engineer",
            
            # Query 2: Data Science & Research (scientist roles)
            # Catches: Data Scientist, Research Scientist, Applied Scientist, AI Researcher
            f"{company_name} (data scientist OR research scientist OR applied scientist OR AI research)",
            
            # Query 3: Specialized AI domains (technical specialists)
            # Catches: Computer Vision Engineer, NLP Engineer, Deep Learning Engineer
            f"{company_name} (computer vision OR NLP OR natural language processing OR deep learning OR neural network)",
            
            # Query 4: Infrastructure & Operations (platform/ops roles)
            # Catches: MLOps Engineer, ML Infrastructure, AI Platform Engineer
            f"{company_name} (MLOps OR ML infrastructure OR AI platform OR machine learning operations)",
            
            # Query 5: Emerging/Trending (newest AI roles)
            # Catches: LLM Engineer, GenAI roles, Prompt Engineer
            f"{company_name} (LLM OR large language model OR generative AI OR gen AI OR prompt engineer)",
            
            # Query 6: Data Engineering with AI focus (often has AI components)
            # Catches: Data Engineer, ML Data Engineer, AI Data Engineer
            f"{company_name} data engineer (machine learning OR AI OR ML pipeline)",
        ]

    #Normalize date to 'YYYY-MM-DD' format; else current date
    @staticmethod
    def _normalize_posted_date(val) -> str:

        if val is None or (isinstance(val, float) and np.isnan(val)):
            return datetime.now().strftime("%Y-%m-%d")
        try:
            dt = pd.to_datetime(val, errors="coerce")
            if pd.isna(dt):
                return datetime.now().strftime("%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return datetime.now().strftime("%Y-%m-%d")

    def _jobspy_df_to_jobs(self, df: pd.DataFrame) -> List[JobPosting]:

        if df is None or df.empty:
            logger.warning("Empty dataframe received from JobSpy")
            return []

        # Build a case-insensitive column map
        cols = {c.lower(): c for c in df.columns}

        def col(*names: str):
            for n in names:
                if n.lower() in cols:
                    return cols[n.lower()]
            return None

        c_site = col("site", "SITE")
        c_title = col("title", "TITLE")
        c_company = col("company", "COMPANY")
        c_location = col("location", "LOCATION")
        c_city = col("city", "CITY")
        c_state = col("state", "STATE")
        c_url = col("job_url", "JOB_URL", "job_url_direct", "JOB_URL_DIRECT")
        c_desc = col("description", "DESCRIPTION")
        c_date = col("date_posted", "DATE_POSTED")

        jobs: List[JobPosting] = []
        
        for _, row in df.iterrows():

            if c_location:
                location = self._safe_str(row.get(c_location)).strip()
            else:
                city = self._safe_str(row.get(c_city)).strip() if c_city else ""
                state = self._safe_str(row.get(c_state)).strip() if c_state else ""
                location = ", ".join([p for p in [city, state] if p]) or "Not specified"

            title = self._safe_str(row.get(c_title)).strip() if c_title else ""
            company = self._safe_str(row.get(c_company)).strip() if c_company else "Unknown Company"
            description = self._safe_str(row.get(c_desc)).strip() if c_desc else ""
            
            if not description:
                description = f"Job posting for {title} at {company}".strip()

            job = JobPosting(
                title=title or "Unknown Title",
                company=company,
                location=location,
                description=description,
                source=self._safe_str(row.get(c_site)).strip().title() if c_site else "JobSpy",
                url=self._safe_str(row.get(c_url)).strip() if c_url else "",
                posted_date=self._normalize_posted_date(row.get(c_date) if c_date else None),
            )
            
            # Classify the job immediately
            self.classify_posting(job)
            
            jobs.append(job)

        logger.info(f"Converted {len(jobs)} jobs from JobSpy dataframe")
        return jobs

    def scrape_jobs_from_multiple_sources(
        self,
        search_query: str,
        sources: List[str] = ["linkedin", "indeed"],
        max_results_per_source: int = 50,
        location: str = "United States",
        hours_old: int = 24 * 30,
        country_indeed: str = "USA",
        linkedin_fetch_description: bool = True,
    ) -> List[JobPosting]:

        logger.info(f"Starting job scrape: query='{search_query}', sources={sources}, location={location}")
        
        site_name: List[str] = []
        for s in (sources or []):
            key = s.strip().lower()
            if key in _SOURCE_TO_JOBSPY_SITE:
                site_name.append(_SOURCE_TO_JOBSPY_SITE[key])

        if not site_name:
            site_name = ["linkedin", "indeed"]
            logger.info(f"No valid sources provided, defaulting to: {site_name}")

        try:
            logger.info(f"Calling JobSpy with: sites={site_name}, results_wanted={max_results_per_source * len(site_name)}")
            
            df = scrape_jobs(
                site_name=site_name,
                search_term=search_query,
                location=location,
                results_wanted=max_results_per_source * len(site_name),
                hours_old=hours_old,
                country_indeed=country_indeed,
                linkedin_fetch_description=linkedin_fetch_description,
            )

            jobs = self._jobspy_df_to_jobs(df)
            logger.info(f"Successfully scraped {len(jobs)} jobs")
            return jobs
            
        except Exception as e:
            logger.error(f"Error scraping jobs: {str(e)}", exc_info=True)
            return []

    def classify_posting(self, posting: JobPosting) -> JobPosting:

        text = f"{posting.title} {posting.description}".lower()
        
        # Check for AI keywords
        posting.is_ai_related = any(kw in text for kw in self.AI_KEYWORDS)
        
        # Extract AI skills
        posting.ai_skills = [skill for skill in self.AI_SKILLS if skill.lower() in text]
        
        # Classify seniority
        posting.seniority_level = self._classify_seniority(posting.title)

        # Calculate AI relevance score
        posting.ai_relevance_score = self.calculate_ai_relevance_score(
        skills=set(posting.ai_skills),
        title=posting.title
        )

        logger.info(
            "job_classified",
            title=posting.title,
            company=posting.company,
            source=posting.source,
            is_ai_related=posting.is_ai_related,
            ai_relevance_score=round(posting.ai_relevance_score, 3),
            skill_count=len(posting.ai_skills),
            skills=posting.ai_skills[:5],
            seniority=posting.seniority_level,
            location=posting.location
        )

        return posting
    

    def _classify_seniority(self, title: str) -> str:
        title_lower = title.lower()
        
        for level, keywords in self.SENIORITY_KEYWORDS.items():
            if any(kw in title_lower for kw in keywords):
                return level
        
        return "mid"  # Default to mid-level if unclear

    def _is_tech_job(self, posting: JobPosting) -> bool:
        tech_keywords = [
            "engineer", "developer", "programmer", "software",
            "data", "analyst", "scientist", "technical", "architect",
            "devops", "sre", "infrastructure"
        ]
        title_lower = posting.title.lower()
        return any(kw in title_lower for kw in tech_keywords)

    def analyze_job_postings(
        self,
        company: str,
        postings: List[JobPosting]
    ) -> ExternalSignal:
        
        logger.info(f"Analyzing {len(postings)} job postings for {company}")

        tech_jobs = [p for p in postings if self._is_tech_job(p)]
        total_tech_jobs = len(tech_jobs)
        
        highly_ai_relevant_jobs = [p for p in tech_jobs if p.ai_relevance_score >= 0.5]
        ai_jobs = len(highly_ai_relevant_jobs)
       
        
        if total_tech_jobs > 0:
            avg_ai_relevance = sum(p.ai_relevance_score for p in tech_jobs) / total_tech_jobs
            ai_ratio = ai_jobs / total_tech_jobs
        else:
            avg_ai_relevance = 0.0
            ai_ratio = 0.0
        
        all_skills = set()
        for posting in highly_ai_relevant_jobs:
            all_skills.update(posting.ai_skills)
        
        seniority_dist = {}
        for posting in highly_ai_relevant_jobs:
            seniority_dist[posting.seniority_level] = seniority_dist.get(posting.seniority_level, 0) + 1
        
        score = (
            min(ai_ratio * 60, 60) +
            min(len(all_skills) / 10, 1) * 20 +
            min(avg_ai_relevance, 1.0) * 20
        )
        
        skill_counts = {}
        for posting in tech_jobs:  # Include ALL tech jobs for skill analysis
            for skill in posting.ai_skills:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1
        
        top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        relevance_buckets = {
            "high (0.8-1.0)": len([p for p in tech_jobs if p.ai_relevance_score >= 0.8]),
            "medium (0.5-0.8)": len([p for p in tech_jobs if 0.5 <= p.ai_relevance_score < 0.8]),
            "low (0.0-0.5)": len([p for p in tech_jobs if p.ai_relevance_score < 0.5]),
        }
        
        logger.info( "INFOOOOOO-",
            f"Analysis complete: ai_jobs={ai_jobs}, "
            f"avg_relevance={avg_ai_relevance:.2f}, score={score:.1f}"
        )

        logger.info(
        "high_relevance_jobs_summary",
        company=company,
        count=len(highly_ai_relevant_jobs),
        jobs=[
            {
                "title": job.title,
                "relevance_score": round(job.ai_relevance_score, 3),
                "skill_count": len(job.ai_skills),
                "seniority": job.seniority_level,
                "source": job.source
            }
            for job in sorted(highly_ai_relevant_jobs, key=lambda x: x.ai_relevance_score, reverse=True)[:10]
            ]
        )
    
        return ExternalSignal(
            company_id=None,
            category=SignalCategory.TECHNOLOGY_HIRING,
            source=SignalSource.MULTIPLE,
            signal_date=datetime.now(timezone.utc),
            raw_value=f"{ai_jobs}/{total_tech_jobs} highly AI-relevant jobs (avg relevance: {avg_ai_relevance:.2f})",
            normalized_score=round(score, 1),
            confidence=min(0.5 + total_tech_jobs / 100, 0.95),
            metadata={
                "total_jobs": len(postings),
                "total_tech_jobs": total_tech_jobs,
                "ai_jobs": ai_jobs,
                "ai_ratio": round(ai_ratio, 3),
                "avg_ai_relevance": round(avg_ai_relevance, 3),
                "relevance_distribution": relevance_buckets,
                "skills_found": list(all_skills),
                "skill_count": len(all_skills),
                "seniority_distribution": seniority_dist,
                "top_skills": top_skills
            }
        )

    def deduplicate_jobs(self, jobs: List[JobPosting]) -> List[JobPosting]:
        seen = set()
        unique_jobs = []
        
        for job in jobs:
            key = (job.title.lower().strip(), 
                   job.company.lower().strip(), 
                   job.location.lower().strip())
            
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)
        
        logger.info(f"Deduplication: {len(jobs)} -> {len(unique_jobs)} jobs")
        return unique_jobs
    
    
    def calculate_ai_relevance_score(self, skills: set, title: str) -> float:

        skill_count = len(skills)
        normalized_skill_count = min(skill_count / 5, 1.0)
        base_score = normalized_skill_count * 0.6
        
        title_lower = title.lower()
        title_has_ai_keywords = any(kw in title_lower for kw in self.AI_TITLE_KEYWORDS)
        title_boost = 0.4 if title_has_ai_keywords else 0.0
        
        # Combine scores, ensuring it doesn't exceed 1.0
        final_score = min(base_score + title_boost, 1.0)
        
        logger.debug(
            "ai_relevance_score_calculated",
            title=title,
            skill_count=skill_count,
            normalized_skill_count=round(normalized_skill_count, 3),
            base_score=round(base_score, 3),
            title_has_ai_keywords=title_has_ai_keywords,
            title_boost=title_boost,
            final_score=round(final_score, 3),
            skills_preview=list(skills)[:3] if skills else []
        )
        
        return final_score