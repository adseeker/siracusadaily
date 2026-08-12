from __future__ import annotations

import json
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from siracusa_daily.notion import (
    NotionPublishError,
    check_notion_access,
    publish_facebook_recap,
)


PAGE_ID = "3b9deac1-b022-8196-8a55-d77a97e81cf9"


class Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class NotionPublishTests(unittest.TestCase):
    def test_recap_is_archived_first_and_only_same_day_toggle_is_replaced(self) -> None:
        responses = [
            Response({
                "results": [
                    {
                        "id": "same-day",
                        "type": "toggle",
                        "toggle": {"rich_text": [{"plain_text": "Post notizie 12 agosto 2026"}]},
                    },
                    {
                        "id": "older",
                        "type": "toggle",
                        "toggle": {"rich_text": [{"plain_text": "Post notizie 11 agosto 2026"}]},
                    },
                    {"id": "intro", "type": "paragraph", "paragraph": {"rich_text": []}},
                ],
                "has_more": False,
            }),
            Response({"results": [{"id": "new-toggle"}]}),
            Response({"id": "same-day"}),
        ]
        with patch("siracusa_daily.notion.urlopen", side_effect=responses) as request:
            result = publish_facebook_recap(
                PAGE_ID,
                "Titolo\nSintesi\nFonte: Testata",
                "FONTI\n1. Testata\nhttps://example.com",
                token="secret",
                updated_at=datetime(2026, 8, 12, 9, 0, tzinfo=ZoneInfo("Europe/Rome")),
            )

        self.assertEqual(result.replaced_blocks, 1)
        self.assertEqual(request.call_count, 3)
        append_request = request.call_args_list[1].args[0]
        append_payload = json.loads(append_request.data.decode("utf-8"))
        self.assertEqual(append_payload["position"], {"type": "start"})
        self.assertEqual(len(append_payload["children"]), 1)
        toggle = append_payload["children"][0]["toggle"]
        self.assertEqual(
            toggle["rich_text"][0]["text"]["content"],
            "Post notizie 12 agosto 2026",
        )
        self.assertEqual(len(toggle["children"]), 4)
        self.assertIn("Titolo", toggle["children"][1]["code"]["rich_text"][0]["text"]["content"])
        self.assertIn("https://example.com", toggle["children"][3]["code"]["rich_text"][0]["text"]["content"])
        self.assertTrue(request.call_args_list[2].args[0].full_url.endswith("/blocks/same-day"))
        self.assertFalse(any("/blocks/older" in call.args[0].full_url for call in request.call_args_list))
        self.assertFalse(any("/blocks/intro" in call.args[0].full_url for call in request.call_args_list))

    def test_long_post_is_split_into_safe_rich_text_chunks(self) -> None:
        with patch(
            "siracusa_daily.notion.urlopen",
            side_effect=[Response({"results": [], "has_more": False}), Response({"results": []})],
        ) as request:
            publish_facebook_recap(PAGE_ID, "x" * 4001, "fonti", token="secret")

        payload = json.loads(request.call_args_list[1].args[0].data.decode("utf-8"))
        chunks = payload["children"][0]["toggle"]["children"][1]["code"]["rich_text"]
        self.assertEqual([len(chunk["text"]["content"]) for chunk in chunks], [1800, 1800, 401])

    def test_invalid_input_is_rejected_before_calling_notion(self) -> None:
        with patch("siracusa_daily.notion.urlopen") as request:
            with self.assertRaises(NotionPublishError):
                publish_facebook_recap("bad-id", "post", "fonti", token="secret")
            with self.assertRaises(NotionPublishError):
                publish_facebook_recap(PAGE_ID, "", "fonti", token="secret")
        request.assert_not_called()

    def test_access_check_reads_writes_and_removes_a_temporary_block(self) -> None:
        responses = [
            Response({"results": [{"id": "existing"}], "has_more": False}),
            Response({"results": [{"id": "temporary"}]}),
            Response({"id": "temporary"}),
        ]
        with patch("siracusa_daily.notion.urlopen", side_effect=responses) as request:
            result = check_notion_access(PAGE_ID, token="secret")

        self.assertEqual(result.readable_blocks, 1)
        self.assertEqual(request.call_count, 3)
        self.assertEqual(request.call_args_list[1].args[0].method, "PATCH")
        self.assertEqual(request.call_args_list[2].args[0].method, "DELETE")
        self.assertTrue(request.call_args_list[2].args[0].full_url.endswith("/blocks/temporary"))


if __name__ == "__main__":
    unittest.main()
