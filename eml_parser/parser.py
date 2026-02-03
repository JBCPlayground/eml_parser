"""Parse .eml files from a directory."""

import email
import os
from dataclasses import dataclass
from datetime import datetime
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterator

import chardet


@dataclass
class ParsedEmail:
    """Represents a parsed email message."""
    filepath: Path
    subject: str
    sender: str
    recipients: list[str]
    date: datetime | None
    plain_body: str
    html_body: str

    @property
    def filename_safe_subject(self) -> str:
        """Return a filesystem-safe version of the subject."""
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in self.subject)
        return safe[:100].strip() or "untitled"

    @property
    def logical_filename(self) -> str:
        """Generate a logical filename for PDF output."""
        date_str = self.date.strftime("%Y-%m-%d") if self.date else "unknown-date"
        return f"{date_str}_{self.filename_safe_subject}"


def decode_mime_header(header_value: str | None) -> str:
    """Decode a MIME-encoded header value."""
    if not header_value:
        return ""

    decoded_parts = []
    for part, charset in decode_header(header_value):
        if isinstance(part, bytes):
            charset = charset or "utf-8"
            try:
                decoded_parts.append(part.decode(charset, errors="replace"))
            except (LookupError, UnicodeDecodeError):
                decoded_parts.append(part.decode("utf-8", errors="replace"))
        else:
            decoded_parts.append(part)

    return " ".join(decoded_parts)


def detect_encoding(filepath: Path) -> str:
    """Detect the encoding of a file using chardet."""
    with open(filepath, "rb") as f:
        raw = f.read()
        result = chardet.detect(raw)
        return result.get("encoding") or "utf-8"


def is_valid_eml_file(filepath: Path) -> bool:
    """Validate that a file appears to be a valid email file."""
    # Check for common email headers in the first 4KB
    try:
        with open(filepath, "rb") as f:
            header = f.read(4096).lower()

        # Look for standard email headers
        email_indicators = [
            b"from:",
            b"to:",
            b"subject:",
            b"date:",
            b"mime-version:",
            b"content-type:",
            b"received:",
        ]

        # File should contain at least 2 email headers to be considered valid
        matches = sum(1 for indicator in email_indicators if indicator in header)
        return matches >= 2
    except (IOError, OSError):
        return False


def parse_eml_file(filepath: Path) -> ParsedEmail:
    """Parse a single .eml file."""
    encoding = detect_encoding(filepath)

    with open(filepath, "r", encoding=encoding, errors="replace") as f:
        msg = email.message_from_file(f)

    subject = decode_mime_header(msg.get("Subject"))
    sender = decode_mime_header(msg.get("From"))

    recipients = []
    for header in ["To", "Cc"]:
        if msg.get(header):
            recipients.extend(
                decode_mime_header(r.strip())
                for r in msg.get(header).split(",")
            )

    date = None
    date_str = msg.get("Date")
    if date_str:
        try:
            date = parsedate_to_datetime(date_str)
        except (ValueError, TypeError):
            pass

    plain_body = ""
    html_body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain" and not plain_body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    plain_body = payload.decode(charset, errors="replace")
            elif content_type == "text/html" and not html_body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html_body = payload.decode(charset, errors="replace")
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace")
            if content_type == "text/html":
                html_body = content
            else:
                plain_body = content

    return ParsedEmail(
        filepath=filepath,
        subject=subject,
        sender=sender,
        recipients=recipients,
        date=date,
        plain_body=plain_body,
        html_body=html_body,
    )


def scan_directory(directory: Path) -> Iterator[ParsedEmail]:
    """Scan a directory for .eml files and parse them."""
    eml_files = sorted(directory.glob("*.eml"))

    for filepath in eml_files:
        # Skip symlinks to prevent path traversal attacks
        if filepath.is_symlink():
            print(f"Warning: Skipping symlink {filepath}")
            continue

        # Validate file appears to be an email
        if not is_valid_eml_file(filepath):
            print(f"Warning: Skipping invalid email file {filepath}")
            continue

        try:
            yield parse_eml_file(filepath)
        except Exception as e:
            print(f"Warning: Failed to parse {filepath}: {e}")
