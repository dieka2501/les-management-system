from __future__ import annotations

import os
import unittest
from http import HTTPStatus
from unittest.mock import patch

from backend.app.main import (
    LesRequestHandler,
    default_host,
    default_port,
    instagram_raw_webhook_debug_enabled,
    instagram_raw_webhook_debug_max_chars,
    instagram_raw_webhook_debug_text,
    is_protected_api_path,
    is_protected_dashboard_path,
    normalize_client_api_path,
    parse_host_value,
    safe_next_path,
)


class DummyHandler:
    def __init__(self) -> None:
        self.error_status = None
        self.error_message = None

    def send_error_json(self, status: HTTPStatus, message: str) -> None:
        self.error_status = status
        self.error_message = message


class ServerConfigTestCase(unittest.TestCase):
    def test_default_host_is_local_outside_railway(self) -> None:
        with patch.dict(os.environ, {"HOST": "", "RAILWAY_ENVIRONMENT": "", "RAILWAY_SERVICE_ID": ""}, clear=False):
            self.assertEqual("127.0.0.1", default_host())

    def test_default_host_binds_all_interfaces_on_railway(self) -> None:
        with patch.dict(os.environ, {"HOST": "", "RAILWAY_ENVIRONMENT": "production"}, clear=False):
            self.assertEqual("0.0.0.0", default_host())

    def test_railway_ignores_explicit_host_for_socket_bind(self) -> None:
        with patch.dict(os.environ, {"HOST": "127.0.0.1", "RAILWAY_ENVIRONMENT": "production"}, clear=False):
            self.assertEqual("0.0.0.0", default_host())

    def test_explicit_host_wins_outside_railway(self) -> None:
        with patch.dict(os.environ, {"HOST": "127.0.0.1", "RAILWAY_ENVIRONMENT": ""}, clear=False):
            self.assertEqual("127.0.0.1", default_host())

    def test_host_value_can_include_port_for_local_runs(self) -> None:
        self.assertEqual(("127.0.0.1", 9000), parse_host_value("127.0.0.1:9000"))

    def test_port_env_wins_over_host_port(self) -> None:
        with patch.dict(os.environ, {"HOST": "127.0.0.1:9000", "PORT": "7000"}, clear=False):
            self.assertEqual(7000, default_port())

    def test_default_port_can_fallback_to_host_port(self) -> None:
        with patch.dict(os.environ, {"HOST": "127.0.0.1:9000", "PORT": ""}, clear=False):
            self.assertEqual(9000, default_port())

    def test_operational_api_paths_are_protected(self) -> None:
        self.assertTrue(is_protected_api_path("/api/dashboard-data"))
        self.assertTrue(is_protected_api_path("/api/branches"))
        self.assertTrue(is_protected_api_path("/api/schedules/generate"))
        self.assertTrue(is_protected_api_path("/api/client/chat-simulations"))

    def test_auth_and_webhook_paths_stay_public(self) -> None:
        self.assertFalse(is_protected_api_path("/api/client/login"))
        self.assertFalse(is_protected_api_path("/api/client/auth"))
        self.assertFalse(is_protected_api_path("/api/provider/login"))
        self.assertFalse(is_protected_api_path("/api/provider/auth"))
        self.assertFalse(is_protected_api_path("/api/v1/webhooks/fonnte"))
        self.assertFalse(is_protected_api_path("/webhooks/fonnte"))
        self.assertFalse(is_protected_api_path("/webhooks/instagram"))

    def test_dashboard_page_paths_are_protected(self) -> None:
        self.assertTrue(is_protected_dashboard_path("/"))
        self.assertTrue(is_protected_dashboard_path("/index.html"))
        self.assertFalse(is_protected_dashboard_path("/privacy-policy/"))

    def test_safe_next_path_allows_only_internal_paths(self) -> None:
        self.assertEqual("/", safe_next_path("/", "/client/chatbot"))
        self.assertEqual("/client/chatbot", safe_next_path("https://evil.example", "/client/chatbot"))
        self.assertEqual("/client/chatbot", safe_next_path("//evil.example", "/client/chatbot"))

    def test_client_chatbot_api_aliases_legacy_internal_paths(self) -> None:
        self.assertEqual("/api/provider/login", normalize_client_api_path("/api/client/login"))
        self.assertEqual(
            "/api/provider/chat-simulations/12/messages/99",
            normalize_client_api_path("/api/client/chat-simulations/12/messages/99"),
        )
        self.assertEqual("/api/branches", normalize_client_api_path("/api/branches"))

    def test_value_error_is_returned_as_user_input_error(self) -> None:
        handler = DummyHandler()

        LesRequestHandler.handle_exception(handler, ValueError("Jam selesai harus lebih besar dari jam mulai."))

        self.assertEqual(HTTPStatus.BAD_REQUEST, handler.error_status)
        self.assertEqual(
            "Input belum valid. Jam selesai harus lebih besar dari jam mulai.",
            handler.error_message,
        )

    def test_instagram_raw_webhook_debug_is_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {"IG_DEBUG_RAW_WEBHOOK": ""}, clear=False):
            self.assertFalse(instagram_raw_webhook_debug_enabled())

    def test_instagram_raw_webhook_debug_can_be_enabled(self) -> None:
        with patch.dict(os.environ, {"IG_DEBUG_RAW_WEBHOOK": "1"}, clear=False):
            self.assertTrue(instagram_raw_webhook_debug_enabled())

    def test_instagram_raw_webhook_debug_text_can_be_truncated(self) -> None:
        with patch.dict(os.environ, {"IG_DEBUG_RAW_WEBHOOK_MAX_CHARS": "5"}, clear=False):
            self.assertEqual("abcde...<truncated 5 chars>", instagram_raw_webhook_debug_text(b"abcdefghij"))

    def test_instagram_raw_webhook_debug_text_can_be_unlimited(self) -> None:
        with patch.dict(os.environ, {"IG_DEBUG_RAW_WEBHOOK_MAX_CHARS": "0"}, clear=False):
            self.assertIsNone(instagram_raw_webhook_debug_max_chars())
            self.assertEqual("abcdefghij", instagram_raw_webhook_debug_text(b"abcdefghij"))


if __name__ == "__main__":
    unittest.main()
