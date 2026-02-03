"""Convert emails to PDF format."""

import re
from pathlib import Path

from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

from .extractor import get_html_for_pdf
from .parser import ParsedEmail


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
    # Keep basic multilingual plane but remove emojis (U+1F300 onwards) and other problematic ranges
    def replace_problematic(match):
        char = match.group(0)
        code = ord(char)
        # Remove emojis and symbols that cause issues
        if code > 0xFFFF:  # Outside BMP (emojis, etc.)
            return ''
        if 0x2600 <= code <= 0x27BF:  # Misc symbols
            return ''
        if 0x1F000 <= code <= 0x1FFFF:  # Emojis
            return ''
        return char

    # Process character by character for high Unicode
    result = []
    for char in html_content:
        code = ord(char)
        if code > 0xFFFF:  # Emoji and other supplementary characters
            continue  # Skip
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
    header_html = f"""
    <div style="border-bottom: 2px solid #333; margin-bottom: 20px; padding-bottom: 10px;">
        <h1 style="margin: 0 0 10px 0; font-size: 18pt;">{subject}</h1>
        <p style="margin: 5px 0;"><strong>From:</strong> {sender}</p>
        <p style="margin: 5px 0;"><strong>To:</strong> {', '.join(recipients)}</p>
        <p style="margin: 5px 0;"><strong>Date:</strong> {email.date.strftime('%B %d, %Y at %H:%M') if email.date else 'Unknown'}</p>
    </div>
    """

    # Insert header after body tag
    if "<body" in html_content.lower():
        html_content = re.sub(
            r"(<body[^>]*>)",
            r"\1" + header_html,
            html_content,
            count=1,
            flags=re.IGNORECASE
        )
    else:
        html_content = f"<html><body>{header_html}{html_content}</body></html>"

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
        output_path = output_dir / filename

        # Handle duplicate filenames
        counter = 1
        while output_path.exists():
            output_path = output_dir / f"{email.logical_filename}_{counter}.pdf"
            counter += 1

        try:
            email_to_pdf(email, output_path)
            results.append((email, output_path))
            print(f"Created: {output_path.name}")
        except Exception as e:
            print(f"Failed to convert {email.filepath.name}: {e}")

    return results
