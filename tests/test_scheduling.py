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

    def test_student_branch_follows_parent_when_parent_changes(self) -> None:
        bandung_branch_id = self.store.branch_by_code("CBG-0003")["id"]
        other_parent = self.store.create_parent(
            {
                "branch_id": bandung_branch_id,
                "full_name": "Bapak Cabang Bandung",
                "phone": "080000000009",
            }
        )

        updated = self.store.update_student(
            self.student["id"],
            {
                "parent_id": other_parent["id"],
            },
        )

        self.assertEqual(other_parent["id"], updated["parent_id"])
        self.assertEqual(bandung_branch_id, updated["branch_id"])

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

    def test_manual_schedule_rejects_invalid_time_range_as_validation_error(self) -> None:
        with self.assertRaisesRegex(ValidationError, "Jam selesai harus lebih besar"):
            self.store.create_schedule(
                {
                    "student_id": self.student["id"],
                    "tutor_id": self.tutor["id"],
                    "subject_id": self.math_id,
                    "day_of_week": 0,
                    "start_time": "17:30",
                    "end_time": "16:00",
                }
            )

    def test_subject_can_be_created_updated_and_archived(self) -> None:
        subject = self.store.create_subject(
            {
                "name": "Fisika",
                "description": "Pendampingan materi Fisika.",
            }
        )
        self.assertEqual("MAP-0005", subject["code"])
        self.assertEqual("Fisika", subject["name"])

        updated = self.store.update_subject(
            subject["id"],
            {
                "name": "Fisika Dasar",
                "description": "Fisika untuk SMP dan SMA.",
            },
        )
        self.assertEqual("Fisika Dasar", updated["name"])

        archived = self.store.archive_subject(subject["id"])
        self.assertEqual("archived", archived["status"])
        self.assertNotIn("Fisika Dasar", [item["name"] for item in self.store.list_subjects()])

    def test_subject_with_active_schedule_cannot_be_archived(self) -> None:
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

        with self.assertRaisesRegex(ValidationError, "jadwal aktif"):
            self.store.archive_subject(self.math_id)

    def test_tutor_update_accepts_multiple_availability_days(self) -> None:
        updated = self.store.update_tutor(
            self.tutor["id"],
            {
                "full_name": "Guru Test",
                "education": "S1 Pendidikan Matematika",
                "subject_ids": [self.math_id],
                "availabilities": [
                    {"day_of_week": 2, "start_time": "14:00", "end_time": "17:00"},
                    {"day_of_week": 4, "start_time": "15:00", "end_time": "18:00"},
                    {"day_of_week": 5, "start_time": "09:00", "end_time": "12:00"},
                ],
            },
        )

        self.assertEqual([2, 4, 5], [item["day_of_week"] for item in updated["availabilities"]])

    def test_manual_schedule_allows_tutor_latest_start_time(self) -> None:
        self.store.update_tutor(
            self.tutor["id"],
            {
                "full_name": "Guru Test",
                "education": "S1 Pendidikan Matematika",
                "subject_ids": [self.math_id],
                "availabilities": [
                    {"day_of_week": 0, "start_time": "14:00", "end_time": "14:00"},
                ],
            },
        )

        schedule = self.store.create_schedule(
            {
                "student_id": self.student["id"],
                "tutor_id": self.tutor["id"],
                "subject_id": self.math_id,
                "day_of_week": 0,
                "start_time": "14:00",
                "end_time": "15:30",
            }
        )

        self.assertEqual("14:00", schedule["start_time"])
        self.assertEqual("15:30", schedule["end_time"])

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

    def test_generator_treats_preferred_end_as_latest_start_time(self) -> None:
        self.store.update_tutor(
            self.tutor["id"],
            {
                "full_name": "Guru Test",
                "education": "S1 Pendidikan Matematika",
                "subject_ids": [self.math_id],
                "availabilities": [
                    {"day_of_week": 0, "start_time": "09:00", "end_time": "14:00"},
                    {"day_of_week": 1, "start_time": "09:00", "end_time": "14:00"},
                ],
            },
        )

        result = self.store.generate_schedule_candidates(
            {
                "student_id": self.student["id"],
                "subject_id": self.math_id,
                "sessions_per_week": 1,
                "duration_minutes": 90,
                "preferred_days": [0],
                "preferred_start": "14:00",
                "preferred_end": "14:00",
            }
        )

        self.assertEqual([], self.store.list_schedules())
        self.assertEqual(1, len(result["candidates"]))
        slot = result["candidates"][0]["slots"][0]
        self.assertEqual("14:00", slot["start_time"])
        self.assertEqual("15:30", slot["end_time"])

    def test_generator_recommends_closest_tutor_when_no_exact_start_match(self) -> None:
        self.store.update_tutor(
            self.tutor["id"],
            {
                "full_name": "Guru Test",
                "education": "S1 Pendidikan Matematika",
                "subject_ids": [self.math_id],
                "availabilities": [
                    {"day_of_week": 0, "start_time": "15:00", "end_time": "17:00"},
                ],
            },
        )
        closer_tutor = self.store.create_tutor(
            {
                "full_name": "Guru Dekat",
                "education": "S1 Pendidikan Matematika",
                "subject_ids": [self.math_id],
                "availabilities": [
                    {"day_of_week": 0, "start_time": "15:00", "end_time": "17:30"},
                ],
            }
        )

        result = self.store.generate_schedule_candidates(
            {
                "student_id": self.student["id"],
                "subject_id": self.math_id,
                "sessions_per_week": 1,
                "duration_minutes": 90,
                "preferred_days": [0],
                "preferred_start": "18:00",
                "preferred_end": "18:00",
            }
        )

        candidate = result["candidates"][0]
        slot = candidate["slots"][0]

        self.assertTrue(candidate["recommendation"])
        self.assertEqual(closer_tutor["id"], candidate["tutor_id"])
        self.assertEqual("18:00", slot["start_time"])
        self.assertEqual(30, slot["recommendation_gap_minutes"])

        confirmed = self.store.confirm_generated_schedule({"slots": [slot]})
        self.assertEqual("draft", confirmed["saved"][0]["status"])
        self.assertIn("Rekomendasi generator", confirmed["saved"][0]["notes"])

    def test_generator_recommends_less_loaded_tutor_when_time_gap_is_equal(self) -> None:
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
        self.store.update_tutor(
            self.tutor["id"],
            {
                "full_name": "Guru Test",
                "education": "S1 Pendidikan Matematika",
                "subject_ids": [self.math_id],
                "availabilities": [
                    {"day_of_week": 0, "start_time": "15:00", "end_time": "17:00"},
                ],
            },
        )
        less_loaded_tutor = self.store.create_tutor(
            {
                "full_name": "Guru Lebih Longgar",
                "education": "S1 Pendidikan Matematika",
                "subject_ids": [self.math_id],
                "availabilities": [
                    {"day_of_week": 0, "start_time": "15:00", "end_time": "17:00"},
                ],
            }
        )

        result = self.store.generate_schedule_candidates(
            {
                "student_id": self.student["id"],
                "subject_id": self.math_id,
                "sessions_per_week": 1,
                "duration_minutes": 90,
                "preferred_days": [0],
                "preferred_start": "18:00",
                "preferred_end": "18:00",
            }
        )

        self.assertTrue(result["candidates"][0]["recommendation"])
        self.assertEqual(less_loaded_tutor["id"], result["candidates"][0]["tutor_id"])

    def test_confirm_generated_schedule_appears_in_schedule_list(self) -> None:
        result = self.store.generate_schedule_candidates(
            {
                "student_id": self.student["id"],
                "subject_id": self.math_id,
                "sessions_per_week": 1,
                "duration_minutes": 90,
                "preferred_days": [1],
                "preferred_start": "15:00",
                "preferred_end": "19:00",
            }
        )

        slot = result["candidates"][0]["slots"][0]
        confirmed = self.store.confirm_generated_schedule({"slots": [slot]})
        saved_id = confirmed["saved"][0]["id"]
        schedule_ids = [schedule["id"] for schedule in self.store.list_schedules()]

        self.assertIn(saved_id, schedule_ids)

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
