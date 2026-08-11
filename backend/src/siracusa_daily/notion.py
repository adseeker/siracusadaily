from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import socket
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


API_BASE = "https://api.notion.com/v1"
API_VERSION = "2026-03-11"
ROME = ZoneInfo("Europe/Rome")
PAGE_ID_PATTERN = re.compile(r"^[0-9a-fA-F-]{32,36}$")


class NotionPublishError(RuntimeError):
    pass


@dataclass(frozen=True)
class NotionPublishResult:
    page_id: str
    replaced_blocks: int


@dataclass(frozen=True)
class NotionAccessCheck:
    page_id: str
    readable_blocks: int


def _token(explicit: str | None = None) -> str:
    value = explicit or os.getenv("NOTION_TOKEN", "")
    if not value:
        raise NotionPublishError("NOTION_TOKEN non configurato")
    return value


def _request(
    method: str, path: str, *, token: str | None = None,
    payload: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None, timeout: int = 30,
) -> dict[str, Any]:
    url = f"{API_BASE}{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {_token(token)}",
            "Notion-Version": API_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw).get("message", raw)
        except json.JSONDecodeError:
            detail = raw
        raise NotionPublishError(f"Notion API {exc.code}: {detail}") from exc
    except (URLError, socket.timeout, OSError) as exc:
        raise NotionPublishError(f"Notion API non raggiungibile: {exc}") from exc
    if not raw:
        return {}
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise NotionPublishError("Notion API ha restituito una risposta non valida") from exc
    if not isinstance(result, dict):
        raise NotionPublishError("Notion API ha restituito un formato inatteso")
    return result


def _rich_text(content: str) -> list[dict[str, Any]]:
    # Notion limits each individual rich-text object to 2,000 characters.
    return [
        {"type": "text", "text": {"content": content[index:index + 1800]}}
        for index in range(0, len(content), 1800)
    ]


def _text_block(block_type: str, content: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": block_type,
        block_type: {"rich_text": _rich_text(content)},
    }


def _recap_blocks(post: str, sources: str, updated_at: datetime) -> list[dict[str, Any]]:
    timestamp = updated_at.astimezone(ROME).strftime("%d/%m/%Y alle %H:%M")
    return [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "✅"},
                "color": "green_background",
                "rich_text": _rich_text(
                    f"Recap aggiornato il {timestamp}. Copia il post e poi il primo commento."
                ),
            },
        },
        _text_block("heading_2", "Post Facebook"),
        {
            "object": "block",
            "type": "code",
            "code": {
                "language": "plain text",
                "caption": [],
                "rich_text": _rich_text(post.strip()),
            },
        },
        _text_block("heading_2", "Primo commento"),
        {
            "object": "block",
            "type": "code",
            "code": {
                "language": "plain text",
                "caption": [],
                "rich_text": _rich_text(sources.strip()),
            },
        },
    ]


def _children(page_id: str, *, token: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        query: dict[str, Any] = {"page_size": 100}
        if cursor:
            query["start_cursor"] = cursor
        result = _request(
            "GET", f"/blocks/{page_id}/children", token=token, query=query,
        )
        batch = result.get("results", [])
        if not isinstance(batch, list):
            raise NotionPublishError("elenco blocchi Notion non valido")
        rows.extend(row for row in batch if isinstance(row, dict))
        if not result.get("has_more"):
            return rows
        cursor = result.get("next_cursor")
        if not isinstance(cursor, str) or not cursor:
            raise NotionPublishError("paginazione Notion non valida")


def publish_facebook_recap(
    page_id: str, post: str, sources: str, *, token: str | None = None,
    updated_at: datetime | None = None,
) -> NotionPublishResult:
    page_id = page_id.strip()
    if not PAGE_ID_PATTERN.fullmatch(page_id):
        raise NotionPublishError("NOTION_FACEBOOK_PAGE_ID non valido")
    if not post.strip() or not sources.strip():
        raise NotionPublishError("post e fonti Facebook devono essere valorizzati")

    existing = _children(page_id, token=token)
    _request(
        "PATCH",
        f"/blocks/{page_id}/children",
        token=token,
        payload={
            "position": {"type": "start"},
            "children": _recap_blocks(post, sources, updated_at or datetime.now(ROME)),
        },
    )

    replaceable = [
        row for row in existing
        if row.get("type") not in {"child_page", "child_database"}
        and isinstance(row.get("id"), str)
    ]
    for row in replaceable:
        _request("DELETE", f"/blocks/{row['id']}", token=token)
    return NotionPublishResult(page_id=page_id, replaced_blocks=len(replaceable))


def check_notion_access(
    page_id: str, *, token: str | None = None,
) -> NotionAccessCheck:
    page_id = page_id.strip()
    if not PAGE_ID_PATTERN.fullmatch(page_id):
        raise NotionPublishError("NOTION_FACEBOOK_PAGE_ID non valido")

    existing = _children(page_id, token=token)
    marker = f"Test temporaneo SiracusaDaily {datetime.now(ROME).isoformat()}"
    created = _request(
        "PATCH",
        f"/blocks/{page_id}/children",
        token=token,
        payload={
            "position": {"type": "end"},
            "children": [_text_block("paragraph", marker)],
        },
    )
    rows = created.get("results", [])
    block_id = rows[0].get("id") if isinstance(rows, list) and rows else None
    if not isinstance(block_id, str) or not block_id:
        raise NotionPublishError("Notion non ha restituito il blocco temporaneo creato")
    _request("DELETE", f"/blocks/{block_id}", token=token)
    return NotionAccessCheck(page_id=page_id, readable_blocks=len(existing))
