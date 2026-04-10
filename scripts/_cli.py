"""CLI argument parsing and schema introspection."""

from __future__ import annotations

import argparse
import json
import sys

from _output import print_err
from schemas import DocumentType, PAYLOAD_SCHEMA_MAP


def build_parser(version: str) -> argparse.ArgumentParser:
    """Build the argument parser for parse_vision.py."""
    parser = argparse.ArgumentParser(
        description="Document extraction engine using Google Gemini models."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {version}")
    parser.add_argument("file_path", nargs="?", help="Local file path")
    parser.add_argument("--url", help="Remote URL to download and extract")
    parser.add_argument(
        "--type", help="Skip pass 1 and use the supplied document type directly"
    )
    parser.add_argument(
        "--skip-liteparse",
        action="store_true",
        help="Skip liteparse local text extraction (vision-only)",
    )
    parser.add_argument(
        "--output", help="Write JSON directly to this file instead of stdout"
    )
    parser.add_argument(
        "--pages",
        help="Pages to extract (e.g., '1-3' or '1,3,5'). Only applies to PDFs.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Dump raw LLM response string on validation failure",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Disable the compact one-line summary printed to stderr after each extraction",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show progress messages on stderr (suppressed by default; warnings and errors always shown)",
    )
    parser.add_argument(
        "--format",
        choices=["plain", "markdown"],
        default="plain",
        help="Summary output format: plain (pipe-delimited) or markdown (table row)",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Classify only (skip extraction pass 2). Print summaries to stderr, no JSON output",
    )
    parser.add_argument(
        "--schema",
        help="Print JSON schema for a document type and exit. Use a TYPE name or 'all'.",
    )
    return parser


def handle_schema(type_arg: str) -> None:
    """Print JSON schema for a document type (or all types) to stdout."""
    if type_arg.lower() == "all":
        all_schemas = {}
        for doc_type, model_cls in PAYLOAD_SCHEMA_MAP.items():
            all_schemas[doc_type.value] = model_cls.model_json_schema()
        print(json.dumps(all_schemas, indent=2))
        return

    raw = type_arg.upper()
    try:
        doc_type = DocumentType(raw)
    except ValueError:
        valid = ", ".join(t.value for t in DocumentType)
        print_err(f"Error: Unknown type '{raw}'. Valid: {valid}")
        sys.exit(2)

    if doc_type not in PAYLOAD_SCHEMA_MAP:
        print_err(f"Error: No schema for type '{raw}' (type exists but has no payload model)")
        sys.exit(2)

    print(json.dumps(PAYLOAD_SCHEMA_MAP[doc_type].model_json_schema(), indent=2))
