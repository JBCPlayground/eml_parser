"""Convert emails to PDF format."""

import re
from pathlib import Path

from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

from .extractor import get_html_for_pdf
from .parser import ParsedEmail
from .utils import (
    build_email_header_html,
    deduplicate_path,
    get_logger,
    inject_header_into_html,
)

logger = get_logger(__name__)


def sanitize_html_for_pdf(html_content: str) -> str:
    """Sanitize HTML content to avoid PDF rendering issues."""
    # Remove zero-width and invisible characters
    html_content = re.sub(r'[\u200b-\u200f\u2028-\u202f\u2060-\u206f\ufeff]', '', html_content)

    # Replace problematic Unicode characters with safe alternatives
    replacements = {
        '\u2018': "'",  # Left single quote
        '\u2019': "'",  # Right single quote
        '\u201c': '"',  # Left double quote
        '\u201d': '"',  # Right double quote
        '\u2014': '-',  # Em dash
        '\u2013': '-',  # En dash
        '\u2026': '...',  # Ellipsis
        '\u00a0': ' ',  # Non-breaking space
    }
    for char, replacement in replacements.items():
        html_content = html_content.replace(char, replacement)

    # Remove emojis and other high Unicode characters that cause pyphen issues
    result = []
    for char in html_content:
        code = ord(char)
        if code > 0xFFFF:  # Emoji and other supplementary characters
            continue
        if 0x2600 <= code <= 0x27BF:  # Misc symbols
            continue
        result.append(char)

    return ''.join(result)


def email_to_pdf(email: ParsedEmail, output_path: Path) -> Path:
    """Convert a parsed email to PDF."""
    html_content = get_html_for_pdf(email)

    # Sanitize to avoid encoding issues
    html_content = sanitize_html_for_pdf(html_content)

    # Sanitize header fields too
    subject = sanitize_html_for_pdf(email.subject)
    sender = sanitize_html_for_pdf(email.sender)
    recipients = [sanitize_html_for_pdf(r) for r in email.recipients[:3]]

    # Add email header information
    header_html = build_email_header_html(subject, sender, recipients, email.date, styled=True)
    html_content = inject_header_into_html(html_content, header_html)

    font_config = FontConfiguration()

    # Disable hyphenation to avoid pyphen character range errors
    css = CSS(string="""
        @page {
            size: letter;
            margin: 1in;
        }
        * {
            hyphens: none !important;
            -webkit-hyphens: none !important;
        }
        body {
            font-family: Arial, Helvetica, sans-serif;
            font-size: 11pt;
            line-height: 1.4;
        }
        img {
            max-width: 100%;
            height: auto;
        }
        a {
            color: #0066cc;
        }
    """, font_config=font_config)

    html = HTML(string=html_content)
    html.write_pdf(output_path, stylesheets=[css], font_config=font_config)

    return output_path


def convert_emails_to_pdf(emails: list[ParsedEmail], output_dir: Path) -> list[tuple[ParsedEmail, Path]]:
    """Convert multiple emails to PDF files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for email in emails:
        filename = f"{email.logical_filename}.pdf"
        output_path = deduplicate_path(output_dir / filename)

        try:
            email_to_pdf(email, output_path)
            results.append((email, output_path))
            logger.info("Created: %s", output_path.name)
        except Exception as e:
            logger.error("Failed to convert %s: %s", email.filepath.name, e)

    return results
