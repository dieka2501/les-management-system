from __future__ import annotations

import json
import hmac
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from .provider_auth import (
    ProviderAuthenticationError,
    authenticate_provider_payload,
    is_provider_authenticated,
    make_provider_auth_cookie,
    make_provider_logout_cookie,
    provider_auth_required,
)
from .store import (
    LesStore,
    NotFoundError,
    ValidationError,
    safe_instagram_webhook_log_result,
    safe_whatsapp_webhook_log_result,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = PROJECT_ROOT / "frontend" / "static"
PROVIDER_ROOT = PROJECT_ROOT / "frontend" / "provider"
PUBLIC_API_PATHS = {
    "/api/client/auth",
    "/api/client/login",
    "/api/client/logout",
    "/api/provider/auth",
    "/api/provider/login",
    "/api/provider/logout",
    "/api/agent/context",
    "/api/v1/webhooks/fonnte",
}
PROTECTED_DASHBOARD_PATHS = {"", "/", "/index.html"}
FONNTE_WEBHOOK_PATHS = {"/webhooks/fonnte", "/api/v1/webhooks/fonnte"}


def is_protected_api_path(path: str) -> bool:
    return path.startswith("/api/") and path not in PUBLIC_API_PATHS


def is_protected_dashboard_path(path: str) -> bool:
    return path in PROTECTED_DASHBOARD_PATHS


def normalize_client_api_path(path: str) -> str:
    client_aliases = {
        "/api/client/auth",
        "/api/client/login",
        "/api/client/logout",
        "/api/client/chatbot-knowledge",
        "/api/client/chat-simulations",
        "/api/client/chat-simulations/faq-script",
        "/api/client/chat-simulations/training-examples",
    }
    if path in client_aliases or path.startswith("/api/client/chat-simulations/"):
        return path.replace("/api/client/", "/api/provider/", 1)
    return path


def safe_next_path(raw_next: str | None, fallback: str) -> str:
    next_path = str(raw_next or "").strip()
    if next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return fallback


def safe_next_path_from_query(query: str, fallback: str) -> str:
    values = parse_qs(query).get("next", [])
    return safe_next_path(values[0] if values else None, fallback)


def instagram_raw_webhook_debug_enabled() -> bool:
    return os.environ.get("IG_DEBUG_RAW_WEBHOOK", "0").strip().lower() in {"1", "true", "yes", "on"}


def agent_context_token() -> str:
    return (
        os.environ.get("AGENT_CONTEXT_TOKEN")
        or os.environ.get("UAT_CONTEXT_API_TOKEN")
        or os.environ.get("MCP_CONTEXT_TOKEN")
        or ""
    ).strip()


def agent_context_request_token(headers: object) -> str:
    header_get = getattr(headers, "get", lambda _key, _default=None: "")
    authorization = str(header_get("Authorization", "") or "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return str(header_get("X-Agent-Context-Token", "") or "").strip()


def instagram_raw_webhook_debug_max_chars() -> int | None:
    raw_value = os.environ.get("IG_DEBUG_RAW_WEBHOOK_MAX_CHARS", "20000").strip()
    try:
        value = int(raw_value)
    except ValueError:
        return 20000
    return value if value > 0 else None


def instagram_raw_webhook_debug_text(raw_body: bytes) -> str:
    text = raw_body.decode("utf-8", errors="replace")
    max_chars = instagram_raw_webhook_debug_max_chars()
    if max_chars is not None and len(text) > max_chars:
        return f"{text[:max_chars]}...<truncated {len(text) - max_chars} chars>"
    return text


def user_error_message(prefix: str, detail: str | None = None) -> str:
    detail = str(detail or "").strip()
    if not detail:
        return prefix
    if detail.rstrip(".!?") == prefix.rstrip(".!?") or detail.startswith(prefix):
        return detail
    return f"{prefix} {detail}"


class LesRequestHandler(BaseHTTPRequestHandler):
    store: LesStore

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        api_path = normalize_client_api_path(path)
        try:
            if is_protected_api_path(path):
                self.require_provider_api_auth()

            if api_path == "/api/dashboard-data":
                self.send_json(self.store.dashboard_data())
            elif api_path == "/api/agent/context":
                self.require_agent_context_auth()
                self.send_json(self.store.agent_context_snapshot())
            elif api_path in FONNTE_WEBHOOK_PATHS:
                secret_status = self.store.verify_whatsapp_webhook_secret(parsed.query)
                self.send_json(
                    {
                        "status": "ok",
                        "message": "Fonnte webhook endpoint is ready.",
                        "method": "GET",
                        "secret": secret_status,
                    }
                )
            elif api_path == "/webhooks/instagram":
                challenge = self.store.verify_instagram_webhook_challenge(parsed.query)
                self.send_text(challenge)
            elif api_path == "/api/summary":
                self.send_json(self.store.summary())
            elif api_path == "/api/subjects":
                self.send_json({"items": self.store.list_subjects()})
            elif api_path == "/api/branches":
                self.send_json({"items": self.store.list_branches()})
            elif api_path == "/api/parents":
                self.send_json({"items": self.store.list_parents()})
            elif api_path == "/api/students":
                self.send_json({"items": self.store.list_students()})
            elif api_path == "/api/tutors":
                self.send_json({"items": self.store.list_tutors()})
            elif api_path == "/api/schedules":
                self.send_json({"items": self.store.list_schedules()})
            elif api_path == "/api/registrations":
                self.send_json({"items": self.store.list_registrations()})
            elif api_path == "/api/provider/auth":
                self.send_json(
                    {
                        "authenticated": self.is_provider_authenticated(),
                        "auth_required": provider_auth_required(),
                    }
                )
            elif api_path == "/api/provider/chat-simulations":
                self.require_provider_api_auth()
                self.send_json({"items": self.store.list_provider_chat_simulation_sessions()})
            elif api_path == "/api/provider/chatbot-knowledge":
                self.require_provider_api_auth()
                self.send_json(self.store.provider_chatbot_knowledge())
            elif api_path == "/api/provider/chat-simulations/faq-script":
                self.require_provider_api_auth()
                self.send_json(self.store.provider_chat_simulation_faq_script())
            elif api_path == "/api/provider/chat-simulations/training-examples":
                self.require_provider_api_auth()
                self.send_json({"items": self.store.list_provider_chat_training_examples()})
            elif api_path.startswith("/api/provider/chat-simulations/"):
                self.require_provider_api_auth()
                session_id = self.parse_provider_chat_simulation_id(api_path)
                self.send_json(self.store.get_provider_chat_simulation_session(session_id))
            elif path in {"/client/login", "/provider/login"}:
                next_path = safe_next_path_from_query(parsed.query, "/client/chatbot")
                if self.is_provider_authenticated():
                    self.send_redirect(next_path)
                else:
                    self.serve_provider_file("login.html")
            elif path in {
                "/client",
                "/client/",
                "/client/chatbot",
                "/client/chatbot/",
                "/provider",
                "/provider/",
                "/provider/chat-simulations",
                "/provider/chat-simulations/",
            }:
                if self.require_provider_page_auth(path):
                    self.serve_provider_file("chat-simulations/index.html")
            elif path.startswith("/client/assets/"):
                if self.require_provider_page_auth(path):
                    self.serve_provider_file(path.removeprefix("/client/"))
            elif path.startswith("/provider/assets/"):
                if self.require_provider_page_auth(path):
                    self.serve_provider_file(path.removeprefix("/provider/"))
            elif is_protected_dashboard_path(path):
                if self.require_provider_page_auth(path or "/"):
                    self.serve_static(path)
            else:
                self.serve_static(path)
        except Exception as exc:
            self.handle_exception(exc)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        api_path = normalize_client_api_path(path)
        try:
            if api_path in FONNTE_WEBHOOK_PATHS:
                secret_status = self.store.verify_whatsapp_webhook_secret(parsed.query)
                raw_body = self.read_raw_body()
                result = self.store.handle_whatsapp_raw_webhook(raw_body, secret_status=secret_status)
                print(
                    "Fonnte webhook processed: "
                    f"{json.dumps(safe_whatsapp_webhook_log_result(result), ensure_ascii=False)}"
                )
                self.send_json({"status": "ok", **result})
                return

            if api_path == "/webhooks/instagram":
                raw_body = self.read_raw_body()
                raw_debug_enabled = instagram_raw_webhook_debug_enabled()
                if raw_debug_enabled:
                    print(f"Instagram webhook raw payload debug: {instagram_raw_webhook_debug_text(raw_body)}")
                result = self.store.handle_instagram_webhook(raw_body, self.headers)
                log_result = result if raw_debug_enabled else safe_instagram_webhook_log_result(result)
                print(
                    "Instagram webhook processed: "
                    f"{json.dumps(log_result, ensure_ascii=False)}"
                )
                self.send_text("EVENT_RECEIVED")
                return

            if is_protected_api_path(path):
                self.require_provider_api_auth()

            data = self.read_json_body()
            if api_path == "/api/provider/login":
                authenticate_provider_payload(data)
                self.send_json(
                    {
                        "authenticated": True,
                        "auth_required": provider_auth_required(),
                    },
                    headers={"Set-Cookie": make_provider_auth_cookie()},
                )
            elif api_path == "/api/provider/logout":
                self.send_json(
                    {"authenticated": False},
                    headers={"Set-Cookie": make_provider_logout_cookie()},
                )
            elif api_path == "/api/branches":
                self.send_json(self.store.create_branch(data), HTTPStatus.CREATED)
            elif api_path == "/api/subjects":
                self.send_json(self.store.create_subject(data), HTTPStatus.CREATED)
            elif api_path == "/api/parents":
                self.send_json(self.store.create_parent(data), HTTPStatus.CREATED)
            elif api_path == "/api/students":
                self.send_json(self.store.create_student(data), HTTPStatus.CREATED)
            elif api_path == "/api/tutors":
                self.send_json(self.store.create_tutor(data), HTTPStatus.CREATED)
            elif api_path == "/api/schedules":
                self.send_json(self.store.create_schedule(data), HTTPStatus.CREATED)
            elif api_path == "/api/schedules/generate":
                self.send_json(self.store.generate_schedule_candidates(data))
            elif api_path == "/api/schedules/confirm":
                self.send_json(self.store.confirm_generated_schedule(data), HTTPStatus.CREATED)
            elif api_path == "/api/provider/chat-simulations":
                self.require_provider_api_auth()
                self.send_json(self.store.create_provider_chat_simulation_session(data), HTTPStatus.CREATED)
            elif self.is_provider_chat_simulation_action_path(api_path, "manual-reply"):
                self.require_provider_api_auth()
                session_id = self.parse_provider_chat_simulation_action_path(api_path, "manual-reply")
                self.send_json(self.store.send_provider_chat_manual_reply(session_id, data), HTTPStatus.CREATED)
            elif api_path.startswith("/api/provider/chat-simulations/"):
                self.require_provider_api_auth()
                session_id = self.parse_provider_chat_simulation_message_path(api_path)
                self.send_json(self.store.send_provider_chat_simulation_message(session_id, data), HTTPStatus.CREATED)
            else:
                self.send_error_json(HTTPStatus.NOT_FOUND, "Endpoint tidak ditemukan.")
        except Exception as exc:
            self.handle_exception(exc)

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        api_path = normalize_client_api_path(path)
        try:
            if is_protected_api_path(path):
                self.require_provider_api_auth()
            data = self.read_json_body()
            if self.is_provider_chat_simulation_action_path(api_path, "supervision"):
                session_id = self.parse_provider_chat_simulation_action_path(api_path, "supervision")
                self.send_json(self.store.update_provider_chat_supervision(session_id, data))
                return
            if api_path.startswith("/api/provider/chat-simulations/"):
                session_id, message_id = self.parse_provider_chat_simulation_message_update_path(api_path)
                self.send_json(self.store.update_provider_chat_simulation_message(session_id, message_id, data))
                return

            resource, item_id = self.parse_resource_id(api_path)
            if resource == "branches":
                self.send_json(self.store.update_branch(item_id, data))
            elif resource == "subjects":
                self.send_json(self.store.update_subject(item_id, data))
            elif resource == "parents":
                self.send_json(self.store.update_parent(item_id, data))
            elif resource == "students":
                self.send_json(self.store.update_student(item_id, data))
            elif resource == "tutors":
                self.send_json(self.store.update_tutor(item_id, data))
            elif resource == "schedules":
                self.send_json(self.store.update_schedule(item_id, data))
            else:
                self.send_error_json(HTTPStatus.NOT_FOUND, "Endpoint tidak ditemukan.")
        except Exception as exc:
            self.handle_exception(exc)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        api_path = normalize_client_api_path(path)
        try:
            if is_protected_api_path(path):
                self.require_provider_api_auth()

            resource, item_id = self.parse_resource_id(api_path)
            if resource == "branches":
                self.send_json(self.store.archive_branch(item_id))
            elif resource == "subjects":
                self.send_json(self.store.archive_subject(item_id))
            elif resource == "parents":
                self.send_json(self.store.archive_parent(item_id))
            elif resource == "students":
                self.send_json(self.store.archive_student(item_id))
            elif resource == "tutors":
                self.send_json(self.store.archive_tutor(item_id))
            elif resource == "schedules":
                self.send_json(self.store.cancel_schedule(item_id))
            else:
                self.send_error_json(HTTPStatus.NOT_FOUND, "Endpoint tidak ditemukan.")
        except Exception as exc:
            self.handle_exception(exc)

    def is_provider_authenticated(self) -> bool:
        return is_provider_authenticated(self.headers.get("Cookie"))

    def require_provider_api_auth(self) -> None:
        if not self.is_provider_authenticated():
            raise ProviderAuthenticationError("Login admin dibutuhkan.")

    def require_agent_context_auth(self) -> None:
        expected_token = agent_context_token()
        if not expected_token:
            raise PermissionError("AGENT_CONTEXT_TOKEN belum dikonfigurasi di server.")
        provided_token = agent_context_request_token(self.headers)
        if not provided_token or not hmac.compare_digest(provided_token, expected_token):
            raise PermissionError("Token agent context tidak valid.")

    def require_provider_page_auth(self, requested_path: str) -> bool:
        if self.is_provider_authenticated():
            return True
        next_path = quote(requested_path or "/client/chatbot", safe="/")
        self.send_redirect(f"/client/login?next={next_path}")
        return False

    def parse_resource_id(self, path: str) -> tuple[str, int]:
        parts = [part for part in path.split("/") if part]
        if len(parts) != 3 or parts[0] != "api":
            raise NotFoundError("Endpoint tidak ditemukan.")
        try:
            return parts[1], int(parts[2])
        except ValueError as exc:
            raise ValidationError("ID harus berupa angka.") from exc

    def parse_provider_chat_simulation_id(self, path: str) -> int:
        parts = [part for part in path.split("/") if part]
        if len(parts) != 4 or parts[:3] != ["api", "provider", "chat-simulations"]:
            raise NotFoundError("Endpoint simulasi percakapan tidak ditemukan.")
        try:
            return int(parts[3])
        except ValueError as exc:
            raise ValidationError("ID simulasi wajib berupa angka.") from exc

    def parse_provider_chat_simulation_message_path(self, path: str) -> int:
        parts = [part for part in path.split("/") if part]
        expected_prefix = ["api", "provider", "chat-simulations"]
        if len(parts) != 5 or parts[:3] != expected_prefix or parts[4] != "messages":
            raise NotFoundError("Endpoint simulasi percakapan tidak ditemukan.")
        try:
            return int(parts[3])
        except ValueError as exc:
            raise ValidationError("ID simulasi wajib berupa angka.") from exc

    def parse_provider_chat_simulation_message_update_path(self, path: str) -> tuple[int, int]:
        parts = [part for part in path.split("/") if part]
        expected_prefix = ["api", "provider", "chat-simulations"]
        if len(parts) != 6 or parts[:3] != expected_prefix or parts[4] != "messages":
            raise NotFoundError("Endpoint update respons simulasi tidak ditemukan.")
        try:
            return int(parts[3]), int(parts[5])
        except ValueError as exc:
            raise ValidationError("ID simulasi dan pesan wajib berupa angka.") from exc

    def is_provider_chat_simulation_action_path(self, path: str, action: str) -> bool:
        parts = [part for part in path.split("/") if part]
        return len(parts) == 5 and parts[:3] == ["api", "provider", "chat-simulations"] and parts[4] == action

    def parse_provider_chat_simulation_action_path(self, path: str, action: str) -> int:
        if not self.is_provider_chat_simulation_action_path(path, action):
            raise NotFoundError("Endpoint aksi percakapan tidak ditemukan.")
        try:
            return int([part for part in path.split("/") if part][3])
        except ValueError as exc:
            raise ValidationError("ID simulasi wajib berupa angka.") from exc

    def read_json_body(self) -> dict:
        raw_body = self.read_raw_body()
        if not raw_body:
            return {}
        try:
            return json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError("Body JSON tidak valid.") from exc

    def read_raw_body(self) -> bytes:
        content_length = int(self.headers.get("Content-Length") or 0)
        if content_length == 0:
            return b""
        return self.rfile.read(content_length)

    def serve_static(self, path: str) -> None:
        if path in {"", "/"}:
            file_path = STATIC_ROOT / "index.html"
            if not file_path.exists():
                self.send_redirect("/client/chatbot")
                return
        else:
            file_path = (STATIC_ROOT / path.lstrip("/")).resolve()
            if STATIC_ROOT.resolve() not in file_path.parents and file_path != STATIC_ROOT.resolve():
                self.send_error_json(HTTPStatus.FORBIDDEN, "Akses file tidak diizinkan.")
                return
            if file_path.exists() and file_path.is_dir():
                file_path = file_path / "index.html"

        if not file_path.exists() or not file_path.is_file():
            self.send_error_json(HTTPStatus.NOT_FOUND, "Halaman tidak ditemukan.")
            return

        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
        }.get(file_path.suffix, "application/octet-stream")
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_provider_file(self, relative_path: str) -> None:
        file_path = (PROVIDER_ROOT / relative_path).resolve()
        if PROVIDER_ROOT.resolve() not in file_path.parents and file_path != PROVIDER_ROOT.resolve():
            self.send_error_json(HTTPStatus.FORBIDDEN, "Akses file admin tidak diizinkan.")
            return

        if not file_path.exists() or not file_path.is_file():
            self.send_error_json(HTTPStatus.NOT_FOUND, "Halaman admin tidak ditemukan.")
            return

        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
        }.get(file_path.suffix, "application/octet-stream")
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(
        self,
        payload: dict | list,
        status: HTTPStatus = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status: HTTPStatus, message: str) -> None:
        self.send_json({"error": message, "message": message, "status": status.value}, status)

    def send_text(
        self,
        payload: str,
        status: HTTPStatus = HTTPStatus.OK,
        content_type: str = "text/plain; charset=utf-8",
    ) -> None:
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_redirect(self, location: str) -> None:
        body = f"Redirecting to {location}".encode("utf-8")
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_exception(self, exc: Exception) -> None:
        if isinstance(exc, ValidationError):
            self.send_error_json(HTTPStatus.BAD_REQUEST, user_error_message("Input belum valid.", str(exc)))
        elif isinstance(exc, ValueError):
            self.send_error_json(HTTPStatus.BAD_REQUEST, user_error_message("Input belum valid.", str(exc)))
        elif isinstance(exc, ProviderAuthenticationError):
            self.send_error_json(HTTPStatus.UNAUTHORIZED, user_error_message("Login admin dibutuhkan.", str(exc)))
        elif isinstance(exc, NotFoundError):
            self.send_error_json(HTTPStatus.NOT_FOUND, user_error_message("Data tidak ditemukan.", str(exc)))
        elif isinstance(exc, PermissionError):
            self.send_error_json(HTTPStatus.FORBIDDEN, user_error_message("Akses ditolak.", str(exc)))
        else:
            print(f"Unexpected error: {exc!r}")
            self.send_error_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "Terjadi gangguan pada sistem. Coba ulangi beberapa saat lagi atau hubungi teknis jika masih gagal.",
            )


def create_server(host: str = "127.0.0.1", port: int = 8000, seed_demo: bool = False) -> ThreadingHTTPServer:
    store = LesStore()
    if seed_demo:
        store.seed_demo_data()
    LesRequestHandler.store = store
    return ThreadingHTTPServer((host, port), LesRequestHandler)


def is_railway_runtime() -> bool:
    return bool(
        os.environ.get("RAILWAY_ENVIRONMENT")
        or os.environ.get("RAILWAY_SERVICE_ID")
        or os.environ.get("RAILWAY_PROJECT_ID")
    )


def parse_host_value(raw_host: str | None) -> tuple[str | None, int | None]:
    value = str(raw_host or "").strip()
    if not value:
        return None, None

    parsed = urlparse(value if "://" in value else f"//{value}")
    host = parsed.hostname or value
    port = parsed.port
    return host, port


def default_host() -> str:
    if is_railway_runtime():
        return "0.0.0.0"

    host, _ = parse_host_value(os.environ.get("HOST"))
    return host or "127.0.0.1"


def default_port() -> int:
    if os.environ.get("PORT"):
        return int(os.environ["PORT"])

    _, host_port = parse_host_value(os.environ.get("HOST"))
    return host_port or 8000


def main() -> None:
    host = default_host()
    port = default_port()
    seed_demo = os.environ.get("LES_SEED_DEMO", "0") == "1"
    server = create_server(host, port, seed_demo)
    print(f"Les Management System running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer dihentikan.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
