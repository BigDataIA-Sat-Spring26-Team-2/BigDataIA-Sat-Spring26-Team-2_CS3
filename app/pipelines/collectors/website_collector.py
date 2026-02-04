
import httpx
import re
from bs4 import BeautifulSoup
from typing import List, Optional, Dict
import structlog

from app.pipelines.collectors.base_collector import BaseLeadershipCollector
from app.models.leadership import ExecutiveProfile, AIIndicator, AIIndicatorType

logger = structlog.get_logger(__name__)


class CompanyWebsiteCollector(BaseLeadershipCollector):
    """
    Scrape company website for leadership information.
    
    This is the primary source (90% weight) for leadership signals.
    """
    
    # Common leadership page URL patterns
    LEADERSHIP_URL_PATTERNS = [
        '/leadership',
        '/about/leadership',
        '/about/management',
        '/company/leadership',
        '/our-team',
        '/about-us/leadership',
        '/investor-relations/leadership',
        '/about/executive-team',
        '/company/management'
    ]
    
    # Role weights for scoring
    ROLE_WEIGHTS = {
        'ceo': 1.0,
        'chief executive': 1.0,
        'president': 0.95,
        'chief ai officer': 1.0,
        'caio': 1.0,
        'chief technology officer': 0.9,
        'cto': 0.9,
        'chief information officer': 0.85,
        'cio': 0.85,
        'chief digital officer': 0.85,
        'cdo': 0.85,
        'chief data officer': 0.85,
        'vice president': 0.7,
        'vp': 0.7,
        'senior vice president': 0.75,
        'svp': 0.75,
        'director': 0.5,
    }
    
    # AI indicator patterns
    AI_COMPANIES = [
        'google', 'alphabet', 'meta', 'facebook', 'amazon', 'aws',
        'microsoft', 'openai', 'anthropic', 'deepmind', 'nvidia',
        'tesla', 'apple', 'ibm', 'oracle', 'salesforce'
    ]
    
    def __init__(self):
        super().__init__("Company Website", weight=0.90)
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )
    
    async def collect_leadership_data(
        self,
        company_name: str,
        ticker: str
    ) -> List[ExecutiveProfile]:
        """
        Scrape company website for leadership information.
        """
        self.logger.info("Starting website scraping", company=company_name, ticker=ticker)
        
        try:
            # Step 1: Determine company domain
            domain = self._get_company_domain(company_name, ticker)
            
            if not domain:
                self.logger.warning("Could not determine domain", company=company_name)
                return []
            
            self.logger.info("Domain found", domain=domain)
            
            # Step 2: Find leadership page
            leadership_url = await self._find_leadership_page(domain)
            
            if not leadership_url:
                self.logger.warning("Leadership page not found", domain=domain)
                return []
            
            self.logger.info("Leadership page found", url=leadership_url)
            
            # Step 3: Scrape leadership page
            executives = await self._scrape_leadership_page(leadership_url)
            
            self.logger.info(
                "Website scraping complete",
                company=company_name,
                executives_found=len(executives)
            )
            
            return executives
            
        except Exception as e:
            self.logger.error("Website scraping failed", company=company_name, error=str(e))
            return []
    
    def _get_company_domain(self, company_name: str, ticker: str) -> Optional[str]:
        """
        Determine company domain from name/ticker.
        
        Uses common patterns - you can enhance with a lookup table later.
        """
        # Manual mapping for your 10 companies
        DOMAIN_MAP = {
            'JPM': 'https://www.jpmorganchase.com',
            'GS': 'https://www.goldmansachs.com',
            'WMT': 'https://corporate.walmart.com',
            'TGT': 'https://corporate.target.com',
            'UNH': 'https://www.unitedhealthgroup.com',
            'ADP': 'https://www.adp.com',
            'PAYX': 'https://www.paychex.com',
            'HCA': 'https://hcahealthcare.com',
            'CAT': 'https://www.caterpillar.com',
            'DE': 'https://www.deere.com',
        }
        
        return DOMAIN_MAP.get(ticker.upper())
    
    async def _find_leadership_page(self, domain: str) -> Optional[str]:
        """
        Find the leadership/management page on the website.
        """
        # Try common URL patterns
        for pattern in self.LEADERSHIP_URL_PATTERNS:
            url = f"{domain}{pattern}"
            
            try:
                response = await self.client.get(url, timeout=10.0)
                if response.status_code == 200:
                    self.logger.info("Leadership page found", url=url)
                    return url
            except Exception as e:
                self.logger.debug("URL not found", url=url, error=str(e))
                continue
        
        # If not found, try to parse homepage for links
        try:
            response = await self.client.get(domain, timeout=10.0)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for links containing leadership keywords
            for link in soup.find_all('a', href=True):
                href = link['href'].lower()
                text = link.get_text().lower()
                
                keywords = ['leadership', 'management', 'team', 'executive', 'officers']
                if any(kw in href or kw in text for kw in keywords):
                    # Build full URL
                    if href.startswith('http'):
                        return href
                    elif href.startswith('/'):
                        return f"{domain}{href}"
                    else:
                        return f"{domain}/{href}"
        except Exception as e:
            self.logger.error("Homepage parsing failed", domain=domain, error=str(e))
        
        return None
    
    async def _scrape_leadership_page(self, url: str) -> List[ExecutiveProfile]:
        """
        Parse leadership page HTML to extract executive information.
        """
        try:
            response = await self.client.get(url, timeout=15.0)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            executives = []
            
            # Strategy 1: Try structured data (Schema.org)
            structured_execs = self._extract_structured_data(soup)
            if structured_execs:
                executives.extend(structured_execs)
                self.logger.info("Used structured data extraction", count=len(structured_execs))
            
            # Strategy 2: CSS class patterns
            if not executives:
                css_execs = self._extract_from_css_classes(soup)
                if css_execs:
                    executives.extend(css_execs)
                    self.logger.info("Used CSS class extraction", count=len(css_execs))
            
            # Strategy 3: Table parsing
            if not executives:
                table_execs = self._extract_from_tables(soup)
                if table_execs:
                    executives.extend(table_execs)
                    self.logger.info("Used table extraction", count=len(table_execs))
            
            # Strategy 4: Heuristic extraction (fallback)
            if not executives:
                heuristic_execs = self._extract_heuristic(soup)
                if heuristic_execs:
                    executives.extend(heuristic_execs)
                    self.logger.info("Used heuristic extraction", count=len(heuristic_execs))
            
            return executives
            
        except Exception as e:
            self.logger.error("Page parsing failed", url=url, error=str(e))
            return []
    
    def _extract_structured_data(self, soup: BeautifulSoup) -> List[ExecutiveProfile]:
        """Extract from Schema.org JSON-LD structured data"""
        executives = []
        
        # Look for JSON-LD script tags
        scripts = soup.find_all('script', type='application/ld+json')
        
        for script in scripts:
            try:
                import json
                data = json.loads(script.string)
                
                # Handle both single object and list
                if isinstance(data, dict):
                    data = [data]
                
                for item in data:
                    if item.get('@type') == 'Person':
                        profile = self._create_profile_from_structured(item)
                        if profile:
                            executives.append(profile)
            except:
                continue
        
        return executives
    
    def _create_profile_from_structured(self, data: dict) -> Optional[ExecutiveProfile]:
        """Create profile from structured data"""
        name = data.get('name')
        title = data.get('jobTitle')
        
        if not name or not title:
            return None
        
        # Get bio/description if available
        bio = data.get('description', '')
        
        role_weight = self._calculate_role_weight(title)
        indicators = self._detect_ai_indicators(title, bio)
        
        profile = ExecutiveProfile(
            name=name,
            title=title,
            role_weight=role_weight,
            indicators=indicators,
            sources=['Company Website (Structured Data)']
        )
        profile.calculate_max_score()
        
        return profile
    
    def _extract_from_css_classes(self, soup: BeautifulSoup) -> List[ExecutiveProfile]:
        """Extract from common CSS class patterns"""
        executives = []
        
        # Common class patterns for executive containers
        class_patterns = [
            'executive', 'team-member', 'leadership', 'bio',
            'profile', 'person', 'officer', 'management'
        ]
        
        for pattern in class_patterns:
            containers = soup.find_all(
                ['div', 'section', 'article'],
                class_=lambda x: x and pattern in str(x).lower()
            )
            
            for container in containers:
                profile = self._extract_profile_from_container(container)
                if profile and not any(e.name == profile.name for e in executives):
                    executives.append(profile)
        
        return executives
    
    def _extract_profile_from_container(self, container) -> Optional[ExecutiveProfile]:
        """Extract executive profile from HTML container"""
        # Extract name (usually in h2, h3, h4, or strong tag)
        name_elem = container.find(['h2', 'h3', 'h4', 'strong', 'span'], 
                                   class_=lambda x: x and 'name' in str(x).lower())
        if not name_elem:
            name_elem = container.find(['h2', 'h3', 'h4'])
        
        if not name_elem:
            return None
        
        name = name_elem.get_text().strip()
        
        # Extract title
        title_elem = container.find(
            ['p', 'span', 'div'],
            class_=lambda x: x and any(kw in str(x).lower() for kw in ['title', 'position', 'role'])
        )
        
        if not title_elem:
            # Look for text with common title keywords
            all_text = container.get_text()
            for line in all_text.split('\n'):
                if any(kw in line for kw in ['Officer', 'President', 'Director', 'Vice President', 'CEO', 'CTO', 'CIO']):
                    title = line.strip()
                    break
            else:
                title = 'Executive'
        else:
            title = title_elem.get_text().strip()
        
        # Get full text for bio analysis
        bio_text = container.get_text()
        
        role_weight = self._calculate_role_weight(title)
        indicators = self._detect_ai_indicators(title, bio_text)
        
        profile = ExecutiveProfile(
            name=name,
            title=title,
            role_weight=role_weight,
            indicators=indicators,
            sources=['Company Website']
        )
        profile.calculate_max_score()
        
        return profile
    
    def _extract_from_tables(self, soup: BeautifulSoup) -> List[ExecutiveProfile]:
        """Extract from table format"""
        executives = []
        
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                
                if len(cells) < 2:
                    continue
                
                name = cells[0].get_text().strip()
                title = cells[1].get_text().strip()
                
                # Skip header rows
                if 'name' in name.lower() or 'officer' in name.lower():
                    continue
                
                # Get additional context if available
                bio_text = ' '.join(cell.get_text() for cell in cells)
                
                role_weight = self._calculate_role_weight(title)
                indicators = self._detect_ai_indicators(title, bio_text)
                
                profile = ExecutiveProfile(
                    name=name,
                    title=title,
                    role_weight=role_weight,
                    indicators=indicators,
                    sources=['Company Website (Table)']
                )
                profile.calculate_max_score()
                
                executives.append(profile)
        
        return executives
    
    def _extract_heuristic(self, soup: BeautifulSoup) -> List[ExecutiveProfile]:
        """Heuristic extraction as fallback"""
        executives = []
        
        # Pattern: Capitalized name followed by title with "Officer" or "President"
        text = soup.get_text()
        
        # Pattern: Name (capitalized) followed by comma and title
        pattern = r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)[\s,]+([^.\n]*?(?:Officer|President|Director|CEO|CTO|CIO|CDO)[^\n.]*)'
        
        matches = re.finditer(pattern, text)
        
        for match in matches:
            name = match.group(1).strip()
            title = match.group(2).strip()
            
            # Basic validation
            if len(name.split()) < 2:  # Need first and last name
                continue
            
            role_weight = self._calculate_role_weight(title)
            indicators = self._detect_ai_indicators(title, '')
            
            profile = ExecutiveProfile(
                name=name,
                title=title,
                role_weight=role_weight,
                indicators=indicators,
                sources=['Company Website (Heuristic)']
            )
            profile.calculate_max_score()
            
            # Avoid duplicates
            if not any(e.name == profile.name for e in executives):
                executives.append(profile)
        
        return executives[:15]  # Limit to top 15 to avoid noise
    
    def _calculate_role_weight(self, title: str) -> float:
        """Calculate role weight based on title"""
        title_lower = title.lower()
        
        # Check for exact matches first
        for key, weight in self.ROLE_WEIGHTS.items():
            if key in title_lower:
                return weight
        
        # Default for unclassified roles
        return 0.4
    
    def _detect_ai_indicators(self, title: str, bio: str) -> List[AIIndicator]:
        """Detect AI indicators in title and bio"""
        indicators = []
        title_lower = title.lower()
        bio_lower = bio.lower()
        combined = f"{title_lower} {bio_lower}"
        
        # 1. Chief AI Officer (highest signal)
        if 'chief ai officer' in title_lower or 'chief artificial intelligence' in title_lower:
            indicators.append(AIIndicator(
                type=AIIndicatorType.CHIEF_AI_OFFICER,
                evidence=f"Title: {title}",
                score=1.0,
                source='Company Website',
                confidence=0.95
            ))
            return indicators  # This is the strongest signal
        
        # 2. AI in title (strong signal)
        if any(kw in title_lower for kw in ['ai', 'artificial intelligence', 'machine learning', 'data science']):
            indicators.append(AIIndicator(
                type=AIIndicatorType.AI_ROLE_TITLE,
                evidence=f"AI-related title: {title}",
                score=0.6,
                source='Company Website',
                confidence=0.85
            ))
        
        # 3. Tech leadership roles
        if any(kw in title_lower for kw in ['chief technology', 'chief information', 'chief digital', 'chief data', 'cto', 'cio', 'cdo']):
            if not indicators:  # Only add if no AI role already
                indicators.append(AIIndicator(
                    type=AIIndicatorType.TECH_LEADERSHIP,
                    evidence=f"Tech leadership role: {title}",
                    score=0.5,
                    source='Company Website',
                    confidence=0.8
                ))
        
        # 4. AI company background (from bio)
        for company in self.AI_COMPANIES:
            if company in bio_lower:
                indicators.append(AIIndicator(
                    type=AIIndicatorType.AI_COMPANY_VETERAN,
                    evidence=f"Previously worked at {company}",
                    score=0.9,
                    source='Company Website',
                    confidence=0.7
                ))
                break  # Only count once
        
        # 5. PhD in relevant field
        if 'ph.d' in bio_lower or 'phd' in bio_lower or 'doctorate' in bio_lower:
            if any(kw in bio_lower for kw in ['computer science', 'artificial intelligence', 'machine learning', 'statistics', 'data science']):
                indicators.append(AIIndicator(
                    type=AIIndicatorType.PHD_AI_ML,
                    evidence="PhD in AI/ML-related field mentioned",
                    score=0.8,
                    source='Company Website',
                    confidence=0.75
                ))
        
        # 6. Generic AI keywords (weakest signal)
        if not indicators:
            ai_keywords = ['artificial intelligence', 'machine learning', 'ai strategy', 'data science', 'analytics']
            if any(kw in combined for kw in ai_keywords):
                indicators.append(AIIndicator(
                    type=AIIndicatorType.AI_KEYWORDS_ONLY,
                    evidence="Generic AI keywords found",
                    score=0.1,
                    source='Company Website',
                    confidence=0.5
                ))
        
        return indicators
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()