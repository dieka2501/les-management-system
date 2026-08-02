from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from backend.app.provider_auth import (
    AUTH_COOKIE_NAME,
    ProviderAuthenticationError,
    authenticate_provider_payload,
    is_production_runtime,
    is_provider_authenticated,
    make_provider_auth_cookie,
    make_provider_logout_cookie,
    provider_auth_configured,
    provider_auth_required,
)


class ProviderAuthTestCase(unittest.TestCase):
    def test_provider_auth_disabled_when_password_empty(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_AUTH_PASSWORD": "",
                "CHATBOT_TEST_PASSWORD": "",
                "DASHBOARD_AUTH_PASSWORD": "",
                "PROVIDER_AUTH_PASSWORD": "",
                "RAILWAY_ENVIRONMENT": "",
                "RAILWAY_SERVICE_ID": "",
                "RAILWAY_PROJECT_ID": "",
                "APP_ENV": "",
            },
            clear=False,
        ):
            self.assertFalse(provider_auth_required())
            self.assertTrue(is_provider_authenticated(None))
            authenticate_provider_payload({"password": ""})

    def test_app_auth_password_is_primary_secret(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_AUTH_PASSWORD": "internal-pass",
                "APP_AUTH_SECRET": "internal-cookie-salt",
                "CHATBOT_TEST_PASSWORD": "",
                "CHATBOT_AUTH_SECRET": "",
            },
            clear=False,
        ):
            self.assertTrue(provider_auth_configured())
            authenticate_provider_payload({"password": "internal-pass"})
            cookie = make_provider_auth_cookie()

        self.assertIn(f"{AUTH_COOKIE_NAME}=", cookie)

    def test_production_requires_configured_password(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_AUTH_PASSWORD": "",
                "CHATBOT_TEST_PASSWORD": "",
                "DASHBOARD_AUTH_PASSWORD": "",
                "PROVIDER_AUTH_PASSWORD": "",
                "RAILWAY_ENVIRONMENT": "production",
            },
            clear=False,
        ):
            self.assertTrue(is_production_runtime())
            self.assertTrue(provider_auth_required())
            self.assertFalse(provider_auth_configured())
            self.assertFalse(is_provider_authenticated(None))
            with self.assertRaises(ProviderAuthenticationError):
                authenticate_provider_payload({"password": ""})

    def test_provider_auth_accepts_matching_password_and_cookie(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_AUTH_PASSWORD": "",
                "APP_AUTH_SECRET": "",
                "CHATBOT_TEST_PASSWORD": "secret-pass",
                "CHATBOT_AUTH_SECRET": "secret-cookie-salt",
            },
            clear=False,
        ):
            authenticate_provider_payload({"password": "secret-pass"})
            cookie = make_provider_auth_cookie()

        self.assertIn(f"{AUTH_COOKIE_NAME}=", cookie)
        with patch.dict(
            os.environ,
            {
                "APP_AUTH_PASSWORD": "",
                "APP_AUTH_SECRET": "",
                "CHATBOT_TEST_PASSWORD": "secret-pass",
                "CHATBOT_AUTH_SECRET": "secret-cookie-salt",
            },
            clear=False,
        ):
            self.assertTrue(is_provider_authenticated(cookie))

    def test_provider_auth_rejects_wrong_password(self) -> None:
        with patch.dict(os.environ, {"APP_AUTH_PASSWORD": "", "CHATBOT_TEST_PASSWORD": "secret-pass"}, clear=False):
            with self.assertRaises(ProviderAuthenticationError):
                authenticate_provider_payload({"password": "wrong"})

    def test_logout_cookie_expires_session_cookie(self) -> None:
        cookie = make_provider_logout_cookie()

        self.assertIn(f"{AUTH_COOKIE_NAME}=", cookie)
        self.assertIn("Max-Age=0", cookie)


if __name__ == "__main__":
    unittest.main()
