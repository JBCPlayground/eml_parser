"""Command-line interface for EML Parser."""

import shutil
from pathlib import Path

import click

from .parser import scan_directory
from .pdf_converter import convert_emails_to_pdf
from .report import generate_report
from .rtf_converter import convert_emails_to_rtf
from .notion_export import export_emails_to_notion, setup_notion_database
from .utils import configure_logging, deduplicate_path


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
@click.option(
    "-v", "--verbose",
    is_flag=True,
    help="Enable verbose logging output"
)
@click.option(
    "--notion",
    is_flag=True,
    help="Export emails to a Notion database"
)
@click.option(
    "--notion-token",
    envvar="NOTION_TOKEN",
    default=None,
    help="Notion API integration token (or set NOTION_TOKEN env var)"
)
@click.option(
    "--notion-database-id",
    envvar="NOTION_DATABASE_ID",
    default=None,
    help="Target Notion database ID (or set NOTION_DATABASE_ID env var)"
)
@click.option(
    "--notion-no-dedup",
    is_flag=True,
    help="Skip duplicate detection when exporting to Notion"
)
@click.option(
    "--notion-setup",
    default=None,
    metavar="PAGE_ID",
    help="Create a Notion database under this page, then exit"
)
def main(
    input_dir: Path,
    output_dir: Path | None,
    sentences: int,
    skip_pdf: bool,
    verbose: bool,
    notion: bool,
    notion_token: str | None,
    notion_database_id: str | None,
    notion_no_dedup: bool,
    notion_setup: str | None,
):
    """
    Parse EML files, generate summaries, and convert to PDF.

    INPUT_DIR: Directory containing .eml files to process. Defaults to <project>/input
    """
    configure_logging(verbose)

    # --- Notion early validation ---
    if notion_setup:
        if not notion_token:
            raise click.ClickException(
                "Notion token is required. Set NOTION_TOKEN or use --notion-token."
            )
        click.echo("Creating Notion database...")
        db_id = setup_notion_database(notion_token, notion_setup)
        click.echo(f"Database created! ID: {db_id}")
        click.echo(f"\nExport emails with:")
        click.echo(f"  NOTION_TOKEN=<token> NOTION_DATABASE_ID={db_id} python run.py --notion")
        return

    if notion and not notion_token:
        raise click.ClickException(
            "Notion token is required. Set NOTION_TOKEN or use --notion-token."
        )
    if notion and not notion_database_id:
        raise click.ClickException(
            "Notion database ID is required. Set NOTION_DATABASE_ID or use --notion-database-id."
        )

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

    # Export to Notion (optional)
    if notion:
        click.echo("\nExporting to Notion...")
        try:
            notion_results = export_emails_to_notion(
                emails,
                notion_database_id,
                notion_token,
                sentences,
                skip_duplicates=not notion_no_dedup,
            )
            click.echo(f"  Exported {len(notion_results)}/{len(emails)} emails to Notion")
        except click.ClickException:
            raise
        except Exception as e:
            click.echo(f"  Notion export failed: {e}", err=True)

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
        dst = deduplicate_path(processed_dir / src.name)
        shutil.move(str(src), str(dst))
        click.echo(f"  Moved: {src.name} -> {dst.name}")


if __name__ == "__main__":
    main()
