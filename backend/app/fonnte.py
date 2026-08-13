from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Mapping
from urllib import error, parse, request


FONNTE_SEND_ENDPOINT = "https://api.fonnte.com/send"


class FonnteWebhookError(Exception):
    """Base error for WhatsApp/Fonnte webhook integration."""


class FonnteWebhookSecretError(FonnteWebhookError):
    """Raised when a Fonnte webhook secret does not match."""


class FonnteSendError(FonnteWebhookError):
    """Raised when sending a WhatsApp reply through Fonnte fails."""


@dataclass(frozen=True)
class FonnteMessageEvent:
    sender_number: str
    text: str
    sender_name: str | None = None
    device_identifier: str | None = None
    message_id: str | None = None
    timestamp: str | int | None = None


def _first_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value.strip()
    return ""


def _env_enabled(name: str, default: bool = False) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def fonnte_api_url() -> str:
    return os.environ.get("FONNTE_API_URL", FONNTE_SEND_ENDPOINT).strip() or FONNTE_SEND_ENDPOINT


def fonnte_token() -> str | None:
    return _first_env("FONNTE_TOKEN", "WA_FONNTE_TOKEN", "WHATSAPP_FONNTE_TOKEN") or None


def fonnte_default_country_code() -> str:
    return os.environ.get("FONNTE_DEFAULT_COUNTRY_CODE", "62").strip() or "62"


def fonnte_webhook_secret() -> str | None:
    return _first_env("FONNTE_WEBHOOK_SECRET", "WA_WEBHOOK_SECRET", "WHATSAPP_WEBHOOK_SECRET") or None


def whatsapp_send_enabled() -> bool:
    return (
        _env_enabled("WA_SEND_ENABLED")
        or _env_enabled("WHATSAPP_SEND_ENABLED")
        or _env_enabled("FONNTE_SEND_ENABLED")
    )


def whatsapp_reply_mode(default: str = "rule_based") -> str:
    return _first_env("WA_REPLY_MODE", "WHATSAPP_REPLY_MODE", "FONNTE_REPLY_MODE") or default


def normalize_number(number: str, country_code: str | None = None) -> str:
    resolved_country_code = (country_code or fonnte_default_country_code()).strip() or "62"
    cleaned = re.sub(r"[^\d+]", "", str(number or "").strip())
    if cleaned.startswith("+"):
        return cleaned[1:]

    digits_only = re.sub(r"\D", "", cleaned)
    if digits_only.startswith("0"):
        return f"{resolved_country_code}{digits_only[1:]}"
    return digits_only


def verify_fonnte_secret(query: str | Mapping[str, list[str]]) -> str:
    expected_secret = fonnte_webhook_secret()
    if not expected_secret:
        return "not_configured"

    if isinstance(query, str):
        values = parse.parse_qs(query).get("secret", [])
    else:
        values = query.get("secret", [])
    provided_secret = values[0] if values else None
    if provided_secret != expected_secret:
        raise FonnteWebhookSecretError("Secret webhook Fonnte tidak valid.")
    return "verified"


def parse_fonnte_webhook_payload(raw_body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise FonnteWebhookError("Payload webhook Fonnte bukan JSON valid.") from exc
    if not isinstance(payload, dict):
        raise FonnteWebhookError("Payload webhook Fonnte harus berupa object JSON.")
    return payload


def extract_fonnte_message_events(payload: dict[str, Any]) -> list[FonnteMessageEvent]:
    if not isinstance(payload, dict):
        raise FonnteWebhookError("Payload webhook Fonnte harus berupa object JSON.")

    events: list[FonnteMessageEvent] = []
    for item in iter_fonnte_payload_items(payload):
        if is_outgoing_echo(item):
            continue
        sender_number = extract_first_text(item, ("sender", "from", "number", "phone", "sender_number"))
        message_text = extract_message_text(item)
        if not sender_number or not message_text:
            continue
        events.append(
            FonnteMessageEvent(
                sender_number=normalize_number(sender_number),
                text=message_text,
                sender_name=extract_first_text(item, ("name", "sender_name", "pushName", "push_name")),
                device_identifier=extract_first_text(item, ("device", "device_id", "deviceId", "receiver", "to")),
                message_id=extract_first_text(item, ("id", "message_id", "messageId", "messageid")),
                timestamp=item.get("timestamp") or item.get("time") or item.get("created_at"),
            )
        )
    return events


def iter_fonnte_payload_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key in ("data", "messages", "events"):
        value = payload.get(key)
        if isinstance(value, list):
            items.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            items.append(value)

    if not items:
        items.append(payload)
    return items


def is_outgoing_echo(item: Mapping[str, Any]) -> bool:
    for key in ("fromMe", "from_me", "isFromMe", "is_from_me", "is_echo"):
        value = item.get(key)
        if isinstance(value, bool) and value:
            return True
        if isinstance(value, str) and value.strip().lower() in {"1", "true", "yes"}:
            return True
    return False


def extract_first_text(item: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def extract_message_text(item: Mapping[str, Any]) -> str:
    for key in ("message", "text", "body", "caption", "message_text"):
        value = item.get(key)
        if isinstance(value, dict):
            nested = extract_first_text(value, ("text", "body", "conversation", "caption"))
            if nested:
                return nested
            continue
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def summarize_fonnte_webhook_payload(payload: dict[str, Any]) -> dict[str, Any]:
    items = iter_fonnte_payload_items(payload) if isinstance(payload, dict) else []
    text_candidates = 0
    sender_candidates = 0
    key_sets: list[str] = []
    for item in items:
        if extract_message_text(item):
            text_candidates += 1
        if extract_first_text(item, ("sender", "from", "number", "phone", "sender_number")):
            sender_candidates += 1
        key_sets.append(",".join(sorted(str(key) for key in item.keys())))

    return {
        "item_count": len(items),
        "text_candidates": text_candidates,
        "sender_candidates": sender_candidates,
        "candidate_key_sets": key_sets[:10],
    }


def send_fonnte_text_message(
    *,
    target_number: str,
    text: str,
    auth_token: str | None = None,
    country_code: str | None = None,
    api_url: str | None = None,
) -> dict[str, Any]:
    resolved_token = auth_token or fonnte_token()
    if not resolved_token:
        raise FonnteSendError("FONNTE_TOKEN belum diset.")

    resolved_country_code = country_code or fonnte_default_country_code()
    payload = parse.urlencode(
        {
            "target": normalize_number(target_number, resolved_country_code),
            "message": text,
            "countryCode": resolved_country_code,
        }
    ).encode("utf-8")
    req = request.Request(
        api_url or fonnte_api_url(),
        data=payload,
        headers={
            "Authorization": resolved_token,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise FonnteSendError(f"Fonnte HTTP {exc.code}: {body}") from exc
    except error.URLError as exc:
        raise FonnteSendError(f"Tidak bisa menghubungi Fonnte: {exc.reason}") from exc
    except TimeoutError as exc:
        raise FonnteSendError("Request ke Fonnte timeout.") from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return {"raw_response": body}
    return parsed if isinstance(parsed, dict) else {"response": parsed}
