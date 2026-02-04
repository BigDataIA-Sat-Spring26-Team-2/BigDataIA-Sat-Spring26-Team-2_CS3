"""
Leadership Signals Test Script - Quick validation for one company.

Usage:
    python test_leadership.py
    
Before running:
    1. Update TEST_COMPANY_ID with your company's UUID
    2. Update TEST_TICKER with the company's ticker
    3. Ensure FastAPI server is running: uvicorn app.main:app --reload
"""

import asyncio
import requests
from uuid import UUID

# =============================================================================
# CONFIGURATION - UPDATE THESE VALUES
# =============================================================================
API_BASE = "http://localhost:8000/api/v1"

# ⚠️ UPDATE THESE WITH YOUR ACTUAL VALUES
TEST_COMPANY_ID = "7f14d942-775b-4340-966b-42c10e88ee98"  # JPM UUID
TEST_TICKER = "ADP"  # Company ticker

# For testing multiple companies, update these and re-run
# TEST_COMPANY_ID = "your-other-company-uuid"
# TEST_TICKER = "WMT"  # or "GS", "CAT", "UNH", etc.


async def test_leadership_signal():
    """Test leadership signal collection for a company."""
    
    print("\n" + "="*60)
    print("🚀 LEADERSHIP SIGNALS TEST SCRIPT")
    print("="*60 + "\n")
    
    # Validate configuration
    if TEST_COMPANY_ID == "7f14d942-775b-4340-966b-42c10e88ee98" and TEST_TICKER == "JPM":
        print("ℹ️  Using default JPM configuration")
        print("   To test other companies, update TEST_COMPANY_ID and TEST_TICKER\n")
    
    print(f"🧪 Testing Leadership Signals for {TEST_TICKER}")
    print("="*60)
    print(f"✅ Using company: {TEST_TICKER} ({TEST_COMPANY_ID})")
    
    # Check if server is running
    try:
        health_check = requests.get(f"{API_BASE}/health", timeout=30)
        if health_check.status_code == 503:
            print("\n⚠️  WARNING: Health check shows degraded service")
            print("   Snowflake connection may be slow")
            print("   Attempting leadership test anyway...\n")
            # Don't return - continue with test
        elif health_check.status_code != 200:
            print("\n❌ ERROR: API server not responding correctly")
            print("   Please start the server: uvicorn app.main:app --reload")
            return
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to API server")
        print("   Please start the server: uvicorn app.main:app --reload")
        return
    except requests.exceptions.Timeout:
        print("\n⏱️  ERROR: Server timeout")
        return
    
    # Collect leadership signals
    print("\n📊 Collecting leadership signals...")
    
    try:
        response = requests.post(
            f"{API_BASE}/signals/collect-leadership-signals",
            params={
                'company_id': TEST_COMPANY_ID,
                'ticker': TEST_TICKER
            },
            timeout=120  # 2 minutes timeout
        )
        
        if response.status_code == 404:
            print("\n❌ ERROR: No document chunks found!")
            print("\n💡 SOLUTION: Download SEC filings first:")
            print(f"   1. Go to http://localhost:8000/docs")
            print(f"   2. Find POST /api/v1/documents/sec-edgar/download")
            print(f"   3. Use these parameters:")
            print(f"      - company_id: {TEST_COMPANY_ID}")
            print(f"      - ticker: {TEST_TICKER}")
            print(f"      - filing_types: ['10-K', 'DEF 14A']")
            print(f"      - after: '2024-01-01'")
            print(f"      - limit: 2")
            return
        
        if response.status_code == 500:
            print(f"\n❌ ERROR: Server error ({response.status_code})")
            error_detail = response.json()
            print(f"\nError details:")
            print(f"   {error_detail.get('message', 'Unknown error')}")
            if 'details' in error_detail:
                print(f"   Details: {error_detail['details']}")
            return
        
        if response.status_code != 201:
            print(f"\n❌ ERROR: Unexpected status code {response.status_code}")
            try:
                print(response.json())
            except:
                print(response.text)
            return
        
        signal = response.json()
        
        # Display results
        print(f"\n✅ Leadership Signal Collected Successfully!")
        print("="*60)
        
        print(f"\n📈 OVERALL SCORE: {signal['normalized_score']:.1f}/100")
        print(f"🎯 CONFIDENCE: {signal['confidence']:.2f}")
        print(f"📝 EVIDENCE COUNT: {signal['metadata']['evidence_count']}")
        
        print("\n" + "="*60)
        print("📊 SCORE BREAKDOWN")
        print("="*60)
        
        metadata = signal['metadata']
        
        print(f"\n💰 Compensation Metrics:  {metadata['tech_comp_score']:.1f}/100")
        print("   → Measures: Tech-linked executive pay")
        
        print(f"\n🎯 AI Strategy:           {metadata['ai_strategy_score']:.1f}/100")
        print("   → Measures: Strategic AI statements")
        
        print(f"\n💵 Tech Investment:       {metadata['tech_investment_score']:.1f}/100")
        print("   → Measures: Technology spending mentions")
        
        print(f"\n⚠️  Risk Awareness:       {metadata['ai_risk_score']:.1f}/100")
        print("   → Measures: AI/tech risk acknowledgment")
        
        print("\n" + "="*60)
        print("📝 TOP EVIDENCE SAMPLES")
        print("="*60)
        
        if metadata.get('top_evidence'):
            for i, evidence in enumerate(metadata['top_evidence'][:5], 1):
                print(f"\n{i}. [{evidence['type'].upper()}]")
                print(f"   \"{evidence['snippet']}...\"")
                keywords = evidence.get('keywords', [])
                if keywords:
                    print(f"   Keywords: {', '.join(keywords[:3])}")
                if evidence.get('section'):
                    print(f"   Section: {evidence['section']}")
        else:
            print("\n(No evidence samples available)")
        
        print("\n" + "="*60)
        print("✅ TEST COMPLETE")
        print("="*60)
        
        # Interpretation guide
        score = signal['normalized_score']
        print("\n📊 Score Interpretation:")
        if score >= 70:
            print(f"   🌟 AI LEADER: {TEST_TICKER} shows strong AI commitment")
        elif score >= 50:
            print(f"   ✅ AI ADOPTER: {TEST_TICKER} is actively investing in AI")
        elif score >= 30:
            print(f"   ⚠️  AI EXPLORER: {TEST_TICKER} has limited AI initiatives")
        else:
            print(f"   ℹ️  TRADITIONAL: {TEST_TICKER} shows minimal AI focus")
        
        # Suggest next steps
        print("\n🚀 Next Steps:")
        print(f"   1. Test another company (update TEST_TICKER)")
        print(f"   2. View signal in Snowflake:")
        print(f"      SELECT * FROM external_signals WHERE company_id = '{TEST_COMPANY_ID}'")
        print(f"   3. Check signal summary:")
        print(f"      GET {API_BASE}/signals/companies/{TEST_COMPANY_ID}/summary")
        
    except requests.exceptions.Timeout:
        print("\n⏱️  Request timed out (>120s)")
        print("💡 This might mean:")
        print("   - Too many document chunks to process")
        print("   - Database query is slow")
        print("   - Try downloading fewer filings")
    
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


async def test_multiple_companies():
    """Test leadership signals for multiple companies."""
    
    companies = [
        ("7f14d942-775b-4340-966b-42c10e88ee98", "JPM"),
        # Add more companies here
        # ("uuid2", "WMT"),
        # ("uuid3", "GS"),
    ]
    
    print("\n" + "="*60)
    print(f"🚀 TESTING {len(companies)} COMPANIES")
    print("="*60 + "\n")
    
    results = []
    
    for company_id, ticker in companies:
        print(f"\n📊 Testing {ticker}...")
        
        try:
            response = requests.post(
                f"{API_BASE}/signals/collect-leadership-signals",
                params={'company_id': company_id, 'ticker': ticker},
                timeout=120
            )
            
            if response.status_code == 201:
                signal = response.json()
                results.append({
                    'ticker': ticker,
                    'score': signal['normalized_score'],
                    'confidence': signal['confidence'],
                    'evidence': signal['metadata']['evidence_count']
                })
                print(f"   ✅ {ticker}: {signal['normalized_score']:.1f}/100")
            else:
                print(f"   ❌ {ticker}: Error {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ {ticker}: {str(e)}")
    
    # Summary table
    if results:
        print("\n" + "="*60)
        print("📊 RESULTS SUMMARY")
        print("="*60)
        print(f"\n{'Ticker':<8} {'Score':>8} {'Confidence':>12} {'Evidence':>10}")
        print("-"*40)
        for r in sorted(results, key=lambda x: x['score'], reverse=True):
            print(f"{r['ticker']:<8} {r['score']:>7.1f} {r['confidence']:>11.2f} {r['evidence']:>10}")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 LEADERSHIP SIGNALS TEST SCRIPT")
    print("="*60 + "\n")
    
    # Configuration check - fixed logic
    if TEST_COMPANY_ID == "YOUR_COMPANY_UUID_HERE":
        print("⚠️  SETUP REQUIRED:")
        print("="*60)
        print("\n1. Get your company UUID from Snowflake:")
        print("   SELECT id, ticker FROM companies WHERE ticker = 'JPM';")
        print("\n2. Update test_leadership.py:")
        print("   TEST_COMPANY_ID = 'your-uuid-here'")
        print("   TEST_TICKER = 'JPM'")
        print("\n3. Run again: python test_leadership.py")
        print("\n" + "="*60)
    else:
        # Run single company test
        asyncio.run(test_leadership_signal())
        
        # Uncomment to test multiple companies:
        # asyncio.run(test_multiple_companies())