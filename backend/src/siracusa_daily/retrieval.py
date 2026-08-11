from __future__ import annotations

import email.utils
import gzip
import html
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

from .models import Article, Endpoint
from .text import canonical_url, strip_html

USER_AGENT = "SiracusaDaily/0.1 (+local-news-research)"

OPPORTUNITY_ENDPOINTS = {"END-0022", "END-0038", "END-0039", "END-0040", "END-0041"}
OPPORTUNITY_EXCLUSIONS = (
    "avviso ai creditori", "avviso ad opponendum", "commissione esaminatrice",
    "verbale del sorteggio", "avviso interno", "mobilità interna", "mobilita interna",
)


class RetrievalError(RuntimeError):
    pass


def _download(url: str, timeout: float = 15.0, accept: str | None = None) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept or "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.5"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                payload = gzip.decompress(payload)
            return payload
    except Exception as exc:  # network boundary
        raise RetrievalError(f"{url}: {exc}") from exc


def _first_text(node: ET.Element, names: tuple[str, ...]) -> str:
    for child in node.iter():
        local = child.tag.rsplit("}", 1)[-1].lower()
        if local in names and child.text:
            return child.text.strip()
    return ""


def _entry_link(node: ET.Element) -> str:
    for child in node.iter():
        if child.tag.rsplit("}", 1)[-1].lower() != "link":
            continue
        href = child.attrib.get("href")
        if href and child.attrib.get("rel", "alternate") in {"alternate", ""}:
            return href
        if child.text and child.text.strip().startswith("http"):
            return child.text.strip()
    return ""


def _parse_date(value: str) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = email.utils.parsedate_to_datetime(value)
    if parsed is not None:
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def retrieve_rss(endpoint: Endpoint, limit: int = 30, timeout: float = 15.0) -> list[Article]:
    feed_url = endpoint.rss_url or endpoint.url
    root = ET.fromstring(_download(feed_url, timeout=timeout))
    entries = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1].lower() in {"item", "entry"}]
    articles: list[Article] = []
    for node in entries[:limit]:
        title = strip_html(_first_text(node, ("title",)))
        link = _entry_link(node)
        if not title or not link:
            continue
        published = _first_text(node, ("pubdate", "published", "updated", "date"))
        excerpt = _first_text(node, ("description", "summary", "encoded", "content"))
        author = _first_text(node, ("creator", "author"))
        articles.append(
            Article(
                source_id=endpoint.source_id,
                endpoint_id=endpoint.endpoint_id,
                title=title,
                url=canonical_url(link),
                published_at=_parse_date(published),
                excerpt=strip_html(excerpt),
                author=strip_html(author),
                content_buckets=endpoint.content_buckets,
            )
        )
    return _prepare_opportunities(endpoint, articles, timeout)


ITALIAN_MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
ROME = ZoneInfo("Europe/Rome")


def _html_text(value: str) -> str:
    return strip_html(html.unescape(value or ""))


def _parse_local_date(value: str) -> datetime:
    parsed = _parse_optional_local_date(value)
    return parsed or datetime.now(timezone.utc)


def _parse_optional_local_date(value: str) -> datetime | None:
    value = _html_text(value).strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=ROME).astimezone(timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except ValueError:
        pass
    for pattern in (
        "%d/%m/%Y %H:%M", "%d/%m/%Y %H.%M", "%d.%m.%Y %H:%M", "%d.%m.%Y %H.%M",
        "%d/%m/%Y", "%d/%m/%y", "%d.%m.%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z",
    ):
        try:
            parsed = datetime.strptime(value, pattern)
            return parsed.replace(tzinfo=ROME).astimezone(timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    match = re.search(
        r"(\d{1,2})\s+([A-Za-zà-ù]+)\s+(\d{4})(?:\s+(?:ore?\s*)?(\d{1,2})[:.]([0-5]\d))?",
        value.lower(),
    )
    if match and match.group(2) in ITALIAN_MONTHS:
        return datetime(
            int(match.group(3)), ITALIAN_MONTHS[match.group(2)], int(match.group(1)),
            int(match.group(4) or 0), int(match.group(5) or 0), tzinfo=ROME,
        ).astimezone(timezone.utc)
    return None


def _is_actionable_opportunity(endpoint: Endpoint, article: Article) -> bool:
    if endpoint.endpoint_id not in OPPORTUNITY_ENDPOINTS:
        return False
    text = _html_text(f"{article.title} {article.excerpt}").lower()
    if any(term in text for term in OPPORTUNITY_EXCLUSIONS):
        return False
    if endpoint.endpoint_id == "END-0040":
        return True
    if endpoint.endpoint_id == "END-0041":
        return any(term in text for term in ("concorso pubblico", "avviso pubblico"))
    if endpoint.endpoint_id == "END-0038":
        return any(term in text for term in (
            "manifestazione di interesse", "assegnazione", "acquisizione di disponibilità",
            "acquisizione di disponibilita", "richiesta di preventivo", "candidatura",
        ))
    if endpoint.endpoint_id == "END-0039":
        return any(term in text for term in (
            "mobilità volontaria", "mobilita volontaria", "concorso", "selezione",
            "sponsor", "candidatura",
        ))
    return any(term in text for term in (
        "offerta di lavoro", "posizioni aperte", "ricerca personale", "cerca personale",
        "assume", "assunzioni", "candidature aperte",
    ))


def _deadline_from_text(value: str) -> datetime | None:
    text = _html_text(value)
    contexts = re.findall(
        r"(?:data\s+(?:di\s+)?scadenza(?:\s+della\s+candidatura)?|scadenza(?:\s+è\s+fissata)?|"
        r"entro(?:\s+e\s+non\s+oltre)?)(.{0,140})",
        text, flags=re.I,
    )
    date_pattern = (
        r"\d{1,2}[/.]\d{1,2}[/.]\d{4}(?:\s+(?:ore?\s*)?\d{1,2}[:.]\d{2})?"
        r"|\d{1,2}\s+[A-Za-zà-ù]+\s+\d{4}(?:\s+(?:ore?\s*)?\d{1,2}[:.]\d{2})?"
    )
    for context in contexts:
        match = re.search(date_pattern, context, flags=re.I)
        if match:
            parsed = _parse_optional_local_date(match.group(0))
            if parsed is not None:
                return parsed
    return None


def _opportunity_detail_metadata(document: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    deadline = _deadline_from_text(document)
    if deadline is not None:
        metadata.update({
            "date_label": "Scadenza",
            "reference_date": deadline.isoformat(),
            "opportunity_deadline": deadline.isoformat(),
        })
    status_match = re.search(
        r"data-element=[\"']service-status[\"'].*?class=[\"'][^\"']*chip-label[^\"']*[\"'][^>]*>(.*?)</span>",
        document, flags=re.I | re.S,
    )
    if status_match:
        label = _html_text(status_match.group(1)).lower()
        metadata["opportunity_status"] = {
            "aperto": "open", "chiuso": "closed", "scaduto": "expired",
        }.get(label, label)
    return metadata


def _prepare_opportunities(
    endpoint: Endpoint, articles: list[Article], timeout: float,
) -> list[Article]:
    candidates = [article for article in articles if _is_actionable_opportunity(endpoint, article)]
    if not candidates:
        return articles
    for article in candidates:
        default_status = (
            "unverified" if endpoint.endpoint_id in {"END-0038", "END-0039"}
            else "listed"
        )
        article.metadata.update({
            "opportunity": "true",
            "opportunity_status": article.metadata.get("opportunity_status", default_status),
            "opportunity_verified_at": article.retrieved_at.isoformat(),
        })
        deadline = _deadline_from_text(f"{article.title} {article.excerpt}")
        if deadline is not None:
            article.metadata.update({
                "date_label": "Scadenza", "reference_date": deadline.isoformat(),
                "opportunity_deadline": deadline.isoformat(),
            })

    def detail(article: Article) -> tuple[Article, dict[str, str] | None]:
        try:
            document = _download(
                article.url, timeout=min(timeout, 12.0),
                accept="text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
            ).decode("utf-8", errors="replace")
        except RetrievalError:
            return article, None
        return article, _opportunity_detail_metadata(document)

    # Detail pages contain authoritative deadlines that are absent from many
    # list pages. Parallel, bounded reads keep the daily run reasonably fast.
    with ThreadPoolExecutor(max_workers=min(6, len(candidates))) as executor:
        futures = [executor.submit(detail, article) for article in candidates]
        for future in as_completed(futures):
            article, metadata = future.result()
            if metadata:
                article.metadata.update(metadata)
    return articles


def _event_metadata(start: datetime, end: datetime | None = None, **values: str) -> dict[str, str]:
    metadata = {
        "date_label": "Inizio",
        "reference_date": start.isoformat(),
        "event_start": start.isoformat(),
        **values,
    }
    if end is not None:
        metadata["event_end"] = end.isoformat()
    return metadata


def _local_wall_time_from_epoch(value: str | int | float) -> datetime | None:
    """Interpret aggregator timestamps that encode local wall time as UTC seconds."""
    try:
        naive = datetime.fromtimestamp(float(value), tz=timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, OverflowError):
        return None
    return naive.replace(tzinfo=ROME).astimezone(timezone.utc)


def _dated_local_value(date_value: str, time_value: str = "", *, end_of_day: bool = False) -> datetime | None:
    date_value = (date_value or "").strip()
    time_value = (time_value or "").strip()
    if not date_value:
        return None
    if time_value:
        return _parse_optional_local_date(f"{date_value} {time_value}")
    parsed = _parse_optional_local_date(date_value)
    if parsed is not None and end_of_day:
        local = parsed.astimezone(ROME).replace(hour=23, minute=59, second=59)
        return local.astimezone(timezone.utc)
    return parsed


def _json_nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _json_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _json_nodes(child)


def _allevents_articles(document: str, endpoint: Endpoint, limit: int) -> list[Article]:
    events: list = []
    for marker in re.finditer(r"\b(?:_this\.)?events_data\s*=\s*", document):
        try:
            candidate, _ = json.JSONDecoder().raw_decode(document[marker.end():])
        except (json.JSONDecodeError, TypeError):
            continue
        # The page initializes the same variable to [] several times before
        # assigning the actual dataset. Keep the richest valid assignment.
        if isinstance(candidate, list) and len(candidate) > len(events):
            events = candidate
    if not events:
        return []

    articles: list[Article] = []
    seen: set[str] = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        title = _html_text(str(event.get("eventname_raw") or event.get("eventname") or ""))
        url = canonical_url(str(event.get("event_url") or event.get("share_url") or ""))
        start = _local_wall_time_from_epoch(event.get("start_time", ""))
        if not title or not url.startswith("http") or start is None or url in seen:
            continue
        seen.add(url)
        end = _local_wall_time_from_epoch(event.get("end_time", ""))
        if end is not None and end <= start:
            end = None
        venue = event.get("venue") if isinstance(event.get("venue"), dict) else {}
        location = _html_text(str(
            venue.get("full_address") or event.get("location_raw") or event.get("location") or ""
        ))
        organizer = event.get("organizer") if isinstance(event.get("organizer"), dict) else {}
        organizer_name = _html_text(str(organizer.get("name") or "AllEvents"))
        description = _html_text(str(event.get("short_description") or ""))
        excerpt = " — ".join(value for value in (description, location) if value)
        articles.append(Article(
            source_id=endpoint.source_id, endpoint_id=endpoint.endpoint_id, title=title,
            url=url, published_at=start, excerpt=excerpt, author=organizer_name,
            content_buckets=endpoint.content_buckets,
            metadata=_event_metadata(start, end, location=location, organizer=organizer_name),
        ))
    return sorted(articles, key=lambda article: article.published_at)[:limit]


def _eventi_siracusa_articles(payload: str, endpoint: Endpoint, limit: int) -> list[Article]:
    try:
        events = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(events, list):
        return []

    articles: list[Article] = []
    for event in events:
        if not isinstance(event, dict) or event.get("published") is False:
            continue
        title = _html_text(str(event.get("title") or ""))
        event_id = str(event.get("id") or "").strip()
        start = _dated_local_value(str(event.get("start_date") or ""), str(event.get("start_time") or ""))
        if not title or not event_id or start is None:
            continue
        end = _dated_local_value(
            str(event.get("end_date") or ""), str(event.get("end_time") or ""), end_of_day=True,
        )
        if end is not None and end < start:
            end = None
        location = " · ".join(value for value in (
            _html_text(str(event.get("location_name") or "")),
            _html_text(str(event.get("location_address") or "")),
        ) if value)
        description = _html_text(str(event.get("short_description") or ""))
        if not description:
            description = _html_text(str(event.get("long_description") or ""))
        excerpt = " — ".join(value for value in (description, location) if value)
        url = canonical_url(f"{endpoint.url.rstrip('/')}/?event={event_id}")
        articles.append(Article(
            source_id=endpoint.source_id, endpoint_id=endpoint.endpoint_id, title=title,
            url=url, published_at=start, excerpt=excerpt, author="Eventi Siracusa",
            content_buckets=endpoint.content_buckets,
            metadata=_event_metadata(
                start, end, location=location,
                event_category=_html_text(str(event.get("category") or "")),
            ),
        ))
    return sorted(articles, key=lambda article: article.published_at)[:limit]


def _virgilio_articles(document: str, endpoint: Endpoint, limit: int) -> list[Article]:
    blocks = re.findall(
        r"<article\b[^>]*itemtype=[\"']http://schema\.org/Event[\"'][^>]*>(.*?)</article>\s*<style",
        document, flags=re.I | re.S,
    )
    articles: list[Article] = []
    seen: set[str] = set()
    for block in blocks:
        title_match = re.search(
            r"<h2[^>]*itemprop=[\"']name[\"'][^>]*>.*?<a(?=[^>]*itemprop=[\"']url[\"'])[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
            block, flags=re.I | re.S,
        )
        start_match = re.search(
            r"<time[^>]*itemprop=[\"']startDate[\"'][^>]*datetime=[\"']([^\"']+)[\"']",
            block, flags=re.I,
        ) or re.search(
            r"<time[^>]*datetime=[\"']([^\"']+)[\"'][^>]*itemprop=[\"']startDate[\"']",
            block, flags=re.I,
        )
        if not title_match or not start_match:
            continue
        title = _html_text(title_match.group(2))
        url = canonical_url(urljoin(endpoint.url, html.unescape(title_match.group(1))))
        start = _parse_optional_local_date(start_match.group(1))
        if not title or not url.startswith("http") or start is None or url in seen:
            continue
        seen.add(url)
        end_match = re.search(
            r"<time[^>]*(?:itemprop=[\"']endDate[\"'][^>]*datetime|datetime=[\"']([^\"']+)[\"'][^>]*itemprop=[\"']endDate[\"'])",
            block, flags=re.I,
        )
        end = None
        if end_match:
            end_value = end_match.group(1)
            if not end_value:
                direct = re.search(
                    r"<time[^>]*itemprop=[\"']endDate[\"'][^>]*datetime=[\"']([^\"']+)[\"']",
                    block, flags=re.I,
                )
                end_value = direct.group(1) if direct else ""
            end = _parse_optional_local_date(end_value)
        description_match = re.search(
            r"<p[^>]*itemprop=[\"']description[\"'][^>]*>(.*?)</p>", block, flags=re.I | re.S,
        )
        location_match = re.search(
            r"<span[^>]*itemprop=[\"']name[\"'][^>]*>(.*?)</span>", block, flags=re.I | re.S,
        )
        description = _html_text(description_match.group(1)) if description_match else ""
        location = _html_text(location_match.group(1)) if location_match else ""
        excerpt = " — ".join(value for value in (description, location) if value)
        articles.append(Article(
            source_id=endpoint.source_id, endpoint_id=endpoint.endpoint_id, title=title,
            url=url, published_at=start, excerpt=excerpt, author="Virgilio Eventi",
            content_buckets=endpoint.content_buckets,
            metadata=_event_metadata(start, end, location=location),
        ))
    return articles[:limit]


def _eventbrite_articles(document: str, endpoint: Endpoint, limit: int) -> list[Article]:
    server_match = re.search(
        r"window\.__SERVER_DATA__\s*=\s*(\{.*?\});\s*(?:window\.__REACT_QUERY_STATE__|</script>)",
        document, flags=re.S,
    )
    if server_match:
        try:
            server_data = json.loads(server_match.group(1))
            events = server_data["search_data"]["events"]["results"]
        except (json.JSONDecodeError, KeyError, TypeError):
            events = []
        parsed: list[Article] = []
        seen_server: set[str] = set()
        for event in events:
            if not event.get("name") or not event.get("url"):
                continue
            url = canonical_url(event["url"])
            if url in seen_server:
                continue
            seen_server.add(url)
            date_value = event.get("start_date", "")
            time_value = event.get("start_time", "00:00") or "00:00"
            try:
                start = datetime.fromisoformat(f"{date_value}T{time_value}").replace(tzinfo=ROME).astimezone(timezone.utc)
            except ValueError:
                start = _parse_optional_local_date(date_value)
            if start is None:
                continue
            end = None
            end_date = event.get("end_date", "")
            if end_date:
                end_time = event.get("end_time", "00:00") or "00:00"
                try:
                    end = datetime.fromisoformat(f"{end_date}T{end_time}").replace(tzinfo=ROME).astimezone(timezone.utc)
                except ValueError:
                    end = _parse_optional_local_date(end_date)
            venue = event.get("primary_venue") or {}
            address = venue.get("address") or {}
            location_text = " · ".join(str(value) for value in (
                venue.get("name"), address.get("address_1"), address.get("city"), address.get("region")
            ) if value)
            summary = _html_text(event.get("summary", ""))
            parsed.append(Article(
                source_id=endpoint.source_id, endpoint_id=endpoint.endpoint_id, title=_html_text(event["name"]),
                url=url, published_at=start, excerpt=" — ".join(value for value in (summary, location_text) if value),
                author="Eventbrite", content_buckets=endpoint.content_buckets,
                metadata=_event_metadata(start, end, location=location_text),
            ))
            if len(parsed) >= limit:
                return parsed
        if parsed:
            return parsed
    scripts = re.findall(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", document, flags=re.I | re.S)
    seen: set[str] = set()
    articles: list[Article] = []
    for script in scripts:
        try:
            payload = json.loads(html.unescape(script.strip()))
        except (json.JSONDecodeError, TypeError):
            continue
        for node in _json_nodes(payload):
            node_type = node.get("@type")
            if node_type != "Event" or not node.get("name") or not node.get("url"):
                continue
            url = canonical_url(str(node["url"]))
            if url in seen:
                continue
            seen.add(url)
            location = node.get("location") or {}
            address = location.get("address") or {} if isinstance(location, dict) else {}
            location_text = " · ".join(
                str(value) for value in (
                    location.get("name") if isinstance(location, dict) else "",
                    address.get("streetAddress"), address.get("addressLocality"), address.get("addressRegion"),
                ) if value
            )
            start = _parse_optional_local_date(str(node.get("startDate", "")))
            if start is None:
                continue
            end = _parse_optional_local_date(str(node.get("endDate", "")))
            description = _html_text(str(node.get("description", "")))
            excerpt = " — ".join(value for value in (description, location_text) if value)
            articles.append(Article(
                source_id=endpoint.source_id, endpoint_id=endpoint.endpoint_id, title=_html_text(str(node["name"])),
                url=url, published_at=start, excerpt=excerpt, author="Eventbrite",
                content_buckets=endpoint.content_buckets,
                metadata=_event_metadata(start, end, location=location_text),
            ))
            if len(articles) >= limit:
                return articles
    return articles


def _comune_articles(document: str, endpoint: Endpoint, limit: int) -> list[Article]:
    pattern = re.compile(
        r"(?:<span class=[\"']data_num[\"']>(?P<date>[^<]+)</span>).*?"
        r"<a class=[\"'][^\"']*card-title[^\"']*[\"'][^>]*href=[\"'](?P<url>[^\"']+)[\"'][^>]*>(?P<title>.*?)</a>.*?"
        r"<p class=[\"'][^\"']*description[^\"']*[\"']>(?P<excerpt>.*?)</p>", re.I | re.S,
    )
    articles: list[Article] = []
    for match in pattern.finditer(document):
        published = _parse_optional_local_date(match.group("date"))
        if published is None:
            continue
        articles.append(Article(
            source_id=endpoint.source_id, endpoint_id=endpoint.endpoint_id,
            title=_html_text(match.group("title")), url=canonical_url(urljoin(endpoint.url, match.group("url"))),
            published_at=published, excerpt=_html_text(match.group("excerpt")), author="Comune di Siracusa",
            content_buckets=endpoint.content_buckets,
            metadata={
                "date_label": "Data", "reference_date": published.isoformat(),
                "event_start": published.isoformat(),
            },
        ))
        if len(articles) >= limit:
            break
    return articles


def _asp_articles(document: str, endpoint: Endpoint, limit: int) -> list[Article]:
    pattern = re.compile(
        r"<h3 class=[\"'][^\"']*card-title[^\"']*[\"']>\s*<a[^>]+href=[\"'](?P<url>[^\"']+)[\"'][^>]*>(?P<title>.*?)</a></h3>"
        r".*?<span class=[\"'][^\"']*font-monospace[^\"']*[\"']>(?P<date>[^<]+)</span>", re.I | re.S,
    )
    articles: list[Article] = []
    for match in pattern.finditer(document):
        published = _parse_local_date(match.group("date"))
        title = _html_text(match.group("title"))
        articles.append(Article(
            source_id=endpoint.source_id, endpoint_id=endpoint.endpoint_id, title=title,
            url=canonical_url(urljoin(endpoint.url, match.group("url"))), published_at=published,
            excerpt=f"Procedura ASP Siracusa: {title}", author="ASP Siracusa",
            content_buckets=endpoint.content_buckets,
            metadata={"date_label": "Pubblicato", "reference_date": published.isoformat()},
        ))
        if len(articles) >= limit:
            break
    return articles


def _concorsi_articles(document: str, endpoint: Endpoint, limit: int) -> list[Article]:
    blocks = re.findall(r"<article\b(?P<attrs>[^>]*)>(?P<body>.*?)</article>", document, flags=re.I | re.S)
    articles: list[Article] = []
    for attrs, body in blocks:
        if "is-expired" in attrs:
            continue
        title_match = re.search(r"class=[\"']contest-title[\"'].*?<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", body, flags=re.I | re.S)
        if not title_match:
            continue
        deadline_match = re.search(r"<time[^>]+datetime=[\"']([^\"']+)[\"'][^>]*>(.*?)</time>", body, flags=re.I | re.S)
        body_match = re.search(r"field--name-body.*?field__item[\"'][^>]*>(.*?)</div>", body, flags=re.I | re.S)
        deadline = _parse_local_date(deadline_match.group(1) if deadline_match else "")
        title = _html_text(title_match.group(2))
        excerpt = _html_text(body_match.group(1)) if body_match else ""
        if deadline_match:
            excerpt = f"Scadenza: {_html_text(deadline_match.group(2))}. {excerpt}".strip()
        articles.append(Article(
            source_id=endpoint.source_id, endpoint_id=endpoint.endpoint_id, title=title,
            url=canonical_url(urljoin(endpoint.url, title_match.group(1))), published_at=deadline,
            excerpt=excerpt, author="ConcorsiPubblici.com", content_buckets=endpoint.content_buckets,
            metadata={
                "date_label": "Scadenza", "reference_date": deadline.isoformat(),
                "opportunity": "true", "opportunity_status": "open",
                "opportunity_deadline": deadline.isoformat(),
            },
        ))
        if len(articles) >= limit:
            break
    return articles


def retrieve_html(endpoint: Endpoint, limit: int = 30, timeout: float = 15.0) -> list[Article]:
    document = _download(endpoint.url, timeout=timeout, accept="text/html,application/xhtml+xml;q=0.9,*/*;q=0.5").decode("utf-8", errors="replace")
    host = urlsplit(endpoint.url).netloc.lower()
    if "allevents.in" in host:
        return _allevents_articles(document, endpoint, limit)
    if "eventisiracusa.base44.app" in host:
        app_match = re.search(r"data-app-id=[\"']([^\"']+)[\"']", document)
        if not app_match:
            raise RetrievalError(f"{endpoint.url}: identificativo pubblico del calendario non trovato")
        data_url = urljoin(
            endpoint.url,
            f"/api/apps/{app_match.group(1)}/entities/Event?sort=-start_date&limit=200",
        )
        payload = _download(
            data_url, timeout=timeout, accept="application/json;q=1.0,*/*;q=0.5",
        ).decode("utf-8", errors="replace")
        return _eventi_siracusa_articles(payload, endpoint, limit)
    if "virgilio.it" in host:
        return _virgilio_articles(document, endpoint, limit)
    if "eventbrite." in host:
        return _eventbrite_articles(document, endpoint, limit)
    if "comune.siracusa.it" in host:
        return _comune_articles(document, endpoint, limit)
    if "concorsipubblici.com" in host:
        return _prepare_opportunities(endpoint, _concorsi_articles(document, endpoint, limit), timeout)
    if "asp.sr.it" in host:
        return _prepare_opportunities(endpoint, _asp_articles(document, endpoint, limit), timeout)
    raise RetrievalError(f"{endpoint.url}: nessun adapter HTML registrato")
