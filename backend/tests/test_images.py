from __future__ import annotations

import io
import unittest
from datetime import date
from datetime import datetime, timezone
from unittest.mock import patch

from PIL import Image

from siracusa_daily.images import (
    discover_article_image,
    extract_image_candidates,
    extract_image_url,
    ImageCandidate,
    image_key,
    image_url_is_reachable,
    PreparedImage,
    prepare_thumbnail,
    publish_newsletter_images,
    upload_thumbnail,
)
from siracusa_daily.models import Article, StoryCluster


class _Response:
    def __init__(self, payload: bytes, content_type: str) -> None:
        self._stream = io.BytesIO(payload)
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)


def _solid_image() -> bytes:
    source = io.BytesIO()
    Image.new("RGB", (1200, 630), "#2455d6").save(source, format="JPEG")
    return source.getvalue()


class ImageDiscoveryTests(unittest.TestCase):
    def test_prefers_open_graph_and_resolves_relative_url(self) -> None:
        document = '''
        <meta name="twitter:image" content="https://example.com/twitter.jpg">
        <meta property="og:image" content="/media/story.jpg">
        <meta property="og:image:width" content="1200">
        <meta property="og:image:height" content="630">
        '''
        candidates = extract_image_candidates(document, "https://example.com/news/story")
        self.assertEqual(candidates[0].url, "https://example.com/media/story.jpg")
        self.assertEqual(candidates[0].width, 1200)
        self.assertEqual(candidates[0].height, 630)

    def test_rejects_logos_and_uses_json_ld_fallback(self) -> None:
        document = '''
        <meta property="og:image" content="https://example.com/site-logo.png">
        <script type="application/ld+json">
          {"@type":"NewsArticle","image":{"@type":"ImageObject","url":"https://cdn.example.com/article.jpg"}}
        </script>
        '''
        self.assertEqual(
            extract_image_url(document, "https://example.com/news"),
            "https://cdn.example.com/article.jpg",
        )

    def test_returns_none_without_a_valid_candidate(self) -> None:
        document = '<meta property="og:image" content="data:image/png;base64,abc">'
        self.assertIsNone(extract_image_url(document, "https://example.com/news"))

    def test_discovers_image_from_article_page(self) -> None:
        response = _Response(
            b'<meta property="og:image" content="https://cdn.example.com/story.jpg">',
            "text/html; charset=utf-8",
        )
        with patch("siracusa_daily.images.urllib.request.urlopen", return_value=response):
            candidate = discover_article_image("https://example.com/story")
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.url, "https://cdn.example.com/story.jpg")

    def test_image_probe_accepts_jpeg_and_rejects_html(self) -> None:
        jpeg = _Response(b"\xff\xd8\xff" + b"x" * 40, "image/jpeg")
        html = _Response(b"<html>", "text/html")
        with patch("siracusa_daily.images.urllib.request.urlopen", return_value=jpeg):
            self.assertTrue(image_url_is_reachable("https://example.com/story.jpg"))
        with patch("siracusa_daily.images.urllib.request.urlopen", return_value=html):
            self.assertFalse(image_url_is_reachable("https://example.com/story.jpg"))

    def test_prepares_a_small_fixed_size_jpeg(self) -> None:
        source = io.BytesIO()
        Image.new("RGB", (1200, 630), "#2455d6").save(source, format="PNG")
        prepared = prepare_thumbnail(source.getvalue())
        self.assertEqual((prepared.width, prepared.height), (480, 300))
        self.assertLessEqual(len(prepared.content), 180_000)
        self.assertTrue(prepared.content.startswith(b"\xff\xd8\xff"))

    def test_rejects_a_tiny_source_image(self) -> None:
        source = io.BytesIO()
        Image.new("RGB", (100, 100), "white").save(source, format="PNG")
        with self.assertRaises(Exception):
            prepare_thumbnail(source.getvalue())

    def test_image_key_is_stable_and_scoped_by_edition(self) -> None:
        key = image_key(
            date(2026, 8, 11),
            "Notizie e cronaca",
            "https://example.com/story",
        )
        self.assertRegex(key, r"^2026-08-11/notizie-[a-f0-9]{12}\.jpg$")

    def test_upload_returns_the_public_netlify_url(self) -> None:
        prepared = prepare_thumbnail(_solid_image())
        response = _Response(b'{"path":"/media/newsletter/key"}', "application/json")
        response.status = 201
        environment = {
            "SIRACUSA_IMAGE_UPLOAD_TOKEN": "secret",
            "SIRACUSA_IMAGE_UPLOAD_URL": "https://siracusadaily.com/upload",
            "SIRACUSA_IMAGE_PUBLIC_BASE": "https://siracusadaily.com/.netlify/functions/newsletter-image",
        }
        with (
            patch.dict("os.environ", environment, clear=True),
            patch("siracusa_daily.images.urllib.request.urlopen", return_value=response),
        ):
            result = upload_thumbnail(prepared, "2026-08-11/notizie-123456789abc.jpg")
        self.assertEqual(
            result,
            "https://siracusadaily.com/.netlify/functions/newsletter-image?key=2026-08-11%2Fnotizie-123456789abc.jpg",
        )

    def test_publishes_only_the_first_item_of_each_target_category(self) -> None:
        def cluster(key: str, category: str) -> StoryCluster:
            article = Article(
                "SRC-A", "END-A", key, f"https://example.com/{key}",
                datetime(2026, 8, 11, tzinfo=timezone.utc),
            )
            return StoryCluster(key, [article], representative=article, category=category)

        first_news = cluster("news-one", "Notizie e cronaca")
        second_news = cluster("news-two", "Notizie e cronaca")
        culture = cluster("culture", "Cultura")
        service = cluster("service", "Servizi e utilità")
        prepared = PreparedImage(b"\xff\xd8\xffdata", 480, 300)
        with (
            patch.dict("os.environ", {"SIRACUSA_IMAGE_MODE": "netlify"}, clear=True),
            patch(
                "siracusa_daily.images.discover_article_image",
                return_value=ImageCandidate("https://cdn.example.com/image.jpg", "og:image"),
            ) as discover,
            patch("siracusa_daily.images.download_image", return_value=b"source"),
            patch("siracusa_daily.images.prepare_thumbnail", return_value=prepared),
            patch(
                "siracusa_daily.images.upload_thumbnail",
                side_effect=lambda _prepared, key: f"https://siracusadaily.com/media/newsletter/{key}",
            ),
        ):
            report = publish_newsletter_images(
                [first_news, second_news, culture, service], date(2026, 8, 11),
            )

        self.assertEqual(report.published, 2)
        self.assertEqual(discover.call_count, 2)
        self.assertIn("newsletter_image_url", first_news.representative.metadata)
        self.assertNotIn("newsletter_image_url", second_news.representative.metadata)
        self.assertIn("newsletter_image_url", culture.representative.metadata)
        self.assertNotIn("newsletter_image_url", service.representative.metadata)


if __name__ == "__main__":
    unittest.main()
