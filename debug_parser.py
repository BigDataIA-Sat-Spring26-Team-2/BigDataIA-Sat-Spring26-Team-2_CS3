from pathlib import Path
import sys
import re

sys.path.insert(0, str(Path(__file__).parent))

from app.pipelines.document_parser import DocumentParser


def debug_parser():
    """Debug the parser to see cleaned text"""
    
    # Find first SEC file
    sec_dir = Path("data/raw/sec/sec-edgar-filings")
    files = list(sec_dir.glob("**/full-submission.txt"))
    
    if not files:
        print("No SEC files found!")
        return
    
    file_path = files[0]
    print(f"Testing file: {file_path}")
    print("="*70)
    
    parser = DocumentParser()
    
    # Parse
    parsed = parser.parse_filing(file_path, ticker="TEST")
    
    # Search for Item 1, 1A, 7 in the cleaned text
    text = parsed.content
    
    print("\nSearching for Item patterns in cleaned text...\n")
    
    # Look for Item 1
    print("─"*70)
    print("SEARCHING FOR ITEM 1 (BUSINESS)")
    print("─"*70)
    pattern = r'.{0,100}Item\s*1[^a-zA-Z].{0,200}'
    matches = re.findall(pattern, text, re.IGNORECASE)
    if matches:
        for i, match in enumerate(matches[:3], 1):
            print(f"\nMatch {i}:")
            print(match.replace('\n', ' '))
    else:
        print("NOT FOUND")
    
    # Look for Item 1A
    print("\n" + "─"*70)
    print("SEARCHING FOR ITEM 1A (RISK FACTORS)")
    print("─"*70)
    pattern = r'.{0,100}Item\s*1A.{0,200}'
    matches = re.findall(pattern, text, re.IGNORECASE)
    if matches:
        for i, match in enumerate(matches[:3], 1):
            print(f"\nMatch {i}:")
            print(match.replace('\n', ' '))
    else:
        print("NOT FOUND")
    
    # Look for Item 7
    print("\n" + "─"*70)
    print("SEARCHING FOR ITEM 7 (MD&A)")
    print("─"*70)
    pattern = r'.{0,100}Item\s*7[^a-zA-Z].{0,200}'
    matches = re.findall(pattern, text, re.IGNORECASE)
    if matches:
        for i, match in enumerate(matches[:3], 1):
            print(f"\nMatch {i}:")
            print(match.replace('\n', ' '))
    else:
        print("NOT FOUND")
    
    # Show what patterns WOULD match
    print("\n" + "="*70)
    print("TESTING DIFFERENT PATTERNS")
    print("="*70)
    
    test_patterns = {
        "Simple Item 1A": r'Item\s*1A',
        "Item 1A with period": r'Item\s*1A\.',
        "Item 1A flexible": r'Item\s*1A[\s.]*Risk',
        "Very flexible": r'Item\s+1A\s+Risk\s+Factors',
    }
    
    for name, pattern in test_patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            context = text[max(0, match.start()-50):match.end()+150]
            print(f"\n✓ {name} MATCHED:")
            print(f"  {context.replace(chr(10), ' ')}")
        else:
            print(f"\n✗ {name} - No match")


if __name__ == "__main__":
    debug_parser()