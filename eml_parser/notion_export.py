"""Export emails to a Notion database."""

from datetime import datetime

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


def _require_notion_client():
    """Raise a clear error if notion-client is not installed."""
    if Client is None:
        raise click.ClickException(
            "notion-client is required for Notion export: pip install notion-client"
        )


def _make_rich_text(content: str) -> list[dict]:
    """Convert a string to a Notion rich_text array, truncating at 2000 chars."""
    if not content:
        return []
    truncated = content[:_MAX_RICH_TEXT]
    return [{"type": "text", "text": {"content": truncated}}]


def _build_page_properties(email: ParsedEmail, key_points: list[str]) -> dict:
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


def _check_duplicate(client, database_id: str, email: ParsedEmail) -> bool:
    """Check if an email with the same subject and date already exists in the database."""
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
        response = client.databases.query(
            database_id=database_id,
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
) -> str:
    """Export a single email to Notion. Returns the created page ID."""
    properties = _build_page_properties(email, key_points)
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
) -> list[tuple[ParsedEmail, str]]:
    """Export emails to a Notion database.

    Returns a list of (email, page_id) tuples for successfully exported emails.
    """
    _require_notion_client()

    client = Client(auth=token)

    # Validate connection by retrieving the database
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

    # Validate schema
    db_properties = db.get("properties", {})
    for prop_name, prop_type in _EXPECTED_SCHEMA.items():
        if prop_name not in db_properties:
            raise click.ClickException(
                f"Database is missing required property '{prop_name}' (type: {prop_type}). "
                f"Use --notion-setup to create a properly configured database."
            )
        actual_type = db_properties[prop_name]["type"]
        if actual_type != prop_type:
            raise click.ClickException(
                f"Property '{prop_name}' has type '{actual_type}', expected '{prop_type}'. "
                f"Use --notion-setup to create a properly configured database."
            )

    results = []
    for email in emails:
        try:
            if skip_duplicates and _check_duplicate(client, database_id, email):
                logger.info("Skipping duplicate: %s", email.subject)
                continue

            text_content = get_text_content(email)
            key_points = extract_key_points(text_content, sentences)

            page_id = export_email_to_notion(client, database_id, email, key_points)
            results.append((email, page_id))
            logger.info("Exported: %s -> %s", email.subject, page_id)

        except Exception as e:
            logger.error("Failed to export '%s' to Notion: %s", email.subject, e)

    return results


def setup_notion_database(token: str, parent_page_id: str, title: str = "Email Archive") -> str:
    """Create a Notion database with the expected schema under the given page.

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

    properties = {
        "Name": {"title": {}},
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
    }

    response = client.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": title}}],
        properties=properties,
    )

    return response["id"]
