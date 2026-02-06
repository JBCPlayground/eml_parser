"""Generate summary report with clickable links to source emails."""

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .extractor import get_text_content
from .parser import ParsedEmail
from .summarizer import extract_key_points
from .utils import get_logger, path_to_file_url

logger = get_logger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def generate_report(
    emails: list[ParsedEmail],
    pdf_paths: dict[Path, Path],
    output_path: Path,
    sentences_per_email: int = 3
) -> Path:
    """Generate an HTML summary report for the processed emails."""
    report_data = []
    for email in sorted(emails, key=lambda e: e.date or datetime.min, reverse=True):
        text_content = get_text_content(email)
        key_points = extract_key_points(text_content, sentences_per_email)

        pdf_path = pdf_paths.get(email.filepath)
        report_data.append({
            "email": email,
            "key_points": key_points,
            "eml_url": path_to_file_url(email.filepath),
            "pdf_url": path_to_file_url(pdf_path) if pdf_path else None,
        })

    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report.html")

    html_output = template.render(
        emails=report_data,
        generated_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    output_path.write_text(html_output, encoding="utf-8")
    logger.info("Report saved to: %s", output_path)

    return output_path
