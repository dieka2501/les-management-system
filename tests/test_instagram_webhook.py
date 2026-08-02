from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.instagram_webhook import (
    InstagramWebhookSignatureError,
    extract_instagram_message_events,
    summarize_instagram_webhook_payload,
    verify_instagram_challenge,
    verify_instagram_signature,
)
from backend.app.store import LesStore


class InstagramWebhookTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store = LesStore(Path(self.tmpdir.name) / "instagram.sqlite3")

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_verify_instagram_challenge_returns_meta_challenge(self) -> None:
        with patch.dict(os.environ, {"IG_WEBHOOK_VERIFY_TOKEN": "secret"}, clear=False):
            challenge = verify_instagram_challenge(
                "hub.mode=subscribe&hub.verify_token=secret&hub.challenge=OK123"
            )

        self.assertEqual("OK123", challenge)

    def test_verify_instagram_signature_uses_app_secret(self) -> None:
        raw_body = b'{"object":"instagram","entry":[]}'
        signature = "sha256=" + hmac.new(b"app-secret", raw_body, hashlib.sha256).hexdigest()

        with patch.dict(os.environ, {"IG_APP_SECRET": "app-secret"}, clear=False):
            self.assertEqual("verified", verify_instagram_signature(raw_body, {"X-Hub-Signature-256": signature}))
            with self.assertRaises(InstagramWebhookSignatureError):
                verify_instagram_signature(raw_body, {"X-Hub-Signature-256": "sha256=bad"})

    def test_extract_instagram_text_message_events_ignores_echoes(self) -> None:
        payload = {
            "object": "instagram",
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": "user-1"},
                            "recipient": {"id": "ig-business"},
                            "message": {"mid": "m_1", "text": "Halo"},
                            "timestamp": 123,
                        },
                        {
                            "sender": {"id": "ig-business"},
                            "recipient": {"id": "user-1"},
                            "message": {"mid": "m_2", "text": "Echo", "is_echo": True},
                            "timestamp": 124,
                        },
                    ]
                }
            ],
        }

        events = extract_instagram_message_events(payload)

        self.assertEqual(1, len(events))
        self.assertEqual("user-1", events[0].sender_id)
        self.assertEqual("ig-business", events[0].recipient_id)
        self.assertEqual("Halo", events[0].text)

    def test_extract_instagram_text_message_events_from_change_payload(self) -> None:
        payload = {
            "object": "instagram",
            "entry": [
                {
                    "id": "ig-business",
                    "time": 123,
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "sender": {"id": "user-3"},
                                "recipient": {"id": "ig-business"},
                                "message": {"mid": "m_3", "text": "Halo dari changes"},
                            },
                        }
                    ],
                }
            ],
        }

        events = extract_instagram_message_events(payload)

        self.assertEqual(1, len(events))
        self.assertEqual("user-3", events[0].sender_id)
        self.assertEqual("ig-business", events[0].recipient_id)
        self.assertEqual("Halo dari changes", events[0].text)

    def test_summarize_instagram_payload_without_raw_message_text(self) -> None:
        payload = {
            "object": "instagram",
            "entry": [
                {
                    "id": "ig-business",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "sender": {"id": "user-4"},
                                "message": {"mid": "m_4", "text": "pesan privat"},
                            },
                        }
                    ],
                }
            ],
        }

        summary = summarize_instagram_webhook_payload(payload)

        self.assertEqual(1, summary["entry_count"])
        self.assertEqual(1, summary["change_items"])
        self.assertEqual(["messages"], summary["change_fields"])
        self.assertEqual(1, summary["candidate_items"])
        self.assertEqual(1, summary["text_candidates"])
        self.assertNotIn("pesan privat", json.dumps(summary, ensure_ascii=False))

    def test_store_handles_instagram_webhook_without_sending_when_disabled(self) -> None:
        raw_body = json.dumps(
            {
                "object": "instagram",
                "entry": [
                    {
                        "messaging": [
                            {
                                "sender": {"id": "user-1"},
                                "recipient": {"id": "ig-business"},
                                "message": {"mid": "m_1", "text": "Halo"},
                            }
                        ]
                    }
                ],
            }
        ).encode("utf-8")

        with patch.dict(os.environ, {"IG_SEND_ENABLED": "0", "IG_REPLY_MODE": "rule_based"}, clear=False):
            result = self.store.handle_instagram_webhook(raw_body, {})

        self.assertEqual(1, result["events_received"])
        self.assertEqual("greeting", result["results"][0]["intent"])
        self.assertFalse(result["results"][0]["sent"])
        session = self.store.get_provider_chat_simulation_session(result["results"][0]["session_id"])
        self.assertEqual("instagram", session["channel"])
        self.assertEqual("instagram_webhook", session["source"])

    def test_store_sends_instagram_reply_when_send_is_enabled(self) -> None:
        raw_body = json.dumps(
            {
                "object": "instagram",
                "entry": [
                    {
                        "messaging": [
                            {
                                "sender": {"id": "user-2"},
                                "recipient": {"id": "ig-business"},
                                "message": {"mid": "m_1", "text": "Halo"},
                            }
                        ]
                    }
                ],
            }
        ).encode("utf-8")

        with patch.dict(os.environ, {"IG_SEND_ENABLED": "1", "IG_REPLY_MODE": "rule_based"}, clear=False):
            with patch("backend.app.store.send_instagram_text_message", return_value={"message_id": "reply-1"}) as mocked:
                result = self.store.handle_instagram_webhook(raw_body, {})

        mocked.assert_called_once()
        self.assertTrue(result["results"][0]["sent"])
        self.assertEqual("reply-1", result["results"][0]["send_result"]["response"]["message_id"])


if __name__ == "__main__":
    unittest.main()
