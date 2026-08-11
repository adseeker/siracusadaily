from __future__ import annotations

import difflib
import hashlib
import math
from collections import Counter
from datetime import datetime, timezone

from .models import Article, Source, StoryCluster
from .categories import classify_article
from .text import normalize_text, tokens

RELIABILITY = {"high": 1.0, "medium": 0.65, "low": 0.3, "unknown": 0.2}
PRIORITY = {"high": 1.0, "medium": 0.6, "low": 0.25}


def _similar(left: Article, right: Article, max_age_hours: float | None = 96) -> bool:
    left_tokens, right_tokens = tokens(left.title), tokens(right.title)
    union = left_tokens | right_tokens
    jaccard = len(left_tokens & right_tokens) / len(union) if union else 0.0
    sequence = difflib.SequenceMatcher(None, normalize_text(left.title), normalize_text(right.title)).ratio()
    left_context = tokens(f"{left.title} {left.excerpt[:500]}")
    right_context = tokens(f"{right.title} {right.excerpt[:500]}")
    context_union = left_context | right_context
    context_jaccard = len(left_context & right_context) / len(context_union) if context_union else 0.0
    shared_title = len(left_tokens & right_tokens)
    hours = abs((left.published_at - right.published_at).total_seconds()) / 3600
    return (max_age_hours is None or hours <= max_age_hours) and (
        jaccard >= 0.5
        or sequence >= 0.82
        or (shared_title >= 3 and jaccard >= 0.18 and context_jaccard >= 0.14)
    )


def cluster_articles(
    articles: list[Article], max_age_hours: float | None = 96,
) -> list[StoryCluster]:
    clusters: list[StoryCluster] = []
    for article in sorted(articles, key=lambda item: item.published_at, reverse=True):
        target = next((
            cluster for cluster in clusters
            if any(_similar(article, other, max_age_hours) for other in cluster.articles)
        ), None)
        if target is None:
            key = hashlib.sha1(normalize_text(article.title).encode()).hexdigest()[:12]
            clusters.append(StoryCluster(key=key, articles=[article]))
        else:
            target.articles.append(article)
    return clusters


def _article_quality(article: Article, source: Source, now: datetime) -> float:
    age_hours = max(0.0, (now - article.published_at.astimezone(timezone.utc)).total_seconds() / 3600)
    recency = math.exp(-age_hours / 36)
    completeness = min(1.0, len(article.excerpt) / 400)
    return (
        article.local_score * 3.2
        + RELIABILITY.get(source.reliability, 0.2) * 1.4
        + PRIORITY.get(source.editorial_priority, 0.4)
        + recency * 1.8
        + completeness * 0.6
    )


def select_stories(
    articles: list[Article], sources: dict[str, Source], last_used: dict[str, int], limit: int = 8,
    max_per_source: int = 3, now: datetime | None = None,
    excluded_article_ids: set[int] | None = None,
    cluster_max_age_hours: float | None = 96,
) -> list[StoryCluster]:
    now = now or datetime.now(timezone.utc)
    clusters = cluster_articles(articles, cluster_max_age_hours)
    if excluded_article_ids:
        # The previously used URL remains inside the lookback window and acts as
        # an anchor: its whole semantic cluster is removed, including duplicates
        # published by other sources on a later day.
        clusters = [
            cluster for cluster in clusters
            if not any(article.article_id in excluded_article_ids for article in cluster.articles)
        ]
    for cluster in clusters:
        scored = []
        for article in cluster.articles:
            quality = _article_quality(article, sources[article.source_id], now)
            fairness = -0.0001 * last_used.get(article.source_id, -1)
            scored.append((quality + fairness, quality, article))
        _, quality, representative = max(scored, key=lambda item: item[0])
        cluster.representative = representative
        cluster.category = classify_article(representative)
        corroboration = min(0.8, 0.2 * (len({item.source_id for item in cluster.articles}) - 1))
        cluster.score = quality + corroboration

    selected: list[StoryCluster] = []
    counts: Counter[str] = Counter()
    remaining = list(clusters)
    covered_categories: set[str] = set()
    while remaining and len(selected) < limit:
        # La prima notizia valida di una sezione riceve un vantaggio moderato,
        # ma una notizia nettamente migliore conserva la precedenza.
        cluster = max(
            remaining,
            key=lambda item: item.score + (0.45 if item.category not in covered_categories else 0.0),
        )
        remaining.remove(cluster)
        source_id = cluster.representative.source_id
        if counts[source_id] >= max_per_source:
            alternatives = sorted(
                (item for item in cluster.articles if counts[item.source_id] < max_per_source),
                key=lambda item: _article_quality(item, sources[item.source_id], now), reverse=True,
            )
            if not alternatives:
                continue
            cluster.representative = alternatives[0]
            cluster.category = classify_article(cluster.representative)
            source_id = cluster.representative.source_id
        selected.append(cluster)
        counts[source_id] += 1
        covered_categories.add(cluster.category)
    return selected
