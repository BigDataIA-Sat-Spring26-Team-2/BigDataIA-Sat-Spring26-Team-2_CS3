from dataclasses import dataclass, field
from datetime import datetime
import time
from typing import List, Optional, Dict
from decimal import Decimal
import structlog
import os
from app.config import get_settings
from app.services.s3_storage import upload_file_to_s3
from apify_client import ApifyClient
from pathlib import Path
from app.services.signal_service import store_signal
from app.models.signal import ExternalSignal
from app.models.enums import SignalCategory, SignalSource
from uuid import uuid4, UUID
from datetime import timezone
import json
import boto3
from botocore.exceptions import ClientError

logger = structlog.get_logger(__name__)


@dataclass
class GlassdoorReview:
    review_id: str
    rating: float
    title: str
    pros: str
    cons: str
    advice_to_management: Optional[str]
    is_current_employee: bool
    job_title: str
    review_date: datetime


@dataclass
class CultureSignal:
    company_id: str
    ticker: str
    innovation_score: Decimal
    data_driven_score: Decimal
    change_readiness_score: Decimal
    ai_awareness_score: Decimal
    overall_score: Decimal
    review_count: int
    avg_rating: Decimal
    confidence: Decimal
    current_employee_ratio: Decimal
    positive_keywords_found: List[str] = field(default_factory=list)
    negative_keywords_found: List[str] = field(default_factory=list)


    def to_external_signal(self):
        """Convert to ExternalSignal for database storage"""
        
        
        # Build metadata from existing fields
        metadata = {
            "review_count": self.review_count,
            "avg_rating": float(self.avg_rating),
            "current_employee_ratio": float(self.current_employee_ratio),
            "component_scores": {
                "innovation": float(self.innovation_score),
                "data_driven": float(self.data_driven_score),
                "change_readiness": float(self.change_readiness_score),
                "ai_awareness": float(self.ai_awareness_score),
            },
            "positive_keywords": self.positive_keywords_found,
            "negative_keywords": self.negative_keywords_found,
        }
        
        return ExternalSignal(
            id=uuid4(),
            company_id=UUID(self.company_id),
            category=SignalCategory.CULTURE,
            source=SignalSource.GLASSDOOR,
            signal_date=datetime.now(timezone.utc),
            raw_value=f"{self.review_count} reviews analyzed",
            normalized_score=float(self.overall_score),
            confidence=float(self.confidence),
            metadata=metadata,
            created_at=datetime.now(timezone.utc)
        )

class GlassdoorScraper:
    """
    DEPRECATED: One-time data collection only.
    Data now stored in S3. Use GlassdoorCultureCollector.load_reviews_from_s3() instead.
    """

    COMPANY_URLS = {
        "JPM": "https://www.glassdoor.com/Reviews/JPMorgan-Chase-and-Co-Reviews-E145.htm",
        "WMT": "https://www.glassdoor.com/Reviews/Walmart-Reviews-E715.htm",
        "NVDA": "https://www.glassdoor.com/Reviews/NVIDIA-Reviews-E7633.htm",
        "GE": "https://www.glassdoor.com/Reviews/GE-Reviews-E277.htm",
        "DG": "https://www.glassdoor.com/Reviews/Dollar-General-Reviews-E1342.htm",
        "GS": "https://www.glassdoor.com/Reviews/Goldman-Sachs-Reviews-E2800.htm",
        "TGT": "https://www.glassdoor.com/Reviews/Target-Reviews-E194.htm",
        "CAT": "https://www.glassdoor.com/Reviews/Caterpillar-Reviews-E14583.htm",
        "DE": "https://www.glassdoor.com/Reviews/Deere-and-Company-Reviews-E1239.htm",
        "UNH": "https://www.glassdoor.com/Reviews/UnitedHealth-Group-Reviews-E1513.htm",
        "HCA": "https://www.glassdoor.com/Reviews/HCA-Healthcare-Reviews-E14106.htm",
        "ADP": "https://www.glassdoor.com/Reviews/ADP-Reviews-E737.htm",
        "PAYX": "https://www.glassdoor.com/Reviews/Paychex-Reviews-E3301.htm",
    }
    
    def __init__(
        self,
        api_token: str = None,
        output_folder: str = "data/glassdoor",
        max_reviews: int = 50,
        upload_to_s3: bool = True
    ):
        self.api_token = api_token or os.getenv("APIFY_API_TOKEN")
        if not self.api_token:
            logger.warning("APIFY_API_TOKEN not found - scraping disabled")
            self.client = None
        else:
            self.client = ApifyClient(self.api_token)
        
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        
        self.max_reviews = max_reviews
        self.upload_to_s3 = upload_to_s3
        
        logger.info("Apify Glassdoor Scraper initialized (DEPRECATED - one-time use only)", 
                   output_folder=str(self.output_folder),
                   max_reviews=max_reviews,
                   upload_to_s3=upload_to_s3)
    
    def scrape_company(self, ticker: str) -> Optional[Path]:
        """DEPRECATED: One-time data collection only."""
        if not self.client:
            logger.error("Scraping disabled - no API token", ticker=ticker)
            return None
            
        url = self.COMPANY_URLS.get(ticker)
        if not url:
            logger.error("Unknown ticker", ticker=ticker)
            return None
        
        logger.info("Scraping Glassdoor (one-time collection)", ticker=ticker, url=url)
        
        try:
            run_input = {
                "startUrls": [{"url": url}],
                "maxItems": self.max_reviews,
                "proxy": {
                    "useApifyProxy": True,
                    "apifyProxyGroups": ["RESIDENTIAL"],
                },
            }
            
            run = self.client.actor("memo23/apify-glassdoor-reviews-scraper").call(
                run_input=run_input
            )
            
            dataset_id = run["defaultDatasetId"]
            logger.info("Scrape complete", ticker=ticker, dataset_id=dataset_id)
            
            reviews = list(self.client.dataset(dataset_id).iterate_items())
            
            if not reviews:
                logger.warning("No reviews returned", ticker=ticker)
                return None
            
            logger.info("Reviews fetched", ticker=ticker, count=len(reviews))
            
            local_path = self.output_folder / f"{ticker}_reviews.json"
            
            with open(local_path, "w", encoding="utf-8") as f:
                json.dump(reviews, f, indent=2, ensure_ascii=False)
            
            logger.info("Saved locally", ticker=ticker, path=str(local_path))
            
            if self.upload_to_s3:
                s3_key = f"glassdoor/{ticker}_reviews.json"
                try:
                    s3_uri = upload_file_to_s3(local_path, s3_key)
                    logger.info("Uploaded to S3", ticker=ticker, s3_uri=s3_uri)
                except Exception as e:
                    logger.error("S3 upload failed", ticker=ticker, error=str(e))
            
            return local_path
            
        except Exception as e:
            logger.error("Scraping failed", ticker=ticker, error=str(e))
            return None
    
    def scrape_all_companies(
        self,
        tickers: List[str] = None,
        sleep_between: int = 5
    ) -> Dict[str, Optional[Path]]:
        """DEPRECATED: One-time batch collection only."""
        if not self.client:
            logger.error("Scraping disabled - no API token")
            return {}
            
        if tickers is None:
            tickers = list(self.COMPANY_URLS.keys())
        
        logger.info("Starting batch scrape (one-time collection)", companies=tickers, count=len(tickers))
        
        results = {}
        
        for i, ticker in enumerate(tickers, 1):
            logger.info("Processing company", ticker=ticker, progress=f"{i}/{len(tickers)}")
            
            local_path = self.scrape_company(ticker)
            results[ticker] = local_path
            
            if i < len(tickers):
                logger.info("Sleeping", seconds=sleep_between)
                time.sleep(sleep_between)
        
        successful = sum(1 for p in results.values() if p is not None)
        logger.info("Batch scrape complete", 
                   total=len(tickers), 
                   successful=successful,
                   failed=len(tickers)-successful)
        
        return results


class GlassdoorCultureCollector:
    
    INNOVATION_POSITIVE = [
        "innovative", "cutting-edge", "forward-thinking", "encourages new ideas", "experimental", "creative freedom",
        "startup mentality", "move fast", "disruptive","innovation", "pioneering", "leading edge",
        "thought leader", "first mover", "visionary","groundbreaking", "state of the art", "next generation", "trailblazing", "ahead of the curve", "bleeding edge",
        "bold ideas", "out of the box", "innovation culture","encourages experimentation", "embraces innovation",
        "celebrates creativity", "invests in innovation","hackathon", "idea generation", "open to new ideas",
        "encourages risk taking", "fosters creativity","rewards innovation", "innovation lab", "r&d culture",
        "future focused", "technology first", "digital first",
    ]

    INNOVATION_NEGATIVE = [
        "bureaucratic", "slow to change", "resistant","outdated", "stuck in old ways", "red tape",
        "politics", "siloed", "hierarchical","legacy mindset", "conservative", "risk-averse",
        "too many approvals", "approval process","micromanagement", "micromanage",
        "no innovation", "discourages ideas","punishes failure", "fear of failure",
        "old fashioned", "behind the times","not agile", "waterfall only",
        "change is hard", "resistant to change","top down", "command and control",
        "no autonomy", "no ownership","death by committee", "too much process",
        "overly cautious", "analysis paralysis","not forward thinking", "stuck in past",
        "no investment in tech", "penny pinching on tech",
    ]

    DATA_DRIVEN_KEYWORDS = [
        "data-driven", "metrics", "evidence-based","analytical", "kpis", "dashboards", "data culture",
        "measurement", "quantitative", "analytics","data informed", "metrics driven",
        "data first", "data obsessed","data literacy", "data fluency",
        "decisions based on data", "fact based","ab testing", "a/b testing", "experimentation",
        "hypothesis driven", "test and learn","performance metrics", "okrs", "scorecards",
        "business intelligence", "reporting culture","real time data", "data transparency",
        "data democratization", "self serve analytics","insight driven", "outcome driven",
        "measure everything", "data accountability","data quality", "single source of truth",
        "data strategy", "data governance",
    ]

    AI_AWARENESS_KEYWORDS = [
        "ai", "artificial intelligence", "machine learning","automation", "data science", "ml", "algorithms",
        "predictive", "neural network", "deep learning","nlp", "computer vision",
        "generative ai", "gen ai", "llm","large language model", "chatgpt", "copilot",
        "ai tools", "ai powered", "ai driven","ai strategy", "ai roadmap", "ai initiative",
        "ai first", "ai transformation","prompt engineering", "rag", "embeddings",
        "pytorch", "tensorflow", "hugging face","model training", "model deployment",
        "mlops", "ai platform", "ai infrastructure","recommendation system", "predictive model",
        "intelligent automation", "cognitive automation","robotic process automation", "rpa",
        "natural language processing", "speech recognition","image recognition", "anomaly detection",
        "ai research", "applied ai", "ai lab",
    ]

    CHANGE_POSITIVE = [
        "agile", "adaptive", "fast-paced", "embraces change", "continuous improvement", "growth mindset",
        "flexible", "dynamic", "responsive","lean", "iterative", "scrum",
        "quick to adapt", "pivots quickly","open minded", "learning culture",
        "feedback culture", "fail fast", "fail forward", "learning from failure",
        "psychological safety", "safe to fail","transparent", "open communication",
        "flat structure", "flat hierarchy", "employee empowerment", "ownership culture",
        "bias for action", "move quickly","always improving", "kaizen",
        "welcomes feedback", "open to feedback","collaborative", "cross functional",
        "embraces technology", "tech savvy","modernizing", "transformation mindset",
    ]

    CHANGE_NEGATIVE = [
        "rigid", "traditional", "slow", "risk-averse",
        "change resistant", "old school", "inflexible",
        "status quo", "stagnant",
        "no feedback", "feedback ignored",
        "ideas go nowhere", "no follow through",
        "slow decision making", "slow to decide",
        "too many layers", "too much bureaucracy",
        "fear driven", "blame culture",
        "no psychological safety", "punitive",
        "not collaborative", "territorial",
        "siloed teams", "no cross team",
        "fiefdoms", "empire building",
        "resistant to feedback", "dismissive",
        "no room for growth", "no career path",
        "outdated processes", "manual processes",
        "no automation", "still using legacy",
        "cant move fast", "slow execution",
        "overly hierarchical", "need approval for everything",
    ]

    TECH_ROLE_KEYWORDS = [
        'software engineer', 'data scientist', 'data engineer','machine learning', 'ml engineer', 'ai engineer',
        'data analyst', 'business intelligence', 'analytics','cto', 'cio', 'chief technology', 'chief information',
        'chief data', 'vp technology', 'vp engineering','director of engineering', 'director of data',
        'engineering director', 'data director','devops', 'mlops', 'site reliability', 'sre',
        'cloud engineer', 'platform engineer', 'infrastructure','database', 'architect', 'tech lead', 'engineering manager',
        'data science', 'analytics manager', 'bi analyst','quantitative analyst', 'research scientist',
        'statistician', 'data manager','developer', 'programmer', 'backend', 'frontend',
        'full stack', 'web developer', 'mobile developer','qa engineer', 'test engineer', 'automation engineer',
        'quality assurance','product manager', 'technical product', 'program manager',
        'scrum master', 'agile coach','ai researcher', 'ml researcher', 'applied scientist',
        'research engineer', 'nlp engineer', 'computer vision engineer','deep learning engineer', 'llm engineer', 'ai scientist',
        'chief ai officer', 'caio', 'head of ai', 'vp of ai','ai product manager', 'ml product manager',
        'ml platform engineer', 'ai infrastructure engineer','prompt engineer', 'ai ops', 'model engineer',
        'cloud architect', 'solutions architect', 'enterprise architect','aws engineer', 'azure engineer', 'gcp engineer',
        'kubernetes engineer', 'docker', 'devsecops','network engineer', 'security engineer', 'cybersecurity',
        'information security', 'cloud operations','analytics engineer', 'data platform engineer',
        'data infrastructure', 'data operations', 'dataops', 'etl developer', 'pipeline engineer', 'spark engineer',
        'hadoop engineer', 'kafka engineer', 'snowflake engineer','databricks engineer', 'dbt engineer',
        'chief digital officer', 'chief analytics officer','head of data', 'head of engineering', 'head of machine learning',
        'vp data science', 'vp analytics', 'vp data engineering','director of ai', 'director of machine learning',
        'director of analytics', 'director of data science','generative ai', 'responsible ai', 'ai ethics',
        'ml operations', 'feature engineer', 'data labeler','annotation engineer', 'ai trainer', 'rlhf engineer',
        'vector database', 'embedding engineer','digital transformation', 'innovation engineer',
    ]

    def __init__(self):
        """Initialize S3 client for fetching reviews"""
        settings = get_settings()
        
        try:
            session = boto3.session.Session(
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
            )
            self.s3_client = session.client("s3")
            self.s3_bucket = settings.S3_BUCKET
            logger.info("S3 client initialized for Glassdoor data", bucket=self.s3_bucket)
        except Exception as e:
            logger.error("Failed to initialize S3 client", error=str(e))
            self.s3_client = None
            self.s3_bucket = None
    
    def _is_tech_role(self, job_title: str) -> bool:

        if not job_title or job_title == 'Unknown':
            return False
        
        title_lower = job_title.lower()

        return any(keyword in title_lower for keyword in self.TECH_ROLE_KEYWORDS)
    
    def load_reviews_from_s3(
        self, 
        ticker: str,
        filter_tech_roles: bool = True
    ) -> List[GlassdoorReview]:

        if not self.s3_client or not self.s3_bucket:
            logger.error("S3 not configured", ticker=ticker)
            return []
        
        s3_key = f"glassdoor/{ticker}_reviews.json"
        
        logger.info("Fetching reviews from S3", 
                   ticker=ticker, 
                   s3_key=s3_key,
                   filter_tech_roles=filter_tech_roles)
        
        try:
            response = self.s3_client.get_object(
                Bucket=self.s3_bucket,
                Key=s3_key
            )
            
            json_data = response['Body'].read().decode('utf-8')
            raw_data = json.loads(json_data)
            
            logger.info("Reviews fetched from S3", ticker=ticker, raw_count=len(raw_data))
            
            # Parse into GlassdoorReview objects
            all_reviews = []
            tech_reviews = []
            
            for item in raw_data:
                try:
                    review_id = str(item.get('reviewId', ''))
                    rating = float(item.get('ratingOverall', 0))
                    summary = item.get('summary', '')
                    pros = item.get('pros', '')
                    cons = item.get('cons', '')
                    advice = item.get('advice', None)
                    is_current = item.get('isCurrentJob', False)
                    
                    # Extract job title
                    job_title_obj = item.get('jobTitle')
                    if job_title_obj and isinstance(job_title_obj, dict):
                        job_title = job_title_obj.get('text', 'Unknown')
                    else:
                        job_title = str(job_title_obj) if job_title_obj else 'Unknown'
                    
                    # Parse date
                    date_str = item.get('reviewDateTime', '')
                    try:
                        review_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    except:
                        review_date = datetime.now()
                    
                    review = GlassdoorReview(
                        review_id=review_id,
                        rating=rating,
                        title=summary,
                        pros=pros,
                        cons=cons,
                        advice_to_management=advice,
                        is_current_employee=is_current,
                        job_title=job_title,
                        review_date=review_date
                    )
                    
                    all_reviews.append(review)
                    
                    # Check if tech role
                    if self._is_tech_role(job_title):
                        tech_reviews.append(review)
                    
                except Exception as e:
                    logger.error("Failed to parse review", ticker=ticker, error=str(e))
                    continue
            
            # Return filtered or all reviews based on flag
            if filter_tech_roles:
                filter_ratio = (len(tech_reviews) / len(all_reviews) * 100) if all_reviews else 0
                
                logger.info("Reviews filtered for tech roles", 
                           ticker=ticker,
                           total_reviews=len(all_reviews),
                           tech_reviews=len(tech_reviews),
                           filter_ratio=f"{filter_ratio:.1f}%")
                
                if len(tech_reviews) < 5:
                    logger.warning("Low tech review count",
                                 ticker=ticker,
                                 tech_count=len(tech_reviews),
                                 total_count=len(all_reviews),
                                 recommendation="Consider setting filter_tech_roles=False or scrape more reviews")
                
                return tech_reviews
            else:
                logger.info("Reviews loaded from S3 (unfiltered)", 
                           ticker=ticker, 
                           parsed_count=len(all_reviews))
                return all_reviews
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            
            if error_code == 'NoSuchKey':
                logger.warning("Glassdoor data not found in S3", 
                             ticker=ticker, 
                             s3_key=s3_key,
                             suggestion="Upload local data using: python scripts/upload_glassdoor_to_s3.py")
            else:
                logger.error("S3 fetch failed", 
                           ticker=ticker, 
                           error=str(e),
                           error_code=error_code)
            return []
            
        except Exception as e:
            logger.error("Unexpected error loading from S3", ticker=ticker, error=str(e))
            return []
    
    def analyze_reviews(
        self,
        company_id: str,
        ticker: str,
        reviews: List[GlassdoorReview],
    ) -> CultureSignal:
        """
        Analyze reviews for culture indicators.
        
        Algorithm:
        1. Combine pros, cons, advice text
        2. Count keyword matches with weighting
        3. Weight by recency (last 2 years = 1.0, older = 0.5)
        4. Weight current employees higher (1.2x)
        5. Calculate component scores
        6. Calculate overall weighted average
        """
        
        if not reviews:
            return self._default_culture_signal(company_id, ticker)
        
        innovation_positive = Decimal(0)
        innovation_negative = Decimal(0)
        data_driven_mentions = Decimal(0)
        ai_awareness_mentions = Decimal(0)
        change_positive = Decimal(0)
        change_negative = Decimal(0)
        total_weight = Decimal(0)
        
        positive_kw_found = set()
        negative_kw_found = set()
        
        for review in reviews:
            text_parts = [review.pros, review.cons]
            if review.advice_to_management:
                text_parts.append(review.advice_to_management)
            text = " ".join(text_parts).lower()
            
            days_old = (datetime.now() - review.review_date).days
            recency_weight = Decimal("1.0") if days_old < 730 else Decimal("0.5")
            employee_weight = Decimal("1.2") if review.is_current_employee else Decimal("1.0")
            weight = recency_weight * employee_weight
            total_weight += weight
            
            for kw in self.INNOVATION_POSITIVE:
                if kw in text:
                    innovation_positive += weight
                    positive_kw_found.add(kw)
            
            for kw in self.INNOVATION_NEGATIVE:
                if kw in text:
                    innovation_negative += weight
                    negative_kw_found.add(kw)
            
            for kw in self.DATA_DRIVEN_KEYWORDS:
                if kw in text:
                    data_driven_mentions += weight
                    positive_kw_found.add(kw)
            
            for kw in self.AI_AWARENESS_KEYWORDS:
                if kw in text:
                    ai_awareness_mentions += weight
                    positive_kw_found.add(kw)
            
            for kw in self.CHANGE_POSITIVE:
                if kw in text:
                    change_positive += weight
                    positive_kw_found.add(kw)
            
            for kw in self.CHANGE_NEGATIVE:
                if kw in text:
                    change_negative += weight
                    negative_kw_found.add(kw)
        
        if total_weight > 0:
            innovation_score = ((innovation_positive - innovation_negative) / total_weight) * 50 + 50
            innovation_score = max(Decimal(0), min(Decimal(100), innovation_score))
            
            data_driven_score = (data_driven_mentions / total_weight) * 100
            data_driven_score = min(Decimal(100), data_driven_score)
            
            ai_awareness_score = (ai_awareness_mentions / total_weight) * 100
            ai_awareness_score = min(Decimal(100), ai_awareness_score)
            
            change_score = ((change_positive - change_negative) / total_weight) * 50 + 50
            change_score = max(Decimal(0), min(Decimal(100), change_score))
        else:
            innovation_score = Decimal(50)
            data_driven_score = Decimal(50)
            ai_awareness_score = Decimal(50)
            change_score = Decimal(50)
        
        overall_score = (
            Decimal("0.30") * innovation_score +
            Decimal("0.25") * data_driven_score +
            Decimal("0.25") * ai_awareness_score +
            Decimal("0.20") * change_score
        )
        
        confidence = min(Decimal("0.5") + Decimal(len(reviews)) / 100, Decimal("0.95"))
        current_count = sum(1 for r in reviews if r.is_current_employee)
        current_ratio = Decimal(current_count) / Decimal(len(reviews)) if reviews else Decimal(0)
        avg_rating = Decimal(sum(r.rating for r in reviews)) / Decimal(len(reviews)) if reviews else Decimal(0)
        
        return CultureSignal(
            company_id=company_id,
            ticker=ticker,
            innovation_score=innovation_score.quantize(Decimal("0.1")),
            data_driven_score=data_driven_score.quantize(Decimal("0.1")),
            change_readiness_score=change_score.quantize(Decimal("0.1")),
            ai_awareness_score=ai_awareness_score.quantize(Decimal("0.1")),
            overall_score=overall_score.quantize(Decimal("0.1")),
            review_count=len(reviews),
            avg_rating=avg_rating.quantize(Decimal("0.1")),
            current_employee_ratio=current_ratio.quantize(Decimal("0.01")),
            confidence=confidence.quantize(Decimal("0.01")),
            positive_keywords_found=sorted(list(positive_kw_found)),
            negative_keywords_found=sorted(list(negative_kw_found))
        )
    
    def _default_culture_signal(self, company_id: str, ticker: str) -> CultureSignal:
        """Default signal when no reviews available"""
        return CultureSignal(
            company_id=company_id,
            ticker=ticker,
            innovation_score=Decimal("10.0"),
            data_driven_score=Decimal("10.0"),
            change_readiness_score=Decimal("10.0"),
            ai_awareness_score=Decimal("10.0"),
            overall_score=Decimal("10.0"),
            review_count=0,
            avg_rating=Decimal("0"),
            current_employee_ratio=Decimal("0"),
            confidence=Decimal("0.10"),
        )


class GlassdoorCollectionPipeline:
    
    def __init__(self):
        self.analyzer = GlassdoorCultureCollector()
    
    def collect_and_analyze(
        self,
        company_id: str,
        ticker: str,
        filter_tech_roles: bool = True
    ) -> CultureSignal:

        logger.info("Starting Glassdoor culture analysis", 
                   ticker=ticker,
                   filter_tech_roles=filter_tech_roles)
        
        reviews = self.analyzer.load_reviews_from_s3(ticker, filter_tech_roles=filter_tech_roles)
        
        if not reviews:
            logger.warning("No reviews available", 
                         ticker=ticker,
                         filter_applied=filter_tech_roles,
                         suggestion="Check S3 data exists or disable filtering")
            return self.analyzer._default_culture_signal(company_id, ticker)
        
        # Analyze
        culture_signal = self.analyzer.analyze_reviews(company_id, ticker, reviews)
        
        self._store_signal(culture_signal)

        logger.info("Culture analysis complete", 
                   ticker=ticker, 
                   score=float(culture_signal.overall_score),
                   review_count=culture_signal.review_count,
                   filter_applied=filter_tech_roles)
        
        return culture_signal
    
    
    def _store_signal(self, culture_signal: CultureSignal) -> None:
        """Store in external_signals table"""
    
        external_signal = culture_signal.to_external_signal()
        store_signal(external_signal)
        
        logger.info(
            "culture_signal_stored",
            ticker=culture_signal.ticker,
            score=float(culture_signal.overall_score)
        )


# ========================================
# CONVENIENCE FUNCTIONS
# ========================================

def collect_glassdoor_for_company(
    company_id: str, 
    ticker: str,
    filter_tech_roles: bool = True
) -> CultureSignal:
   
    pipeline = GlassdoorCollectionPipeline()
    return pipeline.collect_and_analyze(company_id, ticker, filter_tech_roles=filter_tech_roles)


def batch_analyze_glassdoor(
    tickers: List[str],
    filter_tech_roles: bool = True
) -> Dict[str, CultureSignal]:

    pipeline = GlassdoorCollectionPipeline()
    results = {}
    
    for ticker in tickers:
        try:
            signal = pipeline.collect_and_analyze("dummy-id", ticker, filter_tech_roles=filter_tech_roles)
            results[ticker] = signal
        except Exception as e:
            logger.error("Batch analysis failed", ticker=ticker, error=str(e))
            continue
    
    return results


# def example_single_company():
#     """
#     Example: Collect and store Glassdoor signal for NVIDIA.
#     """
#     from app.services.snowflake import get_connection
    
#     print("=" * 70)
#     print("EXAMPLE: Collect Glassdoor Signal for NVIDIA")
#     print("=" * 70)
    
#     # Step 1: Get company_id from database
#     print("\nStep 1: Getting company_id...")
    
#     settings = get_settings()
#     conn = get_connection()
#     cur = conn.cursor()
    
#     cur.execute(f"""
#         SELECT id, name, ticker
#         FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies
#         WHERE ticker = 'WMT'
#         LIMIT 1
#     """)
    
#     row = cur.fetchone()
    
#     if not row:
#         print("✗ NVDA not found in database")
#         cur.close()
#         conn.close()
#         return
    
#     company_id = row[0]
#     company_name = row[1]
#     ticker = row[2]
    
#     print(f"✓ Found: {company_name} (ID: {company_id})")
    
#     cur.close()
#     conn.close()
    
#     # Step 2: Run Glassdoor pipeline
#     print("\nStep 2: Running Glassdoor collection pipeline...")
    
#     pipeline = GlassdoorCollectionPipeline()
    
#     culture_signal = pipeline.collect_and_analyze(
#         company_id=company_id,
#         ticker=ticker,
#         filter_tech_roles=False
#     )
    
#     # Step 3: Display results
#     print("\n" + "=" * 70)
#     print("RESULTS")
#     print("=" * 70)
    
#     print(f"\n📊 Culture Scores:")
#     print(f"   Overall:          {culture_signal.overall_score:.1f}/100")
#     print(f"   Innovation:       {culture_signal.innovation_score:.1f}/100")
#     print(f"   Data-Driven:      {culture_signal.data_driven_score:.1f}/100")
#     print(f"   AI Awareness:     {culture_signal.ai_awareness_score:.1f}/100")
#     print(f"   Change Readiness: {culture_signal.change_readiness_score:.1f}/100")
    
#     print(f"\n📝 Review Info:")
#     print(f"   Reviews Analyzed: {culture_signal.review_count}")
#     print(f"   Average Rating:   {culture_signal.avg_rating:.1f}/5.0")
#     print(f"   Confidence:       {culture_signal.confidence:.2f}")
    
#     # Step 4: Verify it's stored
#     print("\n" + "=" * 70)
#     print("VERIFICATION")
#     print("=" * 70)
    
#     conn = get_connection()
#     cur = conn.cursor()
    
#     cur.execute(f"""
#         SELECT id, category, source, normalized_score, confidence, created_at
#         FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.external_signals
#         WHERE company_id = %s AND category = 'culture'
#         ORDER BY created_at DESC
#         LIMIT 1
#     """, (company_id,))
    
#     row = cur.fetchone()
    
#     if row:
#         print(f"\n✓ Signal stored in external_signals table")
#         print(f"  Signal ID:  {row[0]}")
#         print(f"  Category:   {row[1]}")
#         print(f"  Source:     {row[2]}")
#         print(f"  Score:      {row[3]:.1f}/100")
#         print(f"  Confidence: {row[4]:.2f}")
#         print(f"  Created:    {row[5]}")
#     else:
#         print(f"\n⚠ Signal NOT found in database - check for errors above")
    
#     cur.close()
#     conn.close()
    
#     print("\n" + "=" * 70)
#     print("✅ EXAMPLE COMPLETE")
#     print("=" * 70)


# def example_batch_companies():
#     """
#     Example: Collect and store Glassdoor signals for all CS3 companies.
#     """
#     print("=" * 70)
#     print("EXAMPLE: Batch Collect All CS3 Companies")
#     print("=" * 70)
    
#     # CS3 portfolio companies
#     tickers = ["NVDA", "JPM", "WMT", "GE", "DG"]
    
#     from app.services.snowflake import get_connection
#     settings = get_settings()
    
#     for ticker in tickers:
#         print(f"\n{'─'*70}")
#         print(f"Processing: {ticker}")
#         print('─'*70)
        
#         try:
#             # Get company_id
#             conn = get_connection()
#             cur = conn.cursor()
            
#             cur.execute(f"""
#                 SELECT id, name
#                 FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies
#                 WHERE ticker = %s
#             """, (ticker,))
            
#             row = cur.fetchone()
            
#             if not row:
#                 print(f"✗ {ticker} not found in database - skipping")
#                 cur.close()
#                 conn.close()
#                 continue
            
#             company_id = row[0]
#             company_name = row[1]
            
#             cur.close()
#             conn.close()
            
#             print(f"✓ Found: {company_name}")
            
#             # Run pipeline
#             pipeline = GlassdoorCollectionPipeline()
#             culture_signal = pipeline.collect_and_analyze(
#                 company_id=company_id,
#                 ticker=ticker,
#                 filter_tech_roles=True
#             )
            
#             print(f"✓ Score: {culture_signal.overall_score:.1f}/100 ({culture_signal.review_count} reviews)")
            
#         except Exception as e:
#             print(f"✗ Failed: {str(e)}")
    
#     print("\n" + "=" * 70)
#     print("BATCH COMPLETE")
#     print("=" * 70)


# if __name__ == "__main__":
#     # Run single company example
#     example_single_company()
#     #example_batch_companies()