from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.store import LesStore


class AgentContextTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store = LesStore(Path(self.tmpdir.name) / "agent_context.sqlite3")
        self.store.seed_demo_data()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_agent_context_snapshot_includes_chatbot_and_operational_data(self) -> None:
        snapshot = self.store.agent_context_snapshot()

        self.assertEqual(1, snapshot["schema_version"])
        self.assertEqual("rumah_privat_madani", snapshot["chatbot"]["knowledge_id"])
        self.assertGreaterEqual(snapshot["summary"]["tutors"], 1)
        self.assertGreaterEqual(len(snapshot["operational_data"]["tutors"]), 1)
        self.assertGreaterEqual(len(snapshot["operational_data"]["schedules"]), 1)
        self.assertIn("packages", snapshot["chatbot"])

    def test_agent_context_snapshot_masks_private_contacts(self) -> None:
        parent = self.store.create_parent(
            {
                "full_name": "Ibu Kontak",
                "phone": "081234567890",
                "email": "ibu@example.com",
                "address": "Jalan Rahasia",
            }
        )

        snapshot = self.store.agent_context_snapshot()
        masked_parent = next(
            item for item in snapshot["operational_data"]["parents"] if item["id"] == parent["id"]
        )

        self.assertEqual("0812***890", masked_parent["phone"])
        self.assertEqual("ib***@example.com", masked_parent["email"])
        self.assertEqual("masked", masked_parent["address"])


if __name__ == "__main__":
    unittest.main()
