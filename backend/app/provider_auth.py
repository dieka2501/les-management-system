from __future__ import annotations

import hashlib
import hmac
import os
from http.cookies import SimpleCookie
from typing import Mapping


AUTH_COOKIE_NAME = "les_chatbot_auth"


class ProviderAuthenticationError(Exception):
    """Raised when provider/chatbot tester authentication fails."""


def chatbot_test_password() -> str:
    return (
        os.environ.get("APP_AUTH_PASSWORD")
        or os.environ.get("CHATBOT_TEST_PASSWORD")
        or os.environ.get("DASHBOARD_AUTH_PASSWORD")
        or os.environ.get("PROVIDER_AUTH_PASSWORD")
        or ""
    ).strip()


def chatbot_auth_secret() -> str:
    configured_secret = (
        os.environ.get("APP_AUTH_SECRET")
        or os.environ.get("CHATBOT_AUTH_SECRET")
        or os.environ.get("DASHBOARD_AUTH_SECRET")
        or os.environ.get("PROVIDER_AUTH_SECRET")
        or os.environ.get("SESSION_SECRET")
        or ""
    ).strip()
    return configured_secret or chatbot_test_password()


def is_production_runtime() -> bool:
    app_env = os.environ.get("APP_ENV", "").strip().lower()
    return bool(
        os.environ.get("RAILWAY_ENVIRONMENT")
        or os.environ.get("RAILWAY_SERVICE_ID")
        or os.environ.get("RAILWAY_PROJECT_ID")
        or app_env == "production"
    )


def provider_auth_configured() -> bool:
    return bool(chatbot_test_password())


def provider_auth_required() -> bool:
    return provider_auth_configured() or is_production_runtime()


def verify_provider_password(password: str) -> bool:
    expected_password = chatbot_test_password()
    if not expected_password:
        return not provider_auth_required()
    return hmac.compare_digest(str(password or ""), expected_password)


def provider_session_token() -> str:
    password = chatbot_test_password()
    secret = chatbot_auth_secret()
    digest = hmac.new(
        secret.encode("utf-8"),
        f"les-chatbot-test:{password}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest


def parse_cookie_header(cookie_header: str | None) -> dict[str, str]:
    if not cookie_header:
        return {}
    cookie = SimpleCookie()
    cookie.load(cookie_header)
    return {key: morsel.value for key, morsel in cookie.items()}


def is_provider_authenticated(cookie_header: str | None) -> bool:
    if not provider_auth_required():
        return True
    cookies = parse_cookie_header(cookie_header)
    token = cookies.get(AUTH_COOKIE_NAME, "")
    return hmac.compare_digest(token, provider_session_token())


def make_provider_auth_cookie() -> str:
    secure_flag = "; Secure" if is_production_runtime() else ""
    return (
        f"{AUTH_COOKIE_NAME}={provider_session_token()}; "
        f"Path=/; HttpOnly; SameSite=Lax; Max-Age=43200{secure_flag}"
    )


def make_provider_logout_cookie() -> str:
    secure_flag = "; Secure" if is_production_runtime() else ""
    return f"{AUTH_COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0{secure_flag}"


def authenticate_provider_payload(payload: Mapping[str, object]) -> None:
    if provider_auth_required() and not provider_auth_configured():
        raise ProviderAuthenticationError("Password login belum dikonfigurasi di server.")

    password = str(payload.get("password") or "")
    if not verify_provider_password(password):
        raise ProviderAuthenticationError("Password tidak sesuai.")
