

import httpx
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import structlog

from app.pipelines.collectors.base_collector import BaseLeadershipCollector
from app.models.leadership import AIIndicator, AIIndicatorType
from app.config import get_settings

logger = structlog.get_logger(__name__)


class NewsAPICollector(BaseLeadershipCollector):
    """
    Collect recent AI leadership news from NewsAPI.
    """
    
    AI_KEYWORDS = [
        'artificial intelligence', 'machine learning', 'AI strategy',
        'chief ai officer', 'AI initiative', 'data science',
        'deep learning', 'neural network', 'AI transformation'
    ]
    
    def __init__(self):
        super().__init__("NewsAPI", weight=0.10)
    
    # ✅ FIX: Disable NewsAPI (free tier has 426 errors)
        self.logger.info("NewsAPI disabled - free tier limitations (HTTP 426)")
        self.enabled = False
        self.api_key = None
        self.base_url = "https://newsapi.org/v2"
        self.client = httpx.AsyncClient(timeout=30.0)
        
    
    async def collect_leadership_data(
        self,
        company_name: str,
        ticker: str
    ) -> List[Dict]:
        """
        Search for AI leadership news about the company.
        
        Note: This doesn't discover executives, it validates/enriches them.
        Returns metadata about company AI activity.
        """
        
        if not self.enabled:
            self.logger.info("NewsAPI disabled (no API key)")
            return []
        
        self.logger.info("Searching news", company=company_name)
        
        try:
            # Search for company + AI keywords
            articles = await self._search_company_news(company_name)
            
            # Analyze articles
            signal_data = self._analyze_articles(articles, company_name)
            
            self.logger.info(
                "News search complete",
                company=company_name,
                articles_found=len(articles),
                signal_strength=signal_data['signal_strength']
            )
            
            return [signal_data]
            
        except Exception as e:
            self.logger.error("News search failed", company=company_name, error=str(e))
            return []
    
    async def _search_company_news(self, company_name: str) -> List[dict]:
        """Search for company news with AI keywords"""
        
        url = f"{self.base_url}/everything"
        
        # Last 6 months
        from_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
        
        # Build query - company name + AI keywords
        query = f'"{company_name}" AND (AI OR "artificial intelligence" OR "machine learning")'
        
        params = {
            'q': query,
            'from': from_date,
            'sortBy': 'relevancy',
            'language': 'en',
            'pageSize': 20,
            'apiKey': self.api_key
        }
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            articles = data.get('articles', [])
            
            return articles
            
        except httpx.HTTPError as e:
            self.logger.error("News API request failed", error=str(e))
            return []
    
    def _analyze_articles(self, articles: List[dict], company_name: str) -> Dict:
        """
        Analyze articles for AI leadership signals.
        
        Returns dict with signal metadata.
        """
        
        if not articles:
            return {
                'source': 'NewsAPI',
                'signal_strength': 0.0,
                'article_count': 0,
                'articles': [],
                'keywords_found': []
            }
        
        # Strong signals indicate real AI commitment
        strong_signals = [
            'chief ai officer', 'ai strategy', 'ai investment',
            'launches ai', 'ai initiative', 'ai center',
            'appoints', 'hires', 'names', 'announces'
        ]
        
        strong_count = 0
        keywords_found = set()
        relevant_articles = []
        
        for article in articles:
            title = article.get('title', '').lower()
            description = article.get('description', '').lower()
            content = f"{title} {description}"
            
            # Check for strong signals
            has_strong_signal = any(signal in content for signal in strong_signals)
            if has_strong_signal:
                strong_count += 1
                relevant_articles.append({
                    'title': article.get('title'),
                    'url': article.get('url'),
                    'publishedAt': article.get('publishedAt'),
                    'source': article.get('source', {}).get('name')
                })
            
            # Track keywords
            for keyword in self.AI_KEYWORDS:
                if keyword.lower() in content:
                    keywords_found.add(keyword)
        
        # Calculate signal strength (0.0 - 1.0)
        if strong_count > 0:
            # Strong articles = high signal
            signal_strength = min(1.0, strong_count * 0.3)
        else:
            # Just mentions = moderate signal
            signal_strength = min(0.5, len(articles) * 0.05)
        
        return {
            'source': 'NewsAPI',
            'signal_strength': signal_strength,
            'article_count': len(articles),
            'strong_signal_count': strong_count,
            'articles': relevant_articles[:5],  # Top 5
            'keywords_found': list(keywords_found)
        }
    
    async def enrich_executive(
        self,
        executive_name: str,
        company_name: str
    ) -> List[AIIndicator]:
        """
        Search for news mentions of specific executive in AI context.
        
        This enriches individual executives with recent activity signals.
        """
        
        if not self.enabled:
            return []
        
        self.logger.info("Searching executive news", name=executive_name)
        
        try:
            url = f"{self.base_url}/everything"
            
            from_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
            
            # Search for executive name + AI keywords
            query = f'"{executive_name}" AND "{company_name}" AND (AI OR "artificial intelligence" OR "machine learning")'
            
            params = {
                'q': query,
                'from': from_date,
                'sortBy': 'relevancy',
                'language': 'en',
                'pageSize': 10,
                'apiKey': self.api_key
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            articles = data.get('articles', [])
            
            if not articles:
                return []
            
            # If mentioned in AI context, add bonus indicator
            return [AIIndicator(
                type=AIIndicatorType.AI_KEYWORDS_ONLY,
                evidence=f"Mentioned in {len(articles)} AI-related news articles (last 6 months)",
                score=min(0.2, len(articles) * 0.03),  # Up to 0.2 bonus
                source='NewsAPI',
                confidence=0.7
            )]
            
        except Exception as e:
            self.logger.error("Executive news search failed", name=executive_name, error=str(e))
            return []
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()