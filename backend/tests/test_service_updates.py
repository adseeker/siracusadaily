from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from siracusa_daily.editorial import EditorialItem
from siracusa_daily.models import Article, Source, StoryCluster
from siracusa_daily.service_facebook import render_service_outputs, save_service_outputs
from siracusa_daily.service_updates import (
    SERVICE_ALERT_KEY,
    SERVICE_PRIORITY_KEY,
    SERVICE_TYPE_KEY,
    apply_service_metadata,
    diversify_service_clusters,
    service_alert_is_active,
    service_alert_is_due,
)


class ServiceUpdateTests(unittest.TestCase):
    def article(
        self, title: str, excerpt: str = "", *, day: int = 12, article_id: int = 1,
    ) -> Article:
        return Article(
            article_id=article_id, source_id="SRC-0019", endpoint_id="END-0050",
            title=title, url=f"https://example.com/{article_id}", excerpt=excerpt,
            published_at=datetime(2026, 8, day, 7, 0, tzinfo=timezone.utc),
        )

    def cluster(self, article: Article) -> StoryCluster:
        return StoryCluster(
            key=str(article.article_id), articles=[article], representative=article,
            score=5.0, category="Servizi e utilità",
        )

    def test_concrete_water_interruption_is_marked_critical(self) -> None:
        article = self.article(
            "Interruzione idrica a Siracusa",
            "Per un guasto alla rete idrica l'erogazione sarà sospesa in Ortigia.",
        )
        apply_service_metadata(article)
        self.assertEqual(article.metadata[SERVICE_ALERT_KEY], "true")
        self.assertEqual(article.metadata[SERVICE_TYPE_KEY], "acqua")
        self.assertEqual(article.metadata[SERVICE_PRIORITY_KEY], "critical")

    def test_administrative_notices_are_never_service_alerts(self) -> None:
        for title in (
            "Avviso ai creditori per i lavori stradali",
            "Manifestazione di interesse per il servizio idrico",
            "Il Consiglio comunale approva il bilancio",
        ):
            article = self.article(title, "Avviso del Comune di Siracusa")
            apply_service_metadata(article)
            self.assertNotIn(SERVICE_ALERT_KEY, article.metadata)

    def test_generic_regional_bulletin_is_not_treated_as_local_alert(self) -> None:
        article = self.article(
            "Avviso rischio idrogeologico per il 12 agosto 2026",
            "Allerta meteo regionale. La tabella delle zone include Siracusa.",
        )
        article.endpoint_id = "END-0051"
        apply_service_metadata(article)
        self.assertNotIn(SERVICE_ALERT_KEY, article.metadata)

    def test_expired_alert_is_excluded_and_critical_alert_can_repeat(self) -> None:
        article = self.article("Interruzione idrica", "Servizio idrico sospeso a Siracusa")
        apply_service_metadata(article)
        self.assertTrue(service_alert_is_active(article, date(2026, 8, 12)))
        self.assertTrue(service_alert_is_due(article, date(2026, 8, 12), {article.article_id}))
        self.assertFalse(service_alert_is_active(article, date(2026, 8, 16)))

    def test_notice_published_early_is_kept_when_it_starts_within_72_hours(self) -> None:
        article = self.article(
            "Strada chiusa il 14/08/2026",
            "Divieto di transito per lavori stradali in via Teste Mozze.",
            day=5,
        )
        apply_service_metadata(article)
        self.assertTrue(service_alert_is_active(article, date(2026, 8, 12)))

    def test_diversification_prefers_different_service_types(self) -> None:
        water = self.article("Interruzione idrica", "Servizio idrico sospeso", article_id=1)
        water2 = self.article("Guasto alla rete idrica", "Interruzione del servizio idrico", article_id=2)
        road = self.article("Strada chiusa", "Divieto di transito per lavori stradali", article_id=3)
        for article in (water, water2, road):
            apply_service_metadata(article)
        selected = diversify_service_clusters(
            [self.cluster(water), self.cluster(water2), self.cluster(road)],
            date(2026, 8, 12), limit=2,
        )
        self.assertEqual(
            {item.representative.metadata[SERVICE_TYPE_KEY] for item in selected},
            {"acqua", "viabilità"},
        )

    def test_facebook_output_uses_dedicated_files_and_keeps_urls_in_comment(self) -> None:
        article = self.article("Interruzione idrica", "Servizio idrico sospeso a Siracusa")
        apply_service_metadata(article)
        cluster = self.cluster(article)
        editorial = EditorialItem(
            cluster.key, "Acqua sospesa in Ortigia",
            "L'erogazione sarà interrotta nella zona indicata fino al termine dei lavori.",
            "Servizi e utilità",
        )
        sources = {
            "SRC-0019": Source(
                "SRC-0019", "Aretusacque", "Gestore", "high", "high", "Siracusa",
            ),
        }
        output = render_service_outputs([cluster], sources, [editorial])
        self.assertNotIn("http", output.post)
        self.assertIn(article.url, output.sources)
        with tempfile.TemporaryDirectory() as directory:
            post, source_list = save_service_outputs(Path(directory), output)
            self.assertEqual(post.name, "facebook_service_updates_post.txt")
            self.assertEqual(source_list.name, "facebook_service_updates_sources.txt")


if __name__ == "__main__":
    unittest.main()
