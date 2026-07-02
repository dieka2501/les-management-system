from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.store import LesStore, ValidationError


class SchedulingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.sqlite3"
        self.store = LesStore(self.db_path)
        self.store.seed_master_data()
        self.math_id = self.store.subject_by_name("Matematika")["id"]

        self.parent = self.store.create_parent(
            {
                "full_name": "Ibu Test",
                "phone": "080000000001",
                "email": "test@example.test",
            }
        )
        self.student = self.store.create_student(
            {
                "parent_id": self.parent["id"],
                "full_name": "Murid Test",
                "subject_ids": [self.math_id],
            }
        )
        self.other_student = self.store.create_student(
            {
                "parent_id": self.parent["id"],
                "full_name": "Murid Lain",
                "subject_ids": [self.math_id],
            }
        )
        self.tutor = self.store.create_tutor(
            {
                "full_name": "Guru Test",
                "education": "S1 Pendidikan Matematika",
                "subject_ids": [self.math_id],
                "availabilities": [
                    {"day_of_week": 0, "start_time": "15:00", "end_time": "19:00"},
                    {"day_of_week": 1, "start_time": "15:00", "end_time": "19:00"},
                ],
            }
        )

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_manual_schedule_rejects_tutor_overlap(self) -> None:
        self.store.create_schedule(
            {
                "student_id": self.student["id"],
                "tutor_id": self.tutor["id"],
                "subject_id": self.math_id,
                "day_of_week": 0,
                "start_time": "16:00",
                "end_time": "17:00",
            }
        )

        with self.assertRaisesRegex(ValidationError, "Guru bentrok"):
            self.store.create_schedule(
                {
                    "student_id": self.other_student["id"],
                    "tutor_id": self.tutor["id"],
                    "subject_id": self.math_id,
                    "day_of_week": 0,
                    "start_time": "16:30",
                    "end_time": "17:30",
                }
            )

    def test_generator_returns_non_overlapping_slot(self) -> None:
        self.store.create_schedule(
            {
                "student_id": self.student["id"],
                "tutor_id": self.tutor["id"],
                "subject_id": self.math_id,
                "day_of_week": 0,
                "start_time": "16:00",
                "end_time": "17:00",
            }
        )

        result = self.store.generate_schedule_candidates(
            {
                "student_id": self.other_student["id"],
                "subject_id": self.math_id,
                "sessions_per_week": 1,
                "duration_minutes": 90,
                "preferred_days": [0],
                "preferred_start": "15:00",
                "preferred_end": "19:00",
            }
        )

        self.assertEqual(1, len(result["candidates"]))
        slot = result["candidates"][0]["slots"][0]
        self.assertEqual("17:00", slot["start_time"])
        self.assertEqual("18:30", slot["end_time"])

    def test_confirm_generated_schedule_rejects_internal_overlap(self) -> None:
        slot = {
            "student_id": self.student["id"],
            "tutor_id": self.tutor["id"],
            "subject_id": self.math_id,
            "day_of_week": 1,
            "start_time": "15:00",
            "end_time": "16:30",
        }

        with self.assertRaisesRegex(ValidationError, "saling bentrok"):
            self.store.confirm_generated_schedule({"slots": [slot, slot]})

    def test_schedule_rejects_cross_branch_tutor(self) -> None:
        bandung_branch_id = self.store.branch_by_code("CBG-0003")["id"]
        bandung_tutor = self.store.create_tutor(
            {
                "branch_id": bandung_branch_id,
                "full_name": "Guru Bandung",
                "education": "S1 Pendidikan Matematika",
                "subject_ids": [self.math_id],
                "availabilities": [
                    {"day_of_week": 0, "start_time": "15:00", "end_time": "19:00"},
                ],
            }
        )

        with self.assertRaisesRegex(ValidationError, "cabang guru"):
            self.store.create_schedule(
                {
                    "student_id": self.student["id"],
                    "tutor_id": bandung_tutor["id"],
                    "subject_id": self.math_id,
                    "day_of_week": 0,
                    "start_time": "15:00",
                    "end_time": "16:00",
                }
            )

    def test_update_schedule_allows_same_slot_and_rejects_overlap(self) -> None:
        first = self.store.create_schedule(
            {
                "student_id": self.student["id"],
                "tutor_id": self.tutor["id"],
                "subject_id": self.math_id,
                "day_of_week": 0,
                "start_time": "15:00",
                "end_time": "16:00",
            }
        )
        self.store.create_schedule(
            {
                "student_id": self.other_student["id"],
                "tutor_id": self.tutor["id"],
                "subject_id": self.math_id,
                "day_of_week": 1,
                "start_time": "15:00",
                "end_time": "16:00",
            }
        )

        updated = self.store.update_schedule(
            first["id"],
            {
                "student_id": self.student["id"],
                "tutor_id": self.tutor["id"],
                "subject_id": self.math_id,
                "day_of_week": 0,
                "start_time": "15:00",
                "end_time": "16:00",
                "mode": "online",
            },
        )
        self.assertEqual("15:00", updated["start_time"])

        with self.assertRaisesRegex(ValidationError, "Guru bentrok"):
            self.store.update_schedule(
                first["id"],
                {
                    "student_id": self.student["id"],
                    "tutor_id": self.tutor["id"],
                    "subject_id": self.math_id,
                    "day_of_week": 1,
                    "start_time": "15:30",
                    "end_time": "16:30",
                    "mode": "online",
                },
            )


if __name__ == "__main__":
    unittest.main()
