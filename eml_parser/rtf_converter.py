"""Convert emails to RTF format using pypandoc."""

from pathlib import Path

import pypandoc

from .extractor import get_html_for_pdf
from .parser import ParsedEmail
from .utils import (
    build_email_header_html,
    deduplicate_path,
    get_logger,
    inject_header_into_html,
)

logger = get_logger(__name__)


def inject_email_header(html_content: str, email: ParsedEmail) -> str:
    """Inject email metadata header into HTML before RTF conversion."""
    header_html = build_email_header_html(
        email.subject, email.sender, email.recipients, email.date, styled=False,
    )
    return inject_header_into_html(html_content, header_html)


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
            output_path = deduplicate_path(output_dir / f"{base_name}.rtf", used_names)
            email_to_rtf(email, output_path)
            results.append((email, output_path))
            logger.info("RTF: %s", output_path.name)
        except Exception as e:
            logger.warning("RTF conversion failed for '%s': %s", email.subject, e)

    return results
