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
        "innovative", "cutting-edge", "forward-thinking",
        "encourages new ideas", "experimental", "creative freedom",
        "startup mentality", "move fast", "disruptive",
        "innovation", "pioneering", "leading edge"
    ]
    
    INNOVATION_NEGATIVE = [
        "bureaucratic", "slow to change", "resistant",
        "outdated", "stuck in old ways", "red tape",
        "politics", "siloed", "hierarchical",
        "legacy mindset", "conservative", "risk-averse"
    ]
    
    DATA_DRIVEN_KEYWORDS = [
        "data-driven", "metrics", "evidence-based",
        "analytical", "kpis", "dashboards", "data culture",
        "measurement", "quantitative", "analytics",
        "data informed", "metrics driven"
    ]
    
    AI_AWARENESS_KEYWORDS = [
        "ai", "artificial intelligence", "machine learning",
        "automation", "data science", "ml", "algorithms",
        "predictive", "neural network", "deep learning",
        "nlp", "computer vision"
    ]
    
    CHANGE_POSITIVE = [
        "agile", "adaptive", "fast-paced", "embraces change",
        "continuous improvement", "growth mindset",
        "flexible", "dynamic", "responsive"
    ]
    
    CHANGE_NEGATIVE = [
        "rigid", "traditional", "slow", "risk-averse",
        "change resistant", "old school", "inflexible",
        "status quo", "stagnant"
    ]
    
    TECH_ROLE_KEYWORDS = [
        # Core tech roles
        'software engineer', 'data scientist', 'data engineer', 
        'machine learning', 'ml engineer', 'ai engineer',
        'data analyst', 'business intelligence', 'analytics',
        
        # Leadership
        'cto', 'cio', 'chief technology', 'chief information',
        'chief data', 'vp technology', 'vp engineering',
        'director of engineering', 'director of data',
        'engineering director', 'data director',
        
        # Specialized
        'devops', 'mlops', 'site reliability', 'sre',
        'cloud engineer', 'platform engineer', 'infrastructure',
        'database', 'architect', 'tech lead', 'engineering manager',
        
        # Data roles
        'data science', 'analytics manager', 'bi analyst',
        'quantitative analyst', 'research scientist',
        'statistician', 'data manager',
        
        # Development
        'developer', 'programmer', 'backend', 'frontend',
        'full stack', 'web developer', 'mobile developer',
        
        # QA/Test
        'qa engineer', 'test engineer', 'automation engineer',
        'quality assurance',
        
        # Product/PM (tech-adjacent)
        'product manager', 'technical product', 'program manager',
        'scrum master', 'agile coach'
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
            innovation_score=Decimal("50.0"),
            data_driven_score=Decimal("50.0"),
            change_readiness_score=Decimal("50.0"),
            ai_awareness_score=Decimal("50.0"),
            overall_score=Decimal("50.0"),
            review_count=0,
            avg_rating=Decimal("0"),
            current_employee_ratio=Decimal("0"),
            confidence=Decimal("0.50"),
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
        
        logger.info("Culture analysis complete", 
                   ticker=ticker, 
                   score=float(culture_signal.overall_score),
                   review_count=culture_signal.review_count,
                   filter_applied=filter_tech_roles)
        
        return culture_signal


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


# def test_walmart_culture_from_s3():
#     """Test with Walmart data from S3 - Tech Roles Only"""
    
#     print("="*70)
#     print("WALMART CULTURE ANALYSIS - S3 Data Source (Tech Roles Only)")
#     print("="*70)
    
#     analyzer = GlassdoorCultureCollector()
    
#     reviews = analyzer.load_reviews_from_s3("WMT", filter_tech_roles=True)
    
#     if not reviews:
#         print("\n No tech role reviews found in S3 for WMT")
#         print("\nOptions:")
#         print("1. Upload local data to S3: python scripts/upload_glassdoor_to_s3.py")
#         print("2. Try without filtering: set filter_tech_roles=False")
#         return None
    
#     print(f"\n Loaded {len(reviews)} tech role reviews from S3")
    
#     # Show sample tech reviews
#     if reviews:
#         print(f"\n Sample Tech Role Reviews:")
#         for i, r in enumerate(reviews[:5], 1):
#             print(f"\n{i}. {r.title}")
#             print(f"   {r.rating}⭐ | 💻 {r.job_title}")
#             print(f"   Pros: {r.pros[:80]}...")
#             print(f"   Cons: {r.cons[:80]}...")
    
#     # Analyze
#     culture = analyzer.analyze_reviews("dummy-id", "WMT", reviews)
    
#     print("\n" + "="*70)
#     print("CULTURE SCORES (Tech Roles Only)")
#     print("="*70)
#     print(f"\n  Innovation:       {culture.innovation_score}/100")
#     print(f"  Data-Driven:      {culture.data_driven_score}/100")
#     print(f"  Change Readiness: {culture.change_readiness_score}/100")
#     print(f"  AI Awareness:     {culture.ai_awareness_score}/100")
#     print(f"\n Overall: {culture.overall_score}/100")
#     print(f"   Confidence: {culture.confidence}")
#     print(f"   Based on: {culture.review_count} tech/data/AI role reviews")
    
#     # Show comparison with all roles
#     print("\n" + "="*70)
#     print("COMPARISON: Tech Roles vs All Roles")
#     print("="*70)
    
#     all_reviews = analyzer.load_reviews_from_s3("WMT", filter_tech_roles=False)
#     culture_all = analyzer.analyze_reviews("dummy-id", "WMT", all_reviews)
    
#     print(f"\n{'Metric':<25} {'Tech Roles':<15} {'All Roles':<15} {'Difference':<15}")
#     print("-"*70)
#     print(f"{'Review Count':<25} {culture.review_count:<15} {culture_all.review_count:<15} {culture.review_count - culture_all.review_count:<15}")
#     print(f"{'Innovation':<25} {float(culture.innovation_score):<15.1f} {float(culture_all.innovation_score):<15.1f} {float(culture.innovation_score - culture_all.innovation_score):<15.1f}")
#     print(f"{'Data-Driven':<25} {float(culture.data_driven_score):<15.1f} {float(culture_all.data_driven_score):<15.1f} {float(culture.data_driven_score - culture_all.data_driven_score):<15.1f}")
#     print(f"{'AI Awareness':<25} {float(culture.ai_awareness_score):<15.1f} {float(culture_all.ai_awareness_score):<15.1f} {float(culture.ai_awareness_score - culture_all.ai_awareness_score):<15.1f}")
#     print(f"{'Overall':<25} {float(culture.overall_score):<15.1f} {float(culture_all.overall_score):<15.1f} {float(culture.overall_score - culture_all.overall_score):<15.1f}")
    
#     return culture


# if __name__ == "__main__":
#     test_walmart_culture_from_s3()