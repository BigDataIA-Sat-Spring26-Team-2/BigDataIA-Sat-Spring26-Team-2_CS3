import httpx
import re
from bs4 import BeautifulSoup
from typing import List, Optional
import structlog
from playwright.async_api import async_playwright
import asyncio

from app.pipelines.collectors.base_collector import BaseLeadershipCollector
from app.models.leadership import ExecutiveProfile, AIIndicator, AIIndicatorType

logger = structlog.get_logger(__name__)


class CompanyWebsiteCollector(BaseLeadershipCollector):
    
    ROLE_WEIGHTS = {
        'ceo': 1.0, 'chief executive': 1.0, 'chairman': 0.95, 'president': 0.95,
        'chief ai officer': 1.0, 'caio': 1.0,
        'chief technology officer': 0.9, 'cto': 0.9,
        'chief ai scientist': 0.95,
        'chief information officer': 0.85, 'cio': 0.85,
        'chief digital officer': 0.85, 'cdo': 0.85,
        'chief data officer': 0.85,
        'chief operating officer': 0.90, 'coo': 0.90,
        'chief financial officer': 0.75, 'cfo': 0.75,
        'vice president': 0.7, 'vp': 0.7,
        'senior vice president': 0.75, 'svp': 0.75,
    }
    
    AI_COMPANIES = [
        'google', 'alphabet', 'meta', 'facebook', 'amazon', 'aws',
        'microsoft', 'openai', 'anthropic', 'deepmind', 'nvidia',
        'ibm', 'oracle', 'salesforce', 'intel', 'cisco'
    ]
    
    # Companies known to need Playwright (JavaScript-heavy sites)
    REQUIRES_PLAYWRIGHT = ['UNH', 'GS', 'CAT', 'DE']
    
    def __init__(self):
        super().__init__("Company Website", weight=1.00)
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept-Language": "en-US,en;q=0.9"
            }
        )
    
    async def collect_leadership_data(self, company_name: str, ticker: str) -> List[ExecutiveProfile]:
        
        self.logger.info("Starting website scraping", company=company_name, ticker=ticker)
        
        urls = self._get_urls(ticker)
        if not urls:
            self.logger.warning("No URLs configured", ticker=ticker)
            return []
        
        all_executives = []
        use_playwright = ticker.upper() in self.REQUIRES_PLAYWRIGHT
        
        for url in urls:
            try:
                if use_playwright:
                    self.logger.info("Using Playwright", url=url)
                    soup = await self._fetch_with_playwright(url)
                else:
                    self.logger.info("Using httpx", url=url)
                    soup = await self._fetch_with_httpx(url)
                
                if not soup:
                    self.logger.warning("Failed to fetch", url=url)
                    continue
                
                execs = []
                execs.extend(self._extract_structured(soup))
                execs.extend(self._extract_css(soup))
                execs.extend(self._extract_tables(soup))
                execs.extend(self._extract_heuristic(soup))
                
                # Deduplicate
                for e in execs:
                    is_dup = False
                    
                    for existing in all_executives:
                        if existing.name == e.name:
                            is_dup = True
                            break
                        
                        clean_new = re.sub(r'\s+', ' ', e.name).strip()
                        clean_existing = re.sub(r'\s+', ' ', existing.name).strip()
                        
                        if clean_new in clean_existing or clean_existing in clean_new:
                            if len(e.name) > len(existing.name):
                                all_executives.remove(existing)
                                is_dup = False
                            else:
                                is_dup = True
                            break
                    
                    if not is_dup:
                        all_executives.append(e)
                
            except Exception as ex:
                self.logger.error("Page failed", url=url, error=str(ex))
        
        # Filter senior leadership
        filtered = [
            e for e in all_executives
            if e.role_weight >= 0.70 or any(ind.score >= 0.6 for ind in e.indicators)
        ]
        
        final = filtered if filtered else all_executives
        
        ai_count = len([e for e in final if 'AI-Relevant' in ' '.join(e.sources)])
        
        self.logger.info(
            "Website scraping complete",
            ticker=ticker,
            total_found=len(all_executives),
            ai_relevant=ai_count,
            final_count=len(final),
            method="playwright" if use_playwright else "httpx"
        )
        
        return final
    
    async def _fetch_with_playwright(self, url: str) -> Optional[BeautifulSoup]:
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-blink-features=AutomationControlled'
                    ]
                )
                
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    viewport={'width': 1920, 'height': 1080}
                )
                
                page = await context.new_page()
                
                await page.set_extra_http_headers({
                    'Accept-Language': 'en-US,en;q=0.9'
                })
                
                await page.goto(url, wait_until='networkidle', timeout=30000)
                
                await page.wait_for_timeout(2000)
                
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
                await page.wait_for_timeout(1000)
                
                html = await page.content()
                
                await browser.close()
                
                return BeautifulSoup(html, 'html.parser')
                
        except Exception as e:
            logger.error("Playwright fetch failed", url=url, error=str(e))
            return None
    
    async def _fetch_with_httpx(self, url: str) -> Optional[BeautifulSoup]:
        
        try:
            response = await self.client.get(url, timeout=15.0)
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            logger.error("httpx fetch failed", url=url, error=str(e))
            return None
    
    def _get_urls(self, ticker: str) -> List[str]:
        return {
            'JPM': ['https://www.jpmorganchase.com/about/our-leadership'],
            'GS': [
                'https://www.goldmansachs.com/our-firm/our-people-and-leadership/leadership',
            ],
            'WMT': ['https://corporate.walmart.com/about/leadership'],
            'TGT': ['https://corporate.target.com/about/leadership'],
            'UNH': [],
            'ADP': ['https://www.adp.com/about-adp/leadership.aspx'],
            'PAYX': ['https://www.paychex.com/newsroom/executive-bios'],
            'HCA': [],
            'CAT': ['https://www.caterpillar.com/en/company/governance/officers.html'],
            'DE': ['https://about.deere.com/en-us/explore-john-deere/leadership'],
        }.get(ticker.upper(), [])
    
    def _extract_structured(self, soup: BeautifulSoup) -> List[ExecutiveProfile]:
        execs = []
        
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict):
                    data = [data]
                
                for item in data:
                    if item.get('@type') == 'Person':
                        p = self._make_profile(
                            item.get('name'),
                            item.get('jobTitle'),
                            item.get('description', '')
                        )
                        if p:
                            execs.append(p)
            except:
                pass
        
        return execs
    
    def _extract_css(self, soup: BeautifulSoup) -> List[ExecutiveProfile]:
        execs = []
        
        for pattern in ['executive', 'team-member', 'leadership', 'bio', 'profile', 'officer']:
            for div in soup.find_all(['div', 'section', 'li'], 
                                     class_=lambda x: x and pattern in str(x).lower()):
                
                name_tag = div.find(['h1', 'h2', 'h3', 'h4', 'strong'])
                if not name_tag:
                    continue
                
                name = name_tag.get_text().strip()
                
                text = div.get_text()
                title = None
                for line in text.split('\n'):
                    if any(kw in line for kw in ['Officer', 'President', 'CEO', 'CTO', 'CIO']):
                        if line.strip() != name and len(line) < 150:
                            title = line.strip()
                            break
                
                if name and title:
                    p = self._make_profile(name, title, text)
                    if p:
                        execs.append(p)
        
        return execs
    
    def _extract_tables(self, soup: BeautifulSoup) -> List[ExecutiveProfile]:
        execs = []
        
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                
                if len(cells) >= 2:
                    name = cells[0].get_text().strip()
                    title = cells[1].get_text().strip()
                    
                    if 'name' not in name.lower():
                        p = self._make_profile(name, title, ' '.join(c.get_text() for c in cells))
                        if p:
                            execs.append(p)
        
        return execs
    
    def _extract_heuristic(self, soup: BeautifulSoup) -> List[ExecutiveProfile]:
        execs = []
        text = soup.get_text()
        
        patterns = [
            r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s+)?[A-Z][a-z]+)\s*,\s*([^\n]{5,120}(?:Officer|President|CEO|CTO|CIO|CDO|CFO|COO|Chief))',
            r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*\n+\s*([^\n]{5,100}(?:Officer|President|CEO|CTO|CIO|CDO|CFO|COO|Chief))',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(Chief\s+\w+\s+Officer)',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.MULTILINE):
                name = match.group(1).strip()
                name = re.sub(r'\s+', ' ', name)
                title = match.group(2).strip()
                title = re.sub(r'\s+', ' ', title)[:150]
                
                if len(name) < 2:
                    continue
                
                p = self._make_profile(name, title, '')
                if p and not any(e.name == p.name for e in execs):
                    execs.append(p)
        
        return execs
    
    def _make_profile(self, name: str, title: str, bio: str) -> Optional[ExecutiveProfile]:
        
        if not name or not title:
            return None
        
        if not self._is_valid_name(name):
            return None
        
        role_weight = self._get_role_weight(title)
        
        if role_weight < 0.65:
            return None
        
        indicators = self._detect_ai(title, bio)
        
        is_ai_relevant = self._is_ai_relevant_role(title, indicators)
        name = re.sub(r'\s+', ' ', name).strip()
        
        source = 'Company Website (AI-Relevant)' if is_ai_relevant else 'Company Website (Generic)'
        
        profile = ExecutiveProfile(
            name=name,
            title=title,
            role_weight=role_weight,
            indicators=indicators,
            sources=[source]
        )
        profile.calculate_max_score()
        
        return profile
    
    def _is_valid_name(self, name: str) -> bool:
        
        if not name or len(name) < 5 or len(name) > 50:
            return False
        
        words = name.split()
        if len(words) < 2:
            return False
        
        for word in words:
            clean = word.replace('.', '').replace(',', '')
            if clean and len(clean) < 2:
                return False
        
        name_lower = name.lower()
        
        bad = ['investor', 'committee', 'home', 'about', 'global']
        if any(b in name_lower for b in bad):
            return False
        
        if name.isupper():
            return False
        
        if not any(w[0].isupper() for w in words if w):
            return False
        
        title_words = ['ceo', 'cfo', 'cto', 'cio', 'president', 'officer', 'director', 'chief']
        name_words_lower = [w.lower() for w in words if len(w) > 2]
        if any(tw in name_words_lower for tw in title_words):
            return False
        
        return True
    
    def _get_role_weight(self, title: str) -> float:
        
        t = title.lower()
        
        for key, weight in self.ROLE_WEIGHTS.items():
            if key in t:
                return weight
        
        if 'chief executive' in t: return 1.0
        if 'chief technology' in t or 'chief information' in t: return 0.9
        if 'ceo' in t: return 1.0
        if 'chief data' in t or 'chief digital' in t: return 0.85
        if 'chief operating' in t: return 0.9
        if 'chief ai scientist' in t: return 0.95
        if 'president' in t and 'vice' not in t: return 0.95
        if 'vice president' in t: return 0.7
        if 'senior vice president' in t: return 0.75
        if 'ai officer' in t: return 0.9
        if 'ai lead' in t: return 0.8
        if 'ai research' in t: return 0.7
        if 'director' in t: return 0.65
        
        return 0.4
    
    def _is_ai_relevant_role(self, title: str, indicators: List[AIIndicator]) -> bool:
        
        title_lower = title.lower()
        
        ai_titles = [
            'chief ai officer', 'caio',
            'chief ai scientist', 'chief artificial intelligence', 'artificial intelligence', 'machine learning',
            'data science', 'chief data', 'chief analytics',
            'analytics, and ai', 'analytics and ai', ', ai', 'data, analytics',
            'head of ai', 'vp of ai', 'vp ai', 'svp ai',
        ]
        
        if any(kw in title_lower for kw in ai_titles):
            return True
        
        tech_csuite = [
            'chief technology officer', 'cto',
            'chief information officer', 'cio',
            'chief digital officer', 'cdo',
            'chief information', 'chief technology', 'chief digital', 'chief data'
        ]
        
        if any(kw in title_lower for kw in tech_csuite):
            return True
        
        return False
    
    def _detect_ai(self, title: str, bio: str) -> List[AIIndicator]:
        
        indicators = []
        t = title.lower()
        b = bio.lower()
        
        if re.search(r'chief ai officer|chief artificial intelligence|caio', t):
            return [AIIndicator(
                type=AIIndicatorType.CHIEF_AI_OFFICER,
                evidence=title,
                score=1.0,
                source='Company Website',
                confidence=0.95
            )]
        
        if re.search(r'artificial intelligence|machine learning|\sai\s|^ai\s|\sai$', t):
            indicators.append(AIIndicator(
                type=AIIndicatorType.AI_ROLE_TITLE,
                evidence=title,
                score=1.0,
                source='Company Website',
                confidence=0.85
            ))
        
        if re.search(r'chief data|chief analytics|data.*analytics', t):
            if not indicators:
                indicators.append(AIIndicator(
                    type=AIIndicatorType.DATA_ANALYTICS_LEADERSHIP,
                    evidence=title,
                    score=0.95,
                    source='Company Website',
                    confidence=0.9
                ))
        
        if re.search(r'chief technology|chief information|chief digital|global cto|global cio', t):
            if not indicators:
                indicators.append(AIIndicator(
                    type=AIIndicatorType.TECH_LEADERSHIP,
                    evidence=title,
                    score=0.8,
                    source='Company Website',
                    confidence=0.85
                ))
        
        for company in self.AI_COMPANIES:
            if re.search(rf'\b{company}\b', b, re.IGNORECASE):
                indicators.append(AIIndicator(
                    type=AIIndicatorType.AI_COMPANY_VETERAN,
                    evidence=f"Previously at {company.title()}",
                    score=0.9,
                    source='Company Website',
                    confidence=0.8
                ))
                return indicators
        
        if re.search(r'ph\.?d|doctorate', b):
            if re.search(r'computer science|ai|ml|statistics|data science', b):
                indicators.append(AIIndicator(
                    type=AIIndicatorType.PHD_AI_ML,
                    evidence="PhD in CS/AI/ML",
                    score=0.8,
                    source='Company Website',
                    confidence=0.75
                ))
        
        if not indicators:
            if re.search(r'chief executive|ceo|chairman', t):
                score = 0.30
            elif re.search(r'president|chief operating', t):
                score = 0.25
            elif re.search(r'chief financial|cfo', t):
                score = 0.20
            else:
                score = 0.10
            
            indicators.append(AIIndicator(
                type=AIIndicatorType.AI_KEYWORDS_ONLY,
                evidence=f"Senior executive baseline: {title}",
                score=score,
                source='Company Website',
                confidence=0.7
            ))
        
        return indicators
    
    async def close(self):
        await self.client.aclose()