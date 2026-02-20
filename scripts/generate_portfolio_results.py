"""
Generate 5-company portfolio results and store as JSON files.
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.services.integration_service import ScoringIntegrationService

TARGET_TICKERS = ["NVDA", "JPM", "WMT", "GE", "DG"]


def generate_result(ticker: str, service: ScoringIntegrationService) -> dict:
    print(f"\n{'─'*60}")
    print(f"  Scoring {ticker}...")
    print(f"{'─'*60}")

    result = service.score_company(ticker)
    result["generated_at"] = datetime.now(timezone.utc).isoformat()

    print(f"  Org-AI-R : {result.get('org_air_score', 0):.1f}")
    print(f"  V^R      : {result.get('vr_score', 0):.1f}")
    print(f"  H^R      : {result.get('hr_score', 0):.1f}")
    print(f"  PF       : {result.get('position_factor', 0):.3f}")
    print(f"  TC       : {result.get('talent_concentration', 0):.3f}")

    return result


def save_result(ticker: str, result: dict, out_dir: Path) -> None:
    out_path = out_dir / f"{ticker.lower()}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"  Saved → {out_path}")


def print_summary(results: dict) -> None:
    """Print portfolio comparison table."""
    print("\n" + "=" * 60)
    print("PORTFOLIO SUMMARY")
    print("=" * 60)
    print(f"{'Ticker':<8} {'Org-AI-R':>9} {'V^R':>7} {'H^R':>7} {'PF':>7} {'TC':>7}")
    print("-" * 60)
    for ticker, result in results.items():
        print(
            f"{ticker:<8}"
            f"{result.get('org_air_score', 0):>9.1f}"
            f"{result.get('vr_score', 0):>7.1f}"
            f"{result.get('hr_score', 0):>7.1f}"
            f"{result.get('position_factor', 0):>7.3f}"
            f"{result.get('talent_concentration', 0):>7.3f}"
        )
    print("=" * 60)


def main(tickers: list) -> None:
    out_dir = Path("reports")
    out_dir.mkdir(parents=True, exist_ok=True)

    service = ScoringIntegrationService()
    results = {}

    print("\n" + "=" * 60)
    print("PE ORG-AI-R — 5-COMPANY PORTFOLIO SCORING")
    print("=" * 60)

    for ticker in tickers:
        try:
            result = generate_result(ticker, service)
            save_result(ticker, result, out_dir)
            results[ticker] = result
        except Exception as e:
            print(f"\nFailed to score {ticker}: {e}")
            import traceback
            traceback.print_exc()

    if results:
        print_summary(results)

    print(f"\nResults written to: {out_dir.resolve()}/")
    for f in sorted(out_dir.glob("*.json")):
        print(f"  {f.name}  ({f.stat().st_size:,} bytes)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate 5-company portfolio scoring results"
    )
    parser.add_argument(
        "--ticker",
        type=str,
        help="Score a single ticker (e.g. NVDA). Scores all 5 if omitted.",
        default=None,
    )
    args = parser.parse_args()

    tickers_to_run = [args.ticker.upper()] if args.ticker else TARGET_TICKERS
    main(tickers_to_run)