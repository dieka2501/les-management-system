from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .store import LesStore, NotFoundError, ValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = PROJECT_ROOT / "frontend" / "static"


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
            else:
                self.serve_static(path)
        except Exception as exc:
            self.handle_exception(exc)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        data = self.read_json_body()
        try:
            if path == "/api/branches":
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
            else:
                self.send_error_json(HTTPStatus.NOT_FOUND, "Endpoint tidak ditemukan.")
        except Exception as exc:
            self.handle_exception(exc)

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        data = self.read_json_body()
        try:
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

    def parse_resource_id(self, path: str) -> tuple[str, int]:
        parts = [part for part in path.split("/") if part]
        if len(parts) != 3 or parts[0] != "api":
            raise NotFoundError("Endpoint tidak ditemukan.")
        try:
            return parts[1], int(parts[2])
        except ValueError as exc:
            raise ValidationError("ID harus berupa angka.") from exc

    def read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length") or 0)
        if content_length == 0:
            return {}
        raw_body = self.rfile.read(content_length)
        try:
            return json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError("Body JSON tidak valid.") from exc

    def serve_static(self, path: str) -> None:
        if path in {"", "/"}:
            file_path = STATIC_ROOT / "index.html"
        else:
            file_path = (STATIC_ROOT / path.lstrip("/")).resolve()
            if STATIC_ROOT.resolve() not in file_path.parents and file_path != STATIC_ROOT.resolve():
                self.send_error_json(HTTPStatus.FORBIDDEN, "Akses file tidak diizinkan.")
                return

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

    def send_json(self, payload: dict | list, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status: HTTPStatus, message: str) -> None:
        self.send_json({"error": message}, status)

    def handle_exception(self, exc: Exception) -> None:
        if isinstance(exc, ValidationError):
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        elif isinstance(exc, NotFoundError):
            self.send_error_json(HTTPStatus.NOT_FOUND, str(exc))
        else:
            print(f"Unexpected error: {exc!r}")
            self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, "Terjadi error internal.")


def create_server(host: str = "127.0.0.1", port: int = 8000, seed_demo: bool = False) -> ThreadingHTTPServer:
    store = LesStore()
    if seed_demo:
        store.seed_demo_data()
    LesRequestHandler.store = store
    return ThreadingHTTPServer((host, port), LesRequestHandler)


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
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
