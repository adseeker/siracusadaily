from __future__ import annotations

from dataclasses import dataclass
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .config import load_endpoints, load_sources
from .database import connect, last_source_positions, recent_articles, record_newsletter, upsert_article
from .geography import evaluate_locality
from .retrieval import RetrievalError, retrieve_html, retrieve_rss
from .selection import select_stories
from .writer import render_html, render_markdown, save_html, save_markdown
from .editorial import DEFAULT_MODEL, generate_editorial


@dataclass
class IngestReport:
    endpoints_attempted: int = 0
    endpoints_succeeded: int = 0
    articles_seen: int = 0
    articles_local: int = 0
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
                article.local_score, article.local_reasons = evaluate_locality(article, sources[article.source_id])
                if article.local_score >= 0.55:
                    report.articles_local += 1
                article.article_id = upsert_article(connection, article)
    finally:
        connection.close()
    return report


def build_newsletter(
    source_map: Path, database: Path, output: Path, edition_date: date | None = None,
    lookback_hours: int = 72, limit: int = 8, writer_mode: str = "openai", model: str = DEFAULT_MODEL,
    unsubscribe_url: str | None = None,
) -> tuple[int, int, str, str]:
    edition_date = edition_date or date.today()
    sources = load_sources(source_map)
    connection = connect(database)
    try:
        articles = recent_articles(connection, datetime.now(timezone.utc) - timedelta(hours=lookback_hours))
        clusters = select_stories(articles, sources, last_source_positions(connection), limit=limit)
        selected_clusters = list(clusters)
        editorial_items, writer_used, exclusions, email_subject = generate_editorial(
            clusters, sources, mode=writer_mode, model=model,
        )
        if writer_used == "openai":
            sections = {item.candidate_id: item.section for item in editorial_items}
            for cluster in clusters:
                if cluster.key in sections:
                    cluster.category = sections[cluster.key]
            valid_ids = {item.candidate_id for item in editorial_items}
            clusters = [cluster for cluster in clusters if cluster.key in valid_ids]
        if output.suffix.lower() == ".html":
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
