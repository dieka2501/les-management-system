from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Any, Mapping
from urllib import error, request
from urllib.parse import parse_qs, quote, urlencode


DEFAULT_INSTAGRAM_API_VERSION = "v24.0"
INSTAGRAM_SEND_ENDPOINT_TEMPLATE = "https://graph.instagram.com/{version}/{ig_user_id}/messages"


class InstagramWebhookError(Exception):
    """Base error for Instagram webhook integration."""


class InstagramWebhookVerificationError(InstagramWebhookError):
    """Raised when Meta webhook verification fails."""


class InstagramWebhookSignatureError(InstagramWebhookError):
    """Raised when Meta webhook signature is invalid."""


class InstagramSendError(InstagramWebhookError):
    """Raised when sending a reply to Instagram fails."""


@dataclass(frozen=True)
class InstagramMessageEvent:
    sender_id: str
    recipient_id: str
    text: str
    message_id: str | None = None
    timestamp: int | None = None


def instagram_verify_token() -> str | None:
    return os.environ.get("IG_WEBHOOK_VERIFY_TOKEN") or os.environ.get("INSTAGRAM_WEBHOOK_VERIFY_TOKEN")


def instagram_app_secret() -> str | None:
    return os.environ.get("IG_APP_SECRET") or os.environ.get("INSTAGRAM_APP_SECRET")


def instagram_access_token() -> str | None:
    return os.environ.get("IG_ACCESS_TOKEN") or os.environ.get("INSTAGRAM_ACCESS_TOKEN")


def instagram_user_id() -> str | None:
    return os.environ.get("IG_USER_ID") or os.environ.get("INSTAGRAM_USER_ID")


def instagram_api_version() -> str:
    version = os.environ.get("IG_GRAPH_API_VERSION", DEFAULT_INSTAGRAM_API_VERSION).strip()
    return version or DEFAULT_INSTAGRAM_API_VERSION


def instagram_send_enabled() -> bool:
    return os.environ.get("IG_SEND_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}


def instagram_reply_mode(default: str = "rule_based") -> str:
    return os.environ.get("IG_REPLY_MODE", default).strip() or default


def verify_instagram_challenge(query: str | Mapping[str, list[str]]) -> str:
    params = parse_qs(query, keep_blank_values=True) if isinstance(query, str) else query
    mode = first_query_value(params, "hub.mode")
    token = first_query_value(params, "hub.verify_token")
    challenge = first_query_value(params, "hub.challenge")
    expected_token = instagram_verify_token()

    if not expected_token:
        raise InstagramWebhookVerificationError("IG_WEBHOOK_VERIFY_TOKEN belum diset.")
    if mode == "subscribe" and token == expected_token and challenge is not None:
        return challenge
    raise InstagramWebhookVerificationError("Verifikasi webhook Instagram gagal.")


def first_query_value(params: Mapping[str, list[str]], key: str) -> str | None:
    values = params.get(key) or params.get(key.replace(".", "_")) or []
    return values[0] if values else None


def verify_instagram_signature(raw_body: bytes, headers: Mapping[str, str]) -> str:
    app_secret = instagram_app_secret()
    if not app_secret:
        return "skipped_no_app_secret"

    signature = get_header(headers, "x-hub-signature-256")
    if not signature:
        raise InstagramWebhookSignatureError("Header X-Hub-Signature-256 tidak ditemukan.")

    expected = "sha256=" + hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise InstagramWebhookSignatureError("Signature webhook Instagram tidak valid.")
    return "verified"


def get_header(headers: Mapping[str, str], name: str) -> str | None:
    if hasattr(headers, "get"):
        direct = headers.get(name) or headers.get(name.title())
        if direct:
            return direct
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return None


def parse_instagram_webhook_payload(raw_body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise InstagramWebhookError("Payload webhook Instagram bukan JSON valid.") from exc
    if not isinstance(payload, dict):
        raise InstagramWebhookError("Payload webhook Instagram harus berupa object JSON.")
    return payload


def extract_instagram_message_events(payload: dict[str, Any]) -> list[InstagramMessageEvent]:
    events: list[InstagramMessageEvent] = []
    for entry in payload.get("entry", []) or []:
        if not isinstance(entry, dict):
            continue
        for candidate in iter_instagram_message_candidates(entry):
            event = parse_instagram_message_candidate(candidate, entry)
            if event is not None:
                events.append(event)
    return events


def iter_instagram_message_candidates(entry: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for messaging in entry.get("messaging", []) or []:
        if isinstance(messaging, dict):
            candidates.append(messaging)

    for message in entry.get("messages", []) or []:
        if isinstance(message, dict):
            candidates.append(
                {
                    "sender": entry.get("sender") or {},
                    "recipient": entry.get("recipient") or {"id": entry.get("id")},
                    "message": message,
                    "timestamp": entry.get("time"),
                }
            )

    for change in entry.get("changes", []) or []:
        if not isinstance(change, dict):
            continue
        value = change.get("value") or {}
        if not isinstance(value, dict):
            continue

        for messaging in value.get("messaging", []) or []:
            if isinstance(messaging, dict):
                candidates.append(messaging)

        for message in value.get("messages", []) or []:
            if isinstance(message, dict):
                candidate = dict(value)
                candidate["message"] = message
                candidate.setdefault("recipient", {"id": entry.get("id")})
                candidate.setdefault("timestamp", entry.get("time"))
                candidates.append(candidate)

        if any(key in value for key in ("sender", "recipient", "message", "postback", "text")):
            candidate = dict(value)
            candidate.setdefault("recipient", {"id": entry.get("id")})
            candidate.setdefault("timestamp", entry.get("time"))
            candidates.append(candidate)

    return candidates


def parse_instagram_message_candidate(
    candidate: Mapping[str, Any],
    entry: Mapping[str, Any],
) -> InstagramMessageEvent | None:
    message = candidate.get("message") or {}
    if not isinstance(message, dict):
        message = {}

    message_edit = candidate.get("message_edit") or {}
    if not isinstance(message_edit, dict):
        message_edit = {}

    postback = candidate.get("postback") or message.get("postback") or {}
    if not isinstance(postback, dict):
        postback = {}

    if message.get("is_echo") or message_edit.get("is_echo") or candidate.get("is_echo"):
        return None

    text = str(
        message.get("text")
        or message_edit.get("text")
        or candidate.get("text")
        or postback.get("title")
        or postback.get("payload")
        or ""
    ).strip()
    if not text:
        return None

    sender_id = (
        nested_id(candidate.get("sender"))
        or nested_id(message_edit.get("sender"))
        or str(candidate.get("sender_id") or message_edit.get("sender_id") or "").strip()
    )
    recipient_id = (
        nested_id(candidate.get("recipient"))
        or nested_id(message_edit.get("recipient"))
        or str(candidate.get("recipient_id") or "").strip()
        or str(message_edit.get("recipient_id") or "").strip()
        or str(entry.get("id") or "").strip()
    )
    if not sender_id:
        return None

    return InstagramMessageEvent(
        sender_id=sender_id,
        recipient_id=recipient_id,
        text=text,
        message_id=message.get("mid") or message.get("id") or message_edit.get("mid") or message_edit.get("id") or candidate.get("message_id"),
        timestamp=candidate.get("timestamp") or message.get("timestamp") or message_edit.get("timestamp") or entry.get("time"),
    )


def nested_id(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("id") or "").strip()
    return str(value or "").strip()


def summarize_instagram_webhook_payload(payload: dict[str, Any]) -> dict[str, Any]:
    entries = payload.get("entry", []) or []
    if not isinstance(entries, list):
        entries = []

    entry_key_sets: set[str] = set()
    change_fields: set[str] = set()
    messaging_items = 0
    change_items = 0
    candidate_items = 0
    text_candidates = 0
    echo_candidates = 0
    candidate_key_sets: set[str] = set()
    message_key_sets: set[str] = set()
    message_edit_key_sets: set[str] = set()
    postback_key_sets: set[str] = set()
    message_edit_candidates = 0
    attachment_candidates = 0
    read_candidates = 0
    delivery_candidates = 0
    reaction_candidates = 0
    referral_candidates = 0
    missing_sender_candidates = 0
    missing_recipient_candidates = 0

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_key_sets.add(",".join(sorted(str(key) for key in entry.keys())))

        messaging = entry.get("messaging", []) or []
        changes = entry.get("changes", []) or []
        messaging_items += len(messaging) if isinstance(messaging, list) else 0
        change_items += len(changes) if isinstance(changes, list) else 0

        if isinstance(changes, list):
            for change in changes:
                if isinstance(change, dict) and change.get("field"):
                    change_fields.add(str(change["field"]))

        for candidate in iter_instagram_message_candidates(entry):
            candidate_items += 1
            candidate_key_sets.add(",".join(sorted(str(key) for key in candidate.keys())))
            message = candidate.get("message") or {}
            if not isinstance(message, dict):
                message = {}
            if message:
                message_key_sets.add(",".join(sorted(str(key) for key in message.keys())))
            message_edit = candidate.get("message_edit") or {}
            if not isinstance(message_edit, dict):
                message_edit = {}
            if message_edit:
                message_edit_candidates += 1
                message_edit_key_sets.add(",".join(sorted(str(key) for key in message_edit.keys())))
            postback = candidate.get("postback") or message.get("postback") or {}
            if not isinstance(postback, dict):
                postback = {}
            if postback:
                postback_key_sets.add(",".join(sorted(str(key) for key in postback.keys())))
            if message.get("is_echo") or message_edit.get("is_echo") or candidate.get("is_echo"):
                echo_candidates += 1
                continue
            if message.get("text") or message_edit.get("text") or candidate.get("text") or postback.get("title") or postback.get("payload"):
                text_candidates += 1
            if message.get("attachments") or message_edit.get("attachments") or candidate.get("attachments"):
                attachment_candidates += 1
            if candidate.get("read") or message.get("read"):
                read_candidates += 1
            if candidate.get("delivery") or message.get("delivery"):
                delivery_candidates += 1
            if candidate.get("reaction") or message.get("reaction"):
                reaction_candidates += 1
            if candidate.get("referral") or message.get("referral"):
                referral_candidates += 1
            if not (
                nested_id(candidate.get("sender"))
                or nested_id(message_edit.get("sender"))
                or str(candidate.get("sender_id") or message_edit.get("sender_id") or "").strip()
            ):
                missing_sender_candidates += 1
            if not (
                nested_id(candidate.get("recipient"))
                or nested_id(message_edit.get("recipient"))
                or str(candidate.get("recipient_id") or message_edit.get("recipient_id") or "").strip()
                or str(entry.get("id") or "").strip()
            ):
                missing_recipient_candidates += 1

    return {
        "entry_count": len(entries),
        "entry_key_sets": sorted(entry_key_sets),
        "messaging_items": messaging_items,
        "change_items": change_items,
        "change_fields": sorted(change_fields),
        "candidate_items": candidate_items,
        "text_candidates": text_candidates,
        "echo_candidates": echo_candidates,
        "candidate_key_sets": sorted(candidate_key_sets),
        "message_key_sets": sorted(message_key_sets),
        "message_edit_key_sets": sorted(message_edit_key_sets),
        "postback_key_sets": sorted(postback_key_sets),
        "message_edit_candidates": message_edit_candidates,
        "attachment_candidates": attachment_candidates,
        "read_candidates": read_candidates,
        "delivery_candidates": delivery_candidates,
        "reaction_candidates": reaction_candidates,
        "referral_candidates": referral_candidates,
        "missing_sender_candidates": missing_sender_candidates,
        "missing_recipient_candidates": missing_recipient_candidates,
    }


def send_instagram_text_message(
    *,
    recipient_id: str,
    text: str,
    ig_user_id: str | None = None,
    access_token: str | None = None,
) -> dict[str, Any]:
    resolved_ig_user_id = ig_user_id or instagram_user_id()
    resolved_access_token = access_token or instagram_access_token()
    if not resolved_ig_user_id:
        raise InstagramSendError("IG_USER_ID belum diset dan recipient webhook tidak memuat ID akun bisnis.")
    if not resolved_access_token:
        raise InstagramSendError("IG_ACCESS_TOKEN belum diset.")

    endpoint = INSTAGRAM_SEND_ENDPOINT_TEMPLATE.format(
        version=quote(instagram_api_version(), safe="v0123456789."),
        ig_user_id=quote(str(resolved_ig_user_id), safe=""),
    )
    payload = {
        "recipient": {"id": str(recipient_id)},
        "message": {"text": text[:1000]},
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    query = urlencode({"access_token": resolved_access_token})
    api_request = request.Request(
        f"{endpoint}?{query}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(api_request, timeout=20) as response:
            response_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        raise InstagramSendError(f"Instagram Send API gagal ({exc.code}): {extract_meta_error(raw_body)}") from exc
    except error.URLError as exc:
        raise InstagramSendError(f"Tidak bisa menghubungi Instagram Send API: {exc.reason}") from exc
    except TimeoutError as exc:
        raise InstagramSendError("Request ke Instagram Send API timeout.") from exc

    try:
        return json.loads(response_body)
    except json.JSONDecodeError:
        return {"raw": response_body}


def extract_meta_error(raw_body: str) -> str:
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return raw_body[:500] or "Tidak ada detail error."
    message = ((payload.get("error") or {}).get("message")) or raw_body
    return str(message)[:500]
