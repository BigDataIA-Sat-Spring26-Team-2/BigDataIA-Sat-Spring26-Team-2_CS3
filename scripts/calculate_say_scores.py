# scripts/calculate_say_scores.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pipelines.say_score_analyzer import SayScoreAnalyzer

TARGET_COMPANIES = [
    "CAT", "DE", "UNH", "HCA", "ADP", 
    "PAYX", "WMT", "TGT", "JPM", "GS"
]

def main():
    analyzer = SayScoreAnalyzer()
    
    print("\n" + "="*70)
    print("SAY SCORE ANALYSIS - SEC FILINGS")
    print("="*70 + "\n")
    
    results = []
    
    for ticker in TARGET_COMPANIES:
        try:
            say_score = analyzer.calculate_say_score(ticker)
            
            # Debug: Check what type is returned
            if not isinstance(say_score, (int, float)):
                print(f"⚠️  {ticker}: Unexpected type returned: {type(say_score)}")
                print(f"   Value: {say_score}")
                say_score = 0.0
            
            results.append((ticker, say_score))
            print(f"{ticker:6} | Say Score: {say_score:5.1f}")
            
        except Exception as e:
            print(f"❌ {ticker}: Error - {str(e)}")
            results.append((ticker, 0.0))
    
    if results:
        avg_score = sum(s for _, s in results) / len(results)
        print("\n" + "="*70)
        print(f"Average Say Score: {avg_score:.1f}")
        print("="*70 + "\n")
    
    return results

if __name__ == "__main__":
    main()