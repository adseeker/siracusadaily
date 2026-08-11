from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .models import Article, StoryCluster

ROME = ZoneInfo("Europe/Rome")
EVENT_DATE_LABELS = {"Inizio", "Data"}


def _metadata_datetime(article: Article, key: str) -> datetime | None:
    value = article.metadata.get(key, "")
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ROME)
    return parsed.astimezone(timezone.utc)


def event_interval(article: Article) -> tuple[datetime, datetime | None] | None:
    """Return a trustworthy event interval, never an article publication date."""
    if article.metadata.get("date_label") not in EVENT_DATE_LABELS:
        return None
    start = _metadata_datetime(article, "event_start") or _metadata_datetime(article, "reference_date")
    if start is None:
        return None
    end = _metadata_datetime(article, "event_end")
    if end is not None and end < start:
        end = None
    return start, end


def is_dated_event(article: Article) -> bool:
    return event_interval(article) is not None


def event_window(edition_date: date, days: int = 7) -> tuple[datetime, datetime]:
    if days < 1:
        raise ValueError("La finestra eventi deve contenere almeno un giorno")
    start_local = datetime.combine(edition_date, time.min, tzinfo=ROME)
    end_local = start_local + timedelta(days=days)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def event_is_in_window(article: Article, edition_date: date, days: int = 7) -> bool:
    interval = event_interval(article)
    if interval is None:
        return False
    event_start, event_end = interval
    window_start, window_end = event_window(edition_date, days)
    if event_end is not None:
        return event_end >= window_start and event_start < window_end
    return window_start <= event_start < window_end


def event_sort_key(article: Article) -> datetime:
    interval = event_interval(article)
    return interval[0] if interval else datetime.max.replace(tzinfo=timezone.utc)


def sort_event_clusters(clusters: list[StoryCluster]) -> list[StoryCluster]:
    return sorted(clusters, key=lambda cluster: event_sort_key(cluster.representative))
