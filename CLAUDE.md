# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

EML Parser: A Python CLI tool that processes .eml (email) files from a directory, generates a summary report with key points and clickable links to source emails, and converts each email to PDF format.

## Directory Structure

```
<project_root>/
├── input/      # Drop .eml files here for processing
├── output/     # Generated PDFs and summary report
│   ├── email_summary.html
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
python run.py --skip-pdf  # summary report only
```

## Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Weasyprint requires system dependencies on Linux
sudo apt install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0

# Download NLTK data (required for sumy summarization)
python -c "import nltk; nltk.download('punkt')"
```

## Architecture

```
eml_parser/
├── parser.py        # EML file parsing, encoding detection, ParsedEmail dataclass
├── extractor.py     # Text/HTML extraction, content cleaning for summarization and PDF
├── summarizer.py    # LSA-based extractive summarization using sumy
├── pdf_converter.py # HTML-to-PDF conversion via weasyprint
├── report.py        # Jinja2-based HTML summary report generation
└── cli.py           # Click CLI interface (main entry point)
```

**Data flow**: `scan_directory()` → `ParsedEmail` objects → `get_text_content()` for summarization, `get_html_for_pdf()` for PDF → `generate_report()` produces final HTML with file:// links.

## Key Dependencies

- **Email parsing**: Python's built-in `email` module + `beautifulsoup4` for HTML content
- **PDF generation**: `weasyprint` (HTML-to-PDF)
- **Summarization**: `sumy` with NLTK for extractive key point extraction (LSA algorithm)
- **CLI**: `click` for command-line interface
- **Templates**: `Jinja2` for generating the summary report
