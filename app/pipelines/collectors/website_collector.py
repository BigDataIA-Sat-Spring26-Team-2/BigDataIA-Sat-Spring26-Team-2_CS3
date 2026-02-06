import httpx
import re
from bs4 import BeautifulSoup
from typing import List, Optional
import structlog

from app.pipelines.collectors.base_collector import BaseLeadershipCollector
from app.models.leadership import ExecutiveProfile, AIIndicator, AIIndicatorType

logger = structlog.get_logger(__name__)


class CompanyWebsiteCollector(BaseLeadershipCollector):
    """Universal website scraper - works for all 10 companies."""
    
    ROLE_WEIGHTS = {
        'ceo': 1.0, 'chief executive': 1.0, 'chairman': 0.95, 'president': 0.95,
        'chief ai officer': 1.0, 'caio': 1.0,
        'chief technology officer': 0.9, 'cto': 0.9,
        'chief AI scientist': 0.95,
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
    
    def __init__(self):
        super().__init__("Company Website", weight=1.00)
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
           headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "en-US,en;q=0.9"
}

        )
    
    async def collect_leadership_data(self, company_name: str, ticker: str) -> List[ExecutiveProfile]:
        """Scrape company website - universal approach for all companies."""
        
        self.logger.info("🌐 Starting website scraping", company=company_name, ticker=ticker)
        
        urls = self._get_urls(ticker)
        if not urls:
            self.logger.warning("No URLs configured", ticker=ticker)
            return []
        
        all_executives = []

        for url in urls:
            is_org_chart = 'theofficialboard.com' in url

            try:
                response = await self.client.get(url, timeout=15.0)
                soup = BeautifulSoup(response.text, 'html.parser')

                execs = []

                if is_org_chart:
                    execs.extend(self._extract_org_chart(soup))
                else:
                    execs.extend(self._extract_structured(soup))
                    execs.extend(self._extract_css(soup))
                    execs.extend(self._extract_tables(soup))
                    execs.extend(self._extract_heuristic(soup))
                
                # Smart deduplication (handles "Beer" vs "Lori Beer")
                for e in execs:
                    is_duplicate = False
                    
                    for existing in all_executives:
                        # Exact match
                        if existing.name == e.name:
                            is_duplicate = True
                            break
                        
                        # Substring match (one name contains the other)
                        clean_new = re.sub(r'\s+', ' ', e.name).strip()
                        clean_existing = re.sub(r'\s+', ' ', existing.name).strip()

                        if clean_new in clean_existing or clean_existing in clean_new:
                            # Keep the longer, more complete name
                            if len(e.name) > len(existing.name):
                                all_executives.remove(existing)
                                is_duplicate = False  # Add the new one
                            else:
                                is_duplicate = True  # Skip the shorter one
                            break
                    
                    if not is_duplicate:
                        all_executives.append(e)
                
            except Exception as ex:
                self.logger.error("Page failed", url=url, error=str(ex))
        
        # Filter: keep executives with role_weight >= 0.70 (senior leadership only)
        filtered = [
            e for e in all_executives
            if e.role_weight >= 0.70
            or any(ind.score >= 0.6 for ind in e.indicators)
            ]

        final = filtered if filtered else all_executives

        # Count AI-relevant vs generic
        ai_count = len([e for e in final if 'AI-Relevant' in ' '.join(e.sources)])
        
        self.logger.info(
            "✅ Website scraping complete",
            ticker=ticker,
            total_found=len(all_executives),
            ai_relevant=ai_count,
            final_count=len(final)
        )
        
        return final
    
    
    def _get_urls(self, ticker: str) -> List[str]:
    
        return {
        'JPM': ['https://www.jpmorganchase.com/about/our-leadership'],
        
        'GS': [
            'https://www.goldmansachs.com/our-firm/leadership',
            'https://www.goldmansachs.com/our-firm/leadership/executive-officers'
        ],
        
        'WMT': ['https://corporate.walmart.com/about/leadership'],
        
        'TGT': ['https://corporate.target.com/about/leadership'],
        
        'UNH': ['https://wesdsabsets.exa.ai/websets/directory/unitedhealthcare-executives'],
        
        'ADP': ['https://www.adp.com/about-adp/leadership.aspx'],
        
        'PAYX': ['https://www.paychex.com/corporate/about-paychex/leadership'],
        
        'HCA': ['https://craft.co/unitedhealth/executives'], 
        
        'CAT': ['https://www.caterpillar.com/en/company/leadership.html'],
        
        'DE': ['https://www.deere.com/en/our-company/leadership/'],
        
        }.get(ticker.upper(), [])
    def _extract_org_chart(self, soup: BeautifulSoup) -> List[ExecutiveProfile]:
        execs = []

        for link in soup.select("a[href*='/profile/']"):
            name = link.get_text(strip=True)
            if not name or len(name) < 5:
                continue

        container = link.find_parent('div')
        text = container.get_text(" ", strip=True) if container else ""
        title = None
        for kw in ['Chief', 'CEO', 'CFO', 'CTO', 'Director', 'President']:
            if kw in text:
                title = kw
                break

        if not title:
            title = "Senior Executive"

        p = self._make_profile(name, title, text)
        if p:
            execs.append(p)

        return execs

    def _extract_structured(self, soup: BeautifulSoup) -> List[ExecutiveProfile]:
        """Extract from Schema.org JSON-LD"""
        execs = []
        
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict):
                    data = [data]
                
                for item in data:
                    if item.get('@type') == 'Person':
                        p = self._make_profile(item.get('name'), item.get('jobTitle'), item.get('description', ''))
                        if p:
                            execs.append(p)
            except:
                pass
        
        return execs
    
    def _extract_css(self, soup: BeautifulSoup) -> List[ExecutiveProfile]:
        """Extract from CSS classes"""
        execs = []
        
        for pattern in ['executive', 'team-member', 'leadership', 'bio', 'profile', 'officer']:
            for div in soup.find_all(['div', 'section', 'li'], class_=lambda x: x and pattern in str(x).lower()):
                
                # Find name
                name_tag = div.find(['h1', 'h2', 'h3', 'h4', 'strong'])
                if not name_tag:
                    continue
                
                name = name_tag.get_text().strip()
                
                # Find title in same container
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
        """Extract from tables"""
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
        """Aggressive heuristic extraction"""
        execs = []
        text = soup.get_text()
        
        # Try multiple patterns
        patterns = [
            # Name, Title
            r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s+)?[A-Z][a-z]+)\s*,\s*([^\n]{5,120}(?:Officer|President|CEO|CTO|CIO|CDO|CFO|COO|Chief))',
            
            # Name \n Title  
            r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*\n+\s*([^\n]{5,100}(?:Officer|President|CEO|CTO|CIO|CDO|CFO|COO|Chief))',
            
            # Name Title (no separator)
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(Chief\s+\w+\s+Officer)',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.MULTILINE):
                name = match.group(1).strip()
                name = re.sub(r'\s+', ' ', name)
                title = match.group(2).strip()
                title = re.sub(r'\s+', ' ', title)[:150]
                if len(name)<2:
                    continue
                
                p = self._make_profile(name, title, '')
                if p and not any(e.name == p.name for e in execs):
                    execs.append(p)
        
        return execs
    
    def _make_profile(self, name: str, title: str, bio: str) -> Optional[ExecutiveProfile]:
        """Create profile with validation"""
        
        if not name or not title:
            return None
        
        # Validate name
        if not self._is_valid_name(name):
            return None
        
        # Calculate role weight
        role_weight = self._get_role_weight(title)
        
        # Skip low-level roles
        if role_weight < 0.65:
            return None
        
        indicators = self._detect_ai(title, bio)


        
        # Determine if AI-relevant
        is_ai_relevant = self._is_ai_relevant_role(title, indicators)
        name = re.sub(r'\s+', ' ', name).strip()
        
        # Mark source type
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
        """Validate executive name"""
        
        if not name or len(name) < 5 or len(name) > 50:
            return False
        
        # Must have at least 2 words
        words = name.split()
        if len(words) < 2:
            return False
        
        # Each word must be at least 2 characters (excludes "B. Beer" → "Beer")
        for word in words:
            clean_word = word.replace('.', '').replace(',', '')
            if clean_word and len(clean_word) < 2:
                return False
        
        name_lower = name.lower()
        
        # Reject non-names
        bad = ['investor','committee','home','about','global']
        if any(b in name_lower for b in bad):
            return False
        
        # Must not be all caps
        if name.isupper():
            return False
        
        # Must have capitalized words
        if not any(w[0].isupper() for w in words if w):
            return False
        
        # Must NOT contain title words in name
        title_words = ['ceo', 'cfo', 'cto', 'cio', 'president', 'officer', 'director', 'chief']
        name_words_lower = [w.lower() for w in words if len(w) > 2]
        if any(tw in name_words_lower for tw in title_words):
            return False
        
        return True
    
    def _get_role_weight(self, title: str) -> float:
        """Get role weight"""
        
        t = title.lower()
        
        for key, weight in self.ROLE_WEIGHTS.items():
            if key in t:
                return weight
        
        # Partials for truncated titles
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
        """
        Check if executive role is AI-relevant.
        
        Returns True if:
        1. Title contains AI keywords
        2. Title is tech C-suite (CTO, CIO, CDO, Chief Data)
        3. Executive has AI company background
        
        Returns False for:
        - CEO, CFO, COO, Presidents (unless they have AI background)
        """
        
        title_lower = title.lower()
        
        # Tier 1: AI-Specific titles (ALWAYS include)
        ai_titles = [
            'chief ai officer', 'caio',
            'chief ai scientist', 'chief artificial intelligence', 'artificial intelligence', 'machine learning',
            'data science', 'chief data', 'chief analytics'
        ]
        
        if any(kw in title_lower if isinstance(kw, str) else re.search(kw, title_lower) for kw in ai_titles):
            return True
        
        # Tier 2: Tech C-Suite (ALWAYS include)
        tech_csuite = [
            'chief technology officer', 'cto',
            'chief information officer', 'cio',
            'chief digital officer', 'cdo',
            'chief information', 'chief technology','chief digital','chief data'
        ]
        
        if any(kw in title_lower for kw in tech_csuite):
            return True
        
        # Tier 3: AI Company Background (INCLUDE if strong indicator)
        # if indicators:
        #     max_score = max(ind.score for ind in indicators)
        #     if max_score >= 0.6:
        #         return True

        
        # Everything else is NOT AI-relevant
        return False
    
    def _detect_ai(self, title: str, bio: str) -> List[AIIndicator]:
        """Detect ALL AI indicators"""
        
        indicators = []
        t = title.lower()
        b = bio.lower()
        
        # 1. Chief AI Officer (1.0)
        if re.search(r'chief ai officer|chief artificial intelligence|caio', t):
            return [AIIndicator(
                type=AIIndicatorType.CHIEF_AI_OFFICER,
                evidence=title,
                score=1.0,
                source='Company Website',
                confidence=0.95
            )]
        
        # 2. AI/ML in title (0.7)
        # Only match actual AI terms in title0
        if re.search(r'artificial intelligence|machine learning|\sai\s|^ai\s|\sai$', t):
            indicators.append(AIIndicator(
            type=AIIndicatorType.AI_ROLE_TITLE,
            evidence=title,
            score=1.0,
            source='Company Website',
            confidence=0.85
    ))
        # 3. Chief Data & Analytics (0.8 - HIGH)
        if re.search(r'chief data|chief analytics|data.*analytics', t):
            if not indicators:
                indicators.append(AIIndicator(
                    type=AIIndicatorType.DATA_ANALYTICS_LEADERSHIP,
                    evidence=title,
                    score=0.95,
                    source='Company Website',
                    confidence=0.9
                ))
        
        # 4. CTO/CIO/CDO (0.7 - Tech C-Suite)
        if re.search(r'chief technology|chief information|chief digital|global cto|global cio', t):
            if not indicators:
                indicators.append(AIIndicator(
                    type=AIIndicatorType.TECH_LEADERSHIP,
                    evidence=title,
                    score=0.8,
                    source='Company Website',
                    confidence=0.85
                ))
        
        # 5. AI company background (0.9 - VERY HIGH)
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
        
        # 6. PhD (0.8)
        if re.search(r'ph\.?d|doctorate', b):
            if re.search(r'computer science|ai|ml|statistics|data science', b):
                indicators.append(AIIndicator(
                    type=AIIndicatorType.PHD_AI_ML,
                    evidence="PhD in CS/AI/ML",
                    score=0.8,
                    source='Company Website',
                    confidence=0.75
                ))
        
        # 7. Generic executive baseline (0.2-0.3)
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
