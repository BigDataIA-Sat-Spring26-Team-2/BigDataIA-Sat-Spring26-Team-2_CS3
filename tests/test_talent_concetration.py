"""
Tests for Talent Concentration Calculator
CS3 Task 5.0e Tests

Tests cover:
1. Basic TC calculation
2. Job analysis categorization
3. Edge cases (no data, extreme concentrations)
4. Property-based tests with Hypothesis
"""

import pytest
from hypothesis import given, strategies as st
from decimal import Decimal

from app.scoring.talent_concentration import (
    TalentConcentrationCalculator,
    JobAnalysis
)


class TestJobAnalysis:
    """Test job posting analysis and categorization."""
    
    def test_categorize_senior_jobs(self):
        """Senior keywords should be recognized."""
        calc = TalentConcentrationCalculator()
        
        postings = [
            {
                'title': 'Principal ML Engineer',
                'description': 'Lead team...',
                'is_ai_related': True
            },
            {
                'title': 'Staff Data Scientist',
                'description': 'Research...',
                'is_ai_related': True
            },
            {
                'title': 'Director of AI',
                'description': 'Manage...',
                'is_ai_related': True
            }
        ]
        
        analysis = calc.analyze_job_postings(postings)
        
        assert analysis.total_ai_jobs == 3
        assert analysis.senior_ai_jobs == 3
        assert analysis.mid_ai_jobs == 0
        assert analysis.entry_ai_jobs == 0
        
    def test_categorize_mid_jobs(self):
        """Mid-level keywords should be recognized."""
        calc = TalentConcentrationCalculator()
        
        postings = [
            {
                'title': 'Senior Data Scientist',
                'description': 'Build models...',
                'is_ai_related': True
            },
            {
                'title': 'Lead ML Engineer',
                'description': 'Deploy...',
                'is_ai_related': True
            }
        ]
        
        analysis = calc.analyze_job_postings(postings)
        
        assert analysis.total_ai_jobs == 2
        assert analysis.senior_ai_jobs == 0
        assert analysis.mid_ai_jobs == 2
        
    def test_categorize_entry_jobs(self):
        """Entry-level keywords should be recognized."""
        calc = TalentConcentrationCalculator()
        
        postings = [
            {
                'title': 'Junior ML Engineer',
                'description': 'Support...',
                'is_ai_related': True
            },
            {
                'title': 'Associate Data Scientist',
                'description': 'Learn...',
                'is_ai_related': True
            }
        ]
        
        analysis = calc.analyze_job_postings(postings)
        
        assert analysis.total_ai_jobs == 2
        assert analysis.entry_ai_jobs == 2
        
    def test_skill_extraction_from_ai_skills(self):
        """Should use provided ai_skills when available."""
        calc = TalentConcentrationCalculator()
        
        postings = [
            {
                'title': 'ML Engineer',
                'description': 'Build...',
                'is_ai_related': True,
                'ai_skills': ['python', 'pytorch', 'kubernetes']
            }
        ]
        
        analysis = calc.analyze_job_postings(postings)
        
        assert 'python' in analysis.unique_skills
        assert 'pytorch' in analysis.unique_skills
        assert 'kubernetes' in analysis.unique_skills
        
    def test_skill_extraction_from_text(self):
        """Should extract skills from description when ai_skills not provided."""
        calc = TalentConcentrationCalculator()
        
        postings = [
            {
                'title': 'ML Engineer',
                'description': 'Build models using PyTorch and TensorFlow on Kubernetes',
                'is_ai_related': True
            }
        ]
        
        analysis = calc.analyze_job_postings(postings)
        
        assert 'pytorch' in analysis.unique_skills
        assert 'tensorflow' in analysis.unique_skills
        assert 'kubernetes' in analysis.unique_skills
        
    def test_filters_non_ai_jobs(self):
        """Should only count AI-related jobs."""
        calc = TalentConcentrationCalculator()
        
        postings = [
            {
                'title': 'ML Engineer',
                'description': 'AI work',
                'is_ai_related': True
            },
            {
                'title': 'Accountant',
                'description': 'Finance work',
                'is_ai_related': False
            }
        ]
        
        analysis = calc.analyze_job_postings(postings)
        
        assert analysis.total_ai_jobs == 1


class TestTalentConcentration:
    """Test TC calculation logic."""
    
    def test_high_concentration_small_senior_team(self):
        """Small team of all seniors = high concentration."""
        calc = TalentConcentrationCalculator()
        
        analysis = JobAnalysis(
            total_ai_jobs=5,
            senior_ai_jobs=5,
            mid_ai_jobs=0,
            entry_ai_jobs=0,
            unique_skills={'python', 'pytorch'}  # Few skills
        )
        
        tc = calc.calculate_tc(analysis)
        
        # Should be high concentration (> 0.6)
        assert tc > Decimal("0.6")
        
    def test_low_concentration_large_distributed_team(self):
        """Large team with diverse levels = low concentration."""
        calc = TalentConcentrationCalculator()
        
        analysis = JobAnalysis(
            total_ai_jobs=50,
            senior_ai_jobs=8,   # 16% senior
            mid_ai_jobs=22,
            entry_ai_jobs=20,
            unique_skills={
                'python', 'pytorch', 'tensorflow', 'spark',
                'kubernetes', 'docker', 'nlp', 'computer vision',
                'aws sagemaker', 'mlflow', 'langchain'
            }  # Many skills
        )
        
        tc = calc.calculate_tc(analysis)
        
        # Should be low concentration (< 0.4)
        assert tc < Decimal("0.4")
        
    def test_tc_bounded_to_zero_one(self):
        """TC should always be in [0, 1]."""
        calc = TalentConcentrationCalculator()
        
        # Extreme case: no seniors, huge team, many skills
        analysis = JobAnalysis(
            total_ai_jobs=1000,
            senior_ai_jobs=0,
            mid_ai_jobs=500,
            entry_ai_jobs=500,
            unique_skills=set(calc.AI_SKILLS)  # All skills
        )
        
        tc = calc.calculate_tc(analysis)
        
        assert tc >= Decimal("0")
        assert tc <= Decimal("1")
        
    def test_no_job_data_returns_moderate_tc(self):
        """When no job data available, should default to moderate TC."""
        calc = TalentConcentrationCalculator()
        
        analysis = JobAnalysis(
            total_ai_jobs=0,
            senior_ai_jobs=0,
            mid_ai_jobs=0,
            entry_ai_jobs=0,
            unique_skills=set()
        )
        
        tc = calc.calculate_tc(analysis)
        
        # Should be around 0.5 (moderate risk assumption)
        assert Decimal("0.3") <= tc <= Decimal("0.7")
        
    def test_glassdoor_individual_mentions_increase_tc(self):
        """More individual mentions should increase TC."""
        calc = TalentConcentrationCalculator()
        
        analysis = JobAnalysis(
            total_ai_jobs=10,
            senior_ai_jobs=3,
            mid_ai_jobs=4,
            entry_ai_jobs=3,
            unique_skills={'python', 'pytorch', 'tensorflow'}
        )
        
        # Without individual mentions
        tc_no_mentions = calc.calculate_tc(
            analysis,
            glassdoor_individual_mentions=0,
            glassdoor_review_count=10
        )
        
        # With high individual mentions
        tc_with_mentions = calc.calculate_tc(
            analysis,
            glassdoor_individual_mentions=8,
            glassdoor_review_count=10
        )
        
        assert tc_with_mentions > tc_no_mentions


class TestIndividualMentions:
    """Test Glassdoor individual mention extraction."""
    
    def test_extract_dependency_patterns(self):
        """Should detect individual dependency patterns."""
        calc = TalentConcentrationCalculator()
        
        text = """
        John is the only one who knows PyTorch.
        Everything depends on Sarah's expertise.
        If Mike leaves, we're in trouble.
        """
        
        count = calc.extract_individual_mentions(text)
        
        assert count >= 3
        
    def test_no_mentions_in_generic_review(self):
        """Generic reviews shouldn't count as individual mentions."""
        calc = TalentConcentrationCalculator()
        
        text = "Great company, good benefits, nice office."
        
        count = calc.extract_individual_mentions(text)
        
        assert count == 0


# =============================================================================
# PROPERTY-BASED TESTS (HYPOTHESIS)
# =============================================================================

class TestTCProperties:
    """Property-based tests for TC calculation."""
    
    @given(
        total_jobs=st.integers(min_value=1, max_value=1000),
        senior_ratio=st.floats(min_value=0, max_value=1),
        skill_count=st.integers(min_value=0, max_value=20)
    )
    def test_tc_always_bounded(self, total_jobs, senior_ratio, skill_count):
        """TC must always be in [0, 1] regardless of inputs."""
        calc = TalentConcentrationCalculator()
        
        senior_jobs = int(total_jobs * senior_ratio)
        remaining = total_jobs - senior_jobs
        mid_jobs = remaining // 2
        entry_jobs = remaining - mid_jobs
        
        skills = {f'skill_{i}' for i in range(skill_count)}
        
        analysis = JobAnalysis(
            total_ai_jobs=total_jobs,
            senior_ai_jobs=senior_jobs,
            mid_ai_jobs=mid_jobs,
            entry_ai_jobs=entry_jobs,
            unique_skills=skills
        )
        
        tc = calc.calculate_tc(analysis)
        
        assert Decimal("0") <= tc <= Decimal("1")
        
    @given(
        team_size=st.integers(min_value=1, max_value=100)
    )
    def test_larger_teams_lower_concentration(self, team_size):
        """Larger teams should generally have lower concentration."""
        calc = TalentConcentrationCalculator()
        
        # Same senior ratio, different team sizes
        small_analysis = JobAnalysis(
            total_ai_jobs=5,
            senior_ai_jobs=2,  # 40% senior
            mid_ai_jobs=2,
            entry_ai_jobs=1,
            unique_skills={'python', 'pytorch'}
        )
        
        large_analysis = JobAnalysis(
            total_ai_jobs=team_size,
            senior_ai_jobs=int(team_size * 0.4),  # Same 40% ratio
            mid_ai_jobs=int(team_size * 0.4),
            entry_ai_jobs=team_size - int(team_size * 0.8),
            unique_skills={'python', 'pytorch'}
        )
        
        tc_small = calc.calculate_tc(small_analysis)
        tc_large = calc.calculate_tc(large_analysis)
        
        if team_size > 10:  # Only test when difference is meaningful
            assert tc_large < tc_small


# =============================================================================
# INTEGRATION TEST
# =============================================================================

class TestTCIntegration:
    """Test integration with CS2 job data format."""
    
    def test_end_to_end_with_cs2_format(self):
        """Test complete flow with CS2 JobSignalCollector format."""
        calc = TalentConcentrationCalculator()
        
        # Simulate CS2 job posting data
        cs2_job_postings = [
            {
                'title': 'Principal Machine Learning Engineer',
                'description': 'Build ML platform with PyTorch...',
                'is_ai_related': True,
                'ai_skills': ['python', 'pytorch', 'kubernetes']
            },
            {
                'title': 'Senior Data Scientist',
                'description': 'NLP models...',
                'is_ai_related': True,
                'ai_skills': ['python', 'tensorflow', 'nlp']
            },
            {
                'title': 'Data Scientist',
                'description': 'Analytics...',
                'is_ai_related': True,
                'ai_skills': ['python', 'scikit-learn']
            },
            {
                'title': 'Junior ML Engineer',
                'description': 'Support...',
                'is_ai_related': True,
                'ai_skills': ['python']
            }
        ]
        
        # Step 1: Analyze jobs
        analysis = calc.analyze_job_postings(cs2_job_postings)
        
        assert analysis.total_ai_jobs == 4
        assert analysis.senior_ai_jobs == 1
        assert analysis.mid_ai_jobs == 2
        assert analysis.entry_ai_jobs == 1
        
        # Step 2: Calculate TC
        tc = calc.calculate_tc(analysis)
        
        assert Decimal("0") <= tc <= Decimal("1")
        
        # Step 3: Verify it can feed into VR calculation
        talent_risk_adj = 1 - 0.15 * max(0, float(tc) - 0.25)
        
        assert 0.0 <= talent_risk_adj <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])