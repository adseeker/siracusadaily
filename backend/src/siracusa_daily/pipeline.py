from __future__ import annotations

from dataclasses import dataclass
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .config import load_endpoints, load_sources
from .database import (
    active_opportunity_articles,
    connect,
    last_source_positions,
    previously_drafted_article_ids,
    recent_articles,
    upcoming_event_articles,
    record_newsletter,
    upsert_article,
)
from .geography import evaluate_locality
from .events import is_dated_event, sort_event_clusters
from .event_quality import (
    QUARANTINED,
    QUALITY_STATUS_KEY,
    apply_event_quality,
    mark_multilingual_duplicates,
)
from .opportunities import (
    diversify_opportunity_clusters,
    is_opportunity,
    sort_opportunity_clusters,
)
from .opportunity_quality import (
    QUARANTINED as OPPORTUNITY_QUARANTINED,
    apply_opportunity_quality,
)
from .retrieval import RetrievalError, retrieve_html, retrieve_rss
from .selection import select_stories
from .writer import render_html, render_markdown, save_html, save_markdown
from .editorial import DEFAULT_MODEL, generate_editorial
from .facebook import (
    DEFAULT_SIGNUP_URL,
    FACEBOOK_ITEM_LIMIT,
    FacebookOutputError,
    render_facebook_outputs,
    save_facebook_outputs,
)
from .images import publish_newsletter_images


@dataclass
class IngestReport:
    endpoints_attempted: int = 0
    endpoints_succeeded: int = 0
    articles_seen: int = 0
    articles_local: int = 0
    events_quarantined: int = 0
    opportunities_quarantined: int = 0
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        self.errors = self.errors or []


def ingest(
    source_map: Path, endpoint_map: Path, database: Path, endpoint_limit: int | None = None,
    item_limit: int = 30, methods: set[str] | None = None,
) -> IngestReport:
    sources = load_sources(source_map)
    endpoints = [item for item in load_endpoints(endpoint_map) if item.source_id in sources and item.retrieval_method in {"rss", "web_html"}]
    if methods:
        endpoints = [item for item in endpoints if item.retrieval_method in methods]
    if endpoint_limit is not None:
        endpoints = endpoints[:endpoint_limit]
    report = IngestReport()
    connection = connect(database)
    try:
        for endpoint in endpoints:
            report.endpoints_attempted += 1
            try:
                adapter = retrieve_rss if endpoint.retrieval_method == "rss" else retrieve_html
                articles = adapter(endpoint, limit=item_limit)
            except RetrievalError as exc:
                report.errors.append(f"{endpoint.endpoint_id}: {exc}")
                continue
            report.endpoints_succeeded += 1
            report.articles_seen += len(articles)
            for article in articles:
                apply_event_quality(article)
                apply_opportunity_quality(article)
            mark_multilingual_duplicates(articles)
            for article in articles:
                article.local_score, article.local_reasons = evaluate_locality(article, sources[article.source_id])
                if article.local_score >= 0.55:
                    report.articles_local += 1
                if article.metadata.get(QUALITY_STATUS_KEY) == QUARANTINED:
                    report.events_quarantined += 1
                if article.metadata.get("opportunity_quality_status") == OPPORTUNITY_QUARANTINED:
                    report.opportunities_quarantined += 1
                article.article_id = upsert_article(connection, article)
    finally:
        connection.close()
    return report


def build_newsletter(
    source_map: Path, database: Path, output: Path, edition_date: date | None = None,
    lookback_hours: int = 72, limit: int = 8, writer_mode: str = "openai", model: str = DEFAULT_MODEL,
    unsubscribe_url: str | None = None, event_limit: int = 8,
    opportunity_limit: int = 6,
    facebook_output_dir: Path | None = None,
) -> tuple[int, int, str, str]:
    edition_date = edition_date or date.today()
    sources = load_sources(source_map)
    connection = connect(database)
    try:
        recent = recent_articles(connection, datetime.now(timezone.utc) - timedelta(hours=lookback_hours))
        news_articles = [
            article for article in recent
            if not is_dated_event(article) and not is_opportunity(article)
        ]
        news_clusters = select_stories(
            news_articles,
            sources,
            last_source_positions(connection),
            limit=limit,
            excluded_article_ids=previously_drafted_article_ids(
                connection, edition_date.isoformat(),
            ),
        )
        event_articles = upcoming_event_articles(connection, edition_date, days=7)
        event_clusters = select_stories(
            event_articles, sources, last_source_positions(connection),
            limit=event_limit, max_per_source=max(1, event_limit),
        )
        for cluster in event_clusters:
            cluster.category = "Eventi"
        opportunity_articles = active_opportunity_articles(connection, edition_date)
        opportunity_clusters = select_stories(
            opportunity_articles, sources, last_source_positions(connection),
            limit=len(opportunity_articles),
            max_per_source=max(1, len(opportunity_articles)),
            cluster_max_age_hours=None,
        )
        opportunity_clusters = diversify_opportunity_clusters(
            sort_opportunity_clusters(opportunity_clusters, edition_date),
            opportunity_limit,
        )
        for cluster in opportunity_clusters:
            cluster.category = "Lavoro e opportunità"
        clusters = (
            news_clusters
            + sort_event_clusters(event_clusters)
            + opportunity_clusters
        )
        selected_clusters = list(clusters)
        editorial_items, writer_used, exclusions, email_subject = generate_editorial(
            clusters, sources, mode=writer_mode, model=model,
        )
        if writer_used == "openai":
            sections = {item.candidate_id: item.section for item in editorial_items}
            for cluster in clusters:
                if is_dated_event(cluster.representative):
                    cluster.category = "Eventi"
                elif is_opportunity(cluster.representative):
                    cluster.category = "Lavoro e opportunità"
                elif cluster.key in sections:
                    cluster.category = sections[cluster.key]
            valid_ids = {item.candidate_id for item in editorial_items}
            clusters = [cluster for cluster in clusters if cluster.key in valid_ids]
        if output.suffix.lower() == ".html":
            image_report = publish_newsletter_images(clusters, edition_date)
            if image_report.attempted:
                print(
                    f"Immagini: {image_report.published}/{image_report.attempted} pubblicate; "
                    f"{image_report.skipped} saltate"
                )
            for error in image_report.errors:
                print(f"WARN IMG {error}")
            content = render_html(
                edition_date, clusters, sources, editorial_items,
                publisher_name=os.getenv("SIRACUSA_PUBLISHER_NAME", "SiracusaDaily"),
                publisher_address=os.getenv("SIRACUSA_PUBLISHER_ADDRESS", ""),
                unsubscribe_url=(
                    unsubscribe_url if unsubscribe_url is not None
                    else os.getenv("SIRACUSA_UNSUBSCRIBE_URL", "")
                ),
            )
            save_html(output, content)
        else:
            content = render_markdown(edition_date, clusters, sources, editorial_items, writer_used)
            save_markdown(output, content)
        if facebook_output_dir is not None:
            try:
                if writer_used != "openai":
                    raise FacebookOutputError(
                        "il recap richiede contenuti validati dal writer OpenAI"
                    )
                facebook_outputs = render_facebook_outputs(
                    clusters,
                    sources,
                    editorial_items,
                    limit=FACEBOOK_ITEM_LIMIT,
                    signup_url=os.getenv(
                        "SIRACUSA_FACEBOOK_SIGNUP_URL",
                        DEFAULT_SIGNUP_URL,
                    ),
                )
                post_path, sources_path = save_facebook_outputs(
                    facebook_output_dir,
                    facebook_outputs,
                )
                print(
                    f"Facebook: {facebook_outputs.item_count} contenuti -> "
                    f"{post_path}; {sources_path}"
                )
            except (FacebookOutputError, OSError) as exc:
                print(f"WARN FACEBOOK {exc}")
        items = [(cluster.representative, cluster.key, cluster.score) for cluster in clusters]
        excluded_items = [
            (cluster.representative, cluster.key, exclusions[cluster.key])
            for cluster in selected_clusters if cluster.key in exclusions
        ]
        run_id = record_newsletter(
            connection, edition_date.isoformat(), str(output), items,
            writer_name=writer_used, model=model if writer_used == "openai" else "",
            exclusions=excluded_items, email_subject=email_subject,
        )
        return run_id, len(items), writer_used, email_subject
    finally:
        connection.close()
