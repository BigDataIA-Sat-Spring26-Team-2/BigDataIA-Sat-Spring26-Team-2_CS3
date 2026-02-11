#!/usr/bin/env python
"""
Test leadership signal collection for all 10 companies.

Usage:
    python test_leadership.py
    python test_leadership.py --ticker JPM
"""

import asyncio
import argparse
from uuid import UUID
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from app.pipelines.leadership_signals import LeadershipSignalCollector
from app.services.snowflake import get_connection
from app.config import get_settings


TARGET_COMPANIES = {
    'JPM': {'name': 'JPMorgan Chase', 'sector': 'Financial'},
    'GS': {'name': 'Goldman Sachs', 'sector': 'Financial'},
    'WMT': {'name': 'Walmart Inc.', 'sector': 'Retail'},
    'TGT': {'name': 'Target Corporation', 'sector': 'Retail'},
    'UNH': {'name': 'UnitedHealth Group', 'sector': 'Healthcare'},
    'ADP': {'name': 'Automatic Data Processing', 'sector': 'Services'},
    'PAYX': {'name': 'Paychex Inc.', 'sector': 'Services'},
    'HCA': {'name': 'HCA Healthcare', 'sector': 'Healthcare'},
    'CAT': {'name': 'Caterpillar Inc.', 'sector': 'Manufacturing'},
    'DE': {'name': 'Deere & Company', 'sector': 'Manufacturing'},
}


async def get_company_id(ticker: str) -> UUID:
    """Get company_id from database by ticker"""
    settings = get_settings()
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        query = f"""
        SELECT id FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies
        WHERE ticker = %s AND is_deleted = FALSE
        """
        cur.execute(query, (ticker,))
        row = cur.fetchone()
        
        if not row:
            raise ValueError(f"Company not found: {ticker}")
        
        return UUID(row[0])
    finally:
        cur.close()
        conn.close()


async def test_single_company(ticker: str):
    """Test leadership signal collection for a single company"""
    
    if ticker not in TARGET_COMPANIES:
        print(f"❌ Unknown ticker: {ticker}")
        print(f"Available: {', '.join(TARGET_COMPANIES.keys())}")
        return False
    
    company_info = TARGET_COMPANIES[ticker]
    
    print("\n" + "="*100)
    print(f"🧪 LEADERSHIP SIGNAL ANALYSIS: {ticker} - {company_info['name']}")
    print("="*100 + "\n")
    
    try:
        # Get company_id
        company_id = await get_company_id(ticker)
        
        # Initialize collector
        collector = LeadershipSignalCollector()
        
        # Collect signals
        signal = await collector.analyze_company_leadership(
            company_id=company_id,
            ticker=ticker,
            company_name=company_info['name']
        )
        
        # Display results
        print("\n" + "="*100)
        print("📊 RESULTS SUMMARY")
        print("="*100 + "\n")
        
        print(f"Leadership Score:    {signal.normalized_score:.1f}/100")
        print(f"Confidence:          {signal.confidence:.2f}")
        print(f"Tier:                {signal.metadata['tier']}")
        print(f"Penalty Applied:     {signal.metadata['penalty_multiplier']:.0%}")
        
        if signal.metadata['penalty_multiplier'] < 1.0:
            print(f"Raw Score:           {signal.metadata['raw_score']:.1f}/100 (before penalty)")
        
        print()
        print(f"Total Executives:    {signal.metadata['executives_analyzed']}")
        print(f"  ├─ AI-Relevant:    {signal.metadata['ai_executives']}")
        print(f"  └─ Generic:        {signal.metadata['generic_executives']}")
        
        # Show which executives were used for scoring
        if signal.metadata['ai_executives'] > 0:
            print(f"\n💡 Scoring used {signal.metadata['ai_executives']} AI-relevant executive(s) only")
        else:
            print(f"\n⚠️  No AI-relevant executives found - using {signal.metadata['generic_executives']} generic executive(s) with 50% penalty")
        
        # All executives table
        print("\n" + "="*100)
        print("👥 ALL EXECUTIVES FOUND")
        print("="*100 + "\n")
        
        exec_details = signal.metadata['executive_details']
        
        if not exec_details:
            print("No executives found.\n")
        else:
            print(f"{'#':<4} {'Name':<28} {'Title':<38} {'Type':<14} {'Role Wt':<9} {'AI Score':<9}")
            print("-"*100)
            
            for i, exec_detail in enumerate(exec_details, 1):
                name = exec_detail['name'][:27]
                title = exec_detail['title'][:37]
                exec_type = '🎯 AI-Relevant' if exec_detail['is_ai_relevant'] else '📋 Generic'
                role_wt = exec_detail['role_weight']
                ai_score = exec_detail['ai_score']
                print(f"{i:<4} {name:<28} {title:<38} {exec_type:<14} {role_wt:<9.2f} {ai_score:<9.2f}")
        
        # AI Indicators Detail
        if exec_details:
            print("\n" + "="*100)
            print("🎯 AI INDICATORS BY EXECUTIVE")
            print("="*100 + "\n")
            
            for exec_detail in exec_details:
                is_ai_relevant = exec_detail['is_ai_relevant']
                marker = "🎯" if is_ai_relevant else "📋"
                
                print(f"{marker} {exec_detail['name']}")
                print(f"   Title: {exec_detail['title']}")
                print(f"   Role Weight: {exec_detail['role_weight']:.2f} | AI Score: {exec_detail['ai_score']:.2f}")
                
                if exec_detail['indicators']:
                    print(f"   AI Indicators:")
                    for ind in exec_detail['indicators']:
                        print(f"     ✓ {ind['type']}: {ind['score']:.2f}")
                        print(f"       Evidence: {ind['evidence']}")
                else:
                    print(f"   ✗ No AI indicators found")
                
                print()
        
        # Score calculation breakdown
        print("="*100)
        print("📊 SCORE CALCULATION")
        print("="*100 + "\n")
        
        if signal.metadata['ai_executives'] > 0:
            print(f"Using {signal.metadata['ai_executives']} AI-Relevant Executive(s):\n")
        else:
            print(f"Using {signal.metadata['generic_executives']} Generic Executive(s) (No AI leadership found):\n")
        
        print(f"{'Executive':<30} {'Role Weight':<12} {'AI Score':<10} {'Contribution':<15}")
        print("-"*100)
        
        total_weighted = 0
        total_weight = 0
        
        for exec_detail in exec_details:
            name = exec_detail['name'][:29]
            role = exec_detail['role_weight']
            ai = exec_detail['ai_score']
            contrib = role * ai
            
            total_weighted += contrib
            total_weight += role
            
            print(f"{name:<30} {role:<12.2f} {ai:<10.2f} {contrib:<15.4f}")
        
        print("-"*100)
        print(f"{'TOTALS':<30} {total_weight:<12.2f} {'':10} {total_weighted:<15.4f}")
        print()
        
        if signal.metadata['penalty_multiplier'] < 1.0:
            print(f"Raw Score:    {signal.metadata['raw_score']:.1f}/100")
            print(f"Penalty:      × {signal.metadata['penalty_multiplier']:.0%} (No AI leadership)")
            print(f"Final Score:  {signal.normalized_score:.1f}/100")
        else:
            print(f"Score = {total_weighted:.4f} / {total_weight:.4f} × 100 = {signal.normalized_score:.1f}/100")
        
        # Interpretation
        print("\n" + "="*100)
        print("💡 INTERPRETATION")
        print("="*100 + "\n")
        
        score = signal.normalized_score
        
        if signal.metadata['tier'] == "AI Leadership Present":
            print(f"✅ {ticker} has dedicated AI leadership")
        else:
            print(f"⚠️  {ticker} lacks dedicated AI leadership (penalty applied)")
        
        print()
        
        if score >= 70:
            print(f"🌟 AI LEADER: Strong AI leadership commitment")
            print(f"   → Multiple AI-focused executives with technical backgrounds")
        elif score >= 50:
            print(f"✅ AI ADOPTER: Active investment in AI leadership")
            print(f"   → Has CTO/CIO/Chief Data Officer with AI focus")
        elif score >= 30:
            print(f"⚠️  AI EXPLORER: Limited AI leadership signals")
            print(f"   → Some tech roles, but limited AI-specific expertise")
        else:
            print(f"ℹ️  TRADITIONAL: Minimal AI leadership focus")
            print(f"   → Leadership team lacks AI/tech backgrounds")
        
        # Key findings
        print("\n📌 Key Findings:")
        
        ai_execs = [e for e in exec_details if e['ai_score'] >= 0.5]
        if ai_execs:
            print(f"   ✓ {len(ai_execs)} executive(s) with strong AI signals (score ≥ 0.5):")
            for e in ai_execs:
                print(f"     • {e['name']}: {e['title'][:55]}")
        else:
            print(f"   ✗ No executives with significant AI backgrounds found")
        
        tech_roles = [e for e in exec_details if any(kw in e['title'].lower() 
                     for kw in ['cto', 'cio', 'cdo', 'technology', 'information', 'data', 'digital'])]
        if tech_roles:
            print(f"   ✓ {len(tech_roles)} technology leadership role(s)")
        else:
            print(f"   ✗ No dedicated technology leadership roles")
        
        # Cleanup
        await collector.close()
        
        print("\n" + "="*100)
        print("✅ TEST COMPLETE")
        print("="*100 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}\n")
        import traceback
        traceback.print_exc()
        return False


async def test_all_companies():
    """Test leadership signals for all 10 companies"""
    
    print("\n" + "="*100)
    print("🧪 LEADERSHIP SIGNALS - ALL 10 COMPANIES")
    print("="*100 + "\n")
    
    results = []
    
    for ticker, company_info in TARGET_COMPANIES.items():
        print(f"▶️  {ticker} - {company_info['name']}...", end=' ')
        
        try:
            company_id = await get_company_id(ticker)
            collector = LeadershipSignalCollector()
            
            signal = await collector.analyze_company_leadership(
                company_id=company_id,
                ticker=ticker,
                company_name=company_info['name']
            )
            
            ai_execs = signal.metadata.get('ai_executives', 0)
            tier = signal.metadata.get('tier', 'Unknown')
            
            results.append({
                'ticker': ticker,
                'company': company_info['name'][:28],
                'sector': company_info['sector'],
                'score': signal.normalized_score,
                'confidence': signal.confidence,
                'executives': signal.metadata['executives_analyzed'],
                'ai_executives': ai_execs,
                'tier': tier,
                'status': 'success'
            })
            
            print(f"✅ {signal.normalized_score:.1f}/100 | AI Execs: {ai_execs}")
            
            await collector.close()
            
        except Exception as e:
            print(f"❌ {str(e)[:50]}")
            results.append({
                'ticker': ticker,
                'company': company_info['name'][:28],
                'sector': company_info['sector'],
                'score': 0,
                'confidence': 0,
                'executives': 0,
                'ai_executives': 0,
                'tier': 'Failed',
                'status': 'failed'
            })
    
    # Summary table
    print("\n" + "="*100)
    print("📊 FINAL RESULTS - ALL COMPANIES")
    print("="*100 + "\n")
    
    print(f"{'Rank':<6} {'Ticker':<8} {'Company':<29} {'Sector':<13} {'Score':<9} {'AI Execs':<10} {'Tier':<30}")
    print("-"*100)
    
    for rank, r in enumerate(sorted(results, key=lambda x: x['score'], reverse=True), 1):
        tier_icon = "🎯" if "AI Leadership" in r['tier'] else "⚠️ " if "Penalty" in r['tier'] else "❌"
        print(f"{rank:<6} {r['ticker']:<8} {r['company']:<29} {r['sector']:<13} "
              f"{r['score']:<9.1f} {r['ai_executives']:<10} {tier_icon} {r['tier']:<30}")
    
    # Statistics by sector
    print("\n" + "="*100)
    print("📈 SECTOR ANALYSIS")
    print("="*100 + "\n")
    
    sectors = {}
    for r in results:
        if r['status'] == 'success':
            sector = r['sector']
            if sector not in sectors:
                sectors[sector] = {'scores': [], 'ai_execs': [], 'companies': []}
            sectors[sector]['scores'].append(r['score'])
            sectors[sector]['ai_execs'].append(r['ai_executives'])
            sectors[sector]['companies'].append(r['ticker'])
    
    print(f"{'Sector':<20} {'Avg Score':<12} {'Avg AI Execs':<15} {'Companies':<40}")
    print("-"*100)
    
    for sector, data in sorted(sectors.items(), key=lambda x: sum(x[1]['scores'])/len(x[1]['scores']), reverse=True):
        avg_score = sum(data['scores']) / len(data['scores'])
        avg_ai = sum(data['ai_execs']) / len(data['ai_execs'])
        companies = ', '.join(data['companies'])
        print(f"{sector:<20} {avg_score:<12.1f} {avg_ai:<15.1f} {companies:<40}")
    
    # Overall statistics
    successful = [r for r in results if r['status'] == 'success']
    if successful:
        print("\n" + "="*100)
        print("📊 OVERALL STATISTICS")
        print("="*100 + "\n")
        
        avg_score = sum(r['score'] for r in successful) / len(successful)
        total_executives = sum(r['executives'] for r in successful)
        total_ai = sum(r['ai_executives'] for r in successful)
        companies_with_ai = sum(1 for r in successful if r['ai_executives'] > 0)
        
        print(f"  Success Rate:              {len(successful)}/10 companies")
        print(f"  Average Score:             {avg_score:.1f}/100")
        print(f"  Total Executives Found:    {total_executives}")
        print(f"  Total AI-Relevant Execs:   {total_ai}")
        print(f"  Companies with AI Leaders: {companies_with_ai}/10")
        print(f"  AI Penetration Rate:       {(total_ai/total_executives*100):.1f}%")
    
    print("\n" + "="*100)
    print("✅ ALL TESTS COMPLETE")
    print("="*100 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Test leadership signal collection"
    )
    parser.add_argument(
        '--ticker',
        help='Test single company (e.g., JPM)',
        type=str
    )
    
    args = parser.parse_args()
    
    if args.ticker:
        asyncio.run(test_single_company(args.ticker.upper()))
    else:
        asyncio.run(test_all_companies())


if __name__ == '__main__':
    main()