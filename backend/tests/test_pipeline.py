from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
import urllib.error
from unittest.mock import patch
from datetime import datetime, timezone
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
    connect,
    get_brevo_campaign_for_edition,
    previously_drafted_article_ids,
    record_brevo_draft,
    record_newsletter,
    upsert_article,
)
from siracusa_daily.categories import classify_article
from siracusa_daily.editorial import (
    EditorialError,
    _numbers,
    _request_openai,
    evidence_packet,
    generate_editorial,
    generate_openai,
    validate_items,
)
from siracusa_daily.geography import evaluate_locality
from siracusa_daily.mailer import MailerError, send_html
from siracusa_daily.models import Article, Source, StoryCluster
from siracusa_daily.models import Endpoint
from siracusa_daily.retrieval import _asp_articles, _comune_articles, _concorsi_articles, _eventbrite_articles
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
        self.assertIn("massimo 140", " ".join(invalid["story-1"]))

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
        self.assertLessEqual(len(description), 140)

    def test_html_email_has_no_publication_date_or_automatic_footer(self) -> None:
        article = self.article("Siracusa, una notizia locale")
        article.metadata = {"date_label": "Pubblicato", "reference_date": article.published_at.isoformat()}
        cluster = StoryCluster("story-1", [article], score=0.9, representative=article)
        output = render_html(article.published_at.date(), [cluster], {"SRC-A": self.source})
        self.assertIn('<html lang="it">', output)
        self.assertEqual(output.count("<h1"), 1)
        self.assertIn(f"Edizione del {article.published_at:%d/%m/%Y}", output)
        self.assertIn("background:#ffffff", output)
        self.assertNotIn("Pubblicato", output)
        self.assertNotIn("Bozza generata automaticamente", output)
        self.assertNotIn("Le informazioni locali da conoscere oggi.", output)

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
        payload = '{"search_data":{"events":{"results":[{"name":"Evento serale","url":"https://eventbrite.com/e/2","start_date":"2026-08-12","start_time":"18:30","summary":"A Siracusa","primary_venue":{"name":"Ortigia","address":{"city":"Siracusa"}}}]}}}'
        document = f'<script>window.__SERVER_DATA__ = {payload};</script>'
        rows = _eventbrite_articles(document, self.endpoint(url="https://eventbrite.com/test"), 10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].published_at.astimezone(ZoneInfo("Europe/Rome")).strftime("%H:%M"), "18:30")

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

    def test_asp_card_parser(self) -> None:
        document = '''<h3 class="card-title big-heading"><a href="/concorso/test">Avviso ASP Siracusa</a></h3><span class="font-monospace text-500">23 Luglio 2026</span>'''
        rows = _asp_articles(document, self.endpoint("SRC-0010", "https://www.asp.sr.it/concorsi"), 10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].published_at.month, 7)


if __name__ == "__main__":
    unittest.main()
