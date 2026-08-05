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
    InstagramMessageDetailReference,
    InstagramMessageFetchError,
    InstagramWebhookSignatureError,
    extract_instagram_message_events,
    extract_instagram_message_detail_references,
    instagram_message_detail_to_event,
    summarize_instagram_webhook_payload,
    verify_instagram_challenge,
    verify_instagram_signature,
)
from backend.app.store import LesStore, filter_instagram_payload_for_target_user, safe_instagram_webhook_log_result


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

    def test_filter_instagram_payload_for_target_user_ignores_other_entries(self) -> None:
        payload = {
            "object": "instagram",
            "entry": [
                {"id": "ig-target", "messaging": [{"message": {"text": "Halo target"}}]},
                {"id": "ig-other", "messaging": [{"message": {"text": "Halo other"}}]},
            ],
        }

        with patch.dict(os.environ, {"IG_USER_ID": "ig-target"}, clear=False):
            filtered_payload, summary = filter_instagram_payload_for_target_user(payload)

        self.assertEqual([{"id": "ig-target", "messaging": [{"message": {"text": "Halo target"}}]}], filtered_payload["entry"])
        self.assertEqual(
            {
                "enabled": True,
                "target_user_configured": True,
                "entry_count_before_filter": 2,
                "entry_count_after_filter": 1,
                "ignored_entries": 1,
            },
            summary,
        )

    def test_store_ignores_instagram_entry_that_does_not_match_target_user(self) -> None:
        raw_body = json.dumps(
            {
                "object": "instagram",
                "entry": [
                    {
                        "id": "ig-other",
                        "messaging": [
                            {
                                "sender": {"id": "user-1"},
                                "recipient": {"id": "ig-other"},
                                "message": {"mid": "m_ignored", "text": "Halo"},
                                "timestamp": 123,
                            }
                        ],
                    }
                ],
            }
        ).encode("utf-8")

        with patch.dict(os.environ, {"IG_USER_ID": "ig-target"}, clear=False):
            result = self.store.handle_instagram_webhook(raw_body, {})

        self.assertEqual(0, result["events_received"])
        self.assertEqual(0, result["diagnostics"]["entry_count"])
        self.assertEqual(1, result["diagnostics"]["target_filter"]["ignored_entries"])
        self.assertEqual([], result["results"])

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

    def test_extract_instagram_text_message_events_from_message_edit_payload(self) -> None:
        payload = {
            "object": "instagram",
            "entry": [
                {
                    "id": "ig-business",
                    "time": 123,
                    "messaging": [
                        {
                            "sender": {"id": "user-4"},
                            "recipient": {"id": "ig-business"},
                            "timestamp": 456,
                            "message_edit": {"mid": "m_4", "text": "Halo dari message edit"},
                        }
                    ],
                }
            ],
        }

        events = extract_instagram_message_events(payload)

        self.assertEqual(1, len(events))
        self.assertEqual("user-4", events[0].sender_id)
        self.assertEqual("ig-business", events[0].recipient_id)
        self.assertEqual("Halo dari message edit", events[0].text)
        self.assertEqual("m_4", events[0].message_id)
        self.assertEqual(456, events[0].timestamp)

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
        self.assertEqual(["message,recipient,sender,timestamp"], summary["candidate_key_sets"])
        self.assertEqual(["mid,text"], summary["message_key_sets"])
        self.assertNotIn("pesan privat", json.dumps(summary, ensure_ascii=False))

    def test_summarize_instagram_payload_identifies_message_edit_shape_without_raw_text(self) -> None:
        payload = {
            "object": "instagram",
            "entry": [
                {
                    "id": "ig-business",
                    "time": 123,
                    "messaging": [
                        {
                            "timestamp": 456,
                            "message_edit": {"mid": "m_5", "text": "pesan privat edit"},
                        }
                    ],
                }
            ],
        }

        summary = summarize_instagram_webhook_payload(payload)

        self.assertEqual(1, summary["candidate_items"])
        self.assertEqual(1, summary["message_edit_candidates"])
        self.assertEqual(1, summary["text_candidates"])
        self.assertEqual(1, summary["missing_sender_candidates"])
        self.assertEqual(["message_edit,timestamp"], summary["candidate_key_sets"])
        self.assertEqual(["mid,text"], summary["message_edit_key_sets"])
        self.assertNotIn("pesan privat edit", json.dumps(summary, ensure_ascii=False))

    def test_extract_instagram_message_detail_references_from_metadata_only_message_edit(self) -> None:
        payload = {
            "object": "instagram",
            "entry": [
                {
                    "id": "ig-business",
                    "time": 123,
                    "messaging": [
                        {
                            "timestamp": 456,
                            "message_edit": {"mid": "m_private_1", "num_edit": 1},
                        }
                    ],
                }
            ],
        }

        references = extract_instagram_message_detail_references(payload)

        self.assertEqual(1, len(references))
        self.assertEqual("m_private_1", references[0].message_id)
        self.assertEqual("ig-business", references[0].fallback_recipient_id)
        self.assertEqual(456, references[0].fallback_timestamp)

    def test_instagram_message_detail_to_event_uses_fetched_message_text(self) -> None:
        event = instagram_message_detail_to_event(
            {
                "id": "m_private_2",
                "message": "Halo dari API detail",
                "from": {"id": "user-6"},
                "to": {"data": [{"id": "ig-business"}]},
            },
            InstagramMessageDetailReference(
                message_id="m_private_2",
                fallback_recipient_id="fallback-business",
                fallback_timestamp=789,
            ),
        )

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual("user-6", event.sender_id)
        self.assertEqual("ig-business", event.recipient_id)
        self.assertEqual("Halo dari API detail", event.text)
        self.assertEqual("m_private_2", event.message_id)
        self.assertEqual(789, event.timestamp)

    def test_instagram_message_detail_to_event_accepts_nested_message_text(self) -> None:
        event = instagram_message_detail_to_event(
            {
                "id": "m_private_nested",
                "message": {"text": "Halo dari shape nested"},
                "sender": {"id": "user-nested"},
                "recipient": {"id": "ig-business"},
            },
            InstagramMessageDetailReference(message_id="m_private_nested"),
        )

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual("user-nested", event.sender_id)
        self.assertEqual("ig-business", event.recipient_id)
        self.assertEqual("Halo dari shape nested", event.text)

    def test_summarize_instagram_payload_identifies_non_text_events(self) -> None:
        payload = {
            "object": "instagram",
            "entry": [
                {
                    "id": "ig-business",
                    "time": 123,
                    "messaging": [
                        {
                            "sender": {"id": "user-5"},
                            "recipient": {"id": "ig-business"},
                            "read": {"mid": "m_5"},
                        },
                        {
                            "sender": {"id": "user-5"},
                            "recipient": {"id": "ig-business"},
                            "delivery": {"mids": ["m_6"]},
                        },
                    ],
                }
            ],
        }

        summary = summarize_instagram_webhook_payload(payload)

        self.assertEqual(2, summary["candidate_items"])
        self.assertEqual(0, summary["text_candidates"])
        self.assertEqual(1, summary["read_candidates"])
        self.assertEqual(1, summary["delivery_candidates"])
        self.assertEqual(["delivery,recipient,sender", "read,recipient,sender"], summary["candidate_key_sets"])

    def test_store_fetches_message_detail_for_metadata_only_message_edit(self) -> None:
        raw_body = json.dumps(
            {
                "object": "instagram",
                "entry": [
                    {
                        "id": "ig-business",
                        "messaging": [
                            {
                                "timestamp": 456,
                                "message_edit": {"mid": "m_private_3", "num_edit": 1},
                            }
                        ],
                    }
                ],
            }
        ).encode("utf-8")

        with patch.dict(os.environ, {"IG_SEND_ENABLED": "0", "IG_REPLY_MODE": "rule_based"}, clear=False):
            with patch(
                "backend.app.store.fetch_instagram_message_detail",
                return_value={
                    "id": "m_private_3",
                    "message": "Halo",
                    "from": {"id": "user-7"},
                    "to": {"data": [{"id": "ig-business"}]},
                },
            ) as mocked_fetch:
                result = self.store.handle_instagram_webhook(raw_body, {})

        mocked_fetch.assert_called_once_with("m_private_3")
        self.assertEqual(1, result["events_received"])
        self.assertEqual(1, result["message_detail_fetch"]["attempted"])
        self.assertEqual(1, result["message_detail_fetch"]["resolved"])
        self.assertEqual([], result["message_detail_fetch"]["empty_or_incomplete_details"])
        self.assertEqual("greeting", result["results"][0]["intent"])
        self.assertNotIn("Halo", json.dumps(result["message_detail_fetch"], ensure_ascii=False))

    def test_store_includes_safe_diagnostic_for_incomplete_message_detail(self) -> None:
        raw_body = json.dumps(
            {
                "object": "instagram",
                "entry": [
                    {
                        "id": "ig-business",
                        "messaging": [
                            {
                                "timestamp": 456,
                                "message_edit": {"mid": "m_private_missing", "num_edit": 1},
                            }
                        ],
                    }
                ],
            }
        ).encode("utf-8")

        with patch(
            "backend.app.store.fetch_instagram_message_detail",
            return_value={
                "id": "m_private_missing",
                "created_time": "2026-08-05T14:00:00+0000",
                "from": {"id": "private-user-id"},
            },
        ):
            result = self.store.handle_instagram_webhook(raw_body, {})

        self.assertEqual(0, result["events_received"])
        self.assertEqual(1, result["message_detail_fetch"]["empty_or_incomplete"])
        self.assertEqual(
            [
                {
                    "response_keys": ["created_time", "from", "id"],
                    "message_value_type": "missing",
                    "from_value_type": "object",
                    "to_value_type": "missing",
                    "has_message": False,
                    "has_sender": True,
                    "has_recipient": True,
                    "missing": ["message"],
                }
            ],
            result["message_detail_fetch"]["empty_or_incomplete_details"],
        )
        encoded = json.dumps(result["message_detail_fetch"], ensure_ascii=False)
        self.assertNotIn("private-user-id", encoded)
        self.assertNotIn("m_private_missing", encoded)

    def test_store_keeps_fetch_errors_sanitized(self) -> None:
        raw_body = json.dumps(
            {
                "object": "instagram",
                "entry": [
                    {
                        "id": "ig-business",
                        "messaging": [
                            {
                                "timestamp": 456,
                                "message_edit": {"mid": "m_private_4", "num_edit": 1},
                            }
                        ],
                    }
                ],
            }
        ).encode("utf-8")

        with patch(
            "backend.app.store.fetch_instagram_message_detail",
            side_effect=InstagramMessageFetchError("raw secret m_private_4", status_code=400, error_type="http_error"),
        ):
            result = self.store.handle_instagram_webhook(raw_body, {})

        self.assertEqual(0, result["events_received"])
        self.assertEqual(1, result["message_detail_fetch"]["attempted"])
        self.assertEqual([{"type": "http_error", "status_code": 400}], result["message_detail_fetch"]["errors"])
        self.assertNotIn("raw secret", json.dumps(result["message_detail_fetch"], ensure_ascii=False))
        self.assertNotIn("m_private_4", json.dumps(result["message_detail_fetch"], ensure_ascii=False))

    def test_store_includes_raw_fetch_error_when_debug_enabled(self) -> None:
        raw_body = json.dumps(
            {
                "object": "instagram",
                "entry": [
                    {
                        "id": "ig-business",
                        "messaging": [
                            {
                                "timestamp": 456,
                                "message_edit": {"mid": "m_private_5", "num_edit": 1},
                            }
                        ],
                    }
                ],
            }
        ).encode("utf-8")

        with patch.dict(os.environ, {"IG_DEBUG_RAW_WEBHOOK": "1"}, clear=False):
            with patch(
                "backend.app.store.fetch_instagram_message_detail",
                side_effect=InstagramMessageFetchError(
                    "raw detail failure",
                    status_code=500,
                    error_type="http_error",
                    endpoint="https://graph.instagram.com/v25.0/m_private_5",
                    response_body='{"error":{"message":"Meta raw failure"}}',
                ),
            ):
                result = self.store.handle_instagram_webhook(raw_body, {})

        self.assertEqual(0, result["events_received"])
        self.assertEqual(1, result["message_detail_fetch"]["attempted"])
        self.assertEqual(
            [
                {
                    "type": "http_error",
                    "status_code": 500,
                    "message": "raw detail failure",
                    "endpoint": "https://graph.instagram.com/v25.0/m_private_5",
                    "response_body": '{"error":{"message":"Meta raw failure"}}',
                }
            ],
            result["message_detail_fetch"]["errors"],
        )

    def test_safe_instagram_webhook_log_result_omits_private_ids_and_text(self) -> None:
        safe_result = safe_instagram_webhook_log_result(
            {
                "object": "instagram",
                "signature": "verified",
                "events_received": 1,
                "diagnostics": {"text_candidates": 1},
                "message_detail_fetch": {"attempted": 1, "resolved": 1},
                "results": [
                    {
                        "sender_id": "private-user-id",
                        "session_id": 123,
                        "reply_mode": "rule_based",
                        "intent": "greeting",
                        "stage": "start",
                        "sent": False,
                        "send_result": {"enabled": False, "sent": False, "response": {"message_id": "private-reply-id"}},
                    }
                ],
            }
        )

        encoded = json.dumps(safe_result, ensure_ascii=False)
        self.assertIn("greeting", encoded)
        self.assertNotIn("private-user-id", encoded)
        self.assertNotIn("private-reply-id", encoded)
        self.assertNotIn("session_id", encoded)

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
