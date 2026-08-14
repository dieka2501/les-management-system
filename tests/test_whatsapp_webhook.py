from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.fonnte import (
    FonnteWebhookSecretError,
    extract_fonnte_message_events,
    normalize_number,
    parse_fonnte_webhook_payload,
    verify_fonnte_secret,
    whatsapp_reply_mode,
)
from backend.app.store import LesStore, safe_whatsapp_webhook_log_result


class WhatsAppWebhookTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store = LesStore(Path(self.tmpdir.name) / "whatsapp.sqlite3")

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_normalize_number_uses_indonesia_country_code(self) -> None:
        self.assertEqual("628123456789", normalize_number("0812 3456 789"))
        self.assertEqual("628123456789", normalize_number("+62 812-3456-789"))

    def test_verify_fonnte_secret_accepts_matching_secret(self) -> None:
        with patch.dict(os.environ, {"FONNTE_WEBHOOK_SECRET": "wa-secret"}, clear=False):
            self.assertEqual("verified", verify_fonnte_secret("secret=wa-secret"))
            with self.assertRaises(FonnteWebhookSecretError):
                verify_fonnte_secret("secret=wrong")

    def test_whatsapp_reply_mode_auto_uses_default_mode(self) -> None:
        with patch.dict(os.environ, {"WA_REPLY_MODE": "auto"}, clear=False):
            self.assertEqual("rule_based", whatsapp_reply_mode(default="rule_based"))
            self.assertEqual("gemini", whatsapp_reply_mode(default="gemini"))

    def test_whatsapp_reply_mode_boolean_like_values_do_not_break_webhook(self) -> None:
        with patch.dict(os.environ, {"WA_REPLY_MODE": "1"}, clear=False):
            self.assertEqual("rule_based", whatsapp_reply_mode(default="rule_based"))
        with patch.dict(os.environ, {"WA_REPLY_MODE": "0"}, clear=False):
            self.assertEqual("rule_based", whatsapp_reply_mode(default="gemini"))

    def test_extract_fonnte_message_events_accepts_common_payload_shapes(self) -> None:
        payload = {
            "data": [
                {
                    "device": "6281283679665",
                    "sender": "0812 3456 789",
                    "message": "Halo kak",
                    "name": "Ibu Rina",
                    "id": "wa-1",
                },
                {
                    "device": "6281283679665",
                    "sender": "0813 1111 2222",
                    "message": "Echo",
                    "fromMe": True,
                },
                {
                    "device": "6281283679665",
                    "sender": "0814 1111 2222",
                    "message": "",
                },
            ]
        }

        events = extract_fonnte_message_events(payload)

        self.assertEqual(1, len(events))
        self.assertEqual("628123456789", events[0].sender_number)
        self.assertEqual("Halo kak", events[0].text)
        self.assertEqual("Ibu Rina", events[0].sender_name)
        self.assertEqual("6281283679665", events[0].device_identifier)
        self.assertEqual("wa-1", events[0].message_id)

    def test_parse_fonnte_webhook_payload_accepts_form_encoded_body(self) -> None:
        payload = parse_fonnte_webhook_payload(
            b"device=6281283679665&sender=08123456789&message=Halo+kak&name=Ibu+Rina"
        )

        self.assertEqual(
            {
                "device": "6281283679665",
                "sender": "08123456789",
                "message": "Halo kak",
                "name": "Ibu Rina",
            },
            payload,
        )

    def test_store_handles_whatsapp_form_encoded_webhook_without_sending(self) -> None:
        raw_body = b"device=6281283679665&sender=08123456789&message=Halo+kak&name=Ibu+Rina"

        with patch.dict(
            os.environ,
            {
                "WA_SEND_ENABLED": "0",
                "WHATSAPP_SEND_ENABLED": "0",
                "FONNTE_SEND_ENABLED": "0",
                "WA_REPLY_MODE": "rule_based",
                "GEMINI_API_KEY": "",
                "GOOGLE_API_KEY": "",
            },
            clear=False,
        ):
            result = self.store.handle_whatsapp_raw_webhook(raw_body, secret_status="verified")

        self.assertEqual(1, result["events_received"])
        self.assertEqual("greeting", result["results"][0]["intent"])

    def test_store_handles_whatsapp_webhook_without_sending_when_disabled(self) -> None:
        payload = {
            "device": "6281283679665",
            "sender": "0812 3456 789",
            "message": "Halo",
            "name": "Ibu Rina",
        }

        with patch.dict(
            os.environ,
            {
                "WA_SEND_ENABLED": "0",
                "WHATSAPP_SEND_ENABLED": "0",
                "FONNTE_SEND_ENABLED": "0",
                "WA_REPLY_MODE": "rule_based",
                "GEMINI_API_KEY": "",
                "GOOGLE_API_KEY": "",
            },
            clear=False,
        ):
            result = self.store.handle_whatsapp_webhook(payload, secret_status="not_configured")

        self.assertEqual("fonnte", result["source"])
        self.assertEqual(1, result["events_received"])
        self.assertFalse(result["results"][0]["sent"])
        session = self.store.get_provider_chat_simulation_session(result["results"][0]["session_id"])
        self.assertEqual("whatsapp", session["channel"])
        self.assertEqual("fonnte_webhook", session["source"])
        self.assertEqual("WhatsApp 628123456789", session["title"])
        self.assertIn("selamat datang di Rumah Privat Madani", session["messages"][1]["message"])

    def test_store_sends_whatsapp_reply_when_enabled(self) -> None:
        payload = {
            "device": "6281283679665",
            "sender": "0812 3456 789",
            "message": "Halo",
        }

        with (
            patch.dict(
                os.environ,
                {
                    "WA_SEND_ENABLED": "1",
                    "WHATSAPP_SEND_ENABLED": "0",
                    "FONNTE_SEND_ENABLED": "0",
                    "WA_REPLY_MODE": "rule_based",
                    "GEMINI_API_KEY": "",
                    "GOOGLE_API_KEY": "",
                },
                clear=False,
            ),
            patch("backend.app.store.send_fonnte_text_message", return_value={"status": True}) as mocked_send,
        ):
            result = self.store.handle_whatsapp_webhook(payload, secret_status="verified")

        self.assertTrue(result["results"][0]["sent"])
        mocked_send.assert_called_once()
        self.assertEqual("628123456789", mocked_send.call_args.kwargs["target_number"])

    def test_safe_whatsapp_log_omits_private_sender_and_message_text(self) -> None:
        result = {
            "source": "fonnte",
            "secret": "verified",
            "events_received": 1,
            "diagnostics": {"text_candidates": 1},
            "results": [
                {
                    "sender_number": "628123456789",
                    "message_text": "Halo privat",
                    "reply_mode": "rule_based",
                    "intent": "greeting",
                    "stage": "greeting",
                    "sent": True,
                    "send_result": {"enabled": True, "sent": True},
                }
            ],
        }

        safe_result = safe_whatsapp_webhook_log_result(result)
        safe_text = json.dumps(safe_result, ensure_ascii=False)

        self.assertNotIn("628123456789", safe_text)
        self.assertNotIn("Halo privat", safe_text)
        self.assertIn("greeting", safe_text)


if __name__ == "__main__":
    unittest.main()
