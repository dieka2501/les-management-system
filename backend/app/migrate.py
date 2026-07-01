from __future__ import annotations

from .database import connect, migrate, resolve_db_path


def main() -> None:
    with connect() as conn:
        migrate(conn)
    print(f"Schema database siap: {resolve_db_path()}")


if __name__ == "__main__":
    main()
