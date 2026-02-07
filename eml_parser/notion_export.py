"""Export emails to a Notion database."""

from pathlib import Path

import click

from .extractor import get_text_content
from .parser import ParsedEmail
from .summarizer import extract_key_points
from .utils import get_logger

logger = get_logger(__name__)

try:
    from notion_client import Client
    from notion_client.errors import APIResponseError
except ImportError:
    Client = None
    APIResponseError = None

# Notion rich_text fields have a 2000-character limit
_MAX_RICH_TEXT = 2000

# Database schema: property names and types expected by the exporter
_EXPECTED_SCHEMA = {
    "Name": "title",
    "Sender": "rich_text",
    "Date": "date",
    "Recipients": "rich_text",
    "Key Points": "rich_text",
    "Status": "select",
}

# Properties to add when setting up a new database (via data_sources.update)
_SETUP_PROPERTIES = {
    "Sender": {"rich_text": {}},
    "Date": {"date": {}},
    "Recipients": {"rich_text": {}},
    "Key Points": {"rich_text": {}},
    "Status": {
        "select": {
            "options": [
                {"name": "Processed", "color": "blue"},
                {"name": "Reviewed", "color": "green"},
                {"name": "Archived", "color": "gray"},
            ],
        },
    },
    "PDF": {"files": {}},
}


def _require_notion_client():
    """Raise a clear error if notion-client is not installed."""
    if Client is None:
        raise click.ClickException(
            "notion-client is required for Notion export: pip install notion-client"
        )


def _get_data_source_id(client, database_id: str) -> str:
    """Retrieve the data_source ID for a database."""
    db = client.databases.retrieve(database_id=database_id)
    data_sources = db.get("data_sources", [])
    if not data_sources:
        raise click.ClickException(
            "Database has no data sources. Use --notion-setup to create a properly configured database."
        )
    return data_sources[0]["id"]


def _make_rich_text(content: str) -> list[dict]:
    """Convert a string to a Notion rich_text array, truncating at 2000 chars."""
    if not content:
        return []
    truncated = content[:_MAX_RICH_TEXT]
    return [{"type": "text", "text": {"content": truncated}}]


def _upload_pdf_to_notion(client, pdf_path: Path) -> str | None:
    """Upload a PDF to Notion via the file_uploads API.

    Returns the file_upload ID on success, or None on failure.
    """
    filename = pdf_path.name
    try:
        upload = client.file_uploads.create(
            mode="single_part",
            filename=filename,
            content_type="application/pdf",
        )
        file_upload_id = upload["id"]

        with open(pdf_path, "rb") as f:
            client.file_uploads.send(
                file_upload_id,
                file=(filename, f, "application/pdf"),
                part_number="1",
            )

        return file_upload_id
    except Exception as e:
        logger.error("Failed to upload PDF '%s' to Notion: %s", filename, e)
        return None


def _build_page_properties(email: ParsedEmail, key_points: list[str], *, pdf_upload_id: str | None = None) -> dict:
    """Map a ParsedEmail and its key points to Notion page properties."""
    subject = email.subject or "No Subject"
    properties = {
        "Name": {"title": _make_rich_text(subject)},
        "Sender": {"rich_text": _make_rich_text(email.sender)},
        "Recipients": {"rich_text": _make_rich_text(
            ", ".join(email.recipients)
        )},
        "Key Points": {"rich_text": _make_rich_text(
            "\n".join(f"- {kp}" for kp in key_points) if key_points else ""
        )},
        "Status": {"select": {"name": "Processed"}},
    }

    if email.date:
        properties["Date"] = {"date": {"start": email.date.isoformat()}}

    if pdf_upload_id:
        properties["PDF"] = {
            "files": [{
                "type": "file_upload",
                "file_upload": {"id": pdf_upload_id},
                "name": f"{email.logical_filename[:96]}.pdf",
            }]
        }

    return properties


def _build_page_children(email: ParsedEmail, key_points: list[str]) -> list[dict]:
    """Build Notion block children for the page body."""
    children = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": _make_rich_text("Key Points")},
        },
    ]

    if key_points:
        for kp in key_points:
            children.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": _make_rich_text(kp)},
            })
    else:
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": _make_rich_text("No content available")},
        })

    children.append({
        "object": "block",
        "type": "divider",
        "divider": {},
    })

    children.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": _make_rich_text("Email Details")},
    })

    date_str = email.date.strftime("%B %d, %Y at %I:%M %p") if email.date else "Unknown"
    recipients_str = ", ".join(email.recipients) if email.recipients else "Unknown"

    for label, value in [
        ("From", email.sender),
        ("To", recipients_str),
        ("Date", date_str),
    ]:
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": f"{label}: "}, "annotations": {"bold": True}},
                    {"type": "text", "text": {"content": value}},
                ],
            },
        })

    return children


def _check_duplicate(client, data_source_id: str, email: ParsedEmail) -> bool:
    """Check if an email with the same subject and date already exists."""
    subject = email.subject or "No Subject"

    filter_conditions = {
        "and": [
            {"property": "Name", "title": {"equals": subject}},
        ]
    }

    if email.date:
        date_only = email.date.strftime("%Y-%m-%d")
        filter_conditions["and"].append(
            {"property": "Date", "date": {"equals": date_only}}
        )

    try:
        response = client.data_sources.query(
            data_source_id=data_source_id,
            filter=filter_conditions,
            page_size=1,
        )
        return len(response.get("results", [])) > 0
    except Exception as e:
        logger.warning("Duplicate check failed for '%s': %s", subject, e)
        return False


def export_email_to_notion(
    client,
    database_id: str,
    email: ParsedEmail,
    key_points: list[str],
    *,
    pdf_path: Path | None = None,
) -> str:
    """Export a single email to Notion. Returns the created page ID."""
    pdf_upload_id = None
    if pdf_path and pdf_path.exists():
        pdf_upload_id = _upload_pdf_to_notion(client, pdf_path)

    properties = _build_page_properties(email, key_points, pdf_upload_id=pdf_upload_id)
    children = _build_page_children(email, key_points)

    response = client.pages.create(
        parent={"database_id": database_id},
        properties=properties,
        children=children,
    )

    return response["id"]


def export_emails_to_notion(
    emails: list[ParsedEmail],
    database_id: str,
    token: str,
    sentences: int = 3,
    *,
    skip_duplicates: bool = True,
    pdf_paths: dict[Path, Path] | None = None,
) -> list[tuple[ParsedEmail, str]]:
    """Export emails to a Notion database.

    Returns a list of (email, page_id) tuples for successfully exported emails.
    """
    _require_notion_client()

    client = Client(auth=token)

    # Validate connection and get data source
    try:
        db = client.databases.retrieve(database_id=database_id)
        logger.info("Connected to Notion database: %s", db.get("title", [{}])[0].get("plain_text", database_id))
    except APIResponseError as e:
        if e.status == 401:
            raise click.ClickException(
                "Invalid Notion token. Check your NOTION_TOKEN or --notion-token value."
            )
        if e.status == 404:
            raise click.ClickException(
                "Notion database not found. Check your NOTION_DATABASE_ID and ensure "
                "the integration has access to the database."
            )
        raise click.ClickException(f"Notion API error: {e}")

    data_source_id = _get_data_source_id(client, database_id)

    # Validate schema via data source
    ds = client.data_sources.retrieve(data_source_id=data_source_id)
    ds_properties = ds.get("properties", {})
    if ds_properties:
        for prop_name, prop_type in _EXPECTED_SCHEMA.items():
            if prop_name not in ds_properties:
                raise click.ClickException(
                    f"Database is missing required property '{prop_name}' (type: {prop_type}). "
                    f"Use --notion-setup to create a properly configured database."
                )
            actual_type = ds_properties[prop_name]["type"]
            if actual_type != prop_type:
                raise click.ClickException(
                    f"Property '{prop_name}' has type '{actual_type}', expected '{prop_type}'. "
                    f"Use --notion-setup to create a properly configured database."
                )

    # Check if database has PDF property when pdf_paths are provided
    if pdf_paths and "PDF" not in ds_properties:
        logger.warning(
            "Database is missing 'PDF' files property — PDFs will not be attached. "
            "Recreate the database with --notion-setup to include it."
        )
        pdf_paths = None

    results = []
    for email in emails:
        try:
            if skip_duplicates and _check_duplicate(client, data_source_id, email):
                logger.info("Skipping duplicate: %s", email.subject)
                continue

            text_content = get_text_content(email)
            key_points = extract_key_points(text_content, sentences)

            pdf_path = pdf_paths.get(email.filepath) if pdf_paths else None
            page_id = export_email_to_notion(
                client, database_id, email, key_points, pdf_path=pdf_path,
            )
            results.append((email, page_id))
            logger.info("Exported: %s -> %s", email.subject, page_id)

        except Exception as e:
            logger.error("Failed to export '%s' to Notion: %s", email.subject, e)

    return results


def setup_notion_database(token: str, parent_page_id: str, title: str = "Email Archive") -> str:
    """Create a Notion database with the expected schema under the given page.

    Creates the database, then adds properties via the data_sources API.
    Returns the new database ID.
    """
    _require_notion_client()

    client = Client(auth=token)

    # Validate the token / parent page
    try:
        client.pages.retrieve(page_id=parent_page_id)
    except APIResponseError as e:
        if e.status == 401:
            raise click.ClickException(
                "Invalid Notion token. Check your NOTION_TOKEN or --notion-token value."
            )
        if e.status == 404:
            raise click.ClickException(
                "Parent page not found. Ensure the page ID is correct and "
                "the integration has been shared with the page."
            )
        raise click.ClickException(f"Notion API error: {e}")

    # Create the database (title property is created automatically)
    response = client.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": title}}],
        properties={"Name": {"title": {}}},
    )

    database_id = response["id"]

    # Add remaining properties via the data_sources API
    data_source_id = _get_data_source_id(client, database_id)
    client.data_sources.update(
        data_source_id=data_source_id,
        properties=_SETUP_PROPERTIES,
    )

    return database_id
