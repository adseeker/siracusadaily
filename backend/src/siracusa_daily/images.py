from __future__ import annotations

import hashlib
import io
import json
import os
import re
import urllib.request
from dataclasses import dataclass
from datetime import date
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlsplit

from PIL import Image, ImageOps, UnidentifiedImageError

from .models import StoryCluster


USER_AGENT = "SiracusaDaily/0.1 (+newsletter-image-discovery)"
TARGET_CATEGORIES = ("Notizie e cronaca", "Cultura", "Sport", "Eventi")
MAX_SOURCE_IMAGE_BYTES = 8_000_000
MAX_PUBLISHED_IMAGE_BYTES = 180_000
THUMBNAIL_SIZE = (480, 300)
REJECTED_URL_PARTS = (
    "avatar", "blank.", "default-image", "favicon", "gravatar", "icon-",
    "logo", "no-image", "placeholder", "pixel.", "spinner", "sprite",
    "tracking",
)


class ImageDiscoveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class ImageCandidate:
    url: str
    source: str
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class PreparedImage:
    content: bytes
    width: int
    height: int
    content_type: str = "image/jpeg"


@dataclass
class ImagePublishReport:
    attempted: int = 0
    published: int = 0
    skipped: int = 0
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        self.errors = self.errors or []


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []
        self.json_ld: list[str] = []
        self._json_ld_depth = 0
        self._json_ld_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): (value or "") for name, value in attrs}
        lowered = tag.lower()
        if lowered == "meta":
            self.meta.append(values)
        elif lowered == "link":
            self.links.append(values)
        elif lowered == "script" and values.get("type", "").lower() == "application/ld+json":
            self._json_ld_depth = 1
            self._json_ld_chunks = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._json_ld_depth:
            self.json_ld.append("".join(self._json_ld_chunks))
            self._json_ld_depth = 0
            self._json_ld_chunks = []

    def handle_data(self, data: str) -> None:
        if self._json_ld_depth:
            self._json_ld_chunks.append(data)


def _positive_int(value: str | None) -> int | None:
    try:
        parsed = int(value or "")
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _valid_public_url(value: str, page_url: str) -> str | None:
    resolved = urljoin(page_url, unescape(value).strip())
    parts = urlsplit(resolved)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    lowered = resolved.lower()
    if any(part in lowered for part in REJECTED_URL_PARTS):
        return None
    return resolved


def _json_images(value: object) -> list[str]:
    results: list[str] = []
    if isinstance(value, str):
        results.append(value)
    elif isinstance(value, list):
        for item in value:
            results.extend(_json_images(item))
    elif isinstance(value, dict):
        image = value.get("image")
        if image is not None:
            results.extend(_json_images(image))
        content_url = value.get("contentUrl") or value.get("url")
        if isinstance(content_url, str) and str(value.get("@type", "")).lower() == "imageobject":
            results.append(content_url)
        graph = value.get("@graph")
        if graph is not None:
            results.extend(_json_images(graph))
    return results


def extract_image_candidates(document: str, page_url: str) -> list[ImageCandidate]:
    parser = _MetadataParser()
    parser.feed(document)
    candidates: list[tuple[int, ImageCandidate]] = []
    og_width: int | None = None
    og_height: int | None = None

    for meta in parser.meta:
        key = (meta.get("property") or meta.get("name") or "").lower()
        if key == "og:image:width":
            og_width = _positive_int(meta.get("content"))
        elif key == "og:image:height":
            og_height = _positive_int(meta.get("content"))

    for meta in parser.meta:
        key = (meta.get("property") or meta.get("name") or "").lower()
        raw_url = meta.get("content", "")
        if key in {"og:image", "og:image:url", "og:image:secure_url"}:
            url = _valid_public_url(raw_url, page_url)
            if url:
                candidates.append((100, ImageCandidate(url, key, og_width, og_height)))
        elif key in {"twitter:image", "twitter:image:src"}:
            url = _valid_public_url(raw_url, page_url)
            if url:
                candidates.append((90, ImageCandidate(url, key)))

    for link in parser.links:
        if link.get("rel", "").lower() != "image_src":
            continue
        url = _valid_public_url(link.get("href", ""), page_url)
        if url:
            candidates.append((80, ImageCandidate(url, "link:image_src")))

    for raw_payload in parser.json_ld:
        try:
            payload = json.loads(raw_payload)
        except (TypeError, ValueError):
            continue
        for raw_url in _json_images(payload):
            url = _valid_public_url(raw_url, page_url)
            if url:
                candidates.append((70, ImageCandidate(url, "json-ld")))

    unique: dict[str, tuple[int, ImageCandidate]] = {}
    for priority, candidate in candidates:
        current = unique.get(candidate.url)
        if current is None or priority > current[0]:
            unique[candidate.url] = (priority, candidate)
    return [item[1] for item in sorted(unique.values(), key=lambda item: item[0], reverse=True)]


def extract_image_url(document: str, page_url: str) -> str | None:
    candidates = extract_image_candidates(document, page_url)
    return candidates[0].url if candidates else None


def discover_article_image(page_url: str, timeout: float = 20.0) -> ImageCandidate | None:
    request = urllib.request.Request(
        page_url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml;q=0.9"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            if "html" not in content_type:
                raise ImageDiscoveryError(f"contenuto non HTML: {content_type or 'sconosciuto'}")
            document = response.read(2_000_000).decode("utf-8", errors="replace")
    except ImageDiscoveryError:
        raise
    except Exception as exc:
        raise ImageDiscoveryError(f"{page_url}: {exc}") from exc
    candidates = extract_image_candidates(document, page_url)
    return candidates[0] if candidates else None


def image_url_is_reachable(image_url: str, timeout: float = 15.0) -> bool:
    request = urllib.request.Request(
        image_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8",
            "Range": "bytes=0-65535",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            prefix = response.read(32)
    except Exception:
        return False
    if not content_type.startswith("image/"):
        return False
    signatures = (
        prefix.startswith(b"\xff\xd8\xff"),
        prefix.startswith(b"\x89PNG\r\n\x1a\n"),
        prefix.startswith((b"GIF87a", b"GIF89a")),
        prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP",
    )
    return any(signatures)


def download_image(image_url: str, timeout: float = 20.0) -> bytes:
    request = urllib.request.Request(
        image_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            if not content_type.startswith("image/"):
                raise ImageDiscoveryError(f"risorsa non immagine: {content_type or 'sconosciuta'}")
            payload = response.read(MAX_SOURCE_IMAGE_BYTES + 1)
    except ImageDiscoveryError:
        raise
    except Exception as exc:
        raise ImageDiscoveryError(f"immagine non scaricabile: {exc}") from exc
    if not payload or len(payload) > MAX_SOURCE_IMAGE_BYTES:
        raise ImageDiscoveryError("immagine vuota o superiore a 8 MB")
    return payload


def prepare_thumbnail(payload: bytes) -> PreparedImage:
    Image.MAX_IMAGE_PIXELS = 30_000_000
    try:
        with Image.open(io.BytesIO(payload)) as source:
            source.seek(0)
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.load()
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ImageDiscoveryError(f"formato immagine non valido: {exc}") from exc
    if image.width < 320 or image.height < 180:
        raise ImageDiscoveryError(f"immagine troppo piccola: {image.width}x{image.height}")

    fitted = ImageOps.fit(image, THUMBNAIL_SIZE, method=Image.Resampling.LANCZOS)
    for quality in (78, 72, 66, 60):
        output = io.BytesIO()
        fitted.save(output, format="JPEG", quality=quality, optimize=True, progressive=False)
        content = output.getvalue()
        if len(content) <= MAX_PUBLISHED_IMAGE_BYTES:
            return PreparedImage(content, *THUMBNAIL_SIZE)
    raise ImageDiscoveryError("thumbnail non comprimibile entro 180 KB")


def image_key(edition_date: date, category: str, article_url: str) -> str:
    category_slug = {
        "Notizie e cronaca": "notizie",
        "Cultura": "cultura",
        "Sport": "sport",
        "Eventi": "eventi",
    }[category]
    digest = hashlib.sha256(article_url.encode("utf-8")).hexdigest()[:12]
    return f"{edition_date.isoformat()}/{category_slug}-{digest}.jpg"


def upload_thumbnail(prepared: PreparedImage, key: str, timeout: float = 20.0) -> str:
    endpoint = os.getenv(
        "SIRACUSA_IMAGE_UPLOAD_URL",
        "https://siracusadaily.com/.netlify/functions/newsletter-image",
    )
    token = os.getenv("SIRACUSA_IMAGE_UPLOAD_TOKEN", "")
    if not token:
        raise ImageDiscoveryError("SIRACUSA_IMAGE_UPLOAD_TOKEN non configurato")
    request = urllib.request.Request(
        f"{endpoint}?{urlencode({'key': key})}",
        data=prepared.content,
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": prepared.content_type,
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status not in {200, 201}:
                raise ImageDiscoveryError(f"upload Netlify HTTP {response.status}")
    except ImageDiscoveryError:
        raise
    except Exception as exc:
        raise ImageDiscoveryError(f"upload Netlify non riuscito: {exc}") from exc
    endpoint = os.getenv(
        "SIRACUSA_IMAGE_PUBLIC_BASE",
        "https://siracusadaily.com/.netlify/functions/newsletter-image",
    )
    separator = "&" if "?" in endpoint else "?"
    return f"{endpoint}{separator}{urlencode({'key': key})}"


def publish_newsletter_images(
    clusters: list[StoryCluster], edition_date: date,
) -> ImagePublishReport:
    report = ImagePublishReport()
    mode = os.getenv("SIRACUSA_IMAGE_MODE", "off").strip().lower()
    if mode in {"", "off", "false", "0", "no"}:
        return report
    if mode not in {"netlify", "remote"}:
        report.errors.append(f"modalità immagini non valida: {mode}")
        return report

    for category in TARGET_CATEGORIES:
        cluster = next((item for item in clusters if item.category == category), None)
        if cluster is None or cluster.representative is None:
            continue
        report.attempted += 1
        article = cluster.representative
        try:
            # Quando la fonte espone già l'immagine dell'evento (es. la locandina
            # via API), la usiamo direttamente invece dell'Open Graph della pagina,
            # che per le SPA restituisce il logo del sito.
            source_image = article.metadata.get("source_image_url", "").strip()
            if source_image.startswith("http"):
                image_source_url = source_image
            else:
                candidate = discover_article_image(article.url)
                if candidate is None:
                    report.skipped += 1
                    continue
                image_source_url = candidate.url
            prepared = prepare_thumbnail(download_image(image_source_url))
            public_url = (
                image_source_url
                if mode == "remote"
                else upload_thumbnail(prepared, image_key(edition_date, category, article.url))
            )
            article.metadata.update({
                "newsletter_image_url": public_url,
                "newsletter_image_source_url": image_source_url,
                "newsletter_image_alt": article.title[:180],
                "newsletter_image_width": str(prepared.width),
                "newsletter_image_height": str(prepared.height),
            })
            report.published += 1
        except ImageDiscoveryError as exc:
            report.skipped += 1
            report.errors.append(f"{category}: {exc}")
    return report
