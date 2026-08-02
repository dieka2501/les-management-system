from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlparse

from .provider_auth import (
    ProviderAuthenticationError,
    authenticate_provider_payload,
    is_provider_authenticated,
    make_provider_auth_cookie,
    make_provider_logout_cookie,
    provider_auth_required,
)
from .store import LesStore, NotFoundError, ValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = PROJECT_ROOT / "frontend" / "static"
PROVIDER_ROOT = PROJECT_ROOT / "frontend" / "provider"


class LesRequestHandler(BaseHTTPRequestHandler):
    store: LesStore

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/dashboard-data":
                self.send_json(self.store.dashboard_data())
            elif path == "/webhooks/instagram":
                challenge = self.store.verify_instagram_webhook_challenge(parsed.query)
                self.send_text(challenge)
            elif path == "/api/summary":
                self.send_json(self.store.summary())
            elif path == "/api/subjects":
                self.send_json({"items": self.store.list_subjects()})
            elif path == "/api/branches":
                self.send_json({"items": self.store.list_branches()})
            elif path == "/api/parents":
                self.send_json({"items": self.store.list_parents()})
            elif path == "/api/students":
                self.send_json({"items": self.store.list_students()})
            elif path == "/api/tutors":
                self.send_json({"items": self.store.list_tutors()})
            elif path == "/api/schedules":
                self.send_json({"items": self.store.list_schedules()})
            elif path == "/api/registrations":
                self.send_json({"items": self.store.list_registrations()})
            elif path == "/api/provider/auth":
                self.send_json(
                    {
                        "authenticated": self.is_provider_authenticated(),
                        "auth_required": provider_auth_required(),
                    }
                )
            elif path == "/api/provider/chat-simulations":
                self.require_provider_api_auth()
                self.send_json({"items": self.store.list_provider_chat_simulation_sessions()})
            elif path == "/api/provider/chatbot-knowledge":
                self.require_provider_api_auth()
                self.send_json(self.store.provider_chatbot_knowledge())
            elif path == "/api/provider/chat-simulations/faq-script":
                self.require_provider_api_auth()
                self.send_json(self.store.provider_chat_simulation_faq_script())
            elif path == "/api/provider/chat-simulations/training-examples":
                self.require_provider_api_auth()
                self.send_json({"items": self.store.list_provider_chat_training_examples()})
            elif path.startswith("/api/provider/chat-simulations/"):
                self.require_provider_api_auth()
                session_id = self.parse_provider_chat_simulation_id(path)
                self.send_json(self.store.get_provider_chat_simulation_session(session_id))
            elif path == "/provider/login":
                if self.is_provider_authenticated():
                    self.send_redirect("/provider/chat-simulations")
                else:
                    self.serve_provider_file("login.html")
            elif path in {"/provider", "/provider/", "/provider/chat-simulations", "/provider/chat-simulations/"}:
                if self.require_provider_page_auth(path):
                    self.serve_provider_file("chat-simulations/index.html")
            elif path.startswith("/provider/assets/"):
                if self.require_provider_page_auth(path):
                    self.serve_provider_file(path.removeprefix("/provider/"))
            else:
                self.serve_static(path)
        except Exception as exc:
            self.handle_exception(exc)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/webhooks/instagram":
                raw_body = self.read_raw_body()
                result = self.store.handle_instagram_webhook(raw_body, self.headers)
                print(f"Instagram webhook processed: {json.dumps(result, ensure_ascii=False)}")
                self.send_text("EVENT_RECEIVED")
                return

            data = self.read_json_body()
            if path == "/api/provider/login":
                authenticate_provider_payload(data)
                self.send_json(
                    {
                        "authenticated": True,
                        "auth_required": provider_auth_required(),
                    },
                    headers={"Set-Cookie": make_provider_auth_cookie()},
                )
            elif path == "/api/provider/logout":
                self.send_json(
                    {"authenticated": False},
                    headers={"Set-Cookie": make_provider_logout_cookie()},
                )
            elif path == "/api/branches":
                self.send_json(self.store.create_branch(data), HTTPStatus.CREATED)
            elif path == "/api/parents":
                self.send_json(self.store.create_parent(data), HTTPStatus.CREATED)
            elif path == "/api/students":
                self.send_json(self.store.create_student(data), HTTPStatus.CREATED)
            elif path == "/api/tutors":
                self.send_json(self.store.create_tutor(data), HTTPStatus.CREATED)
            elif path == "/api/schedules":
                self.send_json(self.store.create_schedule(data), HTTPStatus.CREATED)
            elif path == "/api/schedules/generate":
                self.send_json(self.store.generate_schedule_candidates(data))
            elif path == "/api/schedules/confirm":
                self.send_json(self.store.confirm_generated_schedule(data), HTTPStatus.CREATED)
            elif path == "/api/provider/chat-simulations":
                self.require_provider_api_auth()
                self.send_json(self.store.create_provider_chat_simulation_session(data), HTTPStatus.CREATED)
            elif path.startswith("/api/provider/chat-simulations/"):
                self.require_provider_api_auth()
                session_id = self.parse_provider_chat_simulation_message_path(path)
                self.send_json(self.store.send_provider_chat_simulation_message(session_id, data), HTTPStatus.CREATED)
            else:
                self.send_error_json(HTTPStatus.NOT_FOUND, "Endpoint tidak ditemukan.")
        except Exception as exc:
            self.handle_exception(exc)

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        try:
            if path.startswith("/api/provider/"):
                self.require_provider_api_auth()
            data = self.read_json_body()
            if path.startswith("/api/provider/chat-simulations/"):
                session_id, message_id = self.parse_provider_chat_simulation_message_update_path(path)
                self.send_json(self.store.update_provider_chat_simulation_message(session_id, message_id, data))
                return

            resource, item_id = self.parse_resource_id(path)
            if resource == "branches":
                self.send_json(self.store.update_branch(item_id, data))
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
        try:
            resource, item_id = self.parse_resource_id(path)
            if resource == "branches":
                self.send_json(self.store.archive_branch(item_id))
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
            raise ProviderAuthenticationError("Login provider dibutuhkan.")

    def require_provider_page_auth(self, requested_path: str) -> bool:
        if self.is_provider_authenticated():
            return True
        next_path = quote(requested_path or "/provider/chat-simulations", safe="/")
        self.send_redirect(f"/provider/login?next={next_path}")
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
                self.send_redirect("/provider/chat-simulations")
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
            self.send_error_json(HTTPStatus.FORBIDDEN, "Akses file provider tidak diizinkan.")
            return

        if not file_path.exists() or not file_path.is_file():
            self.send_error_json(HTTPStatus.NOT_FOUND, "Halaman provider tidak ditemukan.")
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
        self.send_json({"error": message}, status)

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
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        elif isinstance(exc, ProviderAuthenticationError):
            self.send_error_json(HTTPStatus.UNAUTHORIZED, str(exc))
        elif isinstance(exc, NotFoundError):
            self.send_error_json(HTTPStatus.NOT_FOUND, str(exc))
        elif isinstance(exc, PermissionError):
            self.send_error_json(HTTPStatus.FORBIDDEN, str(exc))
        else:
            print(f"Unexpected error: {exc!r}")
            self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, "Terjadi error internal.")


def create_server(host: str = "127.0.0.1", port: int = 8000, seed_demo: bool = False) -> ThreadingHTTPServer:
    store = LesStore()
    if seed_demo:
        store.seed_demo_data()
    LesRequestHandler.store = store
    return ThreadingHTTPServer((host, port), LesRequestHandler)


def default_host() -> str:
    if os.environ.get("HOST"):
        return os.environ["HOST"]
    if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_SERVICE_ID"):
        return "0.0.0.0"
    return "127.0.0.1"


def main() -> None:
    host = default_host()
    port = int(os.environ.get("PORT", "8000"))
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
