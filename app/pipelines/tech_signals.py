# app/pipelines/tech_signals.py

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import httpx
from bs4 import BeautifulSoup

from app.models.signal import ExternalSignal, SignalCategory, SignalSource

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# COMPANY SOURCES
# Preferred: config/company_sources.json (config-driven, not code-hardcoded)
# Fallback: the dict below (keeps your current behavior if config file is absent)
#
# Supported keys per ticker:
#   - company_pages: [urls...]
#   - tech_blogs: [urls...]
#   - careers: [urls...]
#   - github_orgs: [full GitHub org URLs...]
#   - github_org_hint: [org slugs like "jpmorganchase"...]
#   - name, sector (optional metadata)
# -------------------------------------------------------------------

DEFAULT_COMPANY_SOURCES: Dict[str, Dict[str, List[str]]] = {
    "JPM": {
        "name": "JPMorgan Chase",
        "sector": "Financial",
        "tech_blogs": ["https://www.jpmorgan.com/technology"],
        "github_orgs": ["https://github.com/jpmorganchase"],
        "careers": ["https://jpmorgan.com/careers"],
    },
    "GS": {
        "name": "Goldman Sachs",
        "sector": "Financial",
        "tech_blogs": ["https://developer.gs.com/", "https://developer.gs.com/blog"],
        "github_orgs": ["https://github.com/goldmansachs"],
        "careers": [],
    },
    "WMT": {
        "name": "Walmart",
        "sector": "Consumer",
        "tech_blogs": [
            "https://medium.com/walmartglobaltech",
            "https://tech.walmart.com",
            "https://medium.com/@walmartlabs",
            "https://medium.com/walmartglobaltech/cracking-the-code-boosting-airflow-efficiency-through-airflow-configuration-tuning-optimisation-9770b61c7b94",
        ],
        "github_orgs": ["https://github.com/walmart", "https://github.com/walmartlabs"],
        "careers": ["https://careers.walmart.com"],
    },
    "TGT": {
        "name": "Target",
        "sector": "Consumer",
        "tech_blogs": ["https://tech.target.com/", "https://tech.target.com/blog"],
        "github_orgs": ["https://github.com/target"],
        "careers": ["https://corporate.target.com/careers"],
    },
    "DE": {
        "name": "Deere & Company",
        "sector": "Industrials",
        "tech_blogs": [],
        "github_orgs": ["https://github.com/JohnDeere"],
        "careers": ["https://jobs.deere.com"],
    },
    "CAT": {
        "name": "Caterpillar Inc.",
        "sector": "Industrials",
        "tech_blogs": [],
        "github_orgs": [],
        "careers": ["https://www.caterpillar.com/en/careers.html"],
    },
    "UNH": {
        "name": "UnitedHealth Group",
        "sector": "Healthcare",
        "tech_blogs": [],
        "github_orgs": ["https://github.com/optum", "https://github.com/unitedhealthgroup"],
        "careers": ["https://careers.unitedhealthgroup.com"],
    },
    "HCA": {
        "name": "HCA Healthcare",
        "sector": "Healthcare",
        "tech_blogs": [],
        "github_orgs": [],
        "careers": ["https://careers.hcahealthcare.com"],
    },
    "ADP": {
        "name": "Automatic Data Processing",
        "sector": "Services",
        "tech_blogs": [],
        "github_orgs": ["https://github.com/adp"],
        "careers": ["https://jobs.adp.com"],
    },
    "PAYX": {
        "name": "Paychex Inc.",
        "sector": "Services",
        "tech_blogs": [],
        "github_orgs": [],
        "careers": ["https://www.paychex.com/careers"],
    
    },
    "NVDA": {
    "name": "NVIDIA Corporation",
    "sector": "Technology",
    "tech_blogs": ["https://developer.nvidia.com/blog", "https://blogs.nvidia.com"],
    "github_orgs": ["https://github.com/NVIDIA"],
    "careers": ["https://www.nvidia.com/en-us/about-nvidia/careers/"],
    },
    "DG": {
        "name": "Dollar General Corp",
        "sector": "Retail",
        "tech_blogs": [],
        "github_orgs": [],
        "careers": ["https://careers.dollargeneral.com"],
    },
    "GE": {
        "name": "General Electric Co",
        "sector": "Manufacturing",
        "tech_blogs": ["https://www.ge.com/news/reports"],
        "github_orgs": ["https://github.com/GeneralElectric"],
        "careers": ["https://jobs.gecareers.com"],
    },
}


def load_company_sources() -> Dict[str, Dict[str, List[str]]]:
    """
    Loads config/company_sources.json if present.
    Keeps a safe fallback to DEFAULT_COMPANY_SOURCES so your app never breaks.
    """
    cfg_path = Path("config/company_sources.json")
    if not cfg_path.exists():
        return DEFAULT_COMPANY_SOURCES

    try:
        import json

        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("company_sources.json must be a JSON object at root.")
        return data
    except Exception as e:
        logger.warning("Failed to load config/company_sources.json; using defaults.", extra={"err": str(e)})
        return DEFAULT_COMPANY_SOURCES


COMPANY_SOURCES: Dict[str, Dict[str, List[str]]] = load_company_sources()

# -------------------------------------------------------------------
# AI TECH TAXONOMY (keyword -> category)
# NOTE: Keep aligned with your notebook/taxonomy.
# -------------------------------------------------------------------
AI_TECHNOLOGIES: Dict[str, str] = {
    # Cloud ML / Platforms
    "aws sagemaker": "cloud_ml",
    "azure ml": "cloud_ml",
    "vertex ai": "cloud_ml",
    "databricks": "cloud_ml",
    # ML frameworks
    "tensorflow": "ml_framework",
    "pytorch": "ml_framework",
    "scikit-learn": "ml_framework",
    # Data platforms
    "snowflake": "data_platform",
    "apache spark": "data_platform",
    "spark": "data_platform",
    "hadoop": "data_platform",
    "kafka": "data_platform",
    # AI APIs / LLM ecosystem
    "openai": "ai_api",
    "anthropic": "ai_api",
    "hugging face": "ai_api",
    "huggingface": "ai_api",
    "transformers": "ai_api",
    "llm": "ai_api",
    "large language model": "ai_api",
    # Vector DBs
    "pinecone": "vector_db",
    "weaviate": "vector_db",
    "qdrant": "vector_db",
    # MLOps
    "mlflow": "mlops",
    "kubeflow": "mlops",
    "wandb": "mlops",
    "weights & biases": "mlops",
}

TECH_DISPLAY_NAMES: Dict[str, str] = {
    "aws sagemaker": "AWS SageMaker",
    "azure ml": "Azure ML",
    "vertex ai": "Vertex AI",
    "databricks": "Databricks",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "scikit-learn": "scikit-learn",
    "snowflake": "Snowflake",
    "apache spark": "Apache Spark",
    "spark": "Apache Spark",
    "hadoop": "Hadoop",
    "kafka": "Apache Kafka",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "hugging face": "Hugging Face",
    "huggingface": "Hugging Face",
    "transformers": "Transformers",
    "llm": "LLM",
    "large language model": "Large Language Model",
    "pinecone": "Pinecone",
    "weaviate": "Weaviate",
    "qdrant": "Qdrant",
    "mlflow": "MLflow",
    "kubeflow": "Kubeflow",
    "wandb": "Weights & Biases",
    "weights & biases": "Weights & Biases",
}


@dataclass
class TechnologyDetection:
    name: str
    category: str
    confidence: float
    source: str
    # keep a list of evidence urls for this tech (helps dedupe + evidence)
    urls: List[str] = field(default_factory=list)
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TechSignalCollector:
    """
    Teammate-style pipeline:
      ticker -> COMPANY_SOURCES -> urls -> detect -> score -> ExternalSignal

    Scoring (Case Study 2 style):
      - tech_score = min(#AI_tech * 10, 50)
      - category_score = min(#AI_categories * 12.5, 50)
      - total = tech_score + category_score  (0..100)
    """

    def __init__(self, timeout_s: float = 25.0):
        self.client = httpx.Client(
            timeout=timeout_s,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; OrgAIR collector)"},
        )

    # -----------------------------
    # Helpers
    # -----------------------------
    def _normalize(self, s: str) -> str:
        return " ".join((s or "").lower().split())

    def _extract_text_from_html(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return soup.get_text(" ", strip=True)

    def fetch_page_text(self, url: str) -> str:
        r = self.client.get(url)
        r.raise_for_status()
        return self._extract_text_from_html(r.text)

    def _label_source(self, url: str) -> str:
        u = url.lower()
        if "github.com" in u:
            return "GitHub"
        if "careers" in u or "jobs" in u:
            return "Careers"
        if "blog" in u or "medium.com" in u or "engineering" in u:
            return "Tech Blog"
        return "Company Website"

    def _contains_keyword(self, text_norm: str, keyword: str) -> bool:
        """
        Safer matching:
          - For very short tokens (like "llm"), use word boundaries.
          - For longer phrases, substring match is fine.
        """
        kw = self._normalize(keyword)
        if not kw:
            return False

        # word-boundary matching for short tokens or risky tokens
        if len(kw) <= 3 or kw in {"llm"}:
            # \b won't work perfectly for every unicode case, but is much safer than substring
            return re.search(rf"\b{re.escape(kw)}\b", text_norm) is not None

        return kw in text_norm

    # -----------------------------
    # GitHub repo scanning (no token required)
    # -----------------------------
    def fetch_github_repo_pages(self, org_url: str, max_repos: int = 5) -> List[Tuple[str, str]]:
        """
        Scrape the org repositories listing page (HTML) and fetch up to max_repos repo pages.
        Returns [(repo_url, repo_page_text), ...]
        """
        out: List[Tuple[str, str]] = []
        try:
            org_url = org_url.rstrip("/")
            repos_page = f"{org_url}?tab=repositories"
            html = self.client.get(repos_page).text
            soup = BeautifulSoup(html, "html.parser")

            # Typical selector for repo names on GitHub org repos tab
            links = soup.select('a[itemprop="name codeRepository"]')

            repo_urls: List[str] = []
            for a in links:
                href = a.get("href")
                if href and href.count("/") == 2:
                    repo_urls.append("https://github.com" + href.strip())
                if len(repo_urls) >= max_repos:
                    break

            for repo_url in repo_urls:
                try:
                    repo_html = self.client.get(repo_url).text
                    repo_text = self._extract_text_from_html(repo_html)
                    out.append((repo_url, repo_text))
                except Exception as e:
                    logger.debug("Repo page fetch failed", extra={"repo_url": repo_url, "err": str(e)})
                    continue
        except Exception as e:
            logger.debug("GitHub repo discovery failed", extra={"org_url": org_url, "err": str(e)})

        return out

    # -----------------------------
    # GitHub org auto-discovery (optional)
    # -----------------------------
    def discover_github_org_url(self, company_name: str) -> Optional[str]:
        """
        Best-effort GitHub org discovery using GitHub Search API.
        This is optional and may be rate limited; safe failure is fine.
        """
        try:
            q = company_name.strip()
            if not q:
                return None
            resp = self.client.get(
                "https://api.github.com/search/users",
                params={"q": f"{q} type:org", "per_page": 1},
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items") or []
            if not items:
                return None
            login = items[0].get("login")
            if not login:
                return None
            return f"https://github.com/{login}"
        except Exception as e:
            logger.debug("GitHub org discovery failed", extra={"company_name": company_name, "err": str(e)})
            return None

    # -----------------------------
    # URL building (config + backward compatible keys)
    # -----------------------------
    def build_urls_from_sources(self, ticker: str, company_name: str) -> List[str]:
        t = ticker.upper().strip()
        if t not in COMPANY_SOURCES:
            raise ValueError(f"Ticker '{t}' not present in COMPANY_SOURCES mapping.")

        src = COMPANY_SOURCES[t]
        urls: List[str] = []

        # support these keys
        for key in ("company_pages", "tech_blogs", "careers"):
            urls.extend(src.get(key, []) or [])

        # backward compatibility: if someone used "company_website" or similar
        for key in ("company_site", "company_website"):
            urls.extend(src.get(key, []) or [])

        # GitHub full URLs provided
        for gh_url in (src.get("github_orgs") or []):
            if gh_url:
                urls.append(gh_url.strip().rstrip("/"))

        # GitHub org hints provided as slugs
        for org in (src.get("github_org_hint") or []):
            org = (org or "").strip().strip("/")
            if org:
                urls.append(f"https://github.com/{org}")

        # If no GitHub info provided, try auto-discovery
        has_github = any("github.com" in (u or "").lower() for u in urls)
        if not has_github:
            gh = self.discover_github_org_url(company_name)
            if gh:
                urls.append(gh)

        # Dedupe preserve order
        clean: List[str] = []
        seen: Set[str] = set()
        for u in urls:
            u = (u or "").strip()
            if not u:
                continue
            if u not in seen:
                seen.add(u)
                clean.append(u)
        return clean

    # -----------------------------
    # Detection + scoring
    # -----------------------------
    def detect_ai_technologies(self, text: str, source: str, url: str) -> List[TechnologyDetection]:
        text_norm = self._normalize(text)
        detections: List[TechnologyDetection] = []

        for keyword, category in AI_TECHNOLOGIES.items():
            if self._contains_keyword(text_norm, keyword):
                detections.append(
                    TechnologyDetection(
                        name=TECH_DISPLAY_NAMES.get(keyword, keyword),
                        category=category,
                        confidence=0.85,
                        source=source,
                        urls=[url],
                    )
                )
        return detections

    def deduplicate(self, detections: List[TechnologyDetection]) -> List[TechnologyDetection]:
        """
        Dedupe by (name, category). Merge evidence URLs and keep the highest confidence.
        This avoids triple-counting the same tech across multiple pages.
        """
        merged: Dict[Tuple[str, str], TechnologyDetection] = {}

        for d in detections:
            key = (self._normalize(d.name), d.category)
            if key not in merged:
                merged[key] = d
                continue

            existing = merged[key]
            # merge urls
            for u in d.urls:
                if u not in existing.urls:
                    existing.urls.append(u)
            # keep best confidence (and source label from the best)
            if d.confidence > existing.confidence:
                existing.confidence = d.confidence
                existing.source = d.source
            merged[key] = existing

        # return stable order (first-seen order)
        return list(merged.values())

    def score(self, detections: List[TechnologyDetection]) -> Tuple[float, float, float, Set[str]]:
        categories = {d.category for d in detections}
        tech_score = min(len(detections) * 10.0, 50.0)
        category_score = min(len(categories) * 12.5, 50.0)
        total = round(tech_score + category_score, 1)
        return total, round(tech_score, 1), round(category_score, 1), categories

    # -----------------------------
    # Public API: analyze
    # -----------------------------
    def analyze_digital_presence(self, company_name: str, ticker: str) -> ExternalSignal:
        urls = self.build_urls_from_sources(ticker=ticker, company_name=company_name)

        all_detections: List[TechnologyDetection] = []
        failed_urls: List[str] = []
        urls_checked: List[str] = []

        for url in urls:
            try:
                src_label = self._label_source(url)
                text = self.fetch_page_text(url)
                urls_checked.append(url)
                all_detections.extend(self.detect_ai_technologies(text, src_label, url))

                # GitHub improvement: scan top repos for stronger stack evidence
                if "github.com" in url.lower():
                    for repo_url, repo_text in self.fetch_github_repo_pages(url, max_repos=5):
                        urls_checked.append(repo_url)
                        all_detections.extend(self.detect_ai_technologies(repo_text, "GitHub Repo", repo_url))

            except Exception as e:
                logger.warning("Tech signal fetch failed", extra={"url": url, "err": str(e)})
                failed_urls.append(url)

        all_detections = self.deduplicate(all_detections)
        total, tech_component, category_component, categories = self.score(all_detections)

        confidence = (
            round(sum(d.confidence for d in all_detections) / len(all_detections), 2)
            if all_detections else 0.5
        )

        return ExternalSignal(
            company_id=None,  # router sets this (same as job_signals)
            category=SignalCategory.DIGITAL_PRESENCE,
            source=getattr(SignalSource, "TECH_STACK_SCRAPE", SignalSource.COMPANY_WEBSITE),
            signal_date=datetime.now(timezone.utc),
            raw_value=f"{len(all_detections)} AI technologies detected from {len(urls)} seed sources (ticker={ticker})",
            normalized_score=total,
            confidence=confidence,
            metadata={
                "company_name": company_name,
                "ticker": ticker,
                "seed_urls": urls,                 # the configured starting points
                "urls_checked": urls_checked,      # includes GitHub repos
                "failed_urls": failed_urls,
                "tech_score_component": tech_component,
                "category_score_component": category_component,
                "categories_found": sorted(list(categories)),
                "ai_technologies": [
                    {
                        "name": d.name,
                        "category": d.category,
                        "confidence": d.confidence,
                        "source": d.source,
                        "evidence_urls": d.urls,
                        "detected_at": d.detected_at,
                    }
                    for d in all_detections
                ],
            },
        )
