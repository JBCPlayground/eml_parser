"""Shared utilities for eml_parser: logging, header building, dedup, file URLs."""

import logging
import os
import platform
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

DATE_FORMAT_DISPLAY = "%B %d, %Y at %I:%M %p"


# --- Logging ---

def get_logger(name: str) -> logging.Logger:
    """Return a logger under the eml_parser namespace."""
    return logging.getLogger(f"eml_parser.{name}")


def configure_logging(verbose: bool = False) -> None:
    """Set up root eml_parser logger with a stderr StreamHandler."""
    logger = logging.getLogger("eml_parser")
    logger.setLevel(logging.DEBUG if verbose else logging.WARNING)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(handler)


# --- Email header HTML builder ---

def build_email_header_html(
    subject: str,
    sender: str,
    recipients: list[str],
    date: datetime | None,
    *,
    styled: bool = False,
) -> str:
    """Build email header HTML block.

    styled=True  -> inline CSS (for PDF)
    styled=False -> plain HTML (for RTF)
    """
    date_str = date.strftime(DATE_FORMAT_DISPLAY) if date else "Unknown"
    recipients_str = ", ".join(recipients) if recipients else "Unknown"

    if styled:
        return (
            '<div style="border-bottom: 2px solid #333; margin-bottom: 20px; padding-bottom: 10px;">'
            f'<h1 style="margin: 0 0 10px 0; font-size: 18pt;">{subject}</h1>'
            f'<p style="margin: 5px 0;"><strong>From:</strong> {sender}</p>'
            f'<p style="margin: 5px 0;"><strong>To:</strong> {recipients_str}</p>'
            f'<p style="margin: 5px 0;"><strong>Date:</strong> {date_str}</p>'
            '</div>'
        )

    return (
        "<div>"
        f"<p><strong>Subject:</strong> {subject}</p>"
        f"<p><strong>From:</strong> {sender}</p>"
        f"<p><strong>To:</strong> {recipients_str}</p>"
        f"<p><strong>Date:</strong> {date_str}</p>"
        "<hr>"
        "</div>"
    )


def inject_header_into_html(html_content: str, header_html: str) -> str:
    """Insert header_html immediately after the <body> tag, or prepend."""
    if "<body" in html_content.lower():
        return re.sub(
            r'(<body[^>]*>)',
            rf'\1{header_html}',
            html_content,
            count=1,
            flags=re.IGNORECASE,
        )
    return header_html + html_content


# --- Filename deduplication ---

def deduplicate_path(path: Path, used_names: set[str] | None = None) -> Path:
    """Return a non-colliding path by appending _1, _2, ... if needed.

    Checks both the filesystem and an optional in-memory *used_names* set.
    If *used_names* is provided, the chosen name is added to it.
    """
    if not path.exists() and (used_names is None or path.stem not in used_names):
        if used_names is not None:
            used_names.add(path.stem)
        return path

    parent = path.parent
    stem = path.stem
    suffix = path.suffix
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists() and (used_names is None or candidate.stem not in used_names):
            if used_names is not None:
                used_names.add(candidate.stem)
            return candidate
        counter += 1


# --- Platform-aware file URL generation ---

def _is_wsl() -> bool:
    """Detect WSL by checking the kernel release string."""
    try:
        return "microsoft" in platform.uname().release.lower()
    except Exception:
        return False


def path_to_file_url(path: Path) -> str:
    """Convert a Path to a file:// URL.

    On WSL, produces a Windows-compatible ``file:`` URL via ``\\\\wsl.localhost``.
    Elsewhere, produces a standard ``file:///`` URL.
    """
    absolute_path = str(path.absolute())

    if _is_wsl():
        distro = os.environ.get("WSL_DISTRO_NAME", "")
        if distro:
            windows_path = f"\\\\wsl.localhost\\{distro}{absolute_path.replace('/', '\\')}"
            url_path = windows_path.replace('\\', '/')
            return f"file:{quote(url_path, safe='/:')}"

    # Standard file URL
    return f"file://{quote(absolute_path, safe='/:')}"
