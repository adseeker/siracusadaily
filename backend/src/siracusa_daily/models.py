from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class Source:
    source_id: str
    name: str
    category: str
    reliability: str
    editorial_priority: str
    geographic_scope: str


@dataclass(frozen=True)
class Endpoint:
    endpoint_id: str
    source_id: str
    endpoint_type: str
    name: str
    url: str
    rss_url: str | None
    retrieval_method: str
    content_buckets: tuple[str, ...]


@dataclass
class Article:
    source_id: str
    endpoint_id: str
    title: str
    url: str
    published_at: datetime
    excerpt: str = ""
    author: str = ""
    content_buckets: tuple[str, ...] = field(default_factory=tuple)
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    local_score: float = 0.0
    local_reasons: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, str] = field(default_factory=dict)
    article_id: int | None = None


@dataclass
class StoryCluster:
    key: str
    articles: list[Article]
    score: float = 0.0
    representative: Article | None = None
    category: str = "Notizie e cronaca"
