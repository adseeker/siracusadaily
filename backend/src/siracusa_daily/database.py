from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from .events import event_is_in_window, event_sort_key
from .event_quality import event_is_publishable
from .models import Article
from .opportunities import opportunity_is_active, opportunity_sort_key

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS articles (
  article_id INTEGER PRIMARY KEY,
  canonical_url TEXT NOT NULL UNIQUE,
  source_id TEXT NOT NULL,
  endpoint_id TEXT NOT NULL,
  title TEXT NOT NULL,
  excerpt TEXT NOT NULL DEFAULT '',
  author TEXT NOT NULL DEFAULT '',
  published_at TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  content_buckets TEXT NOT NULL DEFAULT '[]',
  local_score REAL NOT NULL DEFAULT 0,
  local_reasons TEXT NOT NULL DEFAULT '[]',
  metadata TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source_id, published_at DESC);
CREATE TABLE IF NOT EXISTS newsletter_runs (
  run_id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL,
  edition_date TEXT NOT NULL,
  output_path TEXT NOT NULL,
  writer_name TEXT NOT NULL DEFAULT 'template',
  model TEXT NOT NULL DEFAULT '',
  brevo_campaign_id INTEGER,
  brevo_list_id INTEGER,
  delivery_status TEXT NOT NULL DEFAULT 'local',
  email_subject TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS newsletter_items (
  run_id INTEGER NOT NULL REFERENCES newsletter_runs(run_id),
  position INTEGER NOT NULL,
  article_id INTEGER NOT NULL REFERENCES articles(article_id),
  cluster_key TEXT NOT NULL,
  score REAL NOT NULL,
  PRIMARY KEY (run_id, position)
);
CREATE TABLE IF NOT EXISTS newsletter_exclusions (
  run_id INTEGER NOT NULL REFERENCES newsletter_runs(run_id),
  article_id INTEGER NOT NULL REFERENCES articles(article_id),
  cluster_key TEXT NOT NULL,
  reason TEXT NOT NULL,
  PRIMARY KEY (run_id, article_id)
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(articles)")}
    if "metadata" not in columns:
        connection.execute("ALTER TABLE articles ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'")
    run_columns = {row["name"] for row in connection.execute("PRAGMA table_info(newsletter_runs)")}
    if "writer_name" not in run_columns:
        connection.execute("ALTER TABLE newsletter_runs ADD COLUMN writer_name TEXT NOT NULL DEFAULT 'template'")
    if "model" not in run_columns:
        connection.execute("ALTER TABLE newsletter_runs ADD COLUMN model TEXT NOT NULL DEFAULT ''")
    if "brevo_campaign_id" not in run_columns:
        connection.execute("ALTER TABLE newsletter_runs ADD COLUMN brevo_campaign_id INTEGER")
    if "brevo_list_id" not in run_columns:
        connection.execute("ALTER TABLE newsletter_runs ADD COLUMN brevo_list_id INTEGER")
    if "delivery_status" not in run_columns:
        connection.execute("ALTER TABLE newsletter_runs ADD COLUMN delivery_status TEXT NOT NULL DEFAULT 'local'")
    if "email_subject" not in run_columns:
        connection.execute("ALTER TABLE newsletter_runs ADD COLUMN email_subject TEXT NOT NULL DEFAULT ''")
    connection.commit()
    return connection


def upsert_article(connection: sqlite3.Connection, article: Article) -> int:
    connection.execute(
        """
        INSERT INTO articles (
          canonical_url, source_id, endpoint_id, title, excerpt, author, published_at, retrieved_at,
          content_buckets, local_score, local_reasons, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(canonical_url) DO UPDATE SET
          title=excluded.title, excerpt=excluded.excerpt, author=excluded.author,
          published_at=excluded.published_at, retrieved_at=excluded.retrieved_at,
          content_buckets=excluded.content_buckets, local_score=excluded.local_score,
          local_reasons=excluded.local_reasons, metadata=excluded.metadata
        """,
        (
            article.url, article.source_id, article.endpoint_id, article.title, article.excerpt,
            article.author, article.published_at.isoformat(), article.retrieved_at.isoformat(),
            json.dumps(article.content_buckets, ensure_ascii=False), article.local_score,
            json.dumps(article.local_reasons, ensure_ascii=False), json.dumps(article.metadata, ensure_ascii=False),
        ),
    )
    row = connection.execute("SELECT article_id FROM articles WHERE canonical_url = ?", (article.url,)).fetchone()
    connection.commit()
    return int(row["article_id"])


def _articles_from_rows(rows: list[sqlite3.Row]) -> list[Article]:
    return [
        Article(
            article_id=row["article_id"], source_id=row["source_id"], endpoint_id=row["endpoint_id"],
            title=row["title"], url=row["canonical_url"], excerpt=row["excerpt"], author=row["author"],
            published_at=datetime.fromisoformat(row["published_at"]),
            retrieved_at=datetime.fromisoformat(row["retrieved_at"]),
            content_buckets=tuple(json.loads(row["content_buckets"])), local_score=row["local_score"],
            local_reasons=tuple(json.loads(row["local_reasons"])), metadata=json.loads(row["metadata"]),
        )
        for row in rows
    ]


def recent_articles(connection: sqlite3.Connection, since: datetime, minimum_local_score: float = 0.55) -> list[Article]:
    rows = connection.execute(
        "SELECT * FROM articles WHERE published_at >= ? AND local_score >= ? ORDER BY published_at DESC",
        (since.astimezone(timezone.utc).isoformat(), minimum_local_score),
    ).fetchall()
    return _articles_from_rows(rows)


def upcoming_event_articles(
    connection: sqlite3.Connection, edition_date: date, days: int = 7,
    minimum_local_score: float = 0.55,
) -> list[Article]:
    rows = connection.execute(
        """SELECT * FROM articles
           WHERE local_score >= ?
             AND json_extract(metadata, '$.date_label') IN ('Inizio', 'Data')""",
        (minimum_local_score,),
    ).fetchall()
    events = [
        article for article in _articles_from_rows(rows)
        if event_is_in_window(article, edition_date, days)
        and event_is_publishable(article)
    ]
    return sorted(events, key=event_sort_key)


def active_opportunity_articles(
    connection: sqlite3.Connection, edition_date: date,
    minimum_local_score: float = 0.55, grace_days: int = 3,
) -> list[Article]:
    rows = connection.execute(
        """SELECT * FROM articles
           WHERE local_score >= ?
             AND json_extract(metadata, '$.opportunity') = 'true'""",
        (minimum_local_score,),
    ).fetchall()
    from .opportunity_quality import opportunity_is_publishable

    opportunities = [
        article for article in _articles_from_rows(rows)
        if opportunity_is_active(article, edition_date, grace_days)
        and opportunity_is_publishable(article)
    ]
    return sorted(
        opportunities,
        key=lambda article: opportunity_sort_key(article, edition_date),
    )


def last_source_positions(connection: sqlite3.Connection) -> dict[str, int]:
    rows = connection.execute(
        """SELECT a.source_id, MAX(n.run_id) AS last_run
           FROM newsletter_items n JOIN articles a ON a.article_id=n.article_id
           GROUP BY a.source_id"""
    ).fetchall()
    return {row["source_id"]: int(row["last_run"]) for row in rows}


def previously_drafted_article_ids(
    connection: sqlite3.Connection, before_edition: str,
) -> set[int]:
    """Articles already included in an earlier successfully created Brevo draft."""
    rows = connection.execute(
        """SELECT DISTINCT n.article_id
           FROM newsletter_items n
           JOIN newsletter_runs r ON r.run_id = n.run_id
           WHERE r.edition_date < ? AND r.brevo_campaign_id IS NOT NULL""",
        (before_edition,),
    ).fetchall()
    return {int(row["article_id"]) for row in rows}


def record_newsletter(
    connection: sqlite3.Connection, edition_date: str, output_path: str,
    items: list[tuple[Article, str, float]], writer_name: str = "template", model: str = "",
    exclusions: list[tuple[Article, str, str]] | None = None, email_subject: str = "",
) -> int:
    cursor = connection.execute(
        """INSERT INTO newsletter_runs(
             created_at, edition_date, output_path, writer_name, model, email_subject
           ) VALUES (?, ?, ?, ?, ?, ?)""",
        (datetime.now(timezone.utc).isoformat(), edition_date, output_path, writer_name, model, email_subject),
    )
    run_id = int(cursor.lastrowid)
    connection.executemany(
        "INSERT INTO newsletter_items(run_id, position, article_id, cluster_key, score) VALUES (?, ?, ?, ?, ?)",
        [(run_id, position, article.article_id, key, score) for position, (article, key, score) in enumerate(items, 1)],
    )
    connection.executemany(
        "INSERT INTO newsletter_exclusions(run_id, article_id, cluster_key, reason) VALUES (?, ?, ?, ?)",
        [(run_id, article.article_id, key, reason) for article, key, reason in (exclusions or [])],
    )
    connection.commit()
    return run_id


def record_brevo_draft(
    connection: sqlite3.Connection, run_id: int, campaign_id: int, list_id: int,
) -> None:
    cursor = connection.execute(
        """UPDATE newsletter_runs
           SET brevo_campaign_id = ?, brevo_list_id = ?, delivery_status = 'brevo_draft'
           WHERE run_id = ?""",
        (campaign_id, list_id, run_id),
    )
    if cursor.rowcount != 1:
        connection.rollback()
        raise ValueError(f"newsletter run non trovato: {run_id}")
    connection.commit()


def get_newsletter_run(connection: sqlite3.Connection, run_id: int) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM newsletter_runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()


def get_brevo_campaign_for_edition(
    connection: sqlite3.Connection, edition_date: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """SELECT * FROM newsletter_runs
           WHERE edition_date = ? AND brevo_campaign_id IS NOT NULL
           ORDER BY run_id DESC LIMIT 1""",
        (edition_date,),
    ).fetchone()
