"""Command-line interface for EML Parser."""

import shutil
from pathlib import Path

import click

from .parser import scan_directory
from .pdf_converter import convert_emails_to_pdf
from .report import generate_report
from .rtf_converter import convert_emails_to_rtf


# Base directory is the parent of the eml_parser package (project root)
BASE_DIR = Path(__file__).parent.parent.resolve()
DEFAULT_INPUT_DIR = BASE_DIR / "input"
DEFAULT_OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_PROCESSED_DIR = BASE_DIR / "processed"


@click.command()
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False, path_type=Path), default=DEFAULT_INPUT_DIR, required=False)
@click.option(
    "-o", "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Output directory for PDFs and report. Defaults to <project>/output"
)
@click.option(
    "--sentences",
    type=int,
    default=3,
    help="Number of key sentences to extract per email"
)
@click.option(
    "--skip-pdf",
    is_flag=True,
    help="Skip PDF generation, only create summary report"
)
def main(input_dir: Path, output_dir: Path | None, sentences: int, skip_pdf: bool):
    """
    Parse EML files, generate summaries, and convert to PDF.

    INPUT_DIR: Directory containing .eml files to process. Defaults to <project>/input
    """
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR

    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"Scanning {input_dir} for .eml files...")
    emails = list(scan_directory(input_dir))

    if not emails:
        click.echo("No .eml files found in the specified directory.")
        return

    click.echo(f"Found {len(emails)} email(s)")

    pdf_paths = {}

    if not skip_pdf:
        click.echo("\nConverting emails to PDF...")
        pdf_dir = output_dir / "pdfs"
        results = convert_emails_to_pdf(emails, pdf_dir)
        pdf_paths = {email.filepath: pdf_path for email, pdf_path in results}

    # Convert to RTF (always runs, even with --skip-pdf)
    click.echo("\nConverting emails to RTF...")
    rtf_results = convert_emails_to_rtf(emails, output_dir)
    click.echo(f"  Converted {len(rtf_results)}/{len(emails)} emails to RTF")

    click.echo("\nGenerating summary report...")
    report_path = output_dir / "email_summary.html"
    generate_report(emails, pdf_paths, report_path, sentences)

    click.echo(f"\nDone! Output saved to: {output_dir}")
    click.echo(f"  - Summary report: {report_path}")
    click.echo(f"  - RTFs: {output_dir}")
    if not skip_pdf:
        click.echo(f"  - PDFs: {output_dir / 'pdfs'}")

    # Move processed .eml files to processed directory
    processed_dir = DEFAULT_PROCESSED_DIR
    processed_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"\nMoving processed files to: {processed_dir}")
    for email in emails:
        src = email.filepath
        dst = processed_dir / src.name

        # Handle filename collisions to prevent overwriting
        counter = 1
        stem = dst.stem
        suffix = dst.suffix
        while dst.exists():
            dst = processed_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        shutil.move(str(src), str(dst))
        click.echo(f"  Moved: {src.name} -> {dst.name}")


if __name__ == "__main__":
    main()
