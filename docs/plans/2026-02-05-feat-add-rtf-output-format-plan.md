---
title: "feat: Add RTF Output Format for Email Conversions"
type: feat
date: 2026-02-05
---

# feat: Add RTF Output Format for Email Conversions

## Overview

Add automatic RTF file generation alongside existing PDF output. Every processed email will produce both a PDF (in `output/pdfs/`) and an editable RTF file (in `output/` root). RTF content mirrors the PDF: rendered HTML email content with email headers (From, To, Date, Subject). Uses `pypandoc_binary` for HTML-to-RTF conversion with no system dependencies required.

## Problem Statement / Motivation

Users need editable versions of parsed emails. PDFs are read-only and difficult to modify. RTF provides a universally editable format (Word, LibreOffice, Google Docs, WordPad) while preserving email formatting like bold, lists, links, and tables.

## Proposed Solution

### Library Choice: `pypandoc_binary`

| Criterion | Value |
|-----------|-------|
| Package | `pypandoc_binary>=1.14` |
| System deps | None (bundles Pandoc binary) |
| Maintenance | Active (last release Nov 2025, MIT license) |
| HTML support | Bold, italic, links, tables, lists |
| Limitation | Ignores CSS styling (converts structure only) |

This is acceptable since email HTML formatting is mostly structural (`<strong>`, `<em>`, `<table>`, `<a>`), and the goal is editability over pixel-perfect fidelity.

### RTF File Naming

Per user preference, RTF files use the **email subject** (sanitized) as the filename:
- Source: `ParsedEmail.filename_safe_subject` (strips non-alphanumeric, caps at 100 chars, fallback `"untitled"`)
- Format: `{filename_safe_subject}.rtf`
- Example: `Meeting_Notes.rtf`, `Q4_Budget_Review.rtf`
- Duplicates: append `_1`, `_2`, etc. (tracked in-memory during batch, not filesystem-only)

### Output Location

RTF files placed directly in `output/` alongside `email_summary.html`.

### Pipeline Behavior

- RTF **always** generated (no `--skip-rtf` flag)
- `--skip-pdf` only affects PDFs; RTF still produced
- RTF conversion failures are logged and skipped (fail-and-continue), matching PDF behavior
- Summary report (`email_summary.html`) does **not** link to RTF files

## Technical Approach

### Architecture

New module `eml_parser/rtf_converter.py` following the same pattern as `pdf_converter.py`:

```
eml_parser/
├── parser.py          # (unchanged)
├── extractor.py       # (unchanged)
├── summarizer.py      # (unchanged)
├── pdf_converter.py   # (unchanged)
├── rtf_converter.py   # NEW: HTML-to-RTF via pypandoc
├── report.py          # (unchanged)
└── cli.py             # Modified: add RTF step to pipeline
```

### Data Flow (additions in bold)

```
scan_directory() → ParsedEmail objects
  ├→ get_html_for_pdf() → email_to_pdf()     → output/pdfs/{logical_filename}.pdf
  ├→ get_html_for_pdf() → email_to_rtf()     → output/{filename_safe_subject}.rtf  [NEW]
  ├→ get_text_content()  → extract_key_points()
  └→ generate_report()                        → output/email_summary.html
```

### Implementation Details

#### 1. `eml_parser/rtf_converter.py` (new file)

```python
# eml_parser/rtf_converter.py

"""RTF conversion for parsed emails using pypandoc."""

from pathlib import Path
from dataclasses import dataclass
import pypandoc
from .parser import ParsedEmail
from .extractor import get_html_for_pdf


def inject_email_header(html_content: str, email: ParsedEmail) -> str:
    """Inject email metadata header into HTML before RTF conversion.

    Matches the header format used in pdf_converter.email_to_pdf().
    """
    date_str = email.date.strftime("%B %d, %Y %I:%M %p") if email.date else "Unknown"
    recipients = ", ".join(email.recipients) if email.recipients else "Unknown"

    header_html = f"""<div>
<p><strong>Subject:</strong> {email.subject}</p>
<p><strong>From:</strong> {email.sender}</p>
<p><strong>To:</strong> {recipients}</p>
<p><strong>Date:</strong> {date_str}</p>
<hr>
</div>"""

    # Insert after <body> tag if present, otherwise prepend
    if "<body" in html_content.lower():
        import re
        return re.sub(
            r'(<body[^>]*>)',
            rf'\1{header_html}',
            html_content,
            count=1,
            flags=re.IGNORECASE
        )
    return header_html + html_content


def email_to_rtf(email: ParsedEmail, output_path: Path) -> Path:
    """Convert a single ParsedEmail to RTF format.

    Args:
        email: Parsed email object
        output_path: Full path for the output .rtf file

    Returns:
        The output_path on success
    """
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
    """Convert multiple emails to RTF, handling duplicates and errors.

    Args:
        emails: List of parsed emails
        output_dir: Directory to write RTF files into

    Returns:
        List of (email, rtf_path) tuples for successful conversions
    """
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
```

#### 2. `eml_parser/cli.py` (modifications)

Add RTF conversion call after PDF conversion:

```python
# After the existing PDF conversion block (~line 55-60):

# Convert to RTF (always runs, even with --skip-pdf)
print("\nConverting emails to RTF...")
rtf_results = convert_emails_to_rtf(emails, output_dir)
print(f"  Converted {len(rtf_results)}/{len(emails)} emails to RTF")

# Update the summary output to mention RTF:
print(f"\n  - RTFs: {output_dir}")
```

Key points:
- Import `convert_emails_to_rtf` from `rtf_converter`
- RTF conversion runs **unconditionally** (not gated by `--skip-pdf`)
- RTF files go to `output_dir` (not a subdirectory)
- Report generation is unchanged (no RTF links)

#### 3. `requirements.txt` (addition)

Add one line:
```
pypandoc_binary>=1.14
```

### Files Changed Summary

| File | Change |
|------|--------|
| `eml_parser/rtf_converter.py` | **New** — `email_to_rtf()`, `convert_emails_to_rtf()`, `inject_email_header()` |
| `eml_parser/cli.py` | **Modified** — import + RTF conversion step + CLI output |
| `requirements.txt` | **Modified** — add `pypandoc_binary>=1.14` |

### What Stays Unchanged

- `parser.py` — no changes needed, `filename_safe_subject` already exists
- `extractor.py` — reuses `get_html_for_pdf()` as-is
- `pdf_converter.py` — completely independent
- `report.py` — no RTF links per requirements
- `summarizer.py` — unrelated
- `templates/` — unrelated

## Technical Considerations

### HTML Sanitization

The PDF pipeline applies `sanitize_html_for_pdf()` to strip emojis and fix smart quotes for WeasyPrint compatibility. Pandoc handles Unicode better than WeasyPrint, so **no RTF-specific sanitization is needed**. The RTF converter uses `get_html_for_pdf()` directly (which already strips scripts/styles) without the WeasyPrint-specific sanitization layer.

### Header Injection

Both PDF and RTF inject email metadata headers. The PDF converter has its own header injection in `email_to_pdf()`. The RTF converter will have its own `inject_email_header()` function. While shared extraction is possible, keeping them separate avoids coupling and allows format-specific tweaks (PDF uses CSS-styled divs; RTF just needs clean HTML that Pandoc can convert).

### Duplicate Filename Handling

RTF filenames use subject-only (no date prefix), so collisions are more likely than PDFs. The converter tracks used names **in-memory** (a `set`) in addition to checking filesystem state, preventing same-batch collisions reliably.

### Error Isolation

RTF and PDF pipelines are fully independent. A failure in RTF conversion for email X does not affect:
- PDF conversion for email X
- RTF conversion for email Y
- Summary report generation

## Acceptance Criteria

### Functional

- [x] Running `python run.py` produces `.rtf` files in `output/` for each email
- [x] RTF files are named using the sanitized email subject (`filename_safe_subject.rtf`)
- [x] RTF content mirrors the PDF: includes email headers (Subject, From, To, Date) and the email body with formatting
- [x] Duplicate subjects produce unique filenames (e.g., `Meeting_Notes.rtf`, `Meeting_Notes_1.rtf`)
- [ ] Emails with empty subjects produce `untitled.rtf` (and `untitled_1.rtf` for additional ones)
- [x] `--skip-pdf` still produces RTF files
- [x] RTF conversion failures are logged and skipped without halting the pipeline
- [x] PDF generation is unaffected by the RTF changes
- [x] Summary report (`email_summary.html`) is unchanged (no RTF links)

### Non-Functional

- [x] `pypandoc_binary` is the only new dependency (no system packages required)
- [x] RTF files are openable and editable in Word, LibreOffice, and WordPad

## Dependencies & Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| pypandoc_binary adds ~100MB to install size | Certain | Acceptable tradeoff for zero system deps |
| Pandoc drops CSS styling from HTML emails | Certain | Acceptable — structural formatting (bold, tables, links) preserved; goal is editability |
| Complex email HTML (nested tables) may render oddly in RTF | Medium | Pandoc handles most structural HTML well; degrade gracefully |
| High collision rate with subject-only filenames | Low-Medium | In-memory dedup + counter suffix handles this |

## References & Research

### Internal References

- PDF converter pattern: `eml_parser/pdf_converter.py` (lines 59-147)
- Filename sanitization: `eml_parser/parser.py:27-35` (`filename_safe_subject`, `logical_filename`)
- HTML extraction: `eml_parser/extractor.py:146-195` (`get_html_for_pdf`)
- CLI orchestration: `eml_parser/cli.py:28-77` (`main()`)
- Header injection pattern: `eml_parser/pdf_converter.py:67-78`

### External References

- [pypandoc on PyPI](https://pypi.org/project/pypandoc/) — latest: 1.16.2 (Nov 2025)
- [pypandoc_binary on PyPI](https://pypi.org/project/pypandoc-binary/) — bundles Pandoc binary
- [pypandoc GitHub](https://github.com/JessicaTegner/pypandoc) — 1,060+ stars, MIT license
- [Pandoc User's Guide](https://pandoc.org/MANUAL.html) — RTF writer documentation
