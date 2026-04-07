#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path

try:
    from liteparse import LiteParse
except ImportError:
    print("Error: liteparse is not installed. Please run `uv sync` or install it via pip.", file=sys.stderr)
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Extract text from documents using liteparse.")
    parser.add_argument("file_path", type=str, help="Absolute path to the document file")
    
    args = parser.parse_args()
    file_path = Path(args.file_path)
    
    if not file_path.exists():
        print(f"Error: File not found at {file_path}", file=sys.stderr)
        sys.exit(1)
        
    try:
        lp = LiteParse()
        result = lp.parse(str(file_path))
        if hasattr(result, "text"):
            print(result.text)
        else:
            print("Error: Parsing result did not contain text attribute.", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error parsing file: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
