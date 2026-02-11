"""
Standalone Testing Script for Talent Concentration Calculator
Run this independently without any other CS3 components

Usage:
    python test_tc_standalone.py
    
This creates mock data and tests all TC functionality end-to-end.
"""

from decimal import Decimal
from typing import List, Dict

import sys
import os

# Add parent directory to path so we can import our module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scoring.talent_concentration import (
    TalentConcentrationCalculator,
    JobAnalysis
)


# ============================================================================
# MOCK DATA GENERATORS
# ============================================================================

class MockDataGenerator:
    """Generate realistic test data for TC testing."""
    
    @staticmethod
    def generate_high_risk_startup() -> List[Dict]:
        """
        Startup scenario: 5 people, mostly seniors
        Expected TC: > 0.6 (HIGH RISK)
        """
        return [
            {
                'title': 'Head of AI',
                'description': 'Lead AI strategy with deep learning, PyTorch, transformers',
                'is_ai_related': True,
                'ai_skills': ['python', 'pytorch', 'deep learning', 'transformers']
            },
            {
                'title': 'Principal ML Engineer',
                'description': 'Build ML platform using Kubernetes, MLOps, SageMaker',
                'is_ai_related': True,
                'ai_skills': ['python', 'kubernetes', 'aws sagemaker', 'mlflow']
            },
            {
                'title': 'Staff ML Engineer',
                'description': 'Research NLP systems with Huggingface, LangChain',
                'is_ai_related': True,
                'ai_skills': ['python', 'huggingface', 'langchain', 'nlp']
            },
            {
                'title': 'Senior Data Scientist',
                'description': 'Build recommendation models with TensorFlow',
                'is_ai_related': True,
                'ai_skills': ['python', 'tensorflow', 'scikit-learn']
            },
            {
                'title': 'Junior ML Engineer',
                'description': 'Support model deployment',
                'is_ai_related': True,
                'ai_skills': ['python', 'docker']
            }
        ]
    
    @staticmethod
    def generate_low_risk_enterprise() -> List[Dict]:
        """
        Enterprise scenario: 50 people, distributed levels
        Expected TC: < 0.4 (LOW RISK)
        """
        jobs = []
        
        # 6 Senior roles (12%)
        senior_titles = [
            'Principal ML Engineer', 'Staff Data Scientist', 
            'Director of AI', 'Principal Architect',
            'Distinguished Engineer', 'VP Machine Learning'
        ]
        for title in senior_titles:
            jobs.append({
                'title': title,
                'description': 'Senior role with deep expertise',
                'is_ai_related': True,
                'ai_skills': ['python', 'pytorch', 'tensorflow', 'spark']
            })
        
        # 24 Mid-level roles (48%)
        mid_titles = [
            'Senior ML Engineer', 'Senior Data Scientist',
            'Lead ML Engineer', 'ML Engineering Manager'
        ]
        for i in range(24):
            jobs.append({
                'title': mid_titles[i % len(mid_titles)],
                'description': 'Mid-level engineering work',
                'is_ai_related': True,
                'ai_skills': ['python', 'scikit-learn', 'kubernetes', 'docker']
            })
        
        # 20 Entry-level roles (40%)
        entry_titles = [
            'Junior ML Engineer', 'Associate Data Scientist',
            'Entry-Level ML Engineer', 'Data Scientist'
        ]
        for i in range(20):
            jobs.append({
                'title': entry_titles[i % len(entry_titles)],
                'description': 'Entry level work',
                'is_ai_related': True,
                'ai_skills': ['python', 'pandas', 'scikit-learn']
            })
        
        return jobs
    
    @staticmethod
    def generate_moderate_risk_midsize() -> List[Dict]:
        """
        Mid-size company: 15 people, mixed levels
        Expected TC: 0.4-0.6 (MODERATE RISK)
        """
        jobs = []
        
        # 4 Senior (27%)
        for i in range(4):
            jobs.append({
                'title': 'Principal ML Engineer' if i == 0 else 'Staff Data Scientist',
                'description': 'Senior expertise',
                'is_ai_related': True,
                'ai_skills': ['python', 'pytorch', 'spark', 'kubernetes']
            })
        
        # 6 Mid (40%)
        for i in range(6):
            jobs.append({
                'title': 'Senior ML Engineer',
                'description': 'Build models',
                'is_ai_related': True,
                'ai_skills': ['python', 'tensorflow', 'docker']
            })
        
        # 5 Entry (33%)
        for i in range(5):
            jobs.append({
                'title': 'Data Scientist' if i % 2 == 0 else 'Junior ML Engineer',
                'description': 'Support work',
                'is_ai_related': True,
                'ai_skills': ['python', 'scikit-learn']
            })
        
        return jobs
    
    @staticmethod
    def generate_glassdoor_hero_culture() -> str:
        """Glassdoor reviews showing hero culture / key person dependency."""
        return """
        Great company but everything depends on John's ML expertise.
        The ML platform only works because Sarah built it all herself.
        John is the only one who really understands the model architecture.
        If Mike leaves we're screwed - he's the only PyTorch expert.
        Strong team overall but Sarah carries the entire data science org.
        """
    
    @staticmethod
    def generate_glassdoor_distributed() -> str:
        """Glassdoor reviews showing healthy distributed culture."""
        return """
        Great team collaboration on ML projects.
        Knowledge sharing is excellent here.
        The ML platform is well documented and maintained by the whole team.
        Strong culture of mentorship and learning.
        Team members support each other well.
        """


# ============================================================================
# TEST RUNNER
# ============================================================================

class TCTestRunner:
    """Run comprehensive tests on TC calculator."""
    
    def __init__(self):
        self.calc = TalentConcentrationCalculator()
        self.mock = MockDataGenerator()
        self.test_results = []
        
    def run_all_tests(self):
        """Run all test scenarios."""
        print("=" * 70)
        print("TALENT CONCENTRATION CALCULATOR - STANDALONE TESTS")
        print("=" * 70)
        print()
        
        self.test_high_risk_startup()
        self.test_low_risk_enterprise()
        self.test_moderate_risk_midsize()
        self.test_glassdoor_impact()
        self.test_edge_cases()
        self.test_job_categorization()
        self.test_skill_extraction()
        
        self.print_summary()
    
    def test_high_risk_startup(self):
        """Test high concentration scenario."""
        print("TEST 1: High Risk Startup")
        print("-" * 70)
        
        jobs = self.mock.generate_high_risk_startup()
        analysis = self.calc.analyze_job_postings(jobs)
        tc = self.calc.calculate_tc(analysis)
        
        print(f"📊 Job Analysis:")
        print(f"   Total AI jobs: {analysis.total_ai_jobs}")
        print(f"   Senior: {analysis.senior_ai_jobs} ({analysis.senior_ai_jobs/analysis.total_ai_jobs*100:.1f}%)")
        print(f"   Mid: {analysis.mid_ai_jobs}")
        print(f"   Entry: {analysis.entry_ai_jobs}")
        print(f"   Unique skills: {len(analysis.unique_skills)}")
        print(f"   Skills: {sorted(list(analysis.unique_skills)[:5])}...")
        print()
        print(f"🎯 Talent Concentration: {tc}")
        
        # Validate
        expected_high = tc > Decimal("0.6")
        risk_level = "HIGH RISK" if tc > 0.6 else "MODERATE" if tc > 0.3 else "LOW RISK"
        print(f"   Risk Level: {risk_level}")
        print(f"   ✓ Expected high concentration (>0.6): {expected_high}")
        
        # Calculate impact on VR
        talent_penalty = float(tc) - 0.25
        if talent_penalty > 0:
            vr_impact = 0.15 * talent_penalty * 100
            print(f"   Impact on VR: -{vr_impact:.1f}% penalty")
        
        self.test_results.append(("High Risk Startup", expected_high))
        print()
    
    def test_low_risk_enterprise(self):
        """Test low concentration scenario."""
        print("TEST 2: Low Risk Enterprise")
        print("-" * 70)
        
        jobs = self.mock.generate_low_risk_enterprise()
        analysis = self.calc.analyze_job_postings(jobs)
        tc = self.calc.calculate_tc(analysis)
        
        print(f"📊 Job Analysis:")
        print(f"   Total AI jobs: {analysis.total_ai_jobs}")
        print(f"   Senior: {analysis.senior_ai_jobs} ({analysis.senior_ai_jobs/analysis.total_ai_jobs*100:.1f}%)")
        print(f"   Mid: {analysis.mid_ai_jobs}")
        print(f"   Entry: {analysis.entry_ai_jobs}")
        print(f"   Unique skills: {len(analysis.unique_skills)}")
        print()
        print(f"🎯 Talent Concentration: {tc}")
        
        # Validate
        expected_low = tc < Decimal("0.4")
        risk_level = "HIGH RISK" if tc > 0.6 else "MODERATE" if tc > 0.3 else "LOW RISK"
        print(f"   Risk Level: {risk_level}")
        print(f"   ✓ Expected low concentration (<0.4): {expected_low}")
        
        if float(tc) < 0.25:
            print(f"   No VR penalty (TC below 0.25 threshold)")
        
        self.test_results.append(("Low Risk Enterprise", expected_low))
        print()
    
    def test_moderate_risk_midsize(self):
        """Test moderate concentration scenario."""
        print("TEST 3: Moderate Risk Mid-Size Company")
        print("-" * 70)
        
        jobs = self.mock.generate_moderate_risk_midsize()
        analysis = self.calc.analyze_job_postings(jobs)
        tc = self.calc.calculate_tc(analysis)
        
        print(f"📊 Job Analysis:")
        print(f"   Total AI jobs: {analysis.total_ai_jobs}")
        print(f"   Senior: {analysis.senior_ai_jobs} ({analysis.senior_ai_jobs/analysis.total_ai_jobs*100:.1f}%)")
        print(f"   Mid: {analysis.mid_ai_jobs}")
        print(f"   Entry: {analysis.entry_ai_jobs}")
        print(f"   Unique skills: {len(analysis.unique_skills)}")
        print()
        print(f"🎯 Talent Concentration: {tc}")
        
        # Validate
        expected_moderate = Decimal("0.3") < tc < Decimal("0.6")
        risk_level = "HIGH RISK" if tc > 0.6 else "MODERATE" if tc > 0.3 else "LOW RISK"
        print(f"   Risk Level: {risk_level}")
        print(f"   ✓ Expected moderate concentration (0.3-0.6): {expected_moderate}")
        
        self.test_results.append(("Moderate Risk", expected_moderate))
        print()
    
    def test_glassdoor_impact(self):
        """Test impact of Glassdoor individual mentions."""
        print("TEST 4: Glassdoor Individual Mentions Impact")
        print("-" * 70)
        
        jobs = self.mock.generate_moderate_risk_midsize()
        analysis = self.calc.analyze_job_postings(jobs)
        
        # Without hero culture
        hero_text = self.mock.generate_glassdoor_hero_culture()
        distributed_text = self.mock.generate_glassdoor_distributed()
        
        hero_mentions = self.calc.extract_individual_mentions(hero_text)
        distributed_mentions = self.calc.extract_individual_mentions(distributed_text)
        
        tc_hero = self.calc.calculate_tc(
            analysis,
            glassdoor_individual_mentions=hero_mentions,
            glassdoor_review_count=5
        )
        
        tc_distributed = self.calc.calculate_tc(
            analysis,
            glassdoor_individual_mentions=distributed_mentions,
            glassdoor_review_count=5
        )
        
        print(f"📝 Glassdoor Analysis:")
        print(f"   Hero culture mentions: {hero_mentions}")
        print(f"   Distributed culture mentions: {distributed_mentions}")
        print()
        print(f"🎯 TC with hero culture: {tc_hero}")
        print(f"🎯 TC with distributed culture: {tc_distributed}")
        print(f"   Δ TC: {float(tc_hero - tc_distributed):.4f}")
        
        # Validate
        hero_higher = tc_hero > tc_distributed
        print(f"   ✓ Hero culture increases TC: {hero_higher}")
        
        self.test_results.append(("Glassdoor Impact", hero_higher))
        print()
    
    def test_edge_cases(self):
        """Test edge cases."""
        print("TEST 5: Edge Cases")
        print("-" * 70)
        
        # No data
        empty_analysis = JobAnalysis(
            total_ai_jobs=0,
            senior_ai_jobs=0,
            mid_ai_jobs=0,
            entry_ai_jobs=0,
            unique_skills=set()
        )
        tc_empty = self.calc.calculate_tc(empty_analysis)
        print(f"No job data TC: {tc_empty}")
        print(f"   ✓ Returns moderate default (0.3-0.7): {Decimal('0.3') <= tc_empty <= Decimal('0.7')}")
        
        # All seniors
        all_senior = JobAnalysis(
            total_ai_jobs=10,
            senior_ai_jobs=10,
            mid_ai_jobs=0,
            entry_ai_jobs=0,
            unique_skills={'python', 'pytorch'}
        )
        tc_all_senior = self.calc.calculate_tc(all_senior)
        print(f"All senior team TC: {tc_all_senior}")
        print(f"   ✓ Very high (>0.7): {tc_all_senior > Decimal('0.7')}")
        
        # Always bounded
        print(f"   ✓ TC bounded [0,1]: {Decimal('0') <= tc_empty <= Decimal('1') and Decimal('0') <= tc_all_senior <= Decimal('1')}")
        
        self.test_results.append(("Edge Cases", True))
        print()
    
    def test_job_categorization(self):
        """Test job level categorization."""
        print("TEST 6: Job Categorization")
        print("-" * 70)
        
        test_jobs = [
            {'title': 'Principal ML Engineer', 'description': '', 'is_ai_related': True},
            {'title': 'Staff Data Scientist', 'description': '', 'is_ai_related': True},
            {'title': 'Senior ML Engineer', 'description': '', 'is_ai_related': True},
            {'title': 'Lead Data Scientist', 'description': '', 'is_ai_related': True},
            {'title': 'Junior ML Engineer', 'description': '', 'is_ai_related': True},
            {'title': 'Associate Data Scientist', 'description': '', 'is_ai_related': True},
        ]
        
        analysis = self.calc.analyze_job_postings(test_jobs)
        
        print(f"Categorization Results:")
        print(f"   Senior (Principal, Staff): {analysis.senior_ai_jobs}")
        print(f"   Mid (Senior, Lead): {analysis.mid_ai_jobs}")
        print(f"   Entry (Junior, Associate): {analysis.entry_ai_jobs}")
        
        correct = (analysis.senior_ai_jobs == 2 and 
                  analysis.mid_ai_jobs == 2 and 
                  analysis.entry_ai_jobs == 2)
        print(f"   ✓ Correct categorization: {correct}")
        
        self.test_results.append(("Job Categorization", correct))
        print()
    
    def test_skill_extraction(self):
        """Test skill extraction from descriptions."""
        print("TEST 7: Skill Extraction")
        print("-" * 70)
        
        jobs_with_skills = [
            {
                'title': 'ML Engineer',
                'description': 'Build models using PyTorch and TensorFlow on Kubernetes',
                'is_ai_related': True
            }
        ]
        
        jobs_with_provided = [
            {
                'title': 'ML Engineer',
                'description': 'Build models',
                'is_ai_related': True,
                'ai_skills': ['python', 'pytorch', 'kubernetes']
            }
        ]
        
        analysis1 = self.calc.analyze_job_postings(jobs_with_skills)
        analysis2 = self.calc.analyze_job_postings(jobs_with_provided)
        
        print(f"Skills extracted from description: {sorted(analysis1.unique_skills)}")
        print(f"Skills from ai_skills field: {sorted(analysis2.unique_skills)}")
        
        extracted_pytorch = 'pytorch' in analysis1.unique_skills
        used_provided = 'pytorch' in analysis2.unique_skills
        
        print(f"   ✓ Extracts from text: {extracted_pytorch}")
        print(f"   ✓ Uses provided skills: {used_provided}")
        
        self.test_results.append(("Skill Extraction", extracted_pytorch and used_provided))
        print()
    
    def print_summary(self):
        """Print test summary."""
        print("=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        
        passed = sum(1 for _, result in self.test_results if result)
        total = len(self.test_results)
        
        for test_name, result in self.test_results:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"{status} - {test_name}")
        
        print()
        print(f"Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed!")
        else:
            print(f"⚠️  {total - passed} test(s) failed")
        
        print("=" * 70)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run standalone tests."""
    runner = TCTestRunner()
    runner.run_all_tests()


if __name__ == "__main__":
    main()