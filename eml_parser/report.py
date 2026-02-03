"""Generate summary report with clickable links to source emails."""

from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .extractor import get_text_content
from .parser import ParsedEmail
from .summarizer import extract_key_points


def get_wsl_distro() -> str:
    """Get the WSL distro name from environment."""
    import os
    return os.environ.get('WSL_DISTRO_NAME', 'Ubuntu-24.04')


def path_to_file_url(path: Path) -> str:
    """Convert a Path to a Windows-compatible WSL file:// URL."""
    absolute_path = str(path.absolute())
    distro = get_wsl_distro()

    # Convert Linux path to Windows WSL UNC path
    # /home/user/file -> \\wsl.localhost\Ubuntu-24.04\home\user\file
    windows_path = f"\\\\wsl.localhost\\{distro}{absolute_path.replace('/', '\\')}"

    # For file:// URLs, use forward slashes and encode spaces
    url_path = windows_path.replace('\\', '/')
    encoded = quote(url_path, safe='/:')

    return f"file:{encoded}"


REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Email Summary Report</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
            color: #333;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        .summary-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .email-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
        }
        .email-title {
            font-size: 1.2em;
            font-weight: 600;
            color: #2c3e50;
            margin: 0;
        }
        .email-meta {
            color: #666;
            font-size: 0.9em;
        }
        .email-date {
            background: #ecf0f1;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.85em;
        }
        .key-points {
            margin: 15px 0;
            padding-left: 0;
            list-style: none;
        }
        .key-points li {
            padding: 8px 0 8px 25px;
            position: relative;
            border-bottom: 1px solid #ecf0f1;
        }
        .key-points li:last-child {
            border-bottom: none;
        }
        .key-points li::before {
            content: "\\2022";
            color: #3498db;
            font-weight: bold;
            position: absolute;
            left: 8px;
        }
        .email-links {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #ecf0f1;
        }
        .email-links a {
            display: inline-block;
            margin-right: 15px;
            color: #3498db;
            text-decoration: none;
            font-size: 0.9em;
        }
        .email-links a:hover {
            text-decoration: underline;
        }
        .stats {
            background: #3498db;
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 25px;
        }
        .stats span {
            margin-right: 30px;
        }
    </style>
</head>
<body>
    <h1>Email Summary Report</h1>

    <div class="stats">
        <span><strong>{{ emails|length }}</strong> emails processed</span>
        <span>Generated: {{ generated_date }}</span>
    </div>

    {% for item in emails %}
    <div class="summary-card">
        <div class="email-header">
            <h2 class="email-title">{{ item.email.subject or 'No Subject' }}</h2>
            <span class="email-date">{{ item.email.date.strftime('%b %d, %Y') if item.email.date else 'Unknown date' }}</span>
        </div>

        <div class="email-meta">
            <strong>From:</strong> {{ item.email.sender }}
        </div>

        <ul class="key-points">
            {% for point in item.key_points %}
            <li>{{ point }}</li>
            {% endfor %}
        </ul>

        <div class="email-links">
            <a href="{{ item.eml_url }}">View Original (.eml)</a>
            {% if item.pdf_url %}
            <a href="{{ item.pdf_url }}">View PDF</a>
            {% endif %}
        </div>
    </div>
    {% endfor %}
</body>
</html>
"""


def generate_report(
    emails: list[ParsedEmail],
    pdf_paths: dict[Path, Path],
    output_path: Path,
    sentences_per_email: int = 3
) -> Path:
    """Generate an HTML summary report for the processed emails."""
    from datetime import datetime

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

    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    template = env.from_string(REPORT_TEMPLATE)

    html_output = template.render(
        emails=report_data,
        generated_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    output_path.write_text(html_output, encoding="utf-8")
    print(f"Report saved to: {output_path}")

    return output_path
