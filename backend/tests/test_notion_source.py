from __future__ import annotations

import json
import unittest
from datetime import date
from unittest.mock import patch

from siracusa_daily.events import is_dated_event
from siracusa_daily.geography import evaluate_locality
from siracusa_daily.models import Endpoint, Source
from siracusa_daily.notion_source import (
    NotionSourceError,
    SOURCE_ID,
    map_page_to_article,
    retrieve_notion,
)
from siracusa_daily.opportunities import is_opportunity, opportunity_is_active
from siracusa_daily.opportunity_quality import opportunity_is_publishable
from siracusa_daily.service_updates import is_service_alert


def _prop_title(value: str) -> dict:
    return {"title": [{"plain_text": value}]}


def _prop_text(value: str) -> dict:
    return {"rich_text": [{"plain_text": value}] if value else []}


def _prop_select(value: str) -> dict:
    return {"select": {"name": value} if value else None}


def _prop_date(value: str) -> dict:
    return {"date": {"start": value} if value else None}


def make_page(*, titolo: str, tipo: str = "", categoria: str = "", data_inizio: str = "",
              data_fine: str = "", ora: str = "", luogo: str = "", organizzatore: str = "",
              prezzo: str = "", link: str = "", caption: str = "",
              page_id: str = "page-1") -> dict:
    return {
        "id": page_id,
        "url": f"https://www.notion.so/{page_id}",
        "created_time": "2026-08-11T10:00:00.000Z",
        "properties": {
            "Titolo": _prop_title(titolo),
            "Tipo": _prop_select(tipo),
            "Categoria": _prop_select(categoria),
            "Data inizio": _prop_date(data_inizio),
            "Data fine": _prop_date(data_fine),
            "Ora": _prop_text(ora),
            "Luogo": _prop_text(luogo),
            "Indirizzo": _prop_text(""),
            "Organizzatore": _prop_text(organizzatore),
            "Prezzo": _prop_text(prezzo),
            "Link": {"url": link or None},
            "Fonte account": _prop_text(""),
            "Testo grezzo": _prop_text(caption),
        },
    }


class Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class MappingTests(unittest.TestCase):
    def test_event_becomes_a_dated_event(self) -> None:
        page = make_page(
            titolo="Enjoy The Sunset", tipo="Evento", categoria="Eventi",
            data_inizio="2026-08-16", ora="18:30", luogo="Ortigia",
            organizzatore="Samoa", link="https://instagram.com/p/x",
        )
        article = map_page_to_article(page)
        self.assertIsNotNone(article)
        assert article is not None
        self.assertEqual(article.source_id, SOURCE_ID)
        self.assertTrue(is_dated_event(article))
        self.assertEqual(article.metadata["date_label"], "Data")
        self.assertTrue(article.metadata["event_start"].startswith("2026-08-16T18:30"))

    def test_job_becomes_active_opportunity(self) -> None:
        page = make_page(
            titolo="Impiegato amministrativo", tipo="Lavoro", categoria="Lavoro e opportunità",
            data_inizio="2026-08-20", organizzatore="Azienda X",
        )
        article = map_page_to_article(page)
        assert article is not None
        self.assertTrue(is_opportunity(article))
        self.assertTrue(opportunity_is_publishable(article))
        self.assertTrue(opportunity_is_active(article, date(2026, 8, 12)))

    def test_service_avviso_becomes_service_alert(self) -> None:
        page = make_page(
            titolo="Interruzione idrica in via Roma", tipo="Avviso",
            categoria="Servizi e utilità", data_inizio="2026-08-12",
            caption="Sospensione idrica per lavori sulla rete idrica.",
        )
        article = map_page_to_article(page)
        assert article is not None
        self.assertTrue(is_service_alert(article))
        self.assertEqual(article.metadata["service_type"], "acqua")

    def test_generic_avviso_without_service_signal_stays_plain(self) -> None:
        page = make_page(titolo="Comunicazione generica", tipo="Avviso", data_inizio="2026-08-12")
        article = map_page_to_article(page)
        assert article is not None
        self.assertFalse(is_service_alert(article))
        self.assertFalse(is_dated_event(article))
        self.assertFalse(is_opportunity(article))

    def test_news_is_plain_article(self) -> None:
        page = make_page(titolo="Nuovo murale in centro", tipo="News", categoria="Cultura")
        article = map_page_to_article(page)
        assert article is not None
        self.assertFalse(is_dated_event(article))
        self.assertFalse(is_opportunity(article))
        self.assertFalse(is_service_alert(article))
        self.assertEqual(article.content_buckets, ("cultura",))

    def test_link_falls_back_to_notion_url(self) -> None:
        page = make_page(titolo="Senza link", tipo="News", page_id="abc")
        article = map_page_to_article(page)
        assert article is not None
        self.assertEqual(article.url, "https://www.notion.so/abc")

    def test_untitled_row_is_skipped(self) -> None:
        self.assertIsNone(map_page_to_article(make_page(titolo="")))

    def test_manual_source_is_trusted_local(self) -> None:
        article = map_page_to_article(make_page(titolo="Concerto senza toponimo", tipo="News"))
        assert article is not None
        source = Source(
            source_id=SOURCE_ID, name="Raccolta manuale", category="Raccolta manuale",
            reliability="high", editorial_priority="high", geographic_scope="Siracusa",
        )
        score, reasons = evaluate_locality(article, source)
        self.assertGreaterEqual(score, 0.92)
        self.assertTrue(any("curato manualmente" in reason for reason in reasons))


class RetrieveTests(unittest.TestCase):
    ENDPOINT = Endpoint(
        endpoint_id="END-0100", source_id="SRC-0100", endpoint_type="database",
        name="Database Notion", url="db-123", rss_url=None,
        retrieval_method="notion", content_buckets=(),
    )

    def test_missing_token_raises(self) -> None:
        with patch.dict("os.environ", {"NOTION_TOKEN": "", "NOTION_SOCIAL_DB_ID": "db-123"}, clear=False):
            with self.assertRaises(NotionSourceError):
                retrieve_notion(self.ENDPOINT)

    def test_reads_ready_rows_and_maps_them(self) -> None:
        payload = {"results": [make_page(titolo="Evento X", tipo="Evento", data_inizio="2026-08-16", ora="21:00")], "has_more": False}
        with patch.dict("os.environ", {"NOTION_TOKEN": "secret", "NOTION_SOCIAL_DB_ID": "db-123"}, clear=False):
            with patch("siracusa_daily.notion_source.urlopen", return_value=Response(payload)) as opened:
                articles = retrieve_notion(self.ENDPOINT)
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].title, "Evento X")
        sent = json.loads(opened.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(sent["filter"], {"property": "Stato", "select": {"equals": "Pronto"}})


if __name__ == "__main__":
    unittest.main()
