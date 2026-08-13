from __future__ import annotations

import json
import unittest
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from siracusa_daily.events import event_public_id
from siracusa_daily.events_feed import build_feed
from siracusa_daily.models import Article, Endpoint, Source, StoryCluster
from siracusa_daily.retrieval import _eventi_siracusa_articles
from siracusa_daily.writer import render_html

ROME = ZoneInfo("Europe/Rome")


def event_article(title, url, start, *, end=None, source_id="SRC-A", image="", booking="", location=""):
    meta = {"date_label": "Data", "event_start": start.isoformat(), "reference_date": start.isoformat()}
    if end:
        meta["event_end"] = end.isoformat()
    if image:
        meta["source_image_url"] = image
    if booking:
        meta["booking_url"] = booking
    if location:
        meta["location"] = location
    return Article(
        source_id=source_id, endpoint_id="END-A", title=title, url=url,
        published_at=start, excerpt="Descrizione evento", metadata=meta,
    )


SOURCES = {
    "SRC-A": Source("SRC-A", "Eventi Siracusa", "Calendario", "medium", "high", "Siracusa"),
    "SRC-B": Source("SRC-B", "Eventbrite", "Piattaforma", "medium", "high", "Siracusa"),
}


class BuildFeedTests(unittest.TestCase):
    def test_marks_past_events_and_orders_upcoming_first(self) -> None:
        ref = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)
        past = event_article("Sagra andata", "https://x/1", datetime(2026, 8, 1, 20, tzinfo=ROME))
        soon = event_article("Concerto imminente", "https://x/2", datetime(2026, 8, 25, 21, tzinfo=ROME))
        feed = build_feed([past, soon], SOURCES, reference=ref)
        self.assertEqual([e["title"] for e in feed], ["Concerto imminente", "Sagra andata"])
        self.assertFalse(feed[0]["past"])
        self.assertTrue(feed[1]["past"])

    def test_deduplicates_same_event_from_different_sources(self) -> None:
        start = datetime(2026, 9, 1, 21, tzinfo=ROME)
        poor = event_article("Festival del Mare", "https://base44.app/?event=1", start, source_id="SRC-A")
        rich = event_article("Festival del Mare", "https://eventbrite.com/e/1", start, source_id="SRC-B",
                             image="https://img/x.jpg", booking="https://eventbrite.com/e/1")
        feed = build_feed([poor, rich], SOURCES)
        self.assertEqual(len(feed), 1)
        self.assertEqual(feed[0]["image"], "https://img/x.jpg")

    def test_booking_falls_back_to_source_url_except_base44(self) -> None:
        start = datetime(2026, 9, 2, 21, tzinfo=ROME)
        eb = event_article("Mostra", "https://eventbrite.com/e/9", start, source_id="SRC-B")
        b44 = event_article("Raduno", "https://eventisiracusa.base44.app/?event=9", start, source_id="SRC-A")
        feed = build_feed([eb, b44], SOURCES)
        by_title = {e["title"]: e for e in feed}
        self.assertEqual(by_title["Mostra"]["booking_url"], "https://eventbrite.com/e/9")
        self.assertEqual(by_title["Raduno"]["booking_url"], "")


class Base44CaptureTests(unittest.TestCase):
    ENDPOINT = Endpoint("END-0012", "SRC-0012", "web_html", "Eventi Siracusa",
                        "https://eventisiracusa.base44.app/", None, "web_html", ("eventi",))

    def test_captures_image_and_booking_link(self) -> None:
        payload = json.dumps([{
            "id": "abc123", "title": "Mario Biondi", "start_date": "2026-08-26", "start_time": "21:00",
            "location_name": "Piazza Municipio", "short_description": "Concerto",
            "image_url": "https://base44.app/files/poster.jpg",
            "ticket_link": "https://ticketone.it/mario-biondi",
            "contact_website": "https://puntoeacapo.uno",
        }])
        articles = _eventi_siracusa_articles(payload, self.ENDPOINT, 10)
        self.assertEqual(len(articles), 1)
        meta = articles[0].metadata
        self.assertEqual(meta["source_image_url"], "https://base44.app/files/poster.jpg")
        self.assertEqual(meta["booking_url"], "https://ticketone.it/mario-biondi")


class NewsletterEventLinkTests(unittest.TestCase):
    def test_event_card_links_to_hosted_events_page(self) -> None:
        start = datetime(2026, 8, 25, 21, tzinfo=ROME).astimezone(timezone.utc)
        url = "https://eventisiracusa.base44.app/?event=xyz"
        article = event_article("Concerto a Ortigia", url, start)
        cluster = StoryCluster("evt", [article], representative=article, category="Eventi")
        html = render_html(date(2026, 8, 20), [cluster], {"SRC-A": SOURCES["SRC-A"]})
        self.assertIn(f"/eventi?event={event_public_id(url)}", html)
        self.assertIn("Vedi l", html)  # etichetta "Vedi l'evento" (apostrofo escapato in HTML)
        self.assertNotIn("Approfondisci su Eventi Siracusa", html)


if __name__ == "__main__":
    unittest.main()
