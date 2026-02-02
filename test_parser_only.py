#!/usr/bin/env python
"""
Test parser with REAL SEC filing from data directory.

Usage:
    python test_parser_real.py
    python test_parser_real.py path/to/filing.txt
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from app.pipelines.document_parser import DocumentParser


def find_sec_files():
    """Find downloaded SEC filing files"""
    sec_dir = Path("data/raw/sec/sec-edgar-filings")
    
    if not sec_dir.exists():
        return []
    
    # Find all full-submission.txt files
    files = list(sec_dir.glob("**/full-submission.txt"))
    return files


def test_parser_on_file(file_path: Path):
    """Test parser on a real SEC filing"""
    
    print("="*70)
    print(f"TESTING PARSER ON REAL FILE")
    print("="*70)
    
    # Extract info from path
    parts = file_path.parts
    ticker = parts[-3] if len(parts) >= 3 else "UNKNOWN"
    filing_type = parts[-4] if len(parts) >= 4 else "UNKNOWN"
    
    print(f"\nFile Info:")
    print(f"  Path: {file_path}")
    print(f"  Ticker: {ticker}")
    print(f"  Filing Type (from path): {filing_type}")
    print(f"  File size: {file_path.stat().st_size:,} bytes")
    
    # Initialize parser
    parser = DocumentParser()
    print("\n✓ Parser initialized")
    
    # Parse the document
    print("\nParsing document...")
    try:
        parsed = parser.parse_filing(file_path, ticker=ticker)
        print("✓ Parsing complete")
    except Exception as e:
        print(f"❌ Parsing failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Display results
    print(f"\n{'─'*70}")
    print("PARSING RESULTS")
    print(f"{'─'*70}")
    
    print(f"\nDocument Info:")
    print(f"  Filing Type Detected: {parsed.filing_type}")
    print(f"  Ticker: {parsed.company_ticker}")
    print(f"  Format: {parsed.detected_format.value}")
    print(f"  Filing Date: {parsed.filing_date}")
    
    print(f"\nContent Metrics:")
    print(f"  Total Words: {parsed.word_count:,}")
    print(f"  Content Hash: {parsed.content_hash[:16]}...")
    
    print(f"\nSection Extraction:")
    print(f"  Sections Found: {parsed.sections_found}")
    
    if parsed.sections:
        section_words = sum(len(s.split()) for s in parsed.sections.values())
        efficiency = (section_words / parsed.word_count * 100) if parsed.word_count > 0 else 0
        
        print(f"  AI-Relevant Words: {section_words:,}")
        print(f"  Extraction Efficiency: {efficiency:.1f}%")
        print(f"  (Only {efficiency:.1f}% of document needs processing)")
        
        print(f"\n  {'Section Name':<40} {'Words':>10} {'% of Total':>12}")
        print(f"  {'-'*64}")
        for section_name, content in parsed.sections.items():
            word_count = len(content.split())
            pct = (word_count / parsed.word_count * 100) if parsed.word_count > 0 else 0
            print(f"  {section_name:<40} {word_count:>10,} {pct:>11.1f}%")
            
            # Show preview (first 150 chars)
            preview = content[:150].replace('\n', ' ').strip()
            print(f"     Preview: {preview}...")
            print()
        
        # Check for AI keywords
        print(f"{'─'*70}")
        print("AI KEYWORD DETECTION")
        print(f"{'─'*70}")
        
        keywords = [
            'machine learning', 'artificial intelligence', 'AI', 'ML',
            'neural network', 'deep learning', 'data scientist',
            'PyTorch', 'TensorFlow', 'cloud', 'AWS', 'Azure',
            'algorithm', 'automation', 'predictive'
        ]
        
        full_text = ' '.join(parsed.sections.values()).lower()
        found_keywords = [kw for kw in keywords if kw.lower() in full_text]
        
        if found_keywords:
            print(f"\nFound {len(found_keywords)} AI-related keywords:")
            for kw in found_keywords[:10]:  # Show first 10
                print(f"  ✓ {kw}")
            if len(found_keywords) > 10:
                print(f"  ... and {len(found_keywords) - 10} more")
        else:
            print("\n⚠ No AI keywords found (may not be an AI-focused company)")
        
        print(f"\n{'='*70}")
        print("✅ PARSER TEST PASSED!")
        print(f"\nSummary:")
        print(f"  • Successfully parsed {parsed.word_count:,} words")
        print(f"  • Extracted {parsed.sections_found} AI-relevant sections")
        print(f"  • Achieved {efficiency:.1f}% efficiency (reduced processing needs)")
        print(f"  • Detected filing type: {parsed.filing_type}")
        
        return True
    else:
        print("\n❌ No sections found!")
        print("\nPossible reasons:")
        print("  • This filing type may not have the expected sections")
        print("  • Section headers may be formatted differently")
        print("  • File might be corrupted or incomplete")
        
        # Show sample of content to debug
        print(f"\nFirst 500 characters of content:")
        print(parsed.content[:500])
        
        return False


def main():
    """Main test function"""
    
    # Check if file path provided as argument
    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            return False
        return test_parser_on_file(file_path)
    
    # Otherwise, look for SEC files
    print("Looking for SEC filings in data/raw/sec/...")
    files = find_sec_files()
    
    if not files:
        print("\n❌ No SEC filings found!")
        print("\nTo fix this:")
        print("1. Download filings via API:")
        print("   POST /api/v1/companies/{company_id}/sec-edgar/download")
        print("\n2. Or manually place SEC filings in:")
        print("   data/raw/sec/sec-edgar-filings/{TICKER}/{FILING_TYPE}/*/full-submission.txt")
        print("\n3. Or run with a specific file:")
        print("   python test_parser_real.py path/to/your/filing.txt")
        return False
    
    print(f"✓ Found {len(files)} SEC filings\n")
    
    # Test first file
    print(f"Testing first file: {files[0].name}")
    success = test_parser_on_file(files[0])
    
    # Show other available files
    if len(files) > 1:
        print(f"\n{'─'*70}")
        print(f"Other available files to test ({len(files)-1}):")
        print(f"{'─'*70}")
        for f in files[1:6]:  # Show up to 5 more
            parts = f.parts
            ticker = parts[-3] if len(parts) >= 3 else "?"
            filing = parts[-4] if len(parts) >= 4 else "?"
            print(f"  {ticker:6} {filing:8} {f}")
        if len(files) > 6:
            print(f"  ... and {len(files)-6} more")
        print(f"\nTo test a different file:")
        print(f"  python test_parser_real.py <path_to_file>")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)