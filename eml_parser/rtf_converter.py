"""Convert emails to RTF format using pypandoc."""

import re
from pathlib import Path

import pypandoc

from .extractor import get_html_for_pdf
from .parser import ParsedEmail


def inject_email_header(html_content: str, email: ParsedEmail) -> str:
    """Inject email metadata header into HTML before RTF conversion."""
    date_str = email.date.strftime("%B %d, %Y %I:%M %p") if email.date else "Unknown"
    recipients = ", ".join(email.recipients) if email.recipients else "Unknown"

    header_html = (
        "<div>"
        f"<p><strong>Subject:</strong> {email.subject}</p>"
        f"<p><strong>From:</strong> {email.sender}</p>"
        f"<p><strong>To:</strong> {recipients}</p>"
        f"<p><strong>Date:</strong> {date_str}</p>"
        "<hr>"
        "</div>"
    )

    # Insert after <body> tag if present, otherwise prepend
    if "<body" in html_content.lower():
        return re.sub(
            r'(<body[^>]*>)',
            rf'\1{header_html}',
            html_content,
            count=1,
            flags=re.IGNORECASE
        )
    return header_html + html_content


def email_to_rtf(email: ParsedEmail, output_path: Path) -> Path:
    """Convert a single ParsedEmail to RTF format."""
    html_content = get_html_for_pdf(email)
    html_with_header = inject_email_header(html_content, email)

    pypandoc.convert_text(
        html_with_header,
        'rtf',
        format='html',
        extra_args=['--standalone'],
        outputfile=str(output_path)
    )

    return output_path


def convert_emails_to_rtf(
    emails: list[ParsedEmail],
    output_dir: Path
) -> list[tuple[ParsedEmail, Path]]:
    """Convert multiple emails to RTF, handling duplicates and errors."""
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    used_names: set[str] = set()

    for email in emails:
        try:
            base_name = email.filename_safe_subject
            filename = base_name
            counter = 1
            while filename in used_names or (output_dir / f"{filename}.rtf").exists():
                filename = f"{base_name}_{counter}"
                counter += 1

            used_names.add(filename)
            output_path = output_dir / f"{filename}.rtf"
            email_to_rtf(email, output_path)
            results.append((email, output_path))
            print(f"  RTF: {output_path.name}")
        except Exception as e:
            print(f"  Warning: RTF conversion failed for '{email.subject}': {e}")

    return results
