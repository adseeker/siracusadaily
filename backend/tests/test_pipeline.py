from __future__ import annotations

import os
import json
import sqlite3
import tempfile
import unittest
import urllib.error
from unittest.mock import patch
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from siracusa_daily.brevo import (
    BrevoError,
    _api_key,
    create_campaign_draft,
    find_campaign_for_edition,
    find_list,
)
from siracusa_daily.database import (
    active_opportunity_articles,
    connect,
    get_brevo_campaign_for_edition,
    previously_drafted_article_ids,
    record_brevo_draft,
    record_newsletter,
    upcoming_event_articles,
    upsert_article,
)
from siracusa_daily.categories import classify_article
from siracusa_daily.editorial import (
    EditorialError,
    EditorialItem,
    _numbers,
    _request_openai,
    _validated_subject,
    evidence_packet,
    generate_editorial,
    generate_openai,
    validate_items,
)
from siracusa_daily.geography import evaluate_locality
from siracusa_daily.events import event_is_in_window, sort_event_clusters
from siracusa_daily.event_quality import (
    ELIGIBLE,
    QUALITY_REASONS_KEY,
    QUALITY_STATUS_KEY,
    QUARANTINED,
    apply_event_quality,
    evaluate_event_quality,
    mark_multilingual_duplicates,
)
from siracusa_daily.opportunities import (
    diversify_opportunity_clusters,
    opportunity_is_active,
    sort_opportunity_clusters,
)
from siracusa_daily.opportunity_quality import (
    QUARANTINED as OPPORTUNITY_QUARANTINED,
    apply_opportunity_quality,
    opportunity_is_publishable,
)
from siracusa_daily.mailer import MailerError, send_html
from siracusa_daily.models import Article, Source, StoryCluster
from siracusa_daily.models import Endpoint
from siracusa_daily.retrieval import (
    _allevents_articles, _asp_articles, _comune_articles, _concorsi_articles,
    _deadline_from_text, _eventbrite_articles, _eventi_siracusa_articles,
    _gigroup_articles, _inpa_articles, _opportunity_detail_metadata,
    _randstad_articles, _synergie_articles, _virgilio_articles,
)
from siracusa_daily.selection import cluster_articles, select_stories
from siracusa_daily.text import canonical_url
from siracusa_daily.writer import render_html, render_markdown


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = Source("SRC-A", "A", "Testata locale", "high", "high", "Siracusa")

    def article(self, title: str, source_id: str = "SRC-A") -> Article:
        return Article(source_id, "END-A", title, f"https://example.com/{abs(hash(title))}", datetime.now(timezone.utc), "Siracusa: dettagli della notizia")

    def endpoint(self, source_id: str = "SRC-A", url: str = "https://example.com/") -> Endpoint:
        return Endpoint("END-A", source_id, "website", "Test", url, None, "web_html", ("eventi",))

    def test_canonical_url_removes_tracking(self) -> None:
        self.assertEqual(canonical_url("HTTPS://EXAMPLE.COM/a/?utm_source=x&b=2#top"), "https://example.com/a?b=2")

    def test_geographic_filter(self) -> None:
        article = self.article("Nuovo servizio idrico a Ortigia")
        score, reasons = evaluate_locality(article, self.source)
        self.assertGreaterEqual(score, 0.7)
        self.assertTrue(reasons)

    def test_source_boilerplate_is_not_a_geographic_signal(self) -> None:
        article = Article(
            "SRC-A", "END-A", "Notizia regionale da Palermo", "https://example.com/palermo",
            datetime.now(timezone.utc), "Dettagli regionali. L'articolo proviene da Siracusa News.",
        )
        score, _ = evaluate_locality(article, self.source)
        self.assertEqual(score, 0)

    def test_cross_source_deduplication(self) -> None:
        left = self.article("Siracusa, chiusa via Roma per lavori", "SRC-A")
        right = self.article("Chiusa via Roma a Siracusa per i lavori", "SRC-B")
        self.assertEqual(len(cluster_articles([left, right])), 1)

    def test_context_helps_cross_source_deduplication(self) -> None:
        left = self.article("Etna e caos voli, il piano su tre livelli di Cna", "SRC-A")
        left.excerpt = "Cna Siracusa propone protocolli automatici, uso di Comiso e trasporti sostitutivi per l'aeroporto di Catania."
        right = self.article("Etna e aeroporto di Catania, Cna Siracusa: serve un piano straordinario", "SRC-B")
        right.excerpt = "La proposta prevede trasporti sostitutivi, priorità a Comiso e chiusure limitate durante l'eruzione."
        self.assertEqual(len(cluster_articles([left, right])), 1)

    def test_event_deduplication_uses_date_location_and_distinctive_title(self) -> None:
        left = self.article("Artieri Mercato Creativo", "SRC-A")
        right = self.article("Artièri - Festival delle arti e dei mestieri", "SRC-B")
        for article in (left, right):
            article.published_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
            article.metadata = {
                "date_label": "Inizio",
                "event_start": datetime(2026, 8, 1, tzinfo=timezone.utc).isoformat(),
                "location": "Tonnara di Marzamemi, Pachino (SR)",
            }
        self.assertEqual(len(cluster_articles([left, right])), 1)

    def quality_event(
        self, title: str, excerpt: str, source_id: str = "SRC-0011",
        organizer: str = "Organizzatore locale",
    ) -> Article:
        article = Article(
            source_id, "END-EVENT", title,
            f"https://events.example.com/{abs(hash((title, source_id)))}",
            datetime(2026, 9, 7, 7, tzinfo=timezone.utc), excerpt,
            author=organizer,
        )
        article.local_score = 0.9
        article.metadata = {
            "date_label": "Inizio",
            "reference_date": article.published_at.isoformat(),
            "event_start": article.published_at.isoformat(),
            "location": "Siracusa",
            "organizer": organizer,
        }
        return article

    def test_event_quality_quarantines_non_latin_aggregator_card(self) -> None:
        article = self.quality_event(
            "The Now For Next в Гештальт-терапии",
            "зависимость, созависимость, аддикции — Siracusa",
        )
        decision = evaluate_event_quality(article)
        self.assertEqual(decision.status, QUARANTINED)
        self.assertIn("scrittura_non_latina_prevalente", decision.reasons)

    def test_event_quality_quarantines_latin_foreign_retreat(self) -> None:
        article = self.quality_event(
            "Szicíliai Női Elvonulás – Dolce Vita & Önszeretet",
            "Hat napos női utazás és önismereti program — Siracusa",
        )
        decision = evaluate_event_quality(article)
        self.assertEqual(decision.status, QUARANTINED)
        self.assertIn("pubblico_italiano_non_dimostrato", decision.reasons)

    def test_event_quality_accepts_substantive_italian_aggregator_card(self) -> None:
        article = self.quality_event(
            "Concerto al tramonto nel cuore di Ortigia",
            "Una serata di musica dal vivo con artisti locali, aperta a tutta la città. — Siracusa",
        )
        self.assertEqual(evaluate_event_quality(article).status, ELIGIBLE)

    def test_event_quality_accepts_foreign_title_with_italian_description(self) -> None:
        article = self.quality_event(
            "Candlelight Open Air: Tribute to Queen",
            "Il concerto propone i brani più amati dei Queen in una suggestiva serata a Siracusa.",
        )
        self.assertEqual(evaluate_event_quality(article).status, ELIGIBLE)

    def test_event_quality_rejects_long_english_aggregator_copy(self) -> None:
        article = self.quality_event(
            "International Wellness Festival",
            "Join us for a festival in Sicily with international guests, workshops and community activities.",
        )
        self.assertEqual(evaluate_event_quality(article).status, QUARANTINED)

    def test_event_quality_does_not_restrict_eventbrite(self) -> None:
        article = self.quality_event(
            "Around the Van: Vanlife Gathering", "Stories and community.", source_id="SRC-0007",
        )
        self.assertEqual(evaluate_event_quality(article).status, ELIGIBLE)

    def test_multilingual_same_day_cards_are_marked_as_suspicious_duplicates(self) -> None:
        latin = self.quality_event(
            "The Now For Next", "Incontro internazionale con ospiti e partecipanti.",
            organizer="Istituto di Gestalt HCC Italy",
        )
        cyrillic = self.quality_event(
            "The Now For Next в Гештальт-терапии", "зависимость и созависимость",
            organizer="Istituto di Gestalt HCC Italy",
        )
        for article in (latin, cyrillic):
            article.metadata["location"] = "Via Alaimo da Lentini 2, Siracusa"
            apply_event_quality(article)
        mark_multilingual_duplicates([latin, cyrillic])
        self.assertEqual(latin.metadata[QUALITY_STATUS_KEY], QUARANTINED)
        self.assertIn("duplicato_multilingua_sospetto", latin.metadata[QUALITY_REASONS_KEY])

    def test_upcoming_events_exclude_quarantined_aggregator_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            connection = connect(Path(tmp) / "test.db")
            bad = self.quality_event(
                "Szicíliai Női Elvonulás",
                "Hat napos női utazás és önismereti program — Siracusa",
            )
            good = self.quality_event(
                "Festival della musica a Siracusa",
                "Una serata con musica dal vivo e artisti locali aperta a tutta la città. — Siracusa",
            )
            for article in (bad, good):
                apply_event_quality(article)
                article.article_id = upsert_article(connection, article)
            rows = upcoming_event_articles(connection, date(2026, 9, 7))
            connection.close()
        self.assertEqual([row.title for row in rows], [good.title])

    def test_source_cap(self) -> None:
        sources = {"SRC-A": self.source, "SRC-B": Source("SRC-B", "B", "Testata locale", "high", "high", "Siracusa")}
        articles = [self.article(f"Siracusa notizia distinta numero {index}") for index in range(5)]
        other = self.article("Siracusa evento culturale speciale", "SRC-B")
        for article in articles + [other]:
            article.local_score = 0.9
        selected = select_stories(articles + [other], sources, {}, limit=4, max_per_source=2)
        counts = {}
        for cluster in selected:
            sid = cluster.representative.source_id
            counts[sid] = counts.get(sid, 0) + 1
        self.assertLessEqual(counts.get("SRC-A", 0), 2)

    def test_category_classification(self) -> None:
        event = self.article("Concerto domani a Ortigia")
        event.content_buckets = ("eventi",)
        economy = self.article("Nuove misure per le imprese locali")
        economy.content_buckets = ("economia",)
        self.assertEqual(classify_article(event), "Eventi")
        self.assertEqual(classify_article(economy), "Politica ed economia")

    def test_event_window_contains_today_and_the_next_six_days(self) -> None:
        edition = date(2026, 8, 16)  # Sunday

        def event(day: int) -> Article:
            article = self.article(f"Evento del {day} agosto")
            start = datetime(2026, 8, day, 18, 0, tzinfo=ZoneInfo("Europe/Rome")).astimezone(timezone.utc)
            article.metadata = {
                "date_label": "Inizio", "reference_date": start.isoformat(),
                "event_start": start.isoformat(),
            }
            return article

        self.assertTrue(event_is_in_window(event(16), edition))
        self.assertTrue(event_is_in_window(event(22), edition))
        self.assertFalse(event_is_in_window(event(15), edition))
        self.assertFalse(event_is_in_window(event(23), edition))

    def test_event_window_keeps_an_event_already_in_progress(self) -> None:
        article = self.article("Festival in corso")
        start = datetime(2026, 8, 15, 18, 0, tzinfo=ZoneInfo("Europe/Rome")).astimezone(timezone.utc)
        end = datetime(2026, 8, 16, 22, 0, tzinfo=ZoneInfo("Europe/Rome")).astimezone(timezone.utc)
        article.metadata = {
            "date_label": "Inizio", "reference_date": start.isoformat(),
            "event_start": start.isoformat(), "event_end": end.isoformat(),
        }
        self.assertTrue(event_is_in_window(article, date(2026, 8, 16)))

    def test_upcoming_events_ignore_the_article_publication_date(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect(Path(directory) / "test.db")
            event = self.article("Evento annunciato un mese prima")
            event.published_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
            start = datetime(2026, 8, 18, 19, 0, tzinfo=ZoneInfo("Europe/Rome")).astimezone(timezone.utc)
            event.metadata = {
                "date_label": "Inizio", "reference_date": start.isoformat(),
                "event_start": start.isoformat(),
            }
            event.local_score = 0.9
            upsert_article(connection, event)

            result = upcoming_event_articles(connection, date(2026, 8, 16))

            self.assertEqual([article.title for article in result], [event.title])
            connection.close()

    def test_event_clusters_are_sorted_by_start_time(self) -> None:
        late = self.article("Evento serale")
        early = self.article("Evento pomeridiano")
        for article, hour in ((late, 21), (early, 17)):
            start = datetime(2026, 8, 18, hour, tzinfo=ZoneInfo("Europe/Rome")).astimezone(timezone.utc)
            article.metadata = {
                "date_label": "Inizio", "reference_date": start.isoformat(),
                "event_start": start.isoformat(),
            }
        clusters = [
            StoryCluster("late", [late], representative=late, category="Eventi"),
            StoryCluster("early", [early], representative=early, category="Eventi"),
        ]
        self.assertEqual([cluster.key for cluster in sort_event_clusters(clusters)], ["early", "late"])

    def test_opportunity_remains_active_through_its_deadline(self) -> None:
        article = self.article("Concorso per funzionario tecnico")
        article.published_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
        deadline = datetime(2026, 8, 18, 13, tzinfo=ZoneInfo("Europe/Rome")).astimezone(timezone.utc)
        article.metadata = {
            "opportunity": "true", "opportunity_status": "open",
            "date_label": "Scadenza", "reference_date": deadline.isoformat(),
            "opportunity_deadline": deadline.isoformat(),
        }
        self.assertTrue(opportunity_is_active(article, date(2026, 8, 18)))
        self.assertFalse(opportunity_is_active(article, date(2026, 8, 19)))

    def test_closed_opportunity_is_removed_even_before_deadline(self) -> None:
        article = self.article("Bando revocato")
        deadline = datetime(2026, 8, 30, tzinfo=timezone.utc)
        article.metadata = {
            "opportunity": "true", "opportunity_status": "closed",
            "opportunity_deadline": deadline.isoformat(),
        }
        self.assertFalse(opportunity_is_active(article, date(2026, 8, 11)))

    def test_undated_opportunity_tolerates_temporary_source_failure(self) -> None:
        article = self.article("Azienda cerca un tecnico")
        checked = datetime(2026, 8, 10, 8, tzinfo=timezone.utc)
        article.metadata = {
            "opportunity": "true", "opportunity_status": "listed",
            "opportunity_verified_at": checked.isoformat(),
        }
        self.assertTrue(opportunity_is_active(article, date(2026, 8, 11)))
        self.assertFalse(opportunity_is_active(article, date(2026, 8, 14)))

    def test_active_opportunities_ignore_publication_lookback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect(Path(directory) / "test.db")
            article = self.article("Comune di Floridia, selezione aperta")
            article.published_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
            deadline = datetime(2026, 8, 22, tzinfo=timezone.utc)
            article.metadata = {
                "opportunity": "true", "opportunity_status": "open",
                "date_label": "Scadenza", "reference_date": deadline.isoformat(),
                "opportunity_deadline": deadline.isoformat(),
            }
            article.local_score = 0.9
            upsert_article(connection, article)

            result = active_opportunity_articles(connection, date(2026, 8, 11))

            self.assertEqual([item.title for item in result], [article.title])
            connection.close()

    def test_active_opportunities_exclude_quarantined_workplaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect(Path(directory) / "test.db")
            article = self.article("Offerta indicizzata a Siracusa con sede fuori provincia")
            article.metadata = {
                "opportunity": "true", "opportunity_status": "listed",
                "opportunity_verified_at": datetime.now(timezone.utc).isoformat(),
                "opportunity_quality_status": "quarantined",
            }
            article.local_score = 0.9
            upsert_article(connection, article)
            self.assertEqual(active_opportunity_articles(connection, date.today()), [])
            connection.close()

    def test_opportunities_are_sorted_by_urgent_deadline(self) -> None:
        urgent = self.article("Bando in scadenza")
        recent = self.article("Nuova offerta senza scadenza")
        urgent.metadata = {
            "opportunity": "true", "opportunity_status": "open",
            "opportunity_deadline": datetime(2026, 8, 13, tzinfo=timezone.utc).isoformat(),
        }
        recent.metadata = {"opportunity": "true", "opportunity_status": "listed"}
        clusters = [
            StoryCluster("recent", [recent], representative=recent),
            StoryCluster("urgent", [urgent], representative=urgent),
        ]
        ordered = sort_opportunity_clusters(clusters, date(2026, 8, 11))
        self.assertEqual([cluster.key for cluster in ordered], ["urgent", "recent"])

    def test_opportunity_selection_rotates_sources_before_repeating(self) -> None:
        clusters = []
        for key, source_id in (("a1", "SRC-A"), ("a2", "SRC-A"), ("b1", "SRC-B"), ("c1", "SRC-C")):
            article = self.article(key, source_id)
            clusters.append(StoryCluster(key, [article], representative=article))
        selected = diversify_opportunity_clusters(clusters, 4)
        self.assertEqual([cluster.key for cluster in selected], ["a1", "b1", "c1", "a2"])

    def test_opportunity_deduplication_ignores_publication_age(self) -> None:
        left = self.article("Comune di Floridia, selezione per funzionario tecnico", "SRC-A")
        right = self.article("Selezione per funzionario tecnico al Comune di Floridia", "SRC-B")
        left.published_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
        right.published_at = datetime(2026, 8, 22, tzinfo=timezone.utc)
        self.assertEqual(len(cluster_articles([left, right], max_age_hours=None)), 1)

    def test_database_upsert(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect(Path(directory) / "test.db")
            article = self.article("Siracusa prova database")
            first = upsert_article(connection, article)
            second = upsert_article(connection, article)
            self.assertEqual(first, second)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0], 1)
            connection.close()

    def test_brevo_api_key_is_required(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(BrevoError):
                _api_key()

    def test_brevo_list_is_matched_by_exact_name(self) -> None:
        response = {"lists": [
            {"id": 10, "name": "Iscritti SiracusaDaily vecchi"},
            {"id": 11, "name": "Iscritti SiracusaDaily"},
        ]}
        with patch("siracusa_daily.brevo._request", return_value=response):
            result = find_list("Iscritti SiracusaDaily", api_key="test")
        self.assertEqual(result.list_id, 11)

    def test_brevo_campaign_creation_only_creates_a_draft(self) -> None:
        responses = [
            {"lists": [{"id": 11, "name": "Iscritti SiracusaDaily"}]},
            {"id": 99},
        ]
        with patch("siracusa_daily.brevo._request", side_effect=responses) as request:
            result = create_campaign_draft(
                "<html><body>Newsletter valida</body></html>",
                datetime.now(timezone.utc).date(),
                "SiracusaDaily | Test",
                run_id=7,
                api_key="test",
            )
        self.assertEqual(result.campaign_id, 99)
        method, path = request.call_args_list[1].args
        payload = request.call_args_list[1].kwargs["payload"]
        self.assertEqual((method, path), ("POST", "/emailCampaigns"))
        self.assertEqual(payload["recipients"], {"listIds": [11]})
        self.assertNotIn("scheduledAt", payload)
        self.assertNotIn("tag", payload)
        self.assertNotIn("previewText", payload)

    def test_brevo_finds_existing_campaign_for_edition(self) -> None:
        response = {"campaigns": [
            {"id": 90, "name": "Altra campagna", "status": "draft"},
            {"id": 99, "name": "SiracusaDaily | 10/08/2026 | run 8", "status": "draft"},
        ]}
        with patch("siracusa_daily.brevo._request", return_value=response) as request:
            result = find_campaign_for_edition(datetime(2026, 8, 10).date(), api_key="test")
        self.assertIsNotNone(result)
        self.assertEqual(result.campaign_id, 99)
        self.assertEqual(result.status, "draft")
        self.assertEqual(request.call_args.kwargs["query"]["type"], "classic")

    def test_brevo_returns_none_when_edition_does_not_exist(self) -> None:
        with patch("siracusa_daily.brevo._request", return_value={"campaigns": []}):
            result = find_campaign_for_edition(datetime(2026, 8, 10).date(), api_key="test")
        self.assertIsNone(result)

    def test_brevo_draft_is_recorded_on_newsletter_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect(Path(directory) / "test.db")
            article = self.article("Siracusa prova campagna")
            article.article_id = upsert_article(connection, article)
            run_id = record_newsletter(
                connection, article.published_at.date().isoformat(), "newsletter.html",
                [(article, "cluster", 1.0)], writer_name="openai", model="gpt-5-mini",
            )
            record_brevo_draft(connection, run_id, 99, 11)
            row = connection.execute(
                "SELECT brevo_campaign_id, brevo_list_id, delivery_status FROM newsletter_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            self.assertEqual(tuple(row), (99, 11, "brevo_draft"))
            connection.close()

    def test_existing_brevo_campaign_is_found_by_edition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect(Path(directory) / "test.db")
            article = self.article("Siracusa prova campagna esistente")
            article.article_id = upsert_article(connection, article)
            edition_date = article.published_at.date().isoformat()
            run_id = record_newsletter(
                connection, edition_date, "newsletter.html",
                [(article, "cluster", 1.0)], writer_name="openai", model="gpt-5-mini",
            )
            record_brevo_draft(connection, run_id, 99, 11)

            row = get_brevo_campaign_for_edition(connection, edition_date)

            self.assertIsNotNone(row)
            self.assertEqual(row["run_id"], run_id)
            self.assertEqual(row["brevo_campaign_id"], 99)
            connection.close()

    def test_only_earlier_successful_drafts_enter_story_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect(Path(directory) / "test.db")
            old = self.article("Siracusa notizia già usata")
            old.article_id = upsert_article(connection, old)
            drafted_run = record_newsletter(
                connection, "2026-08-09", "old.html", [(old, "old", 1.0)],
                writer_name="openai", model="gpt-5-mini",
            )
            record_brevo_draft(connection, drafted_run, 99, 11)

            same_day = self.article("Siracusa notizia dello stesso giorno")
            same_day.article_id = upsert_article(connection, same_day)
            record_newsletter(
                connection, "2026-08-10", "retry.html", [(same_day, "retry", 1.0)],
                writer_name="openai", model="gpt-5-mini",
            )

            result = previously_drafted_article_ids(connection, "2026-08-10")
            self.assertEqual(result, {old.article_id})
            connection.close()

    def test_previous_story_removes_cross_source_duplicates(self) -> None:
        sources = {
            "SRC-A": self.source,
            "SRC-B": Source("SRC-B", "B", "Testata locale", "high", "high", "Siracusa"),
        }
        previous = self.article("Siracusa, chiusa via Roma per lavori", "SRC-A")
        duplicate = self.article("Chiusa via Roma a Siracusa per i lavori", "SRC-B")
        unrelated = self.article("Siracusa inaugura una nuova biblioteca", "SRC-B")
        previous.article_id = 1
        duplicate.article_id = 2
        unrelated.article_id = 3
        for article in (previous, duplicate, unrelated):
            article.local_score = 0.9
        selected = select_stories(
            [previous, duplicate, unrelated], sources, {}, limit=3,
            excluded_article_ids={previous.article_id},
        )
        self.assertEqual([cluster.representative.article_id for cluster in selected], [3])

    def test_editorial_evidence_keeps_source_provenance(self) -> None:
        article = self.article("Siracusa, apre un nuovo servizio")
        cluster = StoryCluster("story-1", [article], score=0.9, representative=article)
        packet = evidence_packet([cluster], {"SRC-A": self.source})
        self.assertEqual(packet[0]["candidate_id"], "story-1")
        self.assertEqual(packet[0]["source_url"], article.url)

    def test_numeric_grounding_reads_iso_dates_and_times(self) -> None:
        self.assertEqual(_numbers("2026-08-12T16:00:00+00:00"), {"2026", "08", "12", "16", "00"})

    def test_editorial_rejects_invented_numbers(self) -> None:
        article = self.article("Siracusa, apre un nuovo servizio")
        article.excerpt = "Il servizio sarà disponibile nel centro cittadino per i residenti."
        cluster = StoryCluster("story-1", [article], score=0.9, representative=article)
        raw = [{
            "candidate_id": "story-1", "publishable": True, "rejection_reason": "",
            "headline": "Apre il nuovo servizio",
            "summary": "Il nuovo servizio sarà disponibile nel centro cittadino e coinvolgerà 500 residenti, con modalità illustrate dalla fonte locale ai cittadini interessati.",
            "section": "Notizie e cronaca",
            "subject_topic": "apre un nuovo servizio",
        }]
        valid, invalid, _ = validate_items(raw, [cluster])
        self.assertFalse(valid)
        self.assertIn("story-1", invalid)

    def test_editorial_rejects_overlong_summary(self) -> None:
        article = self.article("Siracusa, apre un nuovo servizio")
        cluster = StoryCluster("story-1", [article], score=0.9, representative=article)
        raw = [{
            "candidate_id": "story-1", "publishable": True, "rejection_reason": "",
            "headline": "Apre un nuovo servizio a Siracusa",
            "summary": "Una descrizione molto lunga " * 10 + ".",
            "section": "Notizie e cronaca",
            "subject_topic": "apre un nuovo servizio",
        }]
        valid, invalid, _ = validate_items(raw, [cluster])
        self.assertFalse(valid)
        self.assertIn("massimo 240", " ".join(invalid["story-1"]))

    def test_editorial_accepts_summary_longer_than_old_tweet_limit(self) -> None:
        article = self.article("Siracusa, apre un nuovo servizio")
        cluster = StoryCluster("story-1", [article], score=0.9, representative=article)
        summary = (
            "Il servizio sarà disponibile nel centro cittadino e offrirà ai residenti "
            "un nuovo punto di accesso alle prestazioni comunali, con indicazioni operative "
            "pubblicate attraverso i canali istituzionali."
        )
        raw = [{
            "candidate_id": "story-1", "publishable": True, "rejection_reason": "",
            "headline": "Apre un nuovo servizio a Siracusa",
            "summary": summary,
            "section": "Notizie e cronaca",
            "subject_topic": "apre un nuovo servizio",
        }]
        valid, invalid, _ = validate_items(raw, [cluster])
        self.assertGreater(len(summary), 140)
        self.assertLessEqual(len(summary), 240)
        self.assertEqual(len(valid), 1)
        self.assertFalse(invalid)

    def test_editorial_rejects_em_dash(self) -> None:
        article = self.article("Siracusa, apre un nuovo servizio")
        cluster = StoryCluster("story-1", [article], score=0.9, representative=article)
        raw = [{
            "candidate_id": "story-1", "publishable": True, "rejection_reason": "",
            "headline": "Siracusa - nuovo servizio", "summary": "Il Comune presenta il servizio — sarà disponibile ai residenti.",
            "section": "Servizi e utilità",
            "subject_topic": "il nuovo servizio comunale",
        }]
        valid, invalid, _ = validate_items(raw, [cluster])
        self.assertFalse(valid)
        self.assertIn("em dash non consentito", invalid["story-1"])

    def test_editorial_can_reject_insufficient_evidence(self) -> None:
        article = self.article("Evento locale")
        cluster = StoryCluster("story-1", [article], score=0.9, representative=article)
        raw = [{
            "candidate_id": "story-1", "publishable": False,
            "rejection_reason": "Le evidenze non descrivono il contenuto dell'evento.",
            "headline": "", "summary": "",
        }]
        valid, invalid, rejected = validate_items(raw, [cluster])
        self.assertFalse(valid)
        self.assertFalse(invalid)
        self.assertEqual(rejected, {"story-1"})

    def test_openai_retries_only_invalid_item(self) -> None:
        article = self.article("Siracusa, nuova misura comunale")
        cluster = StoryCluster("story-1", [article], score=0.9, representative=article)
        invalid = [{
            "candidate_id": "story-1", "publishable": True, "rejection_reason": "",
            "headline": article.title, "summary": "Testo troppo lungo " * 20 + ".", "section": "Politica ed economia",
            "subject_topic": "la nuova misura comunale",
        }]
        repaired = [{
            "candidate_id": "story-1", "publishable": True, "rejection_reason": "",
            "headline": article.title,
            "summary": "Il Comune di Siracusa introduce una nuova misura per la città.",
            "section": "Politica ed economia",
            "subject_topic": "la nuova misura comunale",
        }]
        initial_response = {
            "subject": "La nuova misura comunale a Siracusa",
            "subject_candidate_ids": ["story-1"],
            "items": invalid,
        }
        with patch(
            "siracusa_daily.editorial._request_openai",
            side_effect=[initial_response, {"items": repaired}],
        ) as request:
            result = generate_openai([cluster], {"SRC-A": self.source}, api_key="test")
        self.assertEqual(request.call_count, 2)
        self.assertEqual(result.items[0].summary, repaired[0]["summary"])
        self.assertEqual(result.subject, "La nuova misura comunale a Siracusa")
        self.assertFalse(result.exclusions)

    def test_subject_rejects_a_sensitive_story_even_with_neutral_wording(self) -> None:
        article = self.article("Incidente mortale a Carlentini")
        article.excerpt = "Una persona ha perso la vita nello scontro avvenuto sulla strada provinciale."
        cluster = StoryCluster("story-1", [article], score=0.9, representative=article)
        item = EditorialItem(
            "story-1", "Indagini dopo lo scontro", "Sono in corso gli accertamenti.",
            "Notizie e cronaca", "Indagini in corso a Carlentini",
        )
        subject = _validated_subject(
            "Indagini in corso a Carlentini", ["story-1"], [item], [cluster],
        )
        self.assertEqual(subject, "")

    def test_writer_uses_a_safe_story_when_proposed_subject_is_sensitive(self) -> None:
        death = self.article("Incidente mortale a Carlentini")
        death.excerpt = "Una persona ha perso la vita nello scontro."
        bus = self.article("Nuova linea 105 collega Ortigia")
        bus.excerpt = "Il nuovo collegamento serve Ortigia e il centro di Siracusa."
        clusters = [
            StoryCluster("death", [death], score=1.0, representative=death),
            StoryCluster("bus", [bus], score=0.9, representative=bus),
        ]
        response = {
            "subject": "Incidente mortale a Carlentini; nuova linea 105 collega Ortigia",
            "subject_candidate_ids": ["death", "bus"],
            "items": [
                {
                    "candidate_id": "death", "publishable": True, "rejection_reason": "",
                    "headline": "Incidente mortale a Carlentini",
                    "summary": "Una persona ha perso la vita nello scontro avvenuto nel territorio di Carlentini.",
                    "section": "Notizie e cronaca", "subject_topic": "Incidente mortale a Carlentini",
                },
                {
                    "candidate_id": "bus", "publishable": True, "rejection_reason": "",
                    "headline": "La linea 105 collega Ortigia e il centro",
                    "summary": "Il nuovo collegamento serve Ortigia e il centro urbano di Siracusa.",
                    "section": "Servizi e utilità", "subject_topic": "La nuova linea 105 collega Ortigia",
                },
            ],
        }
        with patch("siracusa_daily.editorial._request_openai", return_value=response):
            result = generate_openai(clusters, {"SRC-A": self.source}, api_key="test")
        self.assertEqual(result.subject, "La nuova linea 105 collega Ortigia")
        self.assertEqual(len(result.items), 2)

    def test_writer_returns_no_subject_when_every_story_is_sensitive(self) -> None:
        article = self.article("Incidente mortale a Carlentini")
        article.excerpt = "Una persona ha perso la vita nello scontro."
        cluster = StoryCluster("death", [article], score=1.0, representative=article)
        response = {
            "subject": "Incidente mortale a Carlentini",
            "subject_candidate_ids": ["death"],
            "items": [{
                "candidate_id": "death", "publishable": True, "rejection_reason": "",
                "headline": "Incidente mortale a Carlentini",
                "summary": "Una persona ha perso la vita nello scontro avvenuto nel territorio di Carlentini.",
                "section": "Notizie e cronaca", "subject_topic": "Incidente mortale a Carlentini",
            }],
        }
        with patch("siracusa_daily.editorial._request_openai", return_value=response):
            result = generate_openai([cluster], {"SRC-A": self.source}, api_key="test")
        self.assertEqual(result.subject, "")

    def test_openai_excludes_item_that_fails_repair(self) -> None:
        article = self.article("Siracusa, nuova misura comunale")
        cluster = StoryCluster("story-1", [article], score=0.9, representative=article)
        invalid = [{
            "candidate_id": "story-1", "publishable": True, "rejection_reason": "",
            "headline": article.title, "summary": "Testo troppo lungo " * 20 + ".", "section": "Politica ed economia",
            "subject_topic": "la nuova misura comunale",
        }]
        initial_response = {
            "subject": "La nuova misura comunale a Siracusa",
            "subject_candidate_ids": ["story-1"],
            "items": invalid,
        }
        with patch(
            "siracusa_daily.editorial._request_openai",
            side_effect=[initial_response, {"items": invalid}, {"items": invalid}, {"items": invalid}],
        ):
            result = generate_openai([cluster], {"SRC-A": self.source}, api_key="test")
        self.assertFalse(result.items)
        self.assertIn("story-1", result.exclusions)

    def test_openai_can_recover_on_a_later_generic_correction(self) -> None:
        article = self.article("Siracusa, nuova misura comunale")
        cluster = StoryCluster("story-1", [article], score=0.9, representative=article)
        invalid = [{
            "candidate_id": "story-1", "publishable": True, "rejection_reason": "",
            "headline": article.title, "summary": "Testo troppo lungo " * 20 + ".",
            "section": "Politica ed economia", "subject_topic": "la nuova misura comunale",
        }]
        repaired = [{
            "candidate_id": "story-1", "publishable": True, "rejection_reason": "",
            "headline": article.title,
            "summary": "Il Comune introduce una nuova misura destinata alla città.",
            "section": "Politica ed economia", "subject_topic": "la nuova misura comunale",
        }]
        initial_response = {
            "subject": "La nuova misura comunale a Siracusa",
            "subject_candidate_ids": ["story-1"], "items": invalid,
        }
        with patch(
            "siracusa_daily.editorial._request_openai",
            side_effect=[initial_response, {"items": invalid}, {"items": repaired}],
        ) as request:
            result = generate_openai([cluster], {"SRC-A": self.source}, api_key="test")
        self.assertEqual(request.call_count, 3)
        self.assertEqual(len(result.items), 1)
        self.assertFalse(result.exclusions)

    def test_repair_api_failure_preserves_batch_completion(self) -> None:
        article = self.article("Siracusa, nuova misura comunale")
        cluster = StoryCluster("story-1", [article], score=0.9, representative=article)
        invalid = [{
            "candidate_id": "story-1", "publishable": True, "rejection_reason": "",
            "headline": article.title, "summary": "Testo troppo lungo " * 20 + ".", "section": "Politica ed economia",
            "subject_topic": "la nuova misura comunale",
        }]
        with patch(
            "siracusa_daily.editorial._request_openai",
            side_effect=[{
                "subject": "La nuova misura comunale a Siracusa",
                "subject_candidate_ids": ["story-1"],
                "items": invalid,
            }, EditorialError("timeout")],
        ):
            result = generate_openai([cluster], {"SRC-A": self.source}, api_key="test")
        self.assertFalse(result.items)
        self.assertIn("Correzione editoriale non disponibile", result.exclusions["story-1"])

    def test_openai_writer_requires_api_key(self) -> None:
        article = self.article("Siracusa, apre un nuovo servizio")
        cluster = StoryCluster("story-1", [article], score=0.9, representative=article)
        previous = __import__("os").environ.pop("OPENAI_API_KEY", None)
        try:
            with self.assertRaises(EditorialError):
                generate_editorial([cluster], {"SRC-A": self.source,}, mode="openai")
        finally:
            if previous is not None:
                __import__("os").environ["OPENAI_API_KEY"] = previous

    def test_openai_timeout_configuration_is_validated(self) -> None:
        article = self.article("Siracusa, apre un nuovo servizio")
        cluster = StoryCluster("story-1", [article], score=0.9, representative=article)
        with patch.dict("os.environ", {"SIRACUSA_OPENAI_TIMEOUT": "non-valido"}):
            with self.assertRaises(EditorialError):
                generate_openai([cluster], {"SRC-A": self.source}, api_key="test")

    def test_openai_retries_a_transient_network_error(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self):
                return b'{"output_text":"{\\"items\\":[]}"}'

        with (
            patch.dict(os.environ, {"SIRACUSA_OPENAI_ATTEMPTS": "3"}),
            patch(
                "siracusa_daily.editorial.urllib.request.urlopen",
                side_effect=[urllib.error.URLError("temporary"), Response()],
            ) as urlopen,
            patch("siracusa_daily.editorial.time.sleep") as sleep,
        ):
            result = _request_openai([], "gpt-5-mini", "test", "instructions", 30, include_subject=False)
        self.assertEqual(result, {"items": []})
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once()

    def test_writer_hides_publication_date_and_limits_summary(self) -> None:
        article = self.article("Siracusa, una notizia locale")
        article.excerpt = "Descrizione molto lunga " * 20
        article.metadata = {"date_label": "Pubblicato", "reference_date": article.published_at.isoformat()}
        cluster = StoryCluster("story-1", [article], score=0.9, representative=article)
        output = render_markdown(article.published_at.date(), [cluster], {"SRC-A": self.source})
        self.assertNotIn("Pubblicato", output)
        self.assertNotIn("Bozza generata automaticamente", output)
        description = output.split("\n")[8]
        self.assertLessEqual(len(description), 240)

    def test_html_email_has_no_publication_date_or_automatic_footer(self) -> None:
        article = self.article("Siracusa, una notizia locale")
        article.metadata = {"date_label": "Pubblicato", "reference_date": article.published_at.isoformat()}
        cluster = StoryCluster("story-1", [article], score=0.9, representative=article)
        output = render_html(article.published_at.date(), [cluster], {"SRC-A": self.source})
        self.assertIn('<html lang="it">', output)
        self.assertEqual(output.count("<h1"), 1)
        self.assertIn(f"Edizione del {article.published_at:%d/%m/%Y}", output)
        self.assertIn("background:#ffffff", output)
        self.assertIn("@media only screen and (max-width:480px)", output)
        self.assertIn("table-layout:fixed", output)
        self.assertIn("font:700 20px/1.3 Georgia", output)
        self.assertIn("text-decoration:underline", output)
        self.assertNotIn("#dbe3ea", output)
        self.assertNotIn("border-bottom:1px solid #e5e7eb", output)
        self.assertNotIn("Pubblicato", output)
        self.assertNotIn("Bozza generata automaticamente", output)
        self.assertNotIn("Le informazioni locali da conoscere oggi.", output)

    def test_event_section_uses_the_next_events_heading(self) -> None:
        article = self.article("Concerto a Siracusa")
        article.content_buckets = ("eventi",)
        start = datetime(2026, 8, 12, 21, tzinfo=ZoneInfo("Europe/Rome")).astimezone(timezone.utc)
        article.metadata = {
            "date_label": "Inizio", "reference_date": start.isoformat(),
            "event_start": start.isoformat(),
        }
        cluster = StoryCluster("event", [article], representative=article, category="Eventi")
        markdown = render_markdown(date(2026, 8, 11), [cluster], {"SRC-A": self.source})
        html = render_html(date(2026, 8, 11), [cluster], {"SRC-A": self.source})
        self.assertIn("## I prossimi eventi", markdown)
        self.assertIn("I prossimi eventi", html)
        self.assertNotIn(">Eventi</h2>", html)

    def test_brevo_html_has_an_italian_unsubscribe_link(self) -> None:
        article = self.article("Siracusa, una notizia locale")
        cluster = StoryCluster("story-1", [article], score=0.9, representative=article)
        output = render_html(
            article.published_at.date(), [cluster], {"SRC-A": self.source},
            unsubscribe_url="{{ unsubscribe }}",
        )
        self.assertIn('href="{{ unsubscribe }}"', output)
        self.assertIn("Annulla iscrizione", output)

    def test_internal_email_can_be_sent_without_public_compliance_fields(self) -> None:
        environment = {
            "SIRACUSA_SMTP_HOST": "smtp.example.com",
            "SIRACUSA_SMTP_PORT": "587",
            "SIRACUSA_SMTP_USERNAME": "login",
            "SIRACUSA_SMTP_PASSWORD": "secret",
            "SIRACUSA_EMAIL_FROM": "SiracusaDaily <newsletter@example.com>",
        }
        with patch.dict(os.environ, environment, clear=True), patch("siracusa_daily.mailer.smtplib.SMTP") as smtp:
            client = smtp.return_value.__enter__.return_value
            send_html(["editor@example.com"], "Prova", "<p>Test</p>", require_compliance=False)
            client.send_message.assert_called_once()

    def test_public_email_requires_unsubscribe_and_publisher_address(self) -> None:
        environment = {
            "SIRACUSA_SMTP_HOST": "smtp.example.com",
            "SIRACUSA_EMAIL_FROM": "SiracusaDaily <newsletter@example.com>",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(MailerError):
                send_html(["reader@example.com"], "Edizione", "<p>Test</p>")

    def test_direct_smtp_rejects_multiple_recipients(self) -> None:
        with self.assertRaises(MailerError):
            send_html(
                ["first@example.com", "second@example.com"],
                "Edizione",
                "<p>Test</p>",
                require_compliance=False,
            )

    def test_eventbrite_jsonld_parser(self) -> None:
        document = '''<script type="application/ld+json">{"@type":"ItemList","itemListElement":[{"item":{"@type":"Event","name":"Concerto a Noto","url":"https://eventbrite.com/e/1?utm_source=x","startDate":"2026-08-12","description":"Musica dal vivo","location":{"@type":"Place","name":"Teatro","address":{"addressLocality":"Noto"}}}}]}</script>'''
        rows = _eventbrite_articles(document, self.endpoint(url="https://eventbrite.com/test"), 10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].title, "Concerto a Noto")
        self.assertIn("Noto", rows[0].excerpt)
        self.assertEqual(rows[0].metadata["date_label"], "Inizio")

    def test_eventbrite_server_data_preserves_time(self) -> None:
        payload = '{"search_data":{"events":{"results":[{"name":"Evento serale","url":"https://eventbrite.com/e/2","start_date":"2026-08-12","start_time":"18:30","end_date":"2026-08-12","end_time":"21:00","summary":"A Siracusa","primary_venue":{"name":"Ortigia","address":{"city":"Siracusa"}}}]}}}'
        document = f'<script>window.__SERVER_DATA__ = {payload};</script>'
        rows = _eventbrite_articles(document, self.endpoint(url="https://eventbrite.com/test"), 10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].published_at.astimezone(ZoneInfo("Europe/Rome")).strftime("%H:%M"), "18:30")
        self.assertIn("event_start", rows[0].metadata)
        self.assertIn("event_end", rows[0].metadata)

    def test_allevents_embedded_dataset_parser(self) -> None:
        encoded_wall_time = int(datetime(2026, 8, 12, 18, 30, tzinfo=timezone.utc).timestamp())
        document = f'''<script>_this.events_data = [{{
          "event_id":"1", "eventname_raw":"Concerto &amp; teatro", "start_time":"{encoded_wall_time}",
          "end_time":"{encoded_wall_time}", "event_url":"https://allevents.in/siracusa/test/1?ref=city",
          "venue":{{"full_address":"Ortigia, Siracusa, Italy"}},
          "organizer":{{"name":"Associazione locale"}}, "short_description":"Spettacolo dal vivo"
        }}];</script>'''
        rows = _allevents_articles(document, self.endpoint("SRC-0011", "https://allevents.in/siracusa/all"), 10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].title, "Concerto & teatro")
        self.assertEqual(rows[0].published_at.astimezone(ZoneInfo("Europe/Rome")).strftime("%H:%M"), "18:30")
        self.assertEqual(rows[0].metadata["location"], "Ortigia, Siracusa, Italy")

    def test_eventi_siracusa_public_records_parser(self) -> None:
        payload = '''[{
          "id":"event-1", "published":true, "title":"Festival a Noto",
          "start_date":"2026-08-12", "start_time":"21:00",
          "end_date":"2026-08-13", "end_time":"", "category":"Festival",
          "short_description":"Musica e spettacoli nel centro storico.",
          "location_name":"Centro storico", "location_address":"Noto (SR)"
        }, {
          "id":"place-1", "published":true, "title":"Museo permanente", "start_date":""
        }]'''
        rows = _eventi_siracusa_articles(
            payload, self.endpoint("SRC-0012", "https://eventisiracusa.base44.app/"), 10,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].title, "Festival a Noto")
        self.assertEqual(rows[0].published_at.astimezone(ZoneInfo("Europe/Rome")).strftime("%H:%M"), "21:00")
        self.assertIn("event_end", rows[0].metadata)
        self.assertIn("event=event-1", rows[0].url)

    def test_virgilio_microdata_parser(self) -> None:
        document = '''<article class="cell fll-cell ev_grid" itemscope itemtype="http://schema.org/Event">
        <article class="eventi eventBox"><div class="eventContent">
        <h2 itemprop="name"><a itemprop="url" href="/italia/noto/eventi/festival_1" class="title">Festival a Noto</a></h2>
        <p itemprop="description"><a>Musica nel centro storico.</a></p>
        <time datetime="2026-08-12T00:00:00Z" itemprop="startDate">12 Ago</time></div>
        <a itemprop="location"><span itemprop="name">Noto (SR)</span></a></article><style>.eventBox{}</style></article>'''
        rows = _virgilio_articles(
            document, self.endpoint("SRC-0013", "https://www.virgilio.it/italia/siracusa/eventi"), 10,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].title, "Festival a Noto")
        self.assertEqual(rows[0].metadata["location"], "Noto (SR)")
        self.assertEqual(rows[0].url, "https://www.virgilio.it/italia/noto/eventi/festival_1")

    def test_comune_card_parser(self) -> None:
        document = '''<span class="data_num">12/08/26</span><h3><a class="card-title" href="/evento/test">Evento civico</a></h3><p class="body-description">Incontro a Siracusa</p>'''
        rows = _comune_articles(document, self.endpoint("SRC-0008", "https://www.comune.siracusa.it/eventi"), 10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].url, "https://www.comune.siracusa.it/evento/test")

    def test_concorsi_parser_skips_expired(self) -> None:
        active = '''<article class="node"><h2 class="contest-title"><a href="/bando"><span>Comune di Floridia, funzionario</span></a></h2><time datetime="2026-08-22T12:00:00Z">22/08/2026</time><div class="field--name-body field__item">Selezione pubblica</div></article>'''
        expired = active.replace('class="node"', 'class="node is-expired"').replace('/bando', '/vecchio')
        rows = _concorsi_articles(active + expired, self.endpoint("SRC-0009", "https://www.concorsipubblici.com/lista"), 10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].metadata["date_label"], "Scadenza")
        self.assertEqual(rows[0].metadata["opportunity"], "true")

    def test_opportunity_deadline_parser_reads_italian_date_and_time(self) -> None:
        parsed = _deadline_from_text(
            "Le domande devono essere presentate entro il 18 agosto 2026 ore 13.00."
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.astimezone(ZoneInfo("Europe/Rome")).strftime("%d/%m/%Y %H:%M"), "18/08/2026 13:00")

    def test_opportunity_detail_parser_prefers_deadline_over_open_badge(self) -> None:
        document = '''<div data-element="service-status"><span class="chip-label">Aperto</span></div>
        <small>Data di scadenza della candidatura:</small><p>19/07/2026 23:59</p>'''
        metadata = _opportunity_detail_metadata(document)
        self.assertEqual(metadata["opportunity_status"], "open")
        self.assertIn("opportunity_deadline", metadata)

    def test_asp_card_parser(self) -> None:
        document = '''<h3 class="card-title big-heading"><a href="/concorso/test">Avviso ASP Siracusa</a></h3><span class="font-monospace text-500">23 Luglio 2026</span>'''
        rows = _asp_articles(document, self.endpoint("SRC-0010", "https://www.asp.sr.it/concorsi"), 10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].published_at.month, 7)

    def test_randstad_parser_quarantines_an_outside_workplace(self) -> None:
        payload = {"initialValues": {"results": [{
            "jobTitle": "Operaio generico",
            "description": {"shortDescription": "Sede di partenza: Siracusa. Sede di lavoro: Taranto (TA)."},
            "displayId": "CX1", "postingDetail": {"postingTime": "2026-08-11T08:00:00Z"},
            "workLocationAddress": {"locality": "Siracusa", "administrativeArea": "Sicilia"},
            "webDetails": {"postedUrl": [{"href": "https://www.randstad.it/offerte-lavoro/operaio_1/"}]},
        }]}}
        frame = json.dumps([1, "6:" + json.dumps(payload, separators=(",", ":"))])
        document = f"<script>self.__next_f.push({frame})</script>"
        endpoint = Endpoint("END-0045", "SRC-0014", "website", "Randstad", "https://www.randstad.it/test", None, "web_html", ("lavoro",))
        rows = _randstad_articles(document, endpoint, 10)
        self.assertEqual(len(rows), 1)
        rows[0].metadata["opportunity"] = "true"
        self.assertEqual(apply_opportunity_quality(rows[0]), OPPORTUNITY_QUARANTINED)
        self.assertFalse(opportunity_is_publishable(rows[0]))

    def test_gigroup_parser_preserves_location_and_posting_id(self) -> None:
        document = '''<article class="ggp-job-item">
        <span class="ggpdayspassed-text">Annuncio pubblicato 4 giorni fa</span>
        <a itemprop="url" href="/offerte-lavoro-dettaglio/test/1348695/" class="ggp-job-title-url"
          data-job='{&quot;offerNumber&quot;:&quot;1348695&quot;}'><h2>Manutentore elettrico</h2></a>
        <div class="job-tag">Full time</div><span class="visually-hidden">Luogo di lavoro:</span><span>Siracusa, SR, Sicilia</span>
        </article><article class="ggp-job-item"><a href="/ragusa" class="ggp-job-title-url"><h2>Ruolo fuori provincia</h2></a>
        <span class="visually-hidden">Luogo di lavoro:</span><span>Ragusa, RG, Sicilia</span></article>'''
        rows = _gigroup_articles(document, Endpoint(
            "END-0046", "SRC-0015", "website", "Gi Group", "https://www.gigroup.it/offerte-lavoro/", None, "web_html", ("lavoro",),
        ), 10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].metadata["source_posting_id"], "1348695")
        self.assertIn("Siracusa", rows[0].metadata["work_location"])

    @patch("siracusa_daily.retrieval._post_json")
    def test_synergie_parser_excludes_nearby_provinces(self, post_json) -> None:
        post_json.return_value = {"hits": [
            {"title": "Store manager", "city": "Siracusa", "published_from": 1785715200000,
             "source_vacancy_url": "https://synergie.intervieweb.it/jobs/store-manager/it/", "id_inrecruiting": "349266"},
            {"title": "Addetto vendita", "city": "Catania", "published_from": 1785715200000,
             "source_vacancy_url": "https://synergie.intervieweb.it/jobs/addetto/it/", "id_inrecruiting": "349267"},
        ]}
        document = '{"PUBLIC_ALGOLIA_APP_ID":"APP","PUBLIC_ALGOLIA_API_KEY":"KEY","PUBLIC_ALGOLIA_APPLICATIONS_INDEX_NAME":"applications"}'
        endpoint = Endpoint("END-0047", "SRC-0016", "website", "Synergie", "https://www.synergie-italia.it/test", None, "web_html", ("lavoro",))
        rows = _synergie_articles(document, endpoint, 10, 5)
        self.assertEqual([row.title for row in rows], ["Store manager"])

    @patch("siracusa_daily.retrieval._post_json")
    def test_inpa_parser_excludes_generic_nationwide_results(self, post_json) -> None:
        local = {
            "id": "local", "codice": "SR-1", "titolo": "Funzionario al Comune di Francofonte",
            "sedi": ["Sicilia", "Francofonte"], "calculatedStatus": "OPEN",
            "dataPubblicazione": "2026-08-07T09:10:00Z", "dataScadenza": "2026-09-18T21:59:00Z",
            "entiRiferimento": ["Comune di Francofonte"], "descrizioneBreve": "Selezione pubblica",
        }
        nationwide = {
            "id": "national", "titolo": "Mobilità nazionale MEF",
            "sedi": ["Siracusa"] + [f"Provincia {number}" for number in range(30)],
            "dataPubblicazione": "2026-08-07T09:10:00Z", "entiRiferimento": ["MEF"],
        }
        post_json.return_value = {"content": [local, nationwide]}
        endpoint = Endpoint("END-0049", "SRC-0018", "website", "inPA", "https://www.inpa.gov.it/bandi-e-avvisi/", None, "web_html", ("concorsi",))
        rows = _inpa_articles(endpoint, 10, 5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].metadata["source_posting_id"], "SR-1")
        self.assertIn("opportunity_deadline", rows[0].metadata)


if __name__ == "__main__":
    unittest.main()
