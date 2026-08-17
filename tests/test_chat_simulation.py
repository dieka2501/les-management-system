from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.chat_simulation import CLOSE_HANDOFF_MESSAGE, SimulationReply
from backend.app.gemini_chatbot import OUT_OF_SCOPE_MESSAGE, normalize_gemini_model_name, simulate_provider_ai_reply
from backend.app.store import LesStore


class ProviderChatSimulationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.store = LesStore(Path(self.tmpdir.name) / "chat_simulation.sqlite3")

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_provider_simulation_replies_like_knowledge_base_flow(self) -> None:
        session = self.store.create_provider_chat_simulation_session({"title": "Latihan CS Knowledge Base"})

        first = self.store.send_provider_chat_simulation_message(
            session["id"],
            {"message": "Ada paket apa saja di Rumah Privat Madani?"},
        )
        self.assertIn("Les Privat Calistung", first["assistant_message"]["message"])
        self.assertIn("English Private for Children", first["assistant_message"]["message"])
        self.assertEqual("list_packages", first["reply"]["intent"])

        second = self.store.send_provider_chat_simulation_message(
            session["id"],
            {"message": "Berapa harga English?"},
        )
        self.assertIn("Rp55.000 dan Rp60.000 per sesi", second["assistant_message"]["message"])
        self.assertEqual("needs_admin_confirmation", second["reply"]["stage"])

        third = self.store.send_provider_chat_simulation_message(
            session["id"],
            {"message": "Area layanannya di mana saja?"},
        )
        self.assertIn("Tasikmalaya, Ciamis, dan Singaparna", third["assistant_message"]["message"])
        self.assertEqual("coverage_area", third["reply"]["intent"])

        fourth = self.store.send_provider_chat_simulation_message(
            session["id"],
            {"message": "Saya mau daftar les."},
        )
        self.assertIn("Apakah mau diteruskan ke pendaftaran?", fourth["assistant_message"]["message"])
        self.assertEqual("close_confirmation_prompt", fourth["reply"]["intent"])

        fifth = self.store.send_provider_chat_simulation_message(
            session["id"],
            {"message": "Ya, teruskan ke admin."},
        )
        self.assertEqual(CLOSE_HANDOFF_MESSAGE, fifth["assistant_message"]["message"])
        self.assertEqual("admin_handoff_confirmed", fifth["reply"]["intent"])

        reloaded = self.store.get_provider_chat_simulation_session(session["id"])
        self.assertEqual("provider", reloaded["channel"])
        self.assertEqual("transferred_to_admin", reloaded["current_stage"])
        self.assertEqual(10, len(reloaded["messages"]))

    def test_provider_simulation_greets_from_knowledge_base(self) -> None:
        session = self.store.create_provider_chat_simulation_session({"title": "Latihan greeting"})
        result = self.store.send_provider_chat_simulation_message(session["id"], {"message": "Halo"})

        self.assertIn("selamat datang di Rumah Privat Madani", result["assistant_message"]["message"])
        self.assertEqual("greeting", result["reply"]["intent"])
        self.assertEqual("greeting", result["reply"]["stage"])

    def test_seed_from_knowledge_base_exports_training_examples(self) -> None:
        session = self.store.create_provider_chat_simulation_session(
            {"title": "Dataset Knowledge Base", "seed_from_faq": True}
        )

        self.assertEqual(16, len(session["messages"]))
        self.assertEqual("knowledge_base", session["source"])
        self.assertEqual("knowledge_seeded", session["current_stage"])
        examples = self.store.list_provider_chat_training_examples()

        self.assertEqual(8, len(examples))
        self.assertEqual("rumah_privat_madani_chatbot_knowledge.md#calistung", examples[0]["matched_reference"])
        self.assertIn("Les Privat Calistung", examples[0]["expected_reply"])
        self.assertIn("calistung", examples[0]["training_tags"])

    def test_provider_chatbot_knowledge_is_structured_for_chatbot_consumption(self) -> None:
        knowledge = self.store.provider_chatbot_knowledge()

        self.assertEqual("rumah_privat_madani", knowledge["knowledge_id"])
        self.assertEqual("Rumah Privat Madani", knowledge["business"]["name"])
        self.assertEqual(4, len(knowledge["packages"]))
        english = next(package for package in knowledge["packages"] if package["id"] == "english")
        self.assertEqual("needs_confirmation", english["price"]["status"])
        self.assertIn("Jangan membuat informasi", knowledge["answer_rules"][0])

    def test_unmatched_message_is_rejected_as_out_of_scope(self) -> None:
        session = self.store.create_provider_chat_simulation_session({"title": "Latihan guardrail"})
        result = self.store.send_provider_chat_simulation_message(
            session["id"],
            {"message": "Bisa les robotik sekalian antar jemput?"},
        )

        self.assertFalse(result["reply"]["needs_review"])
        self.assertEqual("out_of_scope", result["reply"]["intent"])
        examples = self.store.list_provider_chat_training_examples()
        self.assertFalse(examples[0]["needs_review"])

    def test_schedule_question_is_not_misread_as_whatsapp_contact(self) -> None:
        session = self.store.create_provider_chat_simulation_session({"title": "Latihan jadwal"})
        result = self.store.send_provider_chat_simulation_message(
            session["id"],
            {"message": "Jadwal belajar hari apa saja?"},
        )

        self.assertNotEqual("contact_info", result["reply"]["intent"])
        self.assertNotIn("WhatsApp", result["assistant_message"]["message"])

    def test_chatbot_asks_close_confirmation_after_question_threshold(self) -> None:
        session = self.store.create_provider_chat_simulation_session({"title": "Latihan threshold"})
        result = None

        for _ in range(10):
            result = self.store.send_provider_chat_simulation_message(session["id"], {"message": "Halo"})

        self.assertIsNotNone(result)
        self.assertEqual("close_confirmation_prompt", result["reply"]["intent"])
        self.assertIn("Apakah mau diteruskan ke pendaftaran?", result["assistant_message"]["message"])

    def test_chatbot_asks_close_confirmation_when_core_knowledge_is_exhausted(self) -> None:
        session = self.store.create_provider_chat_simulation_session({"title": "Latihan KB exhausted"})
        messages = [
            "Halo",
            "Ada paket apa saja di Rumah Privat Madani?",
            "Anak saya belum lancar membaca dan cepat bosan.",
            "Anak sudah bisa Iqra tetapi tajwidnya masih kurang.",
            "Apa materi English?",
            "Berapa harga English?",
            "Apa materi Matematika?",
            "Area layanannya di mana saja?",
        ]
        result = None
        for message in messages:
            result = self.store.send_provider_chat_simulation_message(session["id"], {"message": message})

        self.assertIsNotNone(result)
        self.assertEqual("close_confirmation_prompt", result["reply"]["intent"])
        self.assertIn("knowledge-exhausted", result["reply"]["training_tags"])

    def test_chatbot_continues_qa_when_handoff_declined(self) -> None:
        session = self.store.create_provider_chat_simulation_session({"title": "Latihan decline"})
        self.store.send_provider_chat_simulation_message(session["id"], {"message": "Saya mau daftar les."})
        result = self.store.send_provider_chat_simulation_message(session["id"], {"message": "Tidak dulu"})

        self.assertEqual("admin_handoff_declined", result["reply"]["intent"])
        self.assertEqual("continue_qa", result["reply"]["stage"])

    def test_provider_can_edit_assistant_response_for_training_example(self) -> None:
        session = self.store.create_provider_chat_simulation_session({"title": "Latihan edit"})
        result = self.store.send_provider_chat_simulation_message(
            session["id"],
            {"message": "Berapa harga English?"},
        )
        assistant_message = result["assistant_message"]

        updated = self.store.update_provider_chat_simulation_message(
            session["id"],
            assistant_message["id"],
            {"message": "Harga English akan dikonfirmasi admin dulu agar tidak keliru."},
        )

        self.assertEqual(
            "Harga English akan dikonfirmasi admin dulu agar tidak keliru.",
            updated["message"]["message"],
        )
        examples = self.store.list_provider_chat_training_examples()
        self.assertEqual(
            "Harga English akan dikonfirmasi admin dulu agar tidak keliru.",
            examples[0]["expected_reply"],
        )
        self.assertFalse(examples[0]["needs_review"])
        self.assertTrue(examples[0]["edited_by_provider"])

    def test_provider_edited_response_is_used_as_database_training_override(self) -> None:
        session = self.store.create_provider_chat_simulation_session({"title": "Latihan koreksi DB"})
        result = self.store.send_provider_chat_simulation_message(
            session["id"],
            {"message": "Berapa harga English?"},
        )
        self.store.update_provider_chat_simulation_message(
            session["id"],
            result["assistant_message"]["id"],
            {"message": "Koreksi DB: harga English harus dikonfirmasi admin dulu."},
        )

        new_session = self.store.create_provider_chat_simulation_session({"title": "Sesi setelah koreksi"})
        followup = self.store.send_provider_chat_simulation_message(
            new_session["id"],
            {"message": "Berapa harga English?"},
        )

        self.assertEqual("Koreksi DB: harga English harus dikonfirmasi admin dulu.", followup["assistant_message"]["message"])
        self.assertIn("db-training-override", followup["reply"]["training_tags"])

    def test_gemini_guardrail_rejects_unrelated_questions_without_calling_api(self) -> None:
        def fail_if_called(prompt: str) -> str:
            self.fail(f"Gemini tidak boleh dipanggil untuk pertanyaan out-of-scope: {prompt}")

        reply = simulate_provider_ai_reply("Siapa presiden Indonesia?", generate_content=fail_if_called)

        self.assertEqual(OUT_OF_SCOPE_MESSAGE, reply.message)
        self.assertEqual("out_of_scope", reply.intent)
        self.assertEqual("guardrail/out-of-scope", reply.matched_reference)

    def test_gemini_model_name_accepts_model_id_resource_or_endpoint(self) -> None:
        self.assertEqual("gemini-3.1-flash-lite", normalize_gemini_model_name("gemini-3.1-flash-lite"))
        self.assertEqual("gemini-3.1-flash-lite", normalize_gemini_model_name("models/gemini-3.1-flash-lite"))
        self.assertEqual(
            "gemini-3.1-flash-lite",
            normalize_gemini_model_name(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent"
            ),
        )

    def test_gemini_mode_uses_ai_reply_and_stores_training_example(self) -> None:
        session = self.store.create_provider_chat_simulation_session({"title": "Latihan Gemini"})
        fake_reply = SimulationReply(
            message="Halo kak, aku chatbot Rumah Privat Madani. Ada yang bisa aku bantu?",
            intent="greeting",
            stage="greeting",
            matched_reference="rumah_privat_madani_chatbot_knowledge.md#greeting",
            confidence=0.9,
            needs_review=False,
            training_tags=["gemini", "greeting"],
        )

        with patch("backend.app.store.simulate_provider_ai_reply", return_value=fake_reply) as mocked:
            result = self.store.send_provider_chat_simulation_message(
                session["id"],
                {"message": "Halo", "mode": "gemini"},
            )

        mocked.assert_called_once()
        self.assertEqual("greeting", result["reply"]["intent"])
        self.assertEqual("gemini", result["assistant_message"]["metadata"]["reply_mode"])
        examples = self.store.list_provider_chat_training_examples()
        self.assertEqual("Halo kak, aku chatbot Rumah Privat Madani. Ada yang bisa aku bantu?", examples[0]["expected_reply"])


if __name__ == "__main__":
    unittest.main()
