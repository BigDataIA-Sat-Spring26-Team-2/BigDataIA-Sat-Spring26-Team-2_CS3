import sys
from pathlib import Path
import argparse
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.config import get_settings
from app.services.s3_storage import upload_file_to_s3
import structlog

logger = structlog.get_logger()


ALL_TICKERS = [
    "JPM", "WMT", "NVDA", "GE", "DG", "GS", "TGT", 
    "CAT", "DE", "UNH", "HCA", "ADP", "PAYX"
]


def find_local_glassdoor_files(local_dir: str = "data/glassdoor") -> dict:

    local_path = Path(local_dir)
    
    if not local_path.exists():
        logger.error("Local directory not found", path=str(local_path))
        return {}
    
    found_files = {}
    
    for ticker in ALL_TICKERS:
        possible_files = [
            local_path / f"{ticker.lower()}_glassdoor.json",
        ]
        
        for file_path in possible_files:
            if file_path.exists():
                found_files[ticker] = file_path
                logger.info("Found local file", ticker=ticker, path=str(file_path))
                break
    
    return found_files


def upload_to_s3(ticker: str, local_path: Path, dry_run: bool = False) -> bool:

    s3_key = f"glassdoor/{ticker}_reviews.json"
    
    logger.info("Preparing S3 upload", 
               ticker=ticker,
               local_path=str(local_path),
               s3_key=s3_key,
               dry_run=dry_run)
    
    
    if dry_run:
        logger.info("[DRY RUN] Would upload to S3", 
                   ticker=ticker,
                   s3_key=s3_key,
                   file_size=local_path.stat().st_size)
        return True
    
    try:
        s3_uri = upload_file_to_s3(local_path, s3_key)
        
        logger.info("Upload successful", 
                   ticker=ticker,
                   s3_uri=s3_uri,
                   file_size=local_path.stat().st_size)
        
        return True
        
    except Exception as e:
        logger.error("Upload failed", 
                    ticker=ticker,
                    error=str(e),
                    error_type=type(e).__name__)
        return False


def main(
    tickers: list = None,
    local_dir: str = "data/glassdoor"
):

    print("\n" + "="*80)
    print("GLASSDOOR DATA MIGRATION: LOCAL → S3")
    print("="*80)
    
    
    # Check S3 configuration
    settings = get_settings()
    
    if not all([settings.AWS_ACCESS_KEY_ID, 
                settings.AWS_SECRET_ACCESS_KEY, 
                settings.S3_BUCKET]):
        print(" ERROR: S3 not configured")
        print("\nMissing environment variables:")
        if not settings.AWS_ACCESS_KEY_ID:
            print("  - AWS_ACCESS_KEY_ID")
        if not settings.AWS_SECRET_ACCESS_KEY:
            print("  - AWS_SECRET_ACCESS_KEY")
        if not settings.S3_BUCKET:
            print("  - S3_BUCKET")
        print("\nUpdate your .env file and try again.")
        return
    
    print(f"S3 Configuration:")
    print(f"   Bucket: {settings.S3_BUCKET}")
    print(f"   Region: {settings.AWS_REGION}")
    print()
    
    # Find local files
    print(f"Scanning local directory: {local_dir}")
    found_files = find_local_glassdoor_files(local_dir)
    
    if not found_files:
        print(f"\n No Glassdoor files found in {local_dir}")
        print("\nExpected file patterns:")
        print("  - {TICKER}_reviews.json")
        print("  - {ticker}_glassdoor.json")
        print("  - {TICKER}.json")
        return
    
    print(f"\nFound {len(found_files)} file(s):")
    for ticker, path in found_files.items():
        file_size = path.stat().st_size
        print(f"   {ticker}: {path.name} ({file_size:,} bytes)")
    
    # Filter by requested tickers
    if tickers:
        tickers_upper = [t.upper() for t in tickers]
        found_files = {
            ticker: path 
            for ticker, path in found_files.items() 
            if ticker in tickers_upper
        }
        print(f"\n Filtered to {len(found_files)} requested ticker(s)")
    
    if not found_files:
        print("\n  No files match requested tickers")
        return
    
    # Upload files
    print("\n" + "="*80)
    print("UPLOAD PROGRESS")
    print("="*80 + "\n")
    
    stats = {
        "total": len(found_files),
        "successful": 0,
        "failed": 0,
        "skipped": 0
    }
    
    for idx, (ticker, local_path) in enumerate(found_files.items(), 1):
        print(f"[{idx}/{len(found_files)}] {ticker}...", end=" ")
        
        success = upload_to_s3(ticker, local_path, dry_run=dry_run)
        
        if success:
            stats["successful"] += 1
            print(" Success")
        else:
            stats["failed"] += 1
            print(" Failed")
    
    # Summary
    print("\n" + "="*80)
    print("UPLOAD SUMMARY")
    print("="*80)
    print(f"\nTotal files:      {stats['total']}")
    print(f"Successful:  {stats['successful']}")
    print(f"Failed:      {stats['failed']}")
    
    print(f"\n Upload complete!")
    print(f"\nS3 bucket: s3://{settings.S3_BUCKET}/glassdoor/")
    print(f"Files uploaded: {stats['successful']}")
    
    print("="*80 + "\n")
    
    # Exit code
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Upload Glassdoor reviews from local folder to S3"
    )
    
    parser.add_argument(
        "--ticker",
        type=str,
        help="Upload specific ticker only (e.g., WMT, JPM)",
        default=None
    )
    
    parser.add_argument(
        "--tickers",
        type=str,
        help="Upload multiple tickers (comma-separated, e.g., WMT,JPM,CAT)",
        default=None
    )
    
    parser.add_argument(
        "--local-dir",
        type=str,
        default="data/glassdoor",
        help="Local directory containing Glassdoor JSON files (default: data/glassdoor)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate upload without actually uploading files"
    )
    
    args = parser.parse_args()
    
    tickers = None
    if args.ticker:
        tickers = [args.ticker.strip()]
    elif args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",")]
    
    # Run upload
    exit_code = main(
        tickers=tickers,
        dry_run=args.dry_run,
        local_dir=args.local_dir
    )
    
    sys.exit(exit_code)