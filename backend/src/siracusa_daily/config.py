from __future__ import annotations

import csv
from pathlib import Path

from .models import Endpoint, Source


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y"}


def load_sources(path: Path) -> dict[str, Source]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        return {
            row["source_id"]: Source(
                source_id=row["source_id"],
                name=row["source_name"],
                category=row["source_category"],
                reliability=row["reliability"],
                editorial_priority=row["editorial_priority"],
                geographic_scope=row["geographic_scope"],
            )
            for row in rows
            if _truthy(row.get("active"))
        }


def load_endpoints(path: Path) -> list[Endpoint]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        return [
            Endpoint(
                endpoint_id=row["endpoint_id"],
                source_id=row["source_id"],
                endpoint_type=row["endpoint_type"],
                name=row["endpoint_name"],
                url=row["url"],
                rss_url=row.get("rss_url") or None,
                retrieval_method=row["retrieval_method"],
                content_buckets=tuple(
                    part.strip() for part in row.get("content_buckets", "").split(";") if part.strip()
                ),
            )
            for row in rows
            if _truthy(row.get("active"))
        ]

