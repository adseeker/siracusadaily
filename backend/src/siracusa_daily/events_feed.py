from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import load_sources
from .database import all_event_articles, connect
from .events import event_interval, event_is_past, event_public_id
from .models import Article, Source
from .text import normalize_text

ROME = ZoneInfo("Europe/Rome")
USER_AGENT = "SiracusaDaily/0.1 (+events-feed)"


class EventsFeedError(RuntimeError):
    pass


def _clean(text: str) -> str:
    """Rimuove em dash ed en dash dal testo mostrato in pagina."""
    return (text or "").replace("—", "-").replace("–", "-").strip()


def _has_time(value: datetime) -> bool:
    local = value.astimezone(ROME)
    return bool(local.hour or local.minute)


def _booking_url(article: Article) -> str:
    booking = article.metadata.get("booking_url", "").strip()
    if booking.startswith("http"):
        return booking
    # Le fonti con una pagina evento reale la usano come destinazione esterna;
    # per le SPA non deep-linkabili (Base44) non c'è un link esterno affidabile.
    if "base44.app" not in article.url:
        return article.url
    return ""


def _record(article: Article, reference: datetime) -> dict:
    start, end = event_interval(article)
    meta = article.metadata
    image = meta.get("source_image_url", "").strip() or meta.get("newsletter_image_url", "").strip()
    return {
        "id": event_public_id(article.url),
        "title": _clean(article.title),
        "start": start.isoformat(),
        "end": end.isoformat() if end else None,
        "all_day": not _has_time(start),
        "location": _clean(meta.get("venue") or meta.get("location") or ""),
        "address": _clean(meta.get("address", "")),
        "description": _clean(article.excerpt),
        "image": image if image.startswith("http") else "",
        "booking_url": _booking_url(article),
        "category": _clean(meta.get("event_category", "")),
        "past": event_is_past(article, reference),
    }


def _richness(record: dict) -> tuple[int, int, int]:
    return (bool(record["image"]), bool(record["booking_url"]), len(record["description"] or ""))


def build_feed(
    articles: list[Article], sources: dict[str, Source], reference: datetime | None = None,
) -> list[dict]:
    reference = reference or datetime.now(timezone.utc)
    best: dict[tuple[str, str], dict] = {}
    for article in articles:
        if event_interval(article) is None:
            continue
        record = _record(article, reference)
        # Deduplica eventi equivalenti da fonti diverse (stesso titolo, stesso
        # giorno), tenendo la scheda con più dati.
        key = (normalize_text(record["title"])[:80], record["start"][:10])
        if key not in best or _richness(record) > _richness(best[key]):
            best[key] = record
    records = list(best.values())
    upcoming = sorted((r for r in records if not r["past"]), key=lambda r: r["start"])
    past = sorted((r for r in records if r["past"]), key=lambda r: r["start"], reverse=True)
    return upcoming + past


def _upload(payload: bytes, timeout: float = 20.0) -> None:
    endpoint = os.getenv(
        "SIRACUSA_EVENTS_UPLOAD_URL",
        "https://siracusadaily.com/.netlify/functions/events",
    )
    token = os.getenv("SIRACUSA_IMAGE_UPLOAD_TOKEN", "")
    if not token:
        raise EventsFeedError("SIRACUSA_IMAGE_UPLOAD_TOKEN non configurato")
    request = urllib.request.Request(
        endpoint, data=payload, method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status not in {200, 201}:
                raise EventsFeedError(f"upload Netlify HTTP {response.status}")
    except EventsFeedError:
        raise
    except Exception as exc:  # noqa: BLE001 - isoliamo qualsiasi errore di rete
        raise EventsFeedError(f"upload feed eventi non riuscito: {exc}") from exc


def publish_events_feed(source_map: Path, database: Path) -> int:
    """Costruisce il feed di tutti gli eventi e lo carica su Netlify. Restituisce
    il numero di eventi. Se il token non è configurato (run locale), non pubblica."""
    sources = load_sources(source_map)
    connection = connect(database)
    try:
        articles = all_event_articles(connection)
    finally:
        connection.close()
    events = build_feed(articles, sources)
    if not os.getenv("SIRACUSA_IMAGE_UPLOAD_TOKEN", ""):
        return -1
    feed = {"generated_at": datetime.now(timezone.utc).isoformat(), "count": len(events), "events": events}
    _upload(json.dumps(feed, ensure_ascii=False).encode("utf-8"))
    return len(events)
