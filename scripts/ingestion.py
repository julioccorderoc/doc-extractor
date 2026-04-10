"""File ingestion: validation, download, SSRF protection, PDF slicing, format conversion."""

from __future__ import annotations

import ipaddress
import socket
import sys
import urllib.parse
from pathlib import Path

import requests
from pypdf import PdfReader, PdfWriter

from _output import print_err, print_progress

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".xlsx",
    ".docx",
    ".txt",
    ".md",
    ".csv",
}

MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024  # 100 MB


def validate_file(file_path: str) -> Path:
    """Validate that the file exists and has an allowed extension."""
    path = Path(file_path)
    if not path.exists():
        print_err(f"Error: File not found: {file_path}")
        sys.exit(2)
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        print_err(
            f"Error: Unsupported file type '{path.suffix}'. "
            f"Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
        sys.exit(2)
    return path


def preprocess_file(file_path: Path, temp_dir: Path) -> Path:
    """Convert unsupported formats (.xlsx, .docx, .csv) to markdown text using MarkItDown."""
    if file_path.suffix.lower() in {".xlsx", ".docx", ".csv"}:
        print_progress(f"Converting {file_path.suffix} to markdown via MarkItDown...")
        try:
            from markitdown import MarkItDown

            md = MarkItDown()
            result = md.convert(str(file_path))
            md_path = temp_dir / f"{file_path.stem}.txt"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(result.text_content)
            return md_path
        except ImportError:
            print_err(
                "Error: markitdown is required to process .xlsx/.docx/.csv files. (uv add markitdown)"
            )
            sys.exit(2)
        except Exception as e:
            print_err(f"Error converting file: {e}")
            sys.exit(2)
    return file_path


def _reject_private_url(url: str) -> None:
    """Block requests to private/loopback IPs (basic SSRF protection)."""
    hostname = urllib.parse.urlparse(url).hostname
    if not hostname:
        print_err("Error: URL has no hostname.")
        sys.exit(2)
    try:
        infos = socket.getaddrinfo(hostname, None)
        for info in infos:
            addr = ipaddress.ip_address(info[4][0])
            if addr.is_private or addr.is_loopback or addr.is_link_local:
                print_err(f"Error: URL resolves to a private/loopback address ({addr}). Refusing to download.")
                sys.exit(2)
    except socket.gaierror:
        print_err(f"Error: Could not resolve hostname '{hostname}'.")
        sys.exit(2)


def download_url(url: str, dest_dir: Path) -> Path:
    """Download a file from a URL with size limits and SSRF protection."""
    print_progress(f"Downloading {url}...")
    _reject_private_url(url)
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        # Try to get filename from Content-Disposition or URL
        filename = "downloaded_file.pdf"
        if "content-disposition" in response.headers:
            cd = response.headers["content-disposition"]
            if "filename=" in cd:
                filename = cd.split("filename=")[1].strip("\"'")
        else:
            parsed = urllib.parse.urlparse(url)
            if parsed.path:
                name = parsed.path.split("/")[-1]
                if name:
                    filename = name

        dest_path = dest_dir / filename
        bytes_written = 0
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                bytes_written += len(chunk)
                if bytes_written > MAX_DOWNLOAD_BYTES:
                    f.close()
                    dest_path.unlink(missing_ok=True)
                    print_err(f"Error: Download exceeds {MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB limit.")
                    sys.exit(2)
                f.write(chunk)

        return dest_path
    except SystemExit:
        raise
    except Exception as e:
        print_err(f"Error downloading URL: {e}")
        sys.exit(2)


def slice_pdf(file_path: Path, pages_spec: str, dest_dir: Path) -> Path:
    """Slice a PDF to specific pages (e.g., '1-3' or '1,3,5')."""
    print_progress(f"Slicing PDF to pages: {pages_spec}")
    try:
        reader = PdfReader(file_path)
        writer = PdfWriter()

        # Parse pages_spec: "1-3", "1,3,5"
        pages_to_keep = set()
        for part in pages_spec.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-")
                start_idx = int(start) - 1
                end_idx = int(end) - 1
                for i in range(start_idx, end_idx + 1):
                    pages_to_keep.add(i)
            else:
                pages_to_keep.add(int(part) - 1)

        num_pages = len(reader.pages)
        added_any = False
        for i in sorted(pages_to_keep):
            if 0 <= i < num_pages:
                writer.add_page(reader.pages[i])
                added_any = True
            else:
                print_err(
                    f"Warning: Page {i + 1} is out of range (PDF has {num_pages} pages)."
                )

        if not added_any:
            print_err("Error: No valid pages selected for slicing.")
            sys.exit(2)

        dest_path = dest_dir / f"sliced_{file_path.name}"
        with open(dest_path, "wb") as f:
            writer.write(f)

        return dest_path
    except Exception as e:
        print_err(f"Error slicing PDF: {e}")
        sys.exit(2)
