from app.services.integration_service import ScoringIntegrationService

# Initialize service
service = ScoringIntegrationService(
    cs1_api_url="http://localhost:8000"
)

print("Running scoring pipeline for WMT...")

result = service.score_company(
    ticker="WMT",
    market_cap_percentile=0.95
)

# Display results
print("\n" + "="*70)
print("SCORING RESULTS")
print("="*70)

print(f"\nScores:")
print(f"   Final (Org-AI-R): {result['final_score']:.1f}/100")
print(f"   V^R:              {result['vr_score']:.1f}/100")
print(f"   H^R:              {result['hr_score']:.1f}/100")
print(f"   Synergy:          {result['synergy_score']:.1f}/100")

print(f"\nMetrics:")
print(f"   Position Factor:  {result['position_factor']:+.3f}")
print(f"   Talent Conc:      {result['talent_concentration']:.3f}")
print(f"   Evidence Count:   {result['evidence_count']}")

print(f"\nConfidence:")
print(f"   95% CI: [{result['ci_lower']:.1f}, {result['ci_upper']:.1f}]")
print(f"   ρ:      {result['confidence']:.3f}")
print(f"   SEM:    {result['sem']:.2f}")

print(f"\nAssessment ID: {result['id']}")
print("="*70)