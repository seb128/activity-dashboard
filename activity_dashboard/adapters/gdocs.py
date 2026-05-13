"""Google Docs adapter — extracts 'For next week' and 'Carried over' action items
from a per-subject 1-1 notes document."""

from __future__ import annotations
import re
from datetime import datetime, timezone

from ..item import Item, Bucket

NAME = "gdocs"

_DOC_ID_RE = re.compile(r"/document/d/([A-Za-z0-9_-]+)")

_SECTION_HEADERS = {
    "for next week": "for_next_week",
    "carried over from last week": "carried_over",
}
_HEADING_STYLES = {"HEADING_1", "HEADING_2", "HEADING_3", "TITLE"}


def _extract_doc_id(url_or_id: str) -> str:
    m = _DOC_ID_RE.search(url_or_id)
    if m:
        return m.group(1)
    return url_or_id


def _create_client(settings):
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials as OAuthCredentials
    from google.auth.transport.requests import Request
    from pathlib import Path
    import json

    scopes = ["https://www.googleapis.com/auth/documents.readonly"]
    creds_path = settings.credentials.google_credentials_file
    token_path = settings.credentials.google_token_file

    creds = None
    if Path(token_path).exists():
        creds = OAuthCredentials.from_authorized_user_file(str(token_path), scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes)
            creds = flow.run_local_server(port=0)
        Path(token_path).write_text(creds.to_json())
    return build("docs", "v1", credentials=creds)


def _paragraph_text(paragraph: dict) -> str:
    parts = []
    for el in paragraph.get("elements", []):
        run = el.get("textRun")
        if run:
            parts.append(run.get("content", ""))
    return "".join(parts).strip()


def _paragraph_style(paragraph: dict) -> str:
    return paragraph.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")


def fetch(subject, settings, *, _client=None) -> list[Item]:
    client = _client if _client is not None else _create_client(settings)
    doc_id = _extract_doc_id(subject.one_on_one_doc)
    doc = client.documents().get(documentId=doc_id).execute()

    items: list[Item] = []
    current_section: str | None = None
    now = datetime.now(timezone.utc)

    for entry in doc.get("body", {}).get("content", []):
        paragraph = entry.get("paragraph")
        if not paragraph:
            continue
        text = _paragraph_text(paragraph)
        style = _paragraph_style(paragraph)

        if style in _HEADING_STYLES:
            current_section = _SECTION_HEADERS.get(text.lower())
            continue

        if current_section and text:
            items.append(Item(
                source=NAME,
                kind="action_item",
                title=text,
                url=subject.one_on_one_doc,
                subject_role="assignee",
                status="pending",
                last_activity_at=now,
                bucket=Bucket.NONE,
                raw={"section": current_section},
            ))

    return items
