from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.store import LesStore


class DatabaseSeedTestCase(unittest.TestCase):
    def test_new_database_is_schema_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = LesStore(Path(tmpdir) / "schema_only.sqlite3")

            self.assertEqual(0, store.summary()["branches"])
            self.assertEqual([], store.list_subjects())

    def test_seed_master_data_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = LesStore(Path(tmpdir) / "seeded.sqlite3")
            store.seed_master_data()

            self.assertEqual(3, store.summary()["branches"])
            self.assertEqual(4, len(store.list_subjects()))


if __name__ == "__main__":
    unittest.main()
