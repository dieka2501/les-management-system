from __future__ import annotations

import argparse

from .database import resolve_db_path
from .store import LesStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed data development Les Management System.")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Isi data demo operasional. Tanpa flag ini hanya mengisi master data awal.",
    )
    args = parser.parse_args()

    store = LesStore()
    if args.demo:
        store.seed_demo_data()
    else:
        store.seed_master_data()
    summary = store.summary()
    db_path = resolve_db_path()
    print(f"Database siap: {db_path}")
    print(
        "Data saat ini: "
        f"{summary['branches']} cabang, "
        f"{summary['parents']} orang tua, "
        f"{summary['students']} murid, "
        f"{summary['tutors']} guru, "
        f"{summary['schedules']} jadwal."
    )


if __name__ == "__main__":
    main()
