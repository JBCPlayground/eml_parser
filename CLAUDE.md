# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

EML Parser: A Python CLI tool that processes .eml (email) files from a directory, generates a summary report with key points and clickable links to source emails, and converts each email to PDF and editable RTF formats.

## Directory Structure

```
<project_root>/
├── input/      # Drop .eml files here for processing
├── output/     # Generated PDFs, RTFs, and summary report
│   ├── email_summary.html
│   ├── *.rtf   # Editable RTF versions (named by email subject)
│   └── pdfs/
└── processed/  # Processed .eml files are moved here after successful run
```

## Usage

1. Place `.eml` files in the `input/` directory
2. Run `python run.py`
3. View results in `output/email_summary.html`
4. Processed emails are automatically moved to `processed/`

```bash
# Run the parser (uses default directories)
python run.py

# Run with custom input directory
python run.py /path/to/eml/directory

# Run with options
python run.py -o /custom/output/dir --sentences 5
python run.py --skip-pdf  # summary report + RTFs only (no PDFs)
python run.py -v          # enable verbose logging to stderr

# Notion integration
python run.py --notion-setup PAGE_ID --notion-token TOKEN  # create database
python run.py --notion                                      # export to Notion (requires env vars)
```

## Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Weasyprint requires system dependencies on Linux
sudo apt install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0

# Download NLTK data (required for sumy summarization)
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"
```

## Architecture

```
eml_parser/
├── utils.py         # Shared utilities: logging, header HTML builder, filename dedup, file URLs
├── parser.py        # EML file parsing, encoding detection, ParsedEmail dataclass
├── extractor.py     # Text/HTML extraction, content cleaning for summarization and PDF
├── summarizer.py    # LSA-based extractive summarization using sumy
├── pdf_converter.py # HTML-to-PDF conversion via weasyprint
├── rtf_converter.py # HTML-to-RTF conversion via pypandoc
├── report.py        # Jinja2-based HTML summary report generation
├── notion_export.py # Notion database export (optional, requires notion-client)
├── cli.py           # Click CLI interface (main entry point)
└── templates/
    └── report.html  # Jinja2 template for the summary report
```

**Data flow**: `scan_directory()` → `ParsedEmail` objects → `get_text_content()` for summarization, `get_html_for_pdf()` for PDF and RTF → `generate_report()` produces final HTML with file:// links.

## Key Dependencies

- **Email parsing**: Python's built-in `email` module + `beautifulsoup4` for HTML content
- **PDF generation**: `weasyprint` (HTML-to-PDF)
- **RTF generation**: `pypandoc_binary` (HTML-to-RTF via bundled Pandoc)
- **Summarization**: `sumy` with NLTK for extractive key point extraction (LSA algorithm)
- **CLI**: `click` for command-line interface
- **Notion export** (optional): `notion-client` for database integration
- **Templates**: `Jinja2` for generating the summary report

## Notion Integration Setup

1. Create an integration at https://www.notion.so/my-integrations
2. Share the target page with the integration (click "..." > "Connections" > add your integration)
3. Install the client: `pip install notion-client`
4. Create a database: `python run.py --notion-setup <PAGE_ID> --notion-token <TOKEN>`
5. Export emails: `NOTION_TOKEN=<token> NOTION_DATABASE_ID=<db_id> python run.py --notion`
