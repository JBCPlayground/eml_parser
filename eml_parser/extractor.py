"""Extract and clean content from parsed emails."""

import html
import re

import html2text
from bs4 import BeautifulSoup

from .parser import ParsedEmail

# Invisible/whitespace Unicode characters to strip
INVISIBLE_CHARS = re.compile(r'[\u200c\u200b\u200d\u2060\ufeff\u00ad]+')

# Tracking URL patterns (base64-encoded, long hashes, tracking pixels)
TRACKING_URL_PATTERN = re.compile(
    r'\[.*?\]\(https?://[^\)]*(?:click|track|open|pixel|emails/click|unsubscribe)[^\)]*\)',
    re.IGNORECASE
)

# Markdown link pattern
MARKDOWN_LINK = re.compile(r'\[([^\]]*)\]\([^\)]+\)')

# Repeated whitespace/spacer patterns
SPACER_PATTERN = re.compile(r'(\s*\u00a0\s*){3,}|(\s{10,})')

# Base64-like long strings (tracking tokens)
BASE64_PATTERN = re.compile(r'[A-Za-z0-9+/=]{50,}')


def get_text_content(email: ParsedEmail) -> str:
    """Extract clean text content from an email, preferring HTML for better structure."""
    if email.html_body:
        return html_to_text_for_summary(email.html_body)

    if email.plain_body:
        return clean_text_for_summary(email.plain_body)

    return ""


def html_to_text_for_summary(html_content: str) -> str:
    """Convert HTML to plain text optimized for summarization (strips tracking noise)."""
    soup = BeautifulSoup(html_content, "lxml")

    # Remove tracking pixels, scripts, styles, and hidden elements
    for tag in soup(["script", "style", "img", "noscript"]):
        tag.decompose()

    # Remove elements with tracking-related classes/ids
    for tag in soup.find_all(attrs={"style": re.compile(r"display\s*:\s*none", re.I)}):
        tag.decompose()

    # Remove link tags that are likely tracking (1x1, hidden, etc.)
    for a in soup.find_all("a"):
        # Keep links with meaningful text
        link_text = a.get_text(strip=True)
        if not link_text or len(link_text) < 2:
            a.decompose()

    h = html2text.HTML2Text()
    h.ignore_links = True  # Ignore links for summarization
    h.ignore_images = True
    h.ignore_emphasis = True
    h.body_width = 0

    text = h.handle(str(soup))
    return clean_text_for_summary(text)


def clean_text_for_summary(text: str) -> str:
    """Clean text aggressively for summarization - removes tracking noise."""
    # Remove invisible characters
    text = INVISIBLE_CHARS.sub('', text)

    # Remove tracking URLs in markdown format
    text = TRACKING_URL_PATTERN.sub('', text)

    # Convert remaining markdown links to just the text
    text = MARKDOWN_LINK.sub(r'\1', text)

    # Remove spacer patterns (repeated nbsp, lots of spaces)
    text = SPACER_PATTERN.sub(' ', text)

    # Remove base64-like tracking tokens
    text = BASE64_PATTERN.sub('', text)

    # Remove lines that are just special characters or very short
    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        line = line.strip()
        # Skip empty lines, lines with just punctuation, or very short lines
        if line and len(line) > 10 and re.search(r'[a-zA-Z]{3,}', line):
            # Remove excessive whitespace within line
            line = re.sub(r'\s+', ' ', line)
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def get_html_for_pdf(email: ParsedEmail) -> str:
    """Get HTML content suitable for PDF rendering."""
    if email.html_body:
        soup = BeautifulSoup(email.html_body, "lxml")

        # Remove script and style tags
        for tag in soup(["script", "style"]):
            tag.decompose()

        # Add basic styling if not present
        if not soup.find("style"):
            style = soup.new_tag("style")
            style.string = """
                body {
                    font-family: Arial, sans-serif;
                    font-size: 12pt;
                    line-height: 1.5;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }
                img { max-width: 100%; height: auto; }
            """
            if soup.head:
                soup.head.append(style)
            elif soup.html:
                head = soup.new_tag("head")
                head.append(style)
                soup.html.insert(0, head)

        return str(soup)

    # Convert plain text to simple HTML
    if email.plain_body:
        escaped = html.escape(email.plain_body)
        paragraphs = escaped.split("\n\n")
        html_paragraphs = "".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            font-size: 12pt;
            line-height: 1.5;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
    </style>
</head>
<body>
    {html_paragraphs}
</body>
</html>"""

    return "<html><body><p>No content available</p></body></html>"
