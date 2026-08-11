from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .models import Article, StoryCluster

ROME = ZoneInfo("Europe/Rome")
CLOSED_STATUSES = {"closed", "expired", "unavailable", "chiuso", "scaduto", "non disponibile"}
ACTIVE_UNDATED_STATUSES = {"open", "listed", "aperto"}


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


def is_opportunity(article: Article) -> bool:
    """Only explicitly structured, actionable opportunities enter the persistent track."""
    return article.metadata.get("opportunity") == "true"


def opportunity_deadline(article: Article) -> datetime | None:
    return _metadata_datetime(article, "opportunity_deadline") or (
        _metadata_datetime(article, "reference_date")
        if article.metadata.get("date_label") == "Scadenza"
        else None
    )


def opportunity_is_active(article: Article, edition_date: date, grace_days: int = 3) -> bool:
    if not is_opportunity(article):
        return False
    status = article.metadata.get("opportunity_status", "").strip().lower()
    if status in CLOSED_STATUSES:
        return False
    deadline = opportunity_deadline(article)
    if deadline is not None:
        # A deadline remains valid for the whole local calendar day.
        return deadline.astimezone(ROME).date() >= edition_date
    if status not in ACTIVE_UNDATED_STATUSES:
        return False
    verified = _metadata_datetime(article, "opportunity_verified_at") or article.retrieved_at
    end_of_edition = datetime.combine(edition_date, time.max, tzinfo=ROME).astimezone(timezone.utc)
    return verified >= end_of_edition - timedelta(days=grace_days)


def opportunity_sort_key(article: Article, edition_date: date) -> tuple:
    deadline = opportunity_deadline(article)
    local_deadline = deadline.astimezone(ROME).date() if deadline else date.max
    days_left = (local_deadline - edition_date).days if deadline else 10_000
    is_urgent = days_left <= 7
    published = article.published_at.astimezone(timezone.utc)
    return (
        0 if is_urgent else 1,
        local_deadline if is_urgent else date.max,
        -published.timestamp(),
        local_deadline,
    )


def sort_opportunity_clusters(
    clusters: list[StoryCluster], edition_date: date,
) -> list[StoryCluster]:
    return sorted(
        clusters,
        key=lambda cluster: opportunity_sort_key(cluster.representative, edition_date),
    )


def diversify_opportunity_clusters(
    clusters: list[StoryCluster], limit: int,
) -> list[StoryCluster]:
    """Round-robin sources while preserving each source's editorial order."""
    queues: dict[str, list[StoryCluster]] = {}
    source_order: list[str] = []
    for cluster in clusters:
        source_id = cluster.representative.source_id
        if source_id not in queues:
            queues[source_id] = []
            source_order.append(source_id)
        queues[source_id].append(cluster)
    selected: list[StoryCluster] = []
    while len(selected) < limit:
        added = False
        for source_id in source_order:
            if queues[source_id] and len(selected) < limit:
                selected.append(queues[source_id].pop(0))
                added = True
        if not added:
            break
    return selected
