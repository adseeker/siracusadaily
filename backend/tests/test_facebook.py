from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from siracusa_daily.editorial import EditorialItem
from siracusa_daily.facebook import (
    FacebookOutputError,
    render_facebook_outputs,
    save_facebook_outputs,
)
from siracusa_daily.models import Article, Source, StoryCluster


class FacebookOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sources = {
            "SRC-A": Source("SRC-A", "Siracusa News", "Testata", "high", "high", "Siracusa"),
            "SRC-B": Source("SRC-B", "Comune di Siracusa", "Ente", "high", "high", "Siracusa"),
        }

    def cluster(self, key: str, category: str, score: float, source_id: str = "SRC-A") -> StoryCluster:
        article = Article(
            source_id=source_id,
            endpoint_id=f"END-{key}",
            title=f"Titolo sorgente {key}",
            url=f"https://example.com/{key}",
            excerpt=f"Estratto sorgente {key}",
            published_at=datetime(2026, 8, 12, 6, 0, tzinfo=timezone.utc),
        )
        return StoryCluster(
            key=key,
            articles=[article],
            score=score,
            representative=article,
            category=category,
        )

    def editorial(self, cluster: StoryCluster) -> EditorialItem:
        return EditorialItem(
            candidate_id=cluster.key,
            headline=f"Titolo Facebook {cluster.key}",
            summary=f"Sintesi completa e conclusiva per il contenuto {cluster.key}.",
            section=cluster.category,
        )

    def test_recap_is_balanced_limited_and_keeps_urls_out_of_the_post(self) -> None:
        clusters = [
            self.cluster("n1", "Notizie e cronaca", 10),
            self.cluster("n2", "Notizie e cronaca", 9),
            self.cluster("n3", "Notizie e cronaca", 8),
            self.cluster("n4", "Notizie e cronaca", 7),
            self.cluster("p1", "Politica ed economia", 6),
            self.cluster("c1", "Cultura", 5),
            self.cluster("s1", "Sport", 4),
            self.cluster("u1", "Servizi e utilità", 3, "SRC-B"),
            self.cluster("e1", "Eventi", 100),
            self.cluster("l1", "Lavoro e opportunità", 100),
        ]
        outputs = render_facebook_outputs(
            clusters,
            self.sources,
            [self.editorial(cluster) for cluster in clusters],
        )

        self.assertEqual(outputs.item_count, 4)
        self.assertNotIn("http", outputs.post)
        self.assertEqual(outputs.post.count("Fonte:"), 4)
        self.assertIn("Titolo Facebook n1", outputs.post)
        self.assertIn("Titolo Facebook p1", outputs.post)
        self.assertIn("Titolo Facebook c1", outputs.post)
        self.assertIn("Titolo Facebook s1", outputs.post)
        self.assertNotIn("Titolo Facebook n2", outputs.post)
        self.assertNotIn("Titolo Facebook u1", outputs.post)
        self.assertNotIn("Titolo Facebook e1", outputs.post)
        self.assertNotIn("Titolo Facebook l1", outputs.post)
        self.assertEqual(outputs.sources.count("https://example.com/"), 4)
        self.assertIn("utm_source=facebook", outputs.sources)

    def test_recap_uses_validated_editorial_copy_instead_of_source_copy(self) -> None:
        cluster = self.cluster("n1", "Notizie e cronaca", 10)
        outputs = render_facebook_outputs(
            [cluster],
            self.sources,
            [self.editorial(cluster)],
        )

        self.assertIn("Titolo Facebook n1", outputs.post)
        self.assertIn("Sintesi completa e conclusiva", outputs.post)
        self.assertNotIn("Titolo sorgente n1", outputs.post)

    def test_recap_requires_publishable_news_content_and_valid_limit(self) -> None:
        unknown = self.cluster("x1", "Categoria inesistente", 10)
        with self.assertRaises(FacebookOutputError):
            render_facebook_outputs([unknown], self.sources, [self.editorial(unknown)])
        news = self.cluster("n1", "Notizie e cronaca", 10)
        with self.assertRaises(FacebookOutputError):
            render_facebook_outputs(
                [news], self.sources, [self.editorial(news)], limit=5,
            )

    def test_missing_source_is_reported_as_a_facebook_output_error(self) -> None:
        cluster = self.cluster("n1", "Notizie e cronaca", 10, "SRC-MISSING")
        with self.assertRaisesRegex(FacebookOutputError, "fonte SRC-MISSING"):
            render_facebook_outputs(
                [cluster], self.sources, [self.editorial(cluster)],
            )

    def test_outputs_are_saved_with_the_expected_names(self) -> None:
        cluster = self.cluster("n1", "Notizie e cronaca", 10)
        outputs = render_facebook_outputs(
            [cluster], self.sources, [self.editorial(cluster)],
        )
        with tempfile.TemporaryDirectory() as directory:
            post_path, sources_path = save_facebook_outputs(Path(directory), outputs)
            self.assertEqual(post_path.name, "facebook_post.txt")
            self.assertEqual(sources_path.name, "facebook_sources.txt")
            self.assertEqual(post_path.read_text(encoding="utf-8"), outputs.post)
            self.assertEqual(sources_path.read_text(encoding="utf-8"), outputs.sources)


if __name__ == "__main__":
    unittest.main()
