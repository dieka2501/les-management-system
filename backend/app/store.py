from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .chat_simulation import (
    FAQ_SIMULATION_SCRIPT,
    SimulationReply,
    chat_lifecycle_reply,
    load_chatbot_knowledge,
    maybe_add_close_prompt,
    normalize_text,
    simulate_provider_reply,
)
from .database import connect, migrate, seed_master_data
from .fonnte import (
    FonnteMessageEvent,
    FonnteSendError,
    FonnteWebhookError,
    FonnteWebhookSecretError,
    extract_fonnte_message_events,
    parse_fonnte_webhook_payload,
    send_fonnte_text_message,
    summarize_fonnte_webhook_payload,
    verify_fonnte_secret,
    whatsapp_reply_mode,
    whatsapp_send_enabled,
)
from .gemini_chatbot import GeminiConfigurationError, GeminiServiceError, simulate_provider_ai_reply
from .instagram_webhook import (
    InstagramMessageEvent,
    InstagramMessageFetchError,
    InstagramSendError,
    InstagramWebhookError,
    InstagramWebhookSignatureError,
    extract_instagram_message_events,
    extract_instagram_message_detail_references,
    fetch_instagram_message_detail,
    instagram_message_detail_diagnostic,
    instagram_message_detail_to_event,
    instagram_raw_webhook_debug_enabled,
    instagram_reply_mode,
    instagram_send_enabled,
    instagram_user_id,
    raw_instagram_fetch_error,
    parse_instagram_webhook_payload,
    safe_instagram_fetch_error,
    send_instagram_text_message,
    summarize_instagram_webhook_payload,
    verify_instagram_challenge,
    verify_instagram_signature,
)
from .scheduling import (
    DAY_NAMES,
    contains_range,
    format_time,
    normalize_day,
    parse_time,
    ranges_overlap,
    validate_time_range,
)


ACTIVE_SCHEDULE_STATUSES = ("draft", "active")


class ValidationError(Exception):
    """Raised when user-facing validation fails."""


class NotFoundError(Exception):
    """Raised when a requested row does not exist."""


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def safe_instagram_webhook_log_result(result: dict[str, Any]) -> dict[str, Any]:
    safe_results = []
    for item in result.get("results", []) or []:
        if not isinstance(item, dict):
            continue
        send_result = item.get("send_result") if isinstance(item.get("send_result"), dict) else {}
        safe_results.append(
            {
                "status": item.get("status", "processed"),
                "reply_mode": item.get("reply_mode"),
                "intent": item.get("intent"),
                "stage": item.get("stage"),
                "sent": bool(item.get("sent")),
                "send": {
                    "enabled": bool(send_result.get("enabled")),
                    "sent": bool(send_result.get("sent")),
                    "has_error": bool(send_result.get("error")),
                },
            }
        )

    return {
        "object": result.get("object"),
        "signature": result.get("signature"),
        "events_received": result.get("events_received"),
        "diagnostics": result.get("diagnostics"),
        "message_detail_fetch": result.get("message_detail_fetch"),
        "results": safe_results,
    }


def safe_whatsapp_webhook_log_result(result: dict[str, Any]) -> dict[str, Any]:
    safe_results = []
    for item in result.get("results", []) or []:
        if not isinstance(item, dict):
            continue
        send_result = item.get("send_result") if isinstance(item.get("send_result"), dict) else {}
        safe_results.append(
            {
                "status": item.get("status", "processed"),
                "reply_mode": item.get("reply_mode"),
                "intent": item.get("intent"),
                "stage": item.get("stage"),
                "sent": bool(item.get("sent")),
                "send": {
                    "enabled": bool(send_result.get("enabled")),
                    "sent": bool(send_result.get("sent")),
                    "has_error": bool(send_result.get("error")),
                },
            }
        )

    return {
        "source": result.get("source"),
        "secret": result.get("secret"),
        "events_received": result.get("events_received"),
        "diagnostics": result.get("diagnostics"),
        "results": safe_results,
    }


def filter_instagram_payload_for_target_user(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    target_user_id = str(instagram_user_id() or "").strip()
    if not target_user_id:
        return payload, {"enabled": False}

    entries = payload.get("entry", []) or []
    if not isinstance(entries, list):
        entries = []

    filtered_entries = [
        entry for entry in entries if isinstance(entry, dict) and str(entry.get("id") or "").strip() == target_user_id
    ]
    filtered_payload = dict(payload)
    filtered_payload["entry"] = filtered_entries

    return filtered_payload, {
        "enabled": True,
        "target_user_configured": True,
        "entry_count_before_filter": len(entries),
        "entry_count_after_filter": len(filtered_entries),
        "ignored_entries": len(entries) - len(filtered_entries),
    }


def coerce_int(value: Any, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} wajib berupa angka.") from exc


def require_text(data: dict[str, Any], field_name: str, label: str) -> str:
    value = str(data.get(field_name, "")).strip()
    if not value:
        raise ValidationError(f"{label} wajib diisi.")
    return value


def optional_text(data: dict[str, Any], field_name: str) -> str | None:
    value = str(data.get(field_name, "")).strip()
    return value or None


class LesStore:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = db_path
        with connect(self.db_path) as conn:
            migrate(conn)

    def connection(self) -> sqlite3.Connection:
        return connect(self.db_path)

    def seed_master_data(self) -> None:
        with self.connection() as conn:
            seed_master_data(conn)
            conn.commit()

    def seed_demo_data(self) -> None:
        self.seed_master_data()
        with self.connection() as conn:
            if conn.execute("SELECT COUNT(*) FROM parents").fetchone()[0] > 0:
                return

            tasik_branch_id = self.branch_by_code("CBG-0001")["id"]
            bandung_branch_id = self.branch_by_code("CBG-0003")["id"]
            parent_id = self.create_parent(
                {
                    "branch_id": tasik_branch_id,
                    "full_name": "Ibu Rina Kusuma",
                    "email": "rina@example.test",
                    "phone": "081200001122",
                    "address": "Jl. Merpati No. 10",
                }
            )["id"]
            math_id = self.subject_by_name("Matematika")["id"]
            english_id = self.subject_by_name("Bahasa Inggris")["id"]
            science_id = self.subject_by_name("IPA")["id"]

            student_id = self.create_student(
                {
                    "branch_id": tasik_branch_id,
                    "parent_id": parent_id,
                    "full_name": "Raka Putra",
                    "birthplace": "Bandung",
                    "birthdate": "2015-05-12",
                    "gender": "Laki-laki",
                    "subject_ids": [math_id],
                    "notes": "Preferensi belajar sore setelah jam 16.00.",
                }
            )["id"]
            self.create_student(
                {
                    "branch_id": tasik_branch_id,
                    "parent_id": parent_id,
                    "full_name": "Dina Putri",
                    "birthplace": "Bandung",
                    "birthdate": "2017-08-03",
                    "gender": "Perempuan",
                    "subject_ids": [english_id],
                    "notes": "Butuh latihan conversation ringan.",
                }
            )

            tutor_id = self.create_tutor(
                {
                    "branch_id": tasik_branch_id,
                    "full_name": "Bu Sari",
                    "birthdate": "1994-04-20",
                    "gender": "Perempuan",
                    "education": "S1 Pendidikan Matematika",
                    "subject_ids": [math_id, science_id],
                    "availabilities": [
                        {"day_of_week": 0, "start_time": "15:00", "end_time": "19:00"},
                        {"day_of_week": 1, "start_time": "15:00", "end_time": "19:00"},
                        {"day_of_week": 3, "start_time": "15:00", "end_time": "19:00"},
                    ],
                }
            )["id"]
            self.create_tutor(
                {
                    "branch_id": bandung_branch_id,
                    "full_name": "Pak Dimas",
                    "birthdate": "1990-09-01",
                    "gender": "Laki-laki",
                    "education": "S1 Sastra Inggris",
                    "subject_ids": [english_id],
                    "availabilities": [
                        {"day_of_week": 1, "start_time": "13:00", "end_time": "18:00"},
                        {"day_of_week": 5, "start_time": "09:00", "end_time": "15:00"},
                    ],
                }
            )
            self.create_schedule(
                {
                    "branch_id": tasik_branch_id,
                    "student_id": student_id,
                    "tutor_id": tutor_id,
                    "subject_id": math_id,
                    "day_of_week": 0,
                    "start_time": "16:00",
                    "end_time": "17:30",
                    "mode": "online",
                    "starts_on": date.today().isoformat(),
                    "ends_on": (date.today() + timedelta(days=90)).isoformat(),
                    "notes": "Demo jadwal aktif.",
                }
            )

    def dashboard_data(self) -> dict[str, Any]:
        return {
            "summary": self.summary(),
            "parents": self.list_parents(),
            "students": self.list_students(),
            "tutors": self.list_tutors(),
            "subjects": self.list_subjects(),
            "branches": self.list_branches(),
            "schedules": self.list_schedules(),
            "registrations": self.list_registrations(),
            "day_names": DAY_NAMES,
        }

    def summary(self) -> dict[str, int]:
        with self.connection() as conn:
            return {
                "parents": conn.execute("SELECT COUNT(*) FROM parents WHERE status = 'active'").fetchone()[0],
                "students": conn.execute("SELECT COUNT(*) FROM students WHERE status = 'active'").fetchone()[0],
                "tutors": conn.execute("SELECT COUNT(*) FROM tutors WHERE status = 'active'").fetchone()[0],
                "subjects": conn.execute("SELECT COUNT(*) FROM subjects WHERE status = 'active'").fetchone()[0],
                "schedules": conn.execute(
                    "SELECT COUNT(*) FROM schedules WHERE status IN ('draft', 'active')"
                ).fetchone()[0],
                "branches": conn.execute("SELECT COUNT(*) FROM branches WHERE status = 'active'").fetchone()[0],
                "registrations": conn.execute(
                    "SELECT COUNT(*) FROM registrations WHERE status IN ('new', 'review')"
                ).fetchone()[0],
            }

    def next_code(self, conn: sqlite3.Connection, table: str, prefix: str) -> str:
        row = conn.execute(
            f"SELECT code FROM {table} WHERE code LIKE ? ORDER BY id DESC LIMIT 1",
            (f"{prefix}-%",),
        ).fetchone()
        if not row:
            return f"{prefix}-0001"
        last_number = int(row["code"].rsplit("-", 1)[-1])
        return f"{prefix}-{last_number + 1:04d}"

    def list_branches(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            return rows_to_dicts(
                conn.execute(
                    "SELECT * FROM branches WHERE status = 'active' ORDER BY city, name"
                ).fetchall()
            )

    def default_branch_id(self, conn: sqlite3.Connection) -> int:
        row = conn.execute(
            "SELECT id FROM branches WHERE status = 'active' ORDER BY id LIMIT 1"
        ).fetchone()
        if row is None:
            raise ValidationError("Cabang belum tersedia.")
        return int(row["id"])

    def branch_by_code(self, code: str) -> dict[str, Any]:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM branches WHERE code = ?", (code,)).fetchone()
            if row is None:
                raise NotFoundError(f"Cabang {code!r} tidak ditemukan.")
            return dict(row)

    def get_branch(self, branch_id: int, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        owns_connection = conn is None
        conn = conn or self.connection()
        try:
            row = conn.execute(
                "SELECT * FROM branches WHERE id = ? AND status = 'active'",
                (branch_id,),
            ).fetchone()
            if row is None:
                raise NotFoundError("Cabang tidak ditemukan atau tidak aktif.")
            return dict(row)
        finally:
            if owns_connection:
                conn.close()

    def branch_id_from_data(
        self,
        data: dict[str, Any],
        conn: sqlite3.Connection,
        fallback: int | None = None,
    ) -> int:
        raw_value = data.get("branch_id") or fallback or self.default_branch_id(conn)
        branch_id = coerce_int(raw_value, "Cabang")
        self.get_branch(branch_id, conn)
        return branch_id

    def create_branch(self, data: dict[str, Any]) -> dict[str, Any]:
        name = require_text(data, "name", "Nama cabang")
        address = require_text(data, "address", "Alamat cabang")
        city = require_text(data, "city", "Kota/Kabupaten")
        with self.connection() as conn:
            code = self.next_code(conn, "branches", "CBG")
            cursor = conn.execute(
                """
                INSERT INTO branches (code, name, address, city)
                VALUES (?, ?, ?, ?)
                """,
                (code, name, address, city),
            )
            conn.commit()
            return self.get_branch(cursor.lastrowid)

    def update_branch(self, branch_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self.get_branch(branch_id)
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE branches
                SET name = COALESCE(NULLIF(?, ''), name),
                    address = COALESCE(NULLIF(?, ''), address),
                    city = COALESCE(NULLIF(?, ''), city),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    str(data.get("name", "")).strip(),
                    str(data.get("address", "")).strip(),
                    str(data.get("city", "")).strip(),
                    branch_id,
                ),
            )
            conn.commit()
            return self.get_branch(branch_id)

    def archive_branch(self, branch_id: int) -> dict[str, Any]:
        self.get_branch(branch_id)
        with self.connection() as conn:
            active_schedule_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM schedules
                WHERE branch_id = ? AND status IN ('draft', 'active')
                """,
                (branch_id,),
            ).fetchone()[0]
            if active_schedule_count:
                raise ValidationError("Cabang masih memiliki jadwal aktif, tidak bisa diarsipkan.")
            conn.execute(
                "UPDATE branches SET status = 'archived', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (branch_id,),
            )
            conn.commit()
        return {"id": branch_id, "status": "archived"}

    def list_subjects(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            return rows_to_dicts(
                conn.execute(
                    "SELECT * FROM subjects WHERE status = 'active' ORDER BY name"
                ).fetchall()
            )

    def create_subject(self, data: dict[str, Any]) -> dict[str, Any]:
        name = require_text(data, "name", "Nama mata pelajaran")
        description = optional_text(data, "description")
        with self.connection() as conn:
            code = self.next_code(conn, "subjects", "MAP")
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO subjects (code, name, description)
                    VALUES (?, ?, ?)
                    """,
                    (code, name, description),
                )
            except sqlite3.IntegrityError as exc:
                raise ValidationError("Nama mata pelajaran sudah digunakan.") from exc
            conn.commit()
            return self.get_subject(cursor.lastrowid)

    def update_subject(self, subject_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self.get_subject(subject_id)
        with self.connection() as conn:
            try:
                conn.execute(
                    """
                    UPDATE subjects
                    SET name = COALESCE(NULLIF(?, ''), name),
                        description = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (str(data.get("name", "")).strip(), optional_text(data, "description"), subject_id),
                )
            except sqlite3.IntegrityError as exc:
                raise ValidationError("Nama mata pelajaran sudah digunakan.") from exc
            conn.commit()
        return self.get_subject(subject_id)

    def archive_subject(self, subject_id: int) -> dict[str, Any]:
        self.get_subject(subject_id)
        with self.connection() as conn:
            active_schedule_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM schedules
                WHERE subject_id = ?
                  AND status IN ('draft', 'active')
                """,
                (subject_id,),
            ).fetchone()[0]
            if active_schedule_count:
                raise ValidationError("Mata pelajaran masih dipakai jadwal aktif, tidak bisa diarsipkan.")
            conn.execute(
                "UPDATE subjects SET status = 'archived', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (subject_id,),
            )
            conn.commit()
        return {"id": subject_id, "status": "archived"}

    def subject_by_name(self, name: str) -> dict[str, Any]:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM subjects WHERE name = ?", (name,)).fetchone()
            if row is None:
                raise NotFoundError(f"Mata pelajaran {name!r} tidak ditemukan.")
            return dict(row)

    def get_subject(self, subject_id: int, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        owns_connection = conn is None
        conn = conn or self.connection()
        try:
            row = conn.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,)).fetchone()
            if row is None:
                raise NotFoundError("Mata pelajaran tidak ditemukan.")
            return dict(row)
        finally:
            if owns_connection:
                conn.close()

    def create_parent(self, data: dict[str, Any]) -> dict[str, Any]:
        full_name = require_text(data, "full_name", "Nama orang tua")
        phone = require_text(data, "phone", "Nomor telepon")
        with self.connection() as conn:
            branch_id = self.branch_id_from_data(data, conn)
            code = self.next_code(conn, "parents", "ORT")
            cursor = conn.execute(
                """
                INSERT INTO parents (code, branch_id, full_name, email, phone, address)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (code, branch_id, full_name, optional_text(data, "email"), phone, optional_text(data, "address")),
            )
            conn.commit()
            return self.get_parent(cursor.lastrowid)

    def list_parents(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT p.*,
                       b.name AS branch_name,
                       b.city AS branch_city,
                       COUNT(s.id) AS student_count
                FROM parents p
                JOIN branches b ON b.id = p.branch_id
                LEFT JOIN students s ON s.parent_id = p.id AND s.status != 'archived'
                WHERE p.status != 'archived'
                GROUP BY p.id
                ORDER BY p.id DESC
                """
            ).fetchall()
            return rows_to_dicts(rows)

    def get_parent(self, parent_id: int) -> dict[str, Any]:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT p.*,
                       b.name AS branch_name,
                       b.city AS branch_city
                FROM parents p
                JOIN branches b ON b.id = p.branch_id
                WHERE p.id = ?
                """,
                (parent_id,),
            ).fetchone()
            if row is None:
                raise NotFoundError("Orang tua tidak ditemukan.")
            return dict(row)

    def update_parent(self, parent_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self.get_parent(parent_id)
        with self.connection() as conn:
            branch_id = None
            if str(data.get("branch_id", "")).strip():
                branch_id = self.branch_id_from_data(data, conn)
            conn.execute(
                """
                UPDATE parents
                SET branch_id = COALESCE(?, branch_id),
                    full_name = COALESCE(NULLIF(?, ''), full_name),
                    email = ?,
                    phone = COALESCE(NULLIF(?, ''), phone),
                    address = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    branch_id,
                    str(data.get("full_name", "")).strip(),
                    optional_text(data, "email"),
                    str(data.get("phone", "")).strip(),
                    optional_text(data, "address"),
                    parent_id,
                ),
            )
            conn.commit()
        return self.get_parent(parent_id)

    def archive_parent(self, parent_id: int) -> dict[str, Any]:
        self.get_parent(parent_id)
        with self.connection() as conn:
            conn.execute(
                "UPDATE parents SET status = 'archived', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (parent_id,),
            )
            conn.commit()
        return {"id": parent_id, "status": "archived"}

    def create_student(self, data: dict[str, Any]) -> dict[str, Any]:
        parent_id = coerce_int(data.get("parent_id"), "Orang tua")
        full_name = require_text(data, "full_name", "Nama murid")
        subject_ids = self.normalize_subject_ids(data.get("subject_ids"))
        with self.connection() as conn:
            parent = self.ensure_parent_exists(parent_id, conn)
            branch_id = self.branch_id_from_data(data, conn, parent["branch_id"])
            code = self.next_code(conn, "students", "ANK")
            cursor = conn.execute(
                """
                INSERT INTO students (code, branch_id, parent_id, full_name, birthplace, birthdate, gender, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    code,
                    branch_id,
                    parent_id,
                    full_name,
                    optional_text(data, "birthplace"),
                    optional_text(data, "birthdate"),
                    optional_text(data, "gender"),
                    optional_text(data, "notes"),
                ),
            )
            student_id = cursor.lastrowid
            self.replace_student_subjects(conn, student_id, subject_ids)
            conn.commit()
            return self.get_student(student_id)

    def list_students(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT s.*,
                       p.full_name AS parent_name,
                       b.name AS branch_name,
                       b.city AS branch_city,
                       GROUP_CONCAT(sub.name, ', ') AS subjects
                FROM students s
                JOIN parents p ON p.id = s.parent_id
                JOIN branches b ON b.id = s.branch_id
                LEFT JOIN student_subjects ss ON ss.student_id = s.id
                LEFT JOIN subjects sub ON sub.id = ss.subject_id
                WHERE s.status != 'archived'
                GROUP BY s.id
                ORDER BY s.id DESC
                """
            ).fetchall()
            return rows_to_dicts(rows)

    def get_student(self, student_id: int, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        owns_connection = conn is None
        conn = conn or self.connection()
        try:
            row = conn.execute(
                """
                SELECT s.*,
                       p.full_name AS parent_name,
                       b.name AS branch_name,
                       b.city AS branch_city,
                       GROUP_CONCAT(sub.name, ', ') AS subjects
                FROM students s
                JOIN parents p ON p.id = s.parent_id
                JOIN branches b ON b.id = s.branch_id
                LEFT JOIN student_subjects ss ON ss.student_id = s.id
                LEFT JOIN subjects sub ON sub.id = ss.subject_id
                WHERE s.id = ?
                GROUP BY s.id
                """,
                (student_id,),
            ).fetchone()
            if row is None:
                raise NotFoundError("Murid tidak ditemukan.")
            result = dict(row)
            result["subject_ids"] = [
                item["subject_id"]
                for item in conn.execute(
                    "SELECT subject_id FROM student_subjects WHERE student_id = ? ORDER BY subject_id",
                    (student_id,),
                ).fetchall()
            ]
            return result
        finally:
            if owns_connection:
                conn.close()

    def update_student(self, student_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self.get_student(student_id)
        with self.connection() as conn:
            branch_id = None
            if "parent_id" in data:
                self.ensure_parent_exists(coerce_int(data["parent_id"], "Orang tua"), conn)
            if str(data.get("branch_id", "")).strip():
                branch_id = self.branch_id_from_data(data, conn)
            conn.execute(
                """
                UPDATE students
                SET branch_id = COALESCE(?, branch_id),
                    parent_id = COALESCE(?, parent_id),
                    full_name = COALESCE(NULLIF(?, ''), full_name),
                    birthplace = ?,
                    birthdate = ?,
                    gender = ?,
                    notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    branch_id,
                    data.get("parent_id"),
                    str(data.get("full_name", "")).strip(),
                    optional_text(data, "birthplace"),
                    optional_text(data, "birthdate"),
                    optional_text(data, "gender"),
                    optional_text(data, "notes"),
                    student_id,
                ),
            )
            if "subject_ids" in data:
                self.replace_student_subjects(conn, student_id, self.normalize_subject_ids(data.get("subject_ids")))
            conn.commit()
        return self.get_student(student_id)

    def archive_student(self, student_id: int) -> dict[str, Any]:
        self.get_student(student_id)
        with self.connection() as conn:
            conn.execute(
                "UPDATE students SET status = 'archived', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (student_id,),
            )
            conn.execute(
                "UPDATE schedules SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP WHERE student_id = ?",
                (student_id,),
            )
            conn.commit()
        return {"id": student_id, "status": "archived"}

    def create_tutor(self, data: dict[str, Any]) -> dict[str, Any]:
        full_name = require_text(data, "full_name", "Nama guru")
        subject_ids = self.normalize_subject_ids(data.get("subject_ids"))
        if not subject_ids:
            raise ValidationError("Guru wajib memiliki minimal satu mata pelajaran.")
        availabilities = self.normalize_availabilities(data.get("availabilities"))
        with self.connection() as conn:
            branch_id = self.branch_id_from_data(data, conn)
            code = self.next_code(conn, "tutors", "GR")
            cursor = conn.execute(
                """
                INSERT INTO tutors (code, branch_id, full_name, birthdate, gender, education, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    code,
                    branch_id,
                    full_name,
                    optional_text(data, "birthdate"),
                    optional_text(data, "gender"),
                    optional_text(data, "education"),
                    optional_text(data, "notes"),
                ),
            )
            tutor_id = cursor.lastrowid
            self.replace_tutor_subjects(conn, tutor_id, subject_ids)
            self.replace_tutor_availabilities(conn, tutor_id, availabilities)
            conn.commit()
            return self.get_tutor(tutor_id)

    def list_tutors(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT t.*,
                       b.name AS branch_name,
                       b.city AS branch_city,
                       GROUP_CONCAT(DISTINCT sub.name) AS subjects
                FROM tutors t
                JOIN branches b ON b.id = t.branch_id
                LEFT JOIN tutor_subjects ts ON ts.tutor_id = t.id
                LEFT JOIN subjects sub ON sub.id = ts.subject_id
                WHERE t.status != 'archived'
                GROUP BY t.id
                ORDER BY t.id DESC
                """
            ).fetchall()
            tutors = rows_to_dicts(rows)
            for tutor in tutors:
                tutor["availabilities"] = self.list_tutor_availabilities(tutor["id"], conn)
            return tutors

    def get_tutor(self, tutor_id: int, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        owns_connection = conn is None
        conn = conn or self.connection()
        try:
            row = conn.execute(
                """
                SELECT t.*,
                       b.name AS branch_name,
                       b.city AS branch_city
                FROM tutors t
                JOIN branches b ON b.id = t.branch_id
                WHERE t.id = ?
                """,
                (tutor_id,),
            ).fetchone()
            if row is None:
                raise NotFoundError("Guru tidak ditemukan.")
            result = dict(row)
            result["subject_ids"] = [
                item["subject_id"]
                for item in conn.execute(
                    "SELECT subject_id FROM tutor_subjects WHERE tutor_id = ? ORDER BY subject_id",
                    (tutor_id,),
                ).fetchall()
            ]
            result["subjects"] = ", ".join(
                item["name"]
                for item in conn.execute(
                    """
                    SELECT sub.name
                    FROM tutor_subjects ts
                    JOIN subjects sub ON sub.id = ts.subject_id
                    WHERE ts.tutor_id = ?
                    ORDER BY sub.name
                    """,
                    (tutor_id,),
                ).fetchall()
            )
            result["availabilities"] = self.list_tutor_availabilities(tutor_id, conn)
            return result
        finally:
            if owns_connection:
                conn.close()

    def update_tutor(self, tutor_id: int, data: dict[str, Any]) -> dict[str, Any]:
        self.get_tutor(tutor_id)
        with self.connection() as conn:
            branch_id = None
            if str(data.get("branch_id", "")).strip():
                branch_id = self.branch_id_from_data(data, conn)
            conn.execute(
                """
                UPDATE tutors
                SET branch_id = COALESCE(?, branch_id),
                    full_name = COALESCE(NULLIF(?, ''), full_name),
                    birthdate = ?,
                    gender = ?,
                    education = ?,
                    notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    branch_id,
                    str(data.get("full_name", "")).strip(),
                    optional_text(data, "birthdate"),
                    optional_text(data, "gender"),
                    optional_text(data, "education"),
                    optional_text(data, "notes"),
                    tutor_id,
                ),
            )
            if "subject_ids" in data:
                subject_ids = self.normalize_subject_ids(data.get("subject_ids"))
                if not subject_ids:
                    raise ValidationError("Guru wajib memiliki minimal satu mata pelajaran.")
                self.replace_tutor_subjects(conn, tutor_id, subject_ids)
            if "availabilities" in data:
                self.replace_tutor_availabilities(
                    conn, tutor_id, self.normalize_availabilities(data.get("availabilities"))
                )
            conn.commit()
        return self.get_tutor(tutor_id)

    def archive_tutor(self, tutor_id: int) -> dict[str, Any]:
        self.get_tutor(tutor_id)
        with self.connection() as conn:
            conn.execute(
                "UPDATE tutors SET status = 'archived', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (tutor_id,),
            )
            conn.commit()
        return {"id": tutor_id, "status": "archived"}

    def list_tutor_availabilities(
        self, tutor_id: int, conn: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        owns_connection = conn is None
        conn = conn or self.connection()
        try:
            rows = conn.execute(
                "SELECT * FROM tutor_availabilities WHERE tutor_id = ? ORDER BY day_of_week, start_time",
                (tutor_id,),
            ).fetchall()
            result = rows_to_dicts(rows)
            for row in result:
                row["day_name"] = DAY_NAMES[row["day_of_week"]]
            return result
        finally:
            if owns_connection:
                conn.close()

    def create_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        with self.connection() as conn:
            schedule = self.normalize_schedule_input(data, conn)
            self.validate_schedule_slot(conn, schedule)
            code = self.next_code(conn, "schedules", "JDL")
            cursor = conn.execute(
                """
                INSERT INTO schedules (
                    code, branch_id, student_id, tutor_id, subject_id, day_of_week,
                    start_time, end_time, starts_on, ends_on, mode, location, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    code,
                    schedule["branch_id"],
                    schedule["student_id"],
                    schedule["tutor_id"],
                    schedule["subject_id"],
                    schedule["day_of_week"],
                    schedule["start_time"],
                    schedule["end_time"],
                    schedule.get("starts_on"),
                    schedule.get("ends_on"),
                    schedule.get("mode") or "online",
                    schedule.get("location"),
                    schedule.get("notes"),
                ),
            )
            conn.commit()
            return self.get_schedule(cursor.lastrowid)

    def list_schedules(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT sc.*,
                       st.full_name AS student_name,
                       tu.full_name AS tutor_name,
                       sub.name AS subject_name,
                       b.name AS branch_name,
                       b.city AS branch_city
                FROM schedules sc
                JOIN students st ON st.id = sc.student_id
                JOIN tutors tu ON tu.id = sc.tutor_id
                JOIN subjects sub ON sub.id = sc.subject_id
                JOIN branches b ON b.id = sc.branch_id
                WHERE sc.status != 'cancelled'
                ORDER BY sc.day_of_week, sc.start_time
                """
            ).fetchall()
            result = rows_to_dicts(rows)
            for row in result:
                row["day_name"] = DAY_NAMES[row["day_of_week"]]
            return result

    def get_schedule(self, schedule_id: int) -> dict[str, Any]:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT sc.*,
                       st.full_name AS student_name,
                       tu.full_name AS tutor_name,
                       sub.name AS subject_name,
                       b.name AS branch_name,
                       b.city AS branch_city
                FROM schedules sc
                JOIN students st ON st.id = sc.student_id
                JOIN tutors tu ON tu.id = sc.tutor_id
                JOIN subjects sub ON sub.id = sc.subject_id
                JOIN branches b ON b.id = sc.branch_id
                WHERE sc.id = ?
                """,
                (schedule_id,),
            ).fetchone()
            if row is None:
                raise NotFoundError("Jadwal tidak ditemukan.")
            result = dict(row)
            result["day_name"] = DAY_NAMES[result["day_of_week"]]
            return result

    def update_schedule(self, schedule_id: int, data: dict[str, Any]) -> dict[str, Any]:
        existing = self.get_schedule(schedule_id)
        with self.connection() as conn:
            merged = {**existing, **data}
            schedule = self.normalize_schedule_input(merged, conn)
            self.validate_schedule_slot(conn, schedule, exclude_schedule_id=schedule_id)
            conn.execute(
                """
                UPDATE schedules
                SET branch_id = ?,
                    student_id = ?,
                    tutor_id = ?,
                    subject_id = ?,
                    day_of_week = ?,
                    start_time = ?,
                    end_time = ?,
                    starts_on = ?,
                    ends_on = ?,
                    mode = ?,
                    location = ?,
                    notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    schedule["branch_id"],
                    schedule["student_id"],
                    schedule["tutor_id"],
                    schedule["subject_id"],
                    schedule["day_of_week"],
                    schedule["start_time"],
                    schedule["end_time"],
                    schedule.get("starts_on"),
                    schedule.get("ends_on"),
                    schedule.get("mode") or "online",
                    schedule.get("location"),
                    schedule.get("notes"),
                    schedule_id,
                ),
            )
            conn.commit()
        return self.get_schedule(schedule_id)

    def cancel_schedule(self, schedule_id: int) -> dict[str, Any]:
        self.get_schedule(schedule_id)
        with self.connection() as conn:
            conn.execute(
                "UPDATE schedules SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (schedule_id,),
            )
            conn.commit()
        return {"id": schedule_id, "status": "cancelled"}

    def generate_schedule_candidates(self, data: dict[str, Any]) -> dict[str, Any]:
        student_id = coerce_int(data.get("student_id"), "Murid")
        subject_id = coerce_int(data.get("subject_id"), "Mata pelajaran")
        sessions_per_week = max(1, min(7, coerce_int(data.get("sessions_per_week", 1), "Jumlah sesi")))
        duration_minutes = max(30, min(240, coerce_int(data.get("duration_minutes", 90), "Durasi sesi")))
        preferred_days = [normalize_day(day) for day in data.get("preferred_days", [0, 1, 2, 3, 4, 5])]
        preferred_start = data.get("preferred_start") or "08:00"
        preferred_end = data.get("preferred_end") or "20:00"
        validate_time_range(preferred_start, preferred_end)
        tutor_id = data.get("tutor_id")
        starts_on = data.get("starts_on") or date.today().isoformat()
        ends_on = data.get("ends_on") or (date.today() + timedelta(days=90)).isoformat()
        mode = data.get("mode") or "online"
        location = data.get("location")

        with self.connection() as conn:
            student = self.get_student(student_id, conn)
            subject = self.get_subject(subject_id, conn)
            branch_id = self.branch_id_from_data(data, conn, student["branch_id"])
            branch = self.get_branch(branch_id, conn)
            if branch_id != student["branch_id"]:
                raise ValidationError("Cabang generator harus sama dengan cabang murid.")
            self.ensure_student_has_subject(conn, student_id, subject_id)
            tutors = self.find_eligible_tutors(conn, subject_id, branch_id, tutor_id)
            candidates: list[dict[str, Any]] = []
            for tutor in tutors:
                slots = self.find_available_slots_for_tutor(
                    conn,
                    branch_id=branch_id,
                    student_id=student_id,
                    tutor_id=tutor["id"],
                    subject_id=subject_id,
                    preferred_days=preferred_days,
                    preferred_start=preferred_start,
                    preferred_end=preferred_end,
                    duration_minutes=duration_minutes,
                    starts_on=starts_on,
                    ends_on=ends_on,
                    mode=mode,
                    location=location,
                )
                selected = self.select_slots(slots, sessions_per_week)
                if len(selected) >= sessions_per_week:
                    candidates.append(
                        {
                            "candidate_id": f"cand-{tutor['id']}",
                            "tutor_id": tutor["id"],
                            "tutor_name": tutor["full_name"],
                            "branch_id": branch_id,
                            "branch_name": branch["name"],
                            "branch_city": branch["city"],
                            "subject_id": subject_id,
                            "subject_name": subject["name"],
                            "student_id": student_id,
                            "student_name": student["full_name"],
                            "slots": selected,
                            "reason": (
                                f"{tutor['full_name']} sesuai mata pelajaran {subject['name']} "
                                f"di {branch['name']} dan memiliki slot kosong sesuai preferensi."
                            ),
                            "warnings": [],
                        }
                    )

            return {
                "input": {
                    "student_id": student_id,
                    "student_name": student["full_name"],
                    "branch_id": branch_id,
                    "branch_name": branch["name"],
                    "branch_city": branch["city"],
                    "subject_id": subject_id,
                    "subject_name": subject["name"],
                    "sessions_per_week": sessions_per_week,
                    "duration_minutes": duration_minutes,
                    "preferred_days": preferred_days,
                    "preferred_start": preferred_start,
                    "preferred_end": preferred_end,
                    "starts_on": starts_on,
                    "ends_on": ends_on,
                    "mode": mode,
                    "location": location,
                },
                "candidates": candidates,
                "message": (
                    "Kandidat jadwal ditemukan."
                    if candidates
                    else "Belum ada kandidat jadwal tanpa bentrok. Coba longgarkan hari/jam atau tambah availability guru."
                ),
            }

    def confirm_generated_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        slots = data.get("slots") or []
        if not slots:
            raise ValidationError("Tidak ada slot yang dikonfirmasi.")
        saved: list[dict[str, Any]] = []
        with self.connection() as conn:
            normalized_slots = [self.normalize_schedule_input(slot, conn) for slot in slots]
            self.validate_new_slots_do_not_conflict_each_other(normalized_slots)
            for slot in normalized_slots:
                self.validate_schedule_slot(conn, slot)
            for slot in normalized_slots:
                code = self.next_code(conn, "schedules", "JDL")
                cursor = conn.execute(
                    """
                    INSERT INTO schedules (
                        code, branch_id, student_id, tutor_id, subject_id, day_of_week,
                        start_time, end_time, starts_on, ends_on, mode, location, notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        code,
                        slot["branch_id"],
                        slot["student_id"],
                        slot["tutor_id"],
                        slot["subject_id"],
                        slot["day_of_week"],
                        slot["start_time"],
                        slot["end_time"],
                        slot.get("starts_on"),
                        slot.get("ends_on"),
                        slot.get("mode") or "online",
                        slot.get("location"),
                        slot.get("notes"),
                    ),
                )
                saved.append({"id": cursor.lastrowid, "code": code})
            conn.commit()

        return {"saved": [self.get_schedule(item["id"]) for item in saved]}

    def list_registrations(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT r.*,
                       b.name AS branch_name,
                       b.city AS branch_city
                FROM registrations r
                JOIN branches b ON b.id = r.branch_id
                ORDER BY r.id DESC
                LIMIT 20
                """
            ).fetchall()
            return rows_to_dicts(rows)

    def list_provider_chat_simulation_sessions(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT s.*,
                       COUNT(m.id) AS message_count,
                       MAX(m.created_at) AS last_message_at
                FROM provider_chat_simulation_sessions s
                LEFT JOIN provider_chat_simulation_messages m ON m.session_id = s.id
                GROUP BY s.id
                ORDER BY s.id DESC
                LIMIT 50
                """
            ).fetchall()
            return rows_to_dicts(rows)

    def provider_chat_simulation_faq_script(self) -> dict[str, Any]:
        return {"items": FAQ_SIMULATION_SCRIPT}

    def provider_chatbot_knowledge(self) -> dict[str, Any]:
        return load_chatbot_knowledge()

    def create_provider_chat_simulation_session(self, data: dict[str, Any]) -> dict[str, Any]:
        title = str(data.get("title") or "Simulasi knowledge base Rumah Privat Madani").strip()
        if not title:
            raise ValidationError("Judul simulasi wajib diisi.")
        with self.connection() as conn:
            code = self.next_code(conn, "provider_chat_simulation_sessions", "SIM")
            cursor = conn.execute(
                """
                INSERT INTO provider_chat_simulation_sessions (code, title, channel, source)
                VALUES (?, ?, 'provider', 'knowledge_base')
                """,
                (code, title),
            )
            session_id = cursor.lastrowid
            if data.get("seed_from_faq"):
                self.insert_provider_chat_simulation_faq_script(conn, session_id)
                conn.execute(
                    """
                    UPDATE provider_chat_simulation_sessions
                    SET current_stage = 'knowledge_seeded', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (session_id,),
                )
            conn.commit()
        return self.get_provider_chat_simulation_session(session_id)

    def get_provider_chat_simulation_session(self, session_id: int) -> dict[str, Any]:
        with self.connection() as conn:
            session = self.get_provider_chat_simulation_session_row(conn, session_id)
            session["messages"] = self.list_provider_chat_simulation_messages(conn, session_id)
            return session

    def send_provider_chat_simulation_message(self, session_id: int, data: dict[str, Any]) -> dict[str, Any]:
        message = require_text(data, "message", "Pesan simulasi")
        reply_mode = self.normalize_provider_chat_reply_mode(data.get("mode") or data.get("reply_mode"))
        with self.connection() as conn:
            self.get_provider_chat_simulation_session_row(conn, session_id)
            history = self.list_provider_chat_simulation_messages(conn, session_id)
            try:
                lifecycle_reply = chat_lifecycle_reply(normalize_text(message), history)
                db_reply = None if lifecycle_reply else self.find_provider_chat_training_override(conn, message)
                if lifecycle_reply:
                    reply = lifecycle_reply
                elif db_reply:
                    reply = maybe_add_close_prompt(db_reply, history)
                else:
                    reply = (
                        simulate_provider_ai_reply(message, history)
                        if reply_mode == "gemini"
                        else simulate_provider_reply(message, history)
                    )
            except (GeminiConfigurationError, GeminiServiceError) as exc:
                raise ValidationError(str(exc)) from exc
            turn_index = self.next_provider_chat_turn_index(conn, session_id)
            metadata = {"training_tags": reply.training_tags, "reply_mode": reply_mode}
            parent_message = self.insert_provider_chat_simulation_message(
                conn,
                session_id=session_id,
                turn_index=turn_index,
                role="parent",
                message=message,
                intent=reply.intent,
                expected_reply=reply.message,
                matched_reference=reply.matched_reference,
                confidence=reply.confidence,
                needs_review=reply.needs_review,
                metadata=metadata,
            )
            assistant_message = self.insert_provider_chat_simulation_message(
                conn,
                session_id=session_id,
                turn_index=turn_index,
                role="assistant",
                message=reply.message,
                intent=reply.intent,
                expected_reply=reply.message,
                matched_reference=reply.matched_reference,
                confidence=reply.confidence,
                needs_review=reply.needs_review,
                metadata=metadata,
            )
            conn.execute(
                """
                UPDATE provider_chat_simulation_sessions
                SET current_stage = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (reply.stage, session_id),
            )
            conn.commit()
        return {
            "parent_message": parent_message,
            "assistant_message": assistant_message,
            "reply": reply.to_dict(),
            "session": self.get_provider_chat_simulation_session(session_id),
        }

    def normalize_provider_chat_reply_mode(self, value: Any) -> str:
        mode = str(value or "rule_based").strip().lower().replace("-", "_")
        aliases = {
            "rule": "rule_based",
            "rules": "rule_based",
            "rule_based": "rule_based",
            "simulator": "rule_based",
            "gemini": "gemini",
            "gemini_ai": "gemini",
            "ai": "gemini",
        }
        if mode not in aliases:
            raise ValidationError("Mode balasan harus rule_based atau gemini.")
        return aliases[mode]

    def find_provider_chat_training_override(
        self,
        conn: sqlite3.Connection,
        message: str,
    ) -> SimulationReply | None:
        normalized_message = normalize_text(message)
        if not normalized_message:
            return None

        rows = conn.execute(
            """
            SELECT s.code AS session_code,
                   parent.message AS parent_message,
                   COALESCE(parent.expected_reply, assistant.message) AS expected_reply,
                   COALESCE(parent.intent, assistant.intent, 'training_override') AS intent,
                   COALESCE(parent.matched_reference, assistant.matched_reference, 'provider_training_override') AS matched_reference,
                   COALESCE(parent.confidence, assistant.confidence, 0.98) AS confidence,
                   parent.metadata_json AS parent_metadata_json,
                   assistant.metadata_json AS assistant_metadata_json
            FROM provider_chat_simulation_messages parent
            JOIN provider_chat_simulation_sessions s ON s.id = parent.session_id
            LEFT JOIN provider_chat_simulation_messages assistant
              ON assistant.session_id = parent.session_id
             AND assistant.turn_index = parent.turn_index
             AND assistant.role = 'assistant'
            WHERE parent.role = 'parent'
              AND COALESCE(parent.expected_reply, assistant.message, '') != ''
            ORDER BY s.updated_at DESC, parent.id DESC
            """
        ).fetchall()

        for row in rows:
            if normalize_text(row["parent_message"]) != normalized_message:
                continue
            parent_metadata = self.decode_metadata(row["parent_metadata_json"])
            assistant_metadata = self.decode_metadata(row["assistant_metadata_json"])
            if not (parent_metadata.get("edited_by_provider") or assistant_metadata.get("edited_by_provider")):
                continue

            tags = [
                *(parent_metadata.get("training_tags") or assistant_metadata.get("training_tags") or []),
                "db-training-override",
                "provider-edited",
            ]
            return SimulationReply(
                message=str(row["expected_reply"]),
                intent=str(row["intent"] or "training_override"),
                stage="db_training_override",
                matched_reference=f"{row['matched_reference']}, db/provider-training:{row['session_code']}",
                confidence=float(row["confidence"] or 0.98),
                needs_review=False,
                training_tags=tags,
            )
        return None

    def verify_whatsapp_webhook_secret(self, query: str) -> str:
        try:
            return verify_fonnte_secret(query)
        except FonnteWebhookSecretError as exc:
            raise PermissionError(str(exc)) from exc

    def handle_whatsapp_webhook(
        self,
        payload: dict[str, Any],
        *,
        secret_status: str = "not_checked",
    ) -> dict[str, Any]:
        try:
            events = extract_fonnte_message_events(payload)
            diagnostics = summarize_fonnte_webhook_payload(payload)
        except FonnteWebhookError as exc:
            raise ValidationError(str(exc)) from exc

        results = [self.handle_whatsapp_message_event(event) for event in events]
        return {
            "source": "fonnte",
            "secret": secret_status,
            "events_received": len(events),
            "diagnostics": diagnostics,
            "results": results,
        }

    def handle_whatsapp_raw_webhook(
        self,
        raw_body: bytes,
        *,
        secret_status: str = "not_checked",
    ) -> dict[str, Any]:
        try:
            payload = parse_fonnte_webhook_payload(raw_body)
        except FonnteWebhookError as exc:
            raise ValidationError(str(exc)) from exc
        return self.handle_whatsapp_webhook(payload, secret_status=secret_status)

    def handle_whatsapp_message_event(self, event: FonnteMessageEvent) -> dict[str, Any]:
        session = self.find_or_create_whatsapp_chat_session(event)
        if session["current_stage"] == "transferred_to_admin":
            return {
                "session_id": session["id"],
                "status": "ignored_transferred_to_admin",
                "sent": False,
            }

        mode = self.normalize_provider_chat_reply_mode(
            whatsapp_reply_mode(default=self.default_whatsapp_reply_mode())
        )
        result = self.send_provider_chat_simulation_message(
            session["id"],
            {
                "message": event.text,
                "mode": mode,
            },
        )
        send_result: dict[str, Any] = {"enabled": whatsapp_send_enabled(), "sent": False}
        if whatsapp_send_enabled():
            try:
                send_result = {
                    "enabled": True,
                    "sent": True,
                    "response": send_fonnte_text_message(
                        target_number=event.sender_number,
                        text=result["assistant_message"]["message"],
                    ),
                }
            except FonnteSendError as exc:
                send_result = {"enabled": True, "sent": False, "error": str(exc)}

        return {
            "session_id": result["session"]["id"],
            "reply_mode": mode,
            "intent": result["reply"]["intent"],
            "stage": result["reply"]["stage"],
            "sent": bool(send_result.get("sent")),
            "send_result": send_result,
        }

    def default_whatsapp_reply_mode(self) -> str:
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            return "gemini"
        return "rule_based"

    def find_or_create_whatsapp_chat_session(self, event: FonnteMessageEvent) -> dict[str, Any]:
        title = f"WhatsApp {event.sender_number}"
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM provider_chat_simulation_sessions
                WHERE channel = 'whatsapp'
                  AND source = 'fonnte_webhook'
                  AND title = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (title,),
            ).fetchone()
            if row:
                return dict(row)

            code = self.next_code(conn, "provider_chat_simulation_sessions", "SIM")
            cursor = conn.execute(
                """
                INSERT INTO provider_chat_simulation_sessions (
                    code, title, channel, source, current_stage
                )
                VALUES (?, ?, 'whatsapp', 'fonnte_webhook', 'start')
                """,
                (code, title),
            )
            conn.commit()
            return self.get_provider_chat_simulation_session_row(conn, int(cursor.lastrowid))

    def verify_instagram_webhook_challenge(self, query: str) -> str:
        try:
            return verify_instagram_challenge(query)
        except InstagramWebhookError as exc:
            raise PermissionError(str(exc)) from exc

    def handle_instagram_webhook(self, raw_body: bytes, headers: Any) -> dict[str, Any]:
        try:
            signature_status = verify_instagram_signature(raw_body, headers)
            payload = parse_instagram_webhook_payload(raw_body)
            processing_payload, target_filter = filter_instagram_payload_for_target_user(payload)
            events = extract_instagram_message_events(processing_payload)
            diagnostics = summarize_instagram_webhook_payload(processing_payload)
            diagnostics["target_filter"] = target_filter
            fetched_events, message_detail_fetch = self.fetch_instagram_message_detail_events(processing_payload, events)
            events.extend(fetched_events)
        except InstagramWebhookSignatureError as exc:
            raise PermissionError(str(exc)) from exc
        except InstagramWebhookError as exc:
            raise ValidationError(str(exc)) from exc

        results = [self.handle_instagram_message_event(event) for event in events]
        return {
            "object": payload.get("object"),
            "signature": signature_status,
            "events_received": len(events),
            "diagnostics": diagnostics,
            "message_detail_fetch": message_detail_fetch,
            "results": results,
        }

    def fetch_instagram_message_detail_events(
        self,
        payload: dict[str, Any],
        existing_events: list[InstagramMessageEvent],
    ) -> tuple[list[InstagramMessageEvent], dict[str, Any]]:
        references = extract_instagram_message_detail_references(payload)
        known_message_ids = {event.message_id for event in existing_events if event.message_id}
        fetched_events: list[InstagramMessageEvent] = []
        summary: dict[str, Any] = {
            "references": len(references),
            "attempted": 0,
            "resolved": 0,
            "skipped_existing": 0,
            "empty_or_incomplete": 0,
            "empty_or_incomplete_details": [],
            "errors": [],
        }

        for reference in references:
            if reference.message_id in known_message_ids:
                summary["skipped_existing"] += 1
                continue
            summary["attempted"] += 1
            try:
                message_detail = fetch_instagram_message_detail(reference.message_id)
            except InstagramMessageFetchError as exc:
                if instagram_raw_webhook_debug_enabled():
                    summary["errors"].append(raw_instagram_fetch_error(exc))
                else:
                    summary["errors"].append(safe_instagram_fetch_error(exc))
                continue

            event = instagram_message_detail_to_event(message_detail, reference)
            if event is None:
                summary["empty_or_incomplete"] += 1
                summary["empty_or_incomplete_details"].append(
                    instagram_message_detail_diagnostic(message_detail, reference)
                )
                continue

            known_message_ids.add(event.message_id or reference.message_id)
            fetched_events.append(event)
            summary["resolved"] += 1

        return fetched_events, summary

    def handle_instagram_message_event(self, event: InstagramMessageEvent) -> dict[str, Any]:
        session = self.find_or_create_instagram_chat_session(event)
        if session["current_stage"] == "transferred_to_admin":
            return {
                "sender_id": event.sender_id,
                "session_id": session["id"],
                "status": "ignored_transferred_to_admin",
                "sent": False,
            }

        mode = self.normalize_provider_chat_reply_mode(
            instagram_reply_mode(default=self.default_instagram_reply_mode())
        )
        result = self.send_provider_chat_simulation_message(
            session["id"],
            {
                "message": event.text,
                "mode": mode,
            },
        )
        send_result: dict[str, Any] = {"enabled": instagram_send_enabled(), "sent": False}
        if instagram_send_enabled():
            try:
                send_result = {
                    "enabled": True,
                    "sent": True,
                    "response": send_instagram_text_message(
                        recipient_id=event.sender_id,
                        text=result["assistant_message"]["message"],
                        ig_user_id=event.recipient_id or None,
                    ),
                }
            except InstagramSendError as exc:
                send_result = {"enabled": True, "sent": False, "error": str(exc)}

        return {
            "sender_id": event.sender_id,
            "session_id": result["session"]["id"],
            "reply_mode": mode,
            "intent": result["reply"]["intent"],
            "stage": result["reply"]["stage"],
            "sent": bool(send_result.get("sent")),
            "send_result": send_result,
        }

    def default_instagram_reply_mode(self) -> str:
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            return "gemini"
        return "rule_based"

    def find_or_create_instagram_chat_session(self, event: InstagramMessageEvent) -> dict[str, Any]:
        title = f"Instagram DM {event.sender_id}"
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM provider_chat_simulation_sessions
                WHERE channel = 'instagram'
                  AND source = 'instagram_webhook'
                  AND title = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (title,),
            ).fetchone()
            if row:
                return dict(row)

            code = self.next_code(conn, "provider_chat_simulation_sessions", "SIM")
            cursor = conn.execute(
                """
                INSERT INTO provider_chat_simulation_sessions (
                    code, title, channel, source, current_stage
                )
                VALUES (?, ?, 'instagram', 'instagram_webhook', 'start')
                """,
                (code, title),
            )
            conn.commit()
            return self.get_provider_chat_simulation_session_row(conn, int(cursor.lastrowid))

    def update_provider_chat_simulation_message(
        self, session_id: int, message_id: int, data: dict[str, Any]
    ) -> dict[str, Any]:
        new_response = require_text(data, "message", "Respons asisten")
        with self.connection() as conn:
            self.get_provider_chat_simulation_session_row(conn, session_id)
            row = conn.execute(
                """
                SELECT *
                FROM provider_chat_simulation_messages
                WHERE id = ? AND session_id = ?
                """,
                (message_id, session_id),
            ).fetchone()
            if row is None:
                raise NotFoundError("Pesan simulasi tidak ditemukan.")
            if row["role"] != "assistant":
                raise ValidationError("Hanya respons asisten yang bisa diedit.")

            metadata = self.decode_metadata(row["metadata_json"])
            metadata["edited_by_provider"] = True
            conn.execute(
                """
                UPDATE provider_chat_simulation_messages
                SET message = ?,
                    expected_reply = ?,
                    needs_review = 0,
                    metadata_json = ?
                WHERE id = ?
                """,
                (new_response, new_response, json.dumps(metadata, ensure_ascii=False), message_id),
            )
            conn.execute(
                """
                UPDATE provider_chat_simulation_messages
                SET expected_reply = ?,
                    needs_review = 0,
                    metadata_json = ?
                WHERE session_id = ?
                  AND turn_index = ?
                  AND role = 'parent'
                """,
                (new_response, json.dumps(metadata, ensure_ascii=False), session_id, row["turn_index"]),
            )
            conn.execute(
                """
                UPDATE provider_chat_simulation_sessions
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (session_id,),
            )
            conn.commit()

        return {
            "message": self.get_provider_chat_simulation_message(message_id),
            "session": self.get_provider_chat_simulation_session(session_id),
        }

    def list_provider_chat_training_examples(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT s.code AS session_code,
                       s.title AS session_title,
                       parent.session_id,
                       parent.turn_index,
                       parent.message AS parent_message,
                       COALESCE(parent.expected_reply, assistant.message) AS expected_reply,
                       parent.intent,
                       parent.matched_reference,
                       parent.confidence,
                       parent.needs_review,
                       parent.metadata_json
                FROM provider_chat_simulation_messages parent
                JOIN provider_chat_simulation_sessions s ON s.id = parent.session_id
                LEFT JOIN provider_chat_simulation_messages assistant
                  ON assistant.session_id = parent.session_id
                 AND assistant.turn_index = parent.turn_index
                 AND assistant.role = 'assistant'
                WHERE parent.role = 'parent'
                ORDER BY parent.session_id, parent.turn_index
                """
            ).fetchall()
            examples = []
            for row in rows:
                item = dict(row)
                metadata = self.decode_metadata(item.pop("metadata_json"))
                item["needs_review"] = bool(item["needs_review"])
                item["training_tags"] = metadata.get("training_tags", [])
                item["edited_by_provider"] = bool(metadata.get("edited_by_provider"))
                examples.append(item)
            return examples

    def get_provider_chat_simulation_message(self, message_id: int) -> dict[str, Any]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM provider_chat_simulation_messages WHERE id = ?",
                (message_id,),
            ).fetchone()
            if row is None:
                raise NotFoundError("Pesan simulasi tidak ditemukan.")
            return self.format_provider_chat_message(row)

    def get_provider_chat_simulation_session_row(
        self, conn: sqlite3.Connection, session_id: int
    ) -> dict[str, Any]:
        row = conn.execute(
            "SELECT * FROM provider_chat_simulation_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("Simulasi percakapan tidak ditemukan.")
        return dict(row)

    def list_provider_chat_simulation_messages(
        self, conn: sqlite3.Connection, session_id: int
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT *
            FROM provider_chat_simulation_messages
            WHERE session_id = ?
            ORDER BY turn_index, id
            """,
            (session_id,),
        ).fetchall()
        return [self.format_provider_chat_message(row) for row in rows]

    def insert_provider_chat_simulation_faq_script(
        self, conn: sqlite3.Connection, session_id: int
    ) -> None:
        for item in FAQ_SIMULATION_SCRIPT:
            turn_index = int(item["sequence"])
            metadata = {"training_tags": item["training_tags"]}
            self.insert_provider_chat_simulation_message(
                conn,
                session_id=session_id,
                turn_index=turn_index,
                role="parent",
                message=item["parent_message"],
                intent=item["intent"],
                expected_reply=item["expected_reply"],
                matched_reference=item["matched_reference"],
                confidence=1.0,
                needs_review=False,
                metadata=metadata,
            )
            self.insert_provider_chat_simulation_message(
                conn,
                session_id=session_id,
                turn_index=turn_index,
                role="assistant",
                message=item["expected_reply"],
                intent=item["intent"],
                expected_reply=item["expected_reply"],
                matched_reference=item["matched_reference"],
                confidence=1.0,
                needs_review=False,
                metadata=metadata,
            )

    def insert_provider_chat_simulation_message(
        self,
        conn: sqlite3.Connection,
        *,
        session_id: int,
        turn_index: int,
        role: str,
        message: str,
        intent: str,
        expected_reply: str,
        matched_reference: str,
        confidence: float,
        needs_review: bool,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        cursor = conn.execute(
            """
            INSERT INTO provider_chat_simulation_messages (
                session_id, turn_index, role, message, intent, expected_reply,
                matched_reference, confidence, needs_review, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                turn_index,
                role,
                message,
                intent,
                expected_reply,
                matched_reference,
                confidence,
                1 if needs_review else 0,
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
        row = conn.execute(
            "SELECT * FROM provider_chat_simulation_messages WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return self.format_provider_chat_message(row)

    def next_provider_chat_turn_index(self, conn: sqlite3.Connection, session_id: int) -> int:
        row = conn.execute(
            """
            SELECT COALESCE(MAX(turn_index), 0) + 1 AS next_turn
            FROM provider_chat_simulation_messages
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
        return int(row["next_turn"])

    def format_provider_chat_message(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        metadata = self.decode_metadata(item.pop("metadata_json"))
        item["needs_review"] = bool(item["needs_review"])
        item["metadata"] = metadata
        item["training_tags"] = metadata.get("training_tags", [])
        return item

    def decode_metadata(self, raw_value: str | None) -> dict[str, Any]:
        if not raw_value:
            return {}
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    def normalize_subject_ids(self, value: Any) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            value = [item for item in value.split(",") if item.strip()]
        if not isinstance(value, list):
            raise ValidationError("Mata pelajaran harus berupa daftar.")
        return sorted({coerce_int(item, "Mata pelajaran") for item in value})

    def normalize_availabilities(self, value: Any) -> list[dict[str, Any]]:
        if not value:
            return []
        if not isinstance(value, list):
            raise ValidationError("Availability guru harus berupa daftar.")
        result = []
        for item in value:
            day_of_week = normalize_day(item.get("day_of_week"))
            start_time = require_text(item, "start_time", "Jam mulai availability")
            end_time = require_text(item, "end_time", "Jam selesai availability")
            validate_time_range(start_time, end_time)
            result.append({"day_of_week": day_of_week, "start_time": start_time, "end_time": end_time})
        return result

    def normalize_schedule_input(
        self,
        data: dict[str, Any],
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        student_id = coerce_int(data.get("student_id"), "Murid")
        tutor_id = coerce_int(data.get("tutor_id"), "Guru")
        subject_id = coerce_int(data.get("subject_id"), "Mata pelajaran")
        day_of_week = normalize_day(data.get("day_of_week"))
        start_time = require_text(data, "start_time", "Jam mulai")
        end_time = require_text(data, "end_time", "Jam selesai")
        validate_time_range(start_time, end_time)
        if conn is None:
            branch_id = coerce_int(data.get("branch_id", 1), "Cabang")
        else:
            student_row = conn.execute("SELECT branch_id FROM students WHERE id = ?", (student_id,)).fetchone()
            fallback_branch_id = student_row["branch_id"] if student_row else None
            branch_id = self.branch_id_from_data(data, conn, fallback_branch_id)
        return {
            "branch_id": branch_id,
            "student_id": student_id,
            "tutor_id": tutor_id,
            "subject_id": subject_id,
            "day_of_week": day_of_week,
            "start_time": start_time,
            "end_time": end_time,
            "starts_on": data.get("starts_on") or date.today().isoformat(),
            "ends_on": data.get("ends_on") or (date.today() + timedelta(days=90)).isoformat(),
            "mode": data.get("mode") or "online",
            "location": optional_text(data, "location"),
            "notes": optional_text(data, "notes"),
        }

    def ensure_parent_exists(self, parent_id: int, conn: sqlite3.Connection) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM parents WHERE id = ? AND status != 'archived'", (parent_id,)).fetchone()
        if row is None:
            raise ValidationError("Orang tua tidak ditemukan atau sudah diarsipkan.")
        return dict(row)

    def ensure_student_has_subject(self, conn: sqlite3.Connection, student_id: int, subject_id: int) -> None:
        row = conn.execute(
            "SELECT 1 FROM student_subjects WHERE student_id = ? AND subject_id = ?",
            (student_id, subject_id),
        ).fetchone()
        if row is None:
            raise ValidationError("Murid belum terdaftar pada mata pelajaran tersebut.")

    def ensure_tutor_teaches_subject(self, conn: sqlite3.Connection, tutor_id: int, subject_id: int) -> None:
        row = conn.execute(
            "SELECT 1 FROM tutor_subjects WHERE tutor_id = ? AND subject_id = ?",
            (tutor_id, subject_id),
        ).fetchone()
        if row is None:
            raise ValidationError("Guru tidak mengajar mata pelajaran yang dipilih.")

    def ensure_tutor_available(self, conn: sqlite3.Connection, slot: dict[str, Any]) -> None:
        rows = conn.execute(
            """
            SELECT * FROM tutor_availabilities
            WHERE tutor_id = ? AND day_of_week = ?
            """,
            (slot["tutor_id"], slot["day_of_week"]),
        ).fetchall()
        if not any(contains_range(row["start_time"], row["end_time"], slot["start_time"], slot["end_time"]) for row in rows):
            raise ValidationError("Guru tidak tersedia pada hari dan jam tersebut.")

    def validate_schedule_slot(
        self,
        conn: sqlite3.Connection,
        slot: dict[str, Any],
        exclude_schedule_id: int | None = None,
    ) -> None:
        student = self.get_student(slot["student_id"], conn)
        tutor = self.get_tutor(slot["tutor_id"], conn)
        branch = self.get_branch(slot["branch_id"], conn)
        if student["status"] != "active":
            raise ValidationError("Murid tidak aktif.")
        if tutor["status"] != "active":
            raise ValidationError("Guru tidak aktif.")
        if student["branch_id"] != branch["id"]:
            raise ValidationError("Cabang jadwal harus sama dengan cabang murid.")
        if tutor["branch_id"] != branch["id"]:
            raise ValidationError("Cabang jadwal harus sama dengan cabang guru.")
        subject = self.get_subject(slot["subject_id"], conn)
        if subject["status"] != "active":
            raise ValidationError("Mata pelajaran tidak aktif.")
        self.ensure_student_has_subject(conn, slot["student_id"], slot["subject_id"])
        self.ensure_tutor_teaches_subject(conn, slot["tutor_id"], slot["subject_id"])
        self.ensure_tutor_available(conn, slot)
        self.ensure_no_existing_conflict(conn, slot, exclude_schedule_id=exclude_schedule_id)

    def ensure_no_existing_conflict(
        self,
        conn: sqlite3.Connection,
        slot: dict[str, Any],
        exclude_schedule_id: int | None = None,
    ) -> None:
        rows = conn.execute(
            """
            SELECT sc.*, st.full_name AS student_name, tu.full_name AS tutor_name
            FROM schedules sc
            JOIN students st ON st.id = sc.student_id
            JOIN tutors tu ON tu.id = sc.tutor_id
            WHERE sc.day_of_week = ?
              AND sc.status IN ('draft', 'active')
              AND (sc.student_id = ? OR sc.tutor_id = ?)
            """,
            (slot["day_of_week"], slot["student_id"], slot["tutor_id"]),
        ).fetchall()
        for row in rows:
            if exclude_schedule_id is not None and row["id"] == exclude_schedule_id:
                continue
            if ranges_overlap(slot["start_time"], slot["end_time"], row["start_time"], row["end_time"]):
                if row["student_id"] == slot["student_id"]:
                    raise ValidationError(
                        f"Murid bentrok dengan jadwal {row['code']} ({row['start_time']}-{row['end_time']})."
                    )
                raise ValidationError(
                    f"Guru bentrok dengan jadwal {row['code']} ({row['start_time']}-{row['end_time']})."
                )

    def validate_new_slots_do_not_conflict_each_other(self, slots: list[dict[str, Any]]) -> None:
        for index, slot in enumerate(slots):
            for other in slots[index + 1 :]:
                same_day = slot["day_of_week"] == other["day_of_week"]
                same_student = slot["student_id"] == other["student_id"]
                same_tutor = slot["tutor_id"] == other["tutor_id"]
                if same_day and (same_student or same_tutor) and ranges_overlap(
                    slot["start_time"], slot["end_time"], other["start_time"], other["end_time"]
                ):
                    raise ValidationError("Slot yang dikonfirmasi saling bentrok.")

    def find_eligible_tutors(
        self,
        conn: sqlite3.Connection,
        subject_id: int,
        branch_id: int,
        tutor_id: int | str | None = None,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [subject_id, branch_id]
        tutor_filter = ""
        if tutor_id:
            tutor_filter = "AND t.id = ?"
            params.append(coerce_int(tutor_id, "Guru"))
        rows = conn.execute(
            f"""
            SELECT DISTINCT t.*
            FROM tutors t
            JOIN tutor_subjects ts ON ts.tutor_id = t.id
            WHERE ts.subject_id = ?
              AND t.branch_id = ?
              AND t.status = 'active'
              {tutor_filter}
            ORDER BY t.full_name
            """,
            params,
        ).fetchall()
        return rows_to_dicts(rows)

    def find_available_slots_for_tutor(
        self,
        conn: sqlite3.Connection,
        *,
        branch_id: int,
        student_id: int,
        tutor_id: int,
        subject_id: int,
        preferred_days: list[int],
        preferred_start: str,
        preferred_end: str,
        duration_minutes: int,
        starts_on: str,
        ends_on: str,
        mode: str,
        location: str | None,
    ) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT *
            FROM tutor_availabilities
            WHERE tutor_id = ?
              AND day_of_week IN ({})
            ORDER BY day_of_week, start_time
            """.format(",".join("?" for _ in preferred_days)),
            [tutor_id, *preferred_days],
        ).fetchall()

        slots: list[dict[str, Any]] = []
        preferred_start_minutes = parse_time(preferred_start)
        preferred_end_minutes = parse_time(preferred_end)
        for availability in rows:
            window_start = max(parse_time(availability["start_time"]), preferred_start_minutes)
            window_end = min(parse_time(availability["end_time"]), preferred_end_minutes)
            start = window_start
            while start + duration_minutes <= window_end:
                slot = {
                    "branch_id": branch_id,
                    "student_id": student_id,
                    "tutor_id": tutor_id,
                    "subject_id": subject_id,
                    "day_of_week": availability["day_of_week"],
                    "day_name": DAY_NAMES[availability["day_of_week"]],
                    "start_time": format_time(start),
                    "end_time": format_time(start + duration_minutes),
                    "starts_on": starts_on,
                    "ends_on": ends_on,
                    "mode": mode,
                    "location": location,
                    "notes": "Dibuat dari generator jadwal otomatis.",
                }
                try:
                    self.ensure_no_existing_conflict(conn, slot)
                except ValidationError:
                    start += 30
                    continue
                slots.append(slot)
                start += 30
        return slots

    def select_slots(self, slots: list[dict[str, Any]], sessions_per_week: int) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        selected_days: set[int] = set()
        for slot in slots:
            if slot["day_of_week"] in selected_days:
                continue
            selected.append(slot)
            selected_days.add(slot["day_of_week"])
            if len(selected) >= sessions_per_week:
                return selected
        for slot in slots:
            if slot not in selected:
                selected.append(slot)
            if len(selected) >= sessions_per_week:
                return selected
        return selected

    def replace_student_subjects(
        self, conn: sqlite3.Connection, student_id: int, subject_ids: list[int]
    ) -> None:
        conn.execute("DELETE FROM student_subjects WHERE student_id = ?", (student_id,))
        for subject_id in subject_ids:
            self.get_subject(subject_id, conn)
            conn.execute(
                "INSERT INTO student_subjects (student_id, subject_id) VALUES (?, ?)",
                (student_id, subject_id),
            )

    def replace_tutor_subjects(self, conn: sqlite3.Connection, tutor_id: int, subject_ids: list[int]) -> None:
        conn.execute("DELETE FROM tutor_subjects WHERE tutor_id = ?", (tutor_id,))
        for subject_id in subject_ids:
            self.get_subject(subject_id, conn)
            conn.execute(
                "INSERT INTO tutor_subjects (tutor_id, subject_id) VALUES (?, ?)",
                (tutor_id, subject_id),
            )

    def replace_tutor_availabilities(
        self, conn: sqlite3.Connection, tutor_id: int, availabilities: list[dict[str, Any]]
    ) -> None:
        conn.execute("DELETE FROM tutor_availabilities WHERE tutor_id = ?", (tutor_id,))
        for availability in availabilities:
            conn.execute(
                """
                INSERT INTO tutor_availabilities (tutor_id, day_of_week, start_time, end_time)
                VALUES (?, ?, ?, ?)
                """,
                (tutor_id, availability["day_of_week"], availability["start_time"], availability["end_time"]),
            )
