from __future__ import annotations

import json
import os
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import Article, Endpoint
from .service_updates import _service_type
from .text import canonical_url, normalize_text

API_BASE = "https://api.notion.com/v1"
API_VERSION = "2022-06-28"
ROME = ZoneInfo("Europe/Rome")

SOURCE_ID = "SRC-0100"
ENDPOINT_ID = "END-0100"
READY_STATUS = "Pronto"


class NotionSourceError(RuntimeError):
    pass


# --- Notion API -------------------------------------------------------------

def _query_database(database_id: str, token: str, page_size: int, timeout: int = 20) -> list[dict]:
    """Return the pages in the database whose Stato is 'Pronto'."""
    results: list[dict] = []
    cursor: str | None = None
    while len(results) < page_size:
        payload: dict = {
            "filter": {"property": "Stato", "select": {"equals": READY_STATUS}},
            "page_size": min(100, page_size - len(results)),
        }
        if cursor:
            payload["start_cursor"] = cursor
        request = Request(
            f"{API_BASE}/databases/{database_id}/query",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": API_VERSION,
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise NotionSourceError(f"Notion {exc.code}: {detail}") from exc
        except URLError as exc:
            raise NotionSourceError(f"Notion non raggiungibile: {exc.reason}") from exc
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return results[:page_size]


# --- Property readers -------------------------------------------------------

def _plain(prop: dict | None) -> str:
    if not prop:
        return ""
    for key in ("title", "rich_text"):
        if key in prop:
            return "".join(part.get("plain_text", "") for part in prop[key]).strip()
    return ""


def _select(prop: dict | None) -> str:
    if prop and prop.get("select"):
        return prop["select"].get("name", "").strip()
    return ""


def _date_start(prop: dict | None) -> str:
    if prop and prop.get("date"):
        return (prop["date"].get("start") or "").strip()
    return ""


def _url(prop: dict | None) -> str:
    return (prop.get("url") or "").strip() if prop else ""


# --- Mapping ----------------------------------------------------------------

def _combine(date_value: str, time_value: str, *, end_of_day: bool = False) -> str:
    """Build an ISO datetime (Rome tz) from a 'YYYY-MM-DD' date and an 'HH:MM' time."""
    if not date_value:
        return ""
    try:
        day = datetime.fromisoformat(date_value).date()
    except ValueError:
        return ""
    clock = time.max.replace(microsecond=0) if end_of_day else time(0, 0)
    cleaned = time_value.replace(".", ":").strip()
    if cleaned and not end_of_day:
        try:
            hour, _, minute = cleaned.partition(":")
            clock = time(int(hour), int(minute or 0))
        except (ValueError, TypeError):
            pass
    return datetime.combine(day, clock, tzinfo=ROME).isoformat()


def _published_at(date_value: str, created_time: str) -> datetime:
    for candidate in (date_value, created_time):
        if candidate:
            try:
                parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            except ValueError:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=ROME)
            return parsed.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def map_page_to_article(page: dict) -> Article | None:
    props = page.get("properties", {})
    title = _plain(props.get("Titolo"))
    if not title:
        return None
    tipo = _select(props.get("Tipo"))
    categoria = _select(props.get("Categoria"))
    data_inizio = _date_start(props.get("Data inizio"))
    data_fine = _date_start(props.get("Data fine"))
    ora = _plain(props.get("Ora"))
    luogo = _plain(props.get("Luogo"))
    indirizzo = _plain(props.get("Indirizzo"))
    organizzatore = _plain(props.get("Organizzatore"))
    prezzo = _plain(props.get("Prezzo"))
    caption = _plain(props.get("Testo grezzo"))
    account = _plain(props.get("Fonte account"))
    link = _url(props.get("Link"))

    page_url = page.get("url", "")
    url = canonical_url(link) if link.startswith("http") else (page_url or f"notion:{page.get('id', '')}")

    excerpt = caption or " · ".join(part for part in (luogo, organizzatore, prezzo) if part)
    now = datetime.now(timezone.utc)
    published_at = _published_at(data_inizio, page.get("created_time", ""))

    metadata: dict[str, str] = {"intake_source": "notion", "notion_page_id": page.get("id", "")}
    if luogo:
        metadata["location"] = luogo
        metadata["venue"] = luogo
    if indirizzo:
        metadata["address"] = indirizzo
    if organizzatore:
        metadata["organizer"] = organizzatore
    if prezzo:
        metadata["price"] = prezzo
    if account:
        metadata["social_account"] = account

    if tipo == "Evento" and data_inizio:
        start = _combine(data_inizio, ora)
        if start:
            metadata["date_label"] = "Data"
            metadata["event_start"] = start
            metadata["reference_date"] = start
            end = _combine(data_fine, "", end_of_day=True) if data_fine else ""
            if end:
                metadata["event_end"] = end
    elif tipo == "Lavoro":
        metadata["opportunity"] = "true"
        metadata["opportunity_status"] = "open"
        metadata["opportunity_location_verified"] = "true"
        metadata["opportunity_verified_at"] = now.isoformat()
        deadline = _combine(data_inizio, "", end_of_day=True) if data_inizio else ""
        if deadline:
            metadata["opportunity_deadline"] = deadline
    elif tipo == "Avviso":
        service_type = _service_type(normalize_text(f"{title} {excerpt}"))
        if service_type:
            metadata["service_alert"] = "true"
            metadata["service_type"] = service_type
            metadata["service_status"] = "active"
            metadata["service_verified_at"] = now.isoformat()
            start = _combine(data_inizio, ora) if data_inizio else now.isoformat()
            metadata["service_start"] = start

    buckets = tuple(part.strip().lower() for part in categoria.split(";") if part.strip()) if categoria else ()

    return Article(
        source_id=SOURCE_ID,
        endpoint_id=ENDPOINT_ID,
        title=title,
        url=url,
        published_at=published_at,
        excerpt=excerpt,
        author=organizzatore or account,
        content_buckets=buckets,
        retrieved_at=now,
        metadata=metadata,
    )


def retrieve_notion(endpoint: Endpoint, limit: int = 100, timeout: float = 20.0) -> list[Article]:
    """Import the manually curated rows (Stato = Pronto) from the Notion database."""
    token = os.getenv("NOTION_TOKEN", "").strip()
    if not token:
        raise NotionSourceError("NOTION_TOKEN non configurato")
    database_id = (os.getenv("NOTION_SOCIAL_DB_ID", "") or endpoint.url).strip()
    if not database_id:
        raise NotionSourceError("NOTION_SOCIAL_DB_ID non configurato")
    pages = _query_database(database_id, token, page_size=limit, timeout=int(timeout))
    articles = [map_page_to_article(page) for page in pages]
    return [article for article in articles if article is not None]
