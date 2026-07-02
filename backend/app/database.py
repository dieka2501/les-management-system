from __future__ import annotations

import os
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "backend" / "data" / "les.sqlite3"


def resolve_db_path(db_path: str | os.PathLike[str] | None = None) -> Path:
    raw_path = db_path or os.environ.get("LES_DB_PATH") or DEFAULT_DB_PATH
    return Path(raw_path).expanduser().resolve()


def connect(db_path: str | os.PathLike[str] | None = None) -> sqlite3.Connection:
    path = resolve_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS branches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS parents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            branch_id INTEGER NOT NULL DEFAULT 1,
            full_name TEXT NOT NULL,
            email TEXT,
            phone TEXT NOT NULL,
            address TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (branch_id) REFERENCES branches(id)
        );

        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            branch_id INTEGER NOT NULL DEFAULT 1,
            parent_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            birthplace TEXT,
            birthdate TEXT,
            gender TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (branch_id) REFERENCES branches(id),
            FOREIGN KEY (parent_id) REFERENCES parents(id)
        );

        CREATE TABLE IF NOT EXISTS student_subjects (
            student_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            PRIMARY KEY (student_id, subject_id),
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        );

        CREATE TABLE IF NOT EXISTS tutors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            branch_id INTEGER NOT NULL DEFAULT 1,
            full_name TEXT NOT NULL,
            birthdate TEXT,
            gender TEXT,
            education TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (branch_id) REFERENCES branches(id)
        );

        CREATE TABLE IF NOT EXISTS tutor_subjects (
            tutor_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            PRIMARY KEY (tutor_id, subject_id),
            FOREIGN KEY (tutor_id) REFERENCES tutors(id) ON DELETE CASCADE,
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        );

        CREATE TABLE IF NOT EXISTS tutor_availabilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tutor_id INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL CHECK(day_of_week BETWEEN 0 AND 6),
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            FOREIGN KEY (tutor_id) REFERENCES tutors(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            branch_id INTEGER NOT NULL DEFAULT 1,
            student_id INTEGER NOT NULL,
            tutor_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL CHECK(day_of_week BETWEEN 0 AND 6),
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            starts_on TEXT,
            ends_on TEXT,
            mode TEXT NOT NULL DEFAULT 'online',
            location TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (branch_id) REFERENCES branches(id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (tutor_id) REFERENCES tutors(id),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        );

        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            branch_id INTEGER NOT NULL DEFAULT 1,
            parent_name TEXT NOT NULL,
            parent_phone TEXT NOT NULL,
            child_name TEXT NOT NULL,
            subject_interest TEXT,
            preferred_schedule TEXT,
            source TEXT NOT NULL DEFAULT 'chatbot',
            status TEXT NOT NULL DEFAULT 'new',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    ensure_branch_columns(conn)
    conn.commit()


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_branch_columns(conn: sqlite3.Connection) -> None:
    for table in ("parents", "students", "tutors", "schedules", "registrations"):
        ensure_column(conn, table, "branch_id", "INTEGER NOT NULL DEFAULT 1")


def seed_master_data(conn: sqlite3.Connection) -> None:
    seed_branches(conn)
    seed_subjects(conn)


def seed_branches(conn: sqlite3.Connection) -> None:
    branches = [
        ("CBG-0001", "Cabang Jalan Kenangan", "Jalan Kenangan", "Kota Tasikmalaya"),
        ("CBG-0002", "Cabang Jalan Delima", "Jalan Delima", "Kabupaten Tasik"),
        ("CBG-0003", "Cabang Jalan Seram", "Jalan Seram", "Kota Bandung"),
    ]
    for code, name, address, city in branches:
        conn.execute(
            """
            INSERT OR IGNORE INTO branches (code, name, address, city)
            VALUES (?, ?, ?, ?)
            """,
            (code, name, address, city),
        )


def seed_subjects(conn: sqlite3.Connection) -> None:
    subjects = [
        ("MAP-0001", "Matematika", "Bimbingan belajar Matematika untuk SD/SMP."),
        ("MAP-0002", "Bahasa Inggris", "Vocabulary, grammar, reading, dan conversation."),
        ("MAP-0003", "IPA", "Sains dasar, biologi, fisika, dan kimia tingkat sekolah."),
        ("MAP-0004", "Bahasa Indonesia", "Membaca, menulis, dan pemahaman teks."),
    ]
    for code, name, description in subjects:
        conn.execute(
            """
            INSERT OR IGNORE INTO subjects (code, name, description)
            VALUES (?, ?, ?)
            """,
            (code, name, description),
        )
