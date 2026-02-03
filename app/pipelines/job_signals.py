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
    "indeed": "indeed",
    "glassdoor": "glassdoor"
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

    def __init__(self):
        """Initialize the job signal collector."""
        pass
    
    @staticmethod
    def _safe_str(x) -> str:
        return "" if x is None else str(x)

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
        
        total_tech_jobs = len([p for p in postings if self._is_tech_job(p)])
        ai_jobs = len([p for p in postings if p.is_ai_related])
        
        if total_tech_jobs > 0:
            ai_ratio = ai_jobs / total_tech_jobs
        else:
            ai_ratio = 0
        
        all_skills = set()
        for posting in postings:
            all_skills.update(posting.ai_skills)
        
        seniority_dist = {}
        for posting in [p for p in postings if p.is_ai_related]:
            seniority_dist[posting.seniority_level] = seniority_dist.get(posting.seniority_level, 0) + 1
        
        score = (
            min(ai_ratio * 60, 60) +
            min(len(all_skills) / 10, 1) * 20 +
            min(ai_jobs / 5, 1) * 20
        )
        
        skill_counts = {}
        for posting in postings:
            for skill in posting.ai_skills:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1
        
        top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        logger.info(f"Analysis complete: ai_jobs={ai_jobs}, score={score:.1f}")
        
        return ExternalSignal(
            company_id=None,
            category=SignalCategory.TECHNOLOGY_HIRING,
            source=SignalSource.LINKEDIN,
            signal_date=datetime.now(timezone.utc),
            raw_value=f"{ai_jobs}/{total_tech_jobs} AI jobs",
            normalized_score=round(score, 1),
            confidence=min(0.5 + total_tech_jobs / 100, 0.95),
            metadata={
                "total_jobs": len(postings),
                "total_tech_jobs": total_tech_jobs,
                "ai_jobs": ai_jobs,
                "ai_ratio": round(ai_ratio, 3),
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