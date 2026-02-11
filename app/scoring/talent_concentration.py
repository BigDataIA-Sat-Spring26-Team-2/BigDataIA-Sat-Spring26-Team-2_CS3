"""
Talent Concentration Calculator
CS3 Task 5.0e - Measures key-person risk in AI teams

Formula:
    TC = 0.4 * leadership_ratio + 
         0.3 * team_size_factor + 
         0.2 * skill_concentration + 
         0.1 * individual_mentions
         
Bounded to [0, 1] where:
    0.0 = distributed capability (low risk)
    1.0 = concentrated in few people (high risk)
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Set
import re
import math


@dataclass
class JobAnalysis:
    """Analysis of job postings categorized by seniority level."""
    total_ai_jobs: int
    senior_ai_jobs: int      # Principal, Staff, Director, VP
    mid_ai_jobs: int          # Senior, Lead
    entry_ai_jobs: int        # Junior, Associate, Entry
    unique_skills: Set[str]   # Distinct skills across all postings


class TalentConcentrationCalculator:
    """
    Calculate talent concentration (key-person risk) from job data.
    
    This measures how dependent a company's AI capability is on a 
    small number of senior people. Higher TC = higher risk if those
    people leave.
    """
    
    # Seniority level keywords
    SENIOR_KEYWORDS = [
        'principal', 'staff', 'director', 'vp', 'head', 'chief',
        'lead scientist', 'distinguished', 'fellow'
    ]
    
    MID_KEYWORDS = [
        'senior', 'lead', 'manager', 'specialist'
    ]
    
    ENTRY_KEYWORDS = [
        'junior', 'associate', 'entry', 'intern', 'entry-level',
        'early career', 'graduate'
    ]
    
    # Common AI/ML skills to track
    AI_SKILLS = [
        'python', 'pytorch', 'tensorflow', 'scikit-learn',
        'spark', 'hadoop', 'kubernetes', 'docker',
        'aws sagemaker', 'azure ml', 'gcp vertex',
        'huggingface', 'langchain', 'openai',
        'nlp', 'computer vision', 'deep learning',
        'reinforcement learning', 'transformers', 'llm'
    ]

    def calculate_tc(
        self,
        job_analysis: JobAnalysis,
        glassdoor_individual_mentions: int = 0,
        glassdoor_review_count: int = 1,
    ) -> Decimal:
        """
        Calculate talent concentration ratio.
        
        Algorithm:
        1. Calculate leadership ratio (senior jobs / total)
        2. Calculate team size factor (smaller teams = higher concentration)
        3. Calculate skill concentration (fewer unique skills = higher concentration)
        4. Calculate individual mention factor (Glassdoor mentions specific people)
        5. Weighted combination of all factors
        
        Args:
            job_analysis: Analyzed job posting data
            glassdoor_individual_mentions: Count of reviews mentioning specific names
            glassdoor_review_count: Total Glassdoor reviews analyzed
            
        Returns:
            Talent concentration in [0, 1]
            
        Examples:
            >>> calc = TalentConcentrationCalculator()
            >>> 
            >>> # Example 1: Small team, all senior (HIGH RISK)
            >>> analysis = JobAnalysis(
            ...     total_ai_jobs=5,
            ...     senior_ai_jobs=4,
            ...     mid_ai_jobs=1,
            ...     entry_ai_jobs=0,
            ...     unique_skills={'python', 'pytorch'}
            ... )
            >>> tc = calc.calculate_tc(analysis)
            >>> # tc ≈ 0.75 (high concentration)
            >>>
            >>> # Example 2: Large team, diverse levels (LOW RISK)
            >>> analysis = JobAnalysis(
            ...     total_ai_jobs=50,
            ...     senior_ai_jobs=8,
            ...     mid_ai_jobs=22,
            ...     entry_ai_jobs=20,
            ...     unique_skills={'python', 'pytorch', 'tensorflow', 
            ...                    'spark', 'kubernetes', 'docker', 'nlp'}
            ... )
            >>> tc = calc.calculate_tc(analysis)
            >>> # tc ≈ 0.25 (low concentration)
        """
        
        # 1. LEADERSHIP RATIO
        # Higher ratio = more seniors = higher concentration
        if job_analysis.total_ai_jobs > 0:
            leadership_ratio = job_analysis.senior_ai_jobs / job_analysis.total_ai_jobs
        else:
            # No job data = assume moderate risk
            leadership_ratio = 0.5
            
        # 2. TEAM SIZE FACTOR
        # Smaller teams = higher concentration risk
        # Using inverse square root: 1 / sqrt(n + 0.1)
        # The +0.1 prevents division by zero
        team_size_factor = min(1.0, 1.0 / math.sqrt(job_analysis.total_ai_jobs + 0.1))
        
        # 3. SKILL CONCENTRATION
        # Fewer unique skills = higher concentration
        # We normalize against 15 skills (industry benchmark)
        unique_skill_count = len(job_analysis.unique_skills)
        skill_concentration = max(0, 1 - (unique_skill_count / 15))
        
        # 4. INDIVIDUAL MENTION FACTOR
        # Glassdoor reviews mentioning specific people by name
        # indicates hero culture / key-person dependency
        if glassdoor_review_count > 0:
            individual_factor = min(1.0, glassdoor_individual_mentions / glassdoor_review_count)
        else:
            # No Glassdoor data = assume moderate
            individual_factor = 0.5
            
        # 5. WEIGHTED COMBINATION
        # Weights from CS3 spec
        tc = (
            0.4 * leadership_ratio +      # Most important: senior ratio
            0.3 * team_size_factor +      # Second: team size
            0.2 * skill_concentration +   # Third: skill diversity
            0.1 * individual_factor       # Fourth: glassdoor signals
        )
        
        # 6. BOUND TO [0, 1]
        tc_bounded = max(0, min(1, tc))
        
        # 7. RETURN AS DECIMAL WITH 4 DECIMAL PLACES
        return Decimal(str(tc_bounded)).quantize(
            Decimal("0.0001"), 
            rounding=ROUND_HALF_UP
        )

    def analyze_job_postings(
        self,
        postings: List[dict],  # From CS2 JobSignalCollector
    ) -> JobAnalysis:
        """
        Categorize job postings by seniority level and extract skills.
        
        This takes raw job posting data (from CS2) and analyzes it
        to produce the JobAnalysis needed for TC calculation.
        
        Args:
            postings: List of job posting dicts with keys:
                - title: str (job title)
                - description: str (job description)
                - is_ai_related: bool
                - ai_skills: List[str] (optional)
                
        Returns:
            JobAnalysis with categorized counts and unique skills
            
        Example:
            >>> calc = TalentConcentrationCalculator()
            >>> postings = [
            ...     {
            ...         'title': 'Principal ML Engineer',
            ...         'description': 'Build ML platform with PyTorch...',
            ...         'is_ai_related': True,
            ...         'ai_skills': ['python', 'pytorch', 'kubernetes']
            ...     },
            ...     {
            ...         'title': 'Senior Data Scientist',
            ...         'description': 'Apply NLP to customer data...',
            ...         'is_ai_related': True,
            ...         'ai_skills': ['python', 'nlp', 'tensorflow']
            ...     },
            ...     {
            ...         'title': 'Junior ML Engineer',
            ...         'description': 'Support ML pipeline development...',
            ...         'is_ai_related': True,
            ...         'ai_skills': ['python', 'scikit-learn']
            ...     }
            ... ]
            >>> analysis = calc.analyze_job_postings(postings)
            >>> print(f"Total: {analysis.total_ai_jobs}")
            Total: 3
            >>> print(f"Senior: {analysis.senior_ai_jobs}")
            Senior: 1
            >>> print(f"Mid: {analysis.mid_ai_jobs}")
            Mid: 1
            >>> print(f"Entry: {analysis.entry_ai_jobs}")
            Entry: 1
        """
        
        # Filter to AI-related jobs only
        ai_postings = [p for p in postings if p.get('is_ai_related', False)]
        
        senior_count = 0
        mid_count = 0
        entry_count = 0
        all_skills = set()
        
        for posting in ai_postings:
            title = posting.get('title', '').lower()
            description = posting.get('description', '').lower()
            combined_text = f"{title} {description}"
            
            # CATEGORIZE BY SENIORITY
            # Check senior first (most specific)
            is_senior = any(kw in combined_text for kw in self.SENIOR_KEYWORDS)
            is_mid = any(kw in combined_text for kw in self.MID_KEYWORDS)
            is_entry = any(kw in combined_text for kw in self.ENTRY_KEYWORDS)
            
            # Priority: senior > mid > entry > default to mid
            if is_senior:
                senior_count += 1
            elif is_entry:
                entry_count += 1
            elif is_mid:
                mid_count += 1
            else:
                # No clear seniority signal = assume mid-level
                mid_count += 1
                
            # EXTRACT SKILLS
            # Use provided ai_skills if available
            if 'ai_skills' in posting and posting['ai_skills']:
                all_skills.update(posting['ai_skills'])
            else:
                # Extract from text
                detected_skills = [
                    skill for skill in self.AI_SKILLS 
                    if skill in combined_text
                ]
                all_skills.update(detected_skills)
        
        return JobAnalysis(
            total_ai_jobs=len(ai_postings),
            senior_ai_jobs=senior_count,
            mid_ai_jobs=mid_count,
            entry_ai_jobs=entry_count,
            unique_skills=all_skills
        )
    
    def extract_individual_mentions(self, glassdoor_text: str) -> int:
        """
        Count mentions of specific individuals in Glassdoor reviews.
        
        This identifies "hero culture" patterns like:
        - "John is the only one who knows PyTorch"
        - "Everything depends on Sarah's expertise"
        - "If Mike leaves, we're screwed"
        
        Args:
            glassdoor_text: Concatenated review text
            
        Returns:
            Count of reviews mentioning specific names with dependency context
        """
        
        # Patterns indicating individual dependency
        dependency_patterns = [
            r"(\w+) is the only one",
            r"everything depends on (\w+)",
            r"only (\w+) knows",
            r"if (\w+) leaves",
            r"(\w+)'s the expert",
            r"all knowledge with (\w+)",
        ]
        
        mention_count = 0
        text_lower = glassdoor_text.lower()
        
        for pattern in dependency_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            mention_count += len(matches)
            
        return mention_count


# =============================================================================
# INTEGRATION EXAMPLE: How this fits into the full pipeline
# =============================================================================

def example_full_pipeline_integration():
    """
    Example showing how TC calculation integrates with CS2 job data
    and feeds into CS3 VR calculation.
    
    This would be called from the ScoringIntegrationService (Task 6.0b)
    """
    
    # STEP 1: Get job postings from CS2
    # (This would come from your JobSignalCollector)
    job_postings_from_cs2 = [
        {
            'title': 'Principal Machine Learning Engineer',
            'description': 'Lead ML platform development using PyTorch and Kubernetes...',
            'is_ai_related': True,
            'ai_skills': ['python', 'pytorch', 'kubernetes', 'mlflow']
        },
        {
            'title': 'Staff Data Scientist',
            'description': 'Build recommendation systems with deep learning...',
            'is_ai_related': True,
            'ai_skills': ['python', 'tensorflow', 'spark', 'nlp']
        },
        {
            'title': 'Senior ML Engineer',
            'description': 'Deploy models to production using SageMaker...',
            'is_ai_related': True,
            'ai_skills': ['python', 'aws sagemaker', 'docker']
        },
        {
            'title': 'Data Scientist',
            'description': 'Apply ML to customer analytics...',
            'is_ai_related': True,
            'ai_skills': ['python', 'scikit-learn', 'pandas']
        },
        {
            'title': 'Junior ML Engineer',
            'description': 'Support model training pipeline...',
            'is_ai_related': True,
            'ai_skills': ['python', 'scikit-learn']
        }
    ]
    
    # STEP 2: Analyze job postings
    calc = TalentConcentrationCalculator()
    job_analysis = calc.analyze_job_postings(job_postings_from_cs2)
    
    print("Job Analysis:")
    print(f"  Total AI jobs: {job_analysis.total_ai_jobs}")
    print(f"  Senior: {job_analysis.senior_ai_jobs}")
    print(f"  Mid: {job_analysis.mid_ai_jobs}")
    print(f"  Entry: {job_analysis.entry_ai_jobs}")
    print(f"  Unique skills: {len(job_analysis.unique_skills)}")
    print(f"  Skills: {sorted(job_analysis.unique_skills)}")
    
    # STEP 3: Get Glassdoor data (from Task 5.0c)
    glassdoor_reviews = """
    Great company but everything depends on John's ML expertise.
    Sarah is the only one who really understands the model architecture.
    Strong team overall, data-driven culture.
    """
    
    individual_mentions = calc.extract_individual_mentions(glassdoor_reviews)
    
    # STEP 4: Calculate TC
    tc = calc.calculate_tc(
        job_analysis=job_analysis,
        glassdoor_individual_mentions=individual_mentions,
        glassdoor_review_count=3  # 3 reviews
    )
    
    print(f"\nTalent Concentration: {tc}")
    print(f"Risk Level: {'HIGH RISK' if tc > 0.6 else 'MODERATE' if tc > 0.3 else 'LOW RISK'}")
    
    # STEP 5: This TC feeds into VR calculation (Task 5.2)
    # VR uses: TalentRiskAdj = 1 - 0.15 * max(0, TC - 0.25)
    talent_risk_adj = 1 - 0.15 * max(0, float(tc) - 0.25)
    print(f"\nTalent Risk Adjustment: {talent_risk_adj:.4f}")
    print(f"Impact on VR: {(1 - talent_risk_adj) * 100:.1f}% penalty")


if __name__ == "__main__":
    example_full_pipeline_integration() 