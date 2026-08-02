from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


KNOWLEDGE_PATH = Path(__file__).resolve().parent / "knowledge" / "rumah_privat_madani.json"


@lru_cache(maxsize=1)
def load_chatbot_knowledge() -> dict[str, Any]:
    with KNOWLEDGE_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def package_catalog() -> list[dict[str, Any]]:
    return list(load_chatbot_knowledge()["packages"])


def package_by_id(package_id: str) -> dict[str, Any] | None:
    return next((item for item in package_catalog() if item["id"] == package_id), None)


def training_examples() -> list[dict[str, Any]]:
    return list(load_chatbot_knowledge()["training_examples"])


FAQ_SIMULATION_SCRIPT: list[dict[str, Any]] = training_examples()
DEFAULT_QUESTION_CLOSE_THRESHOLD = 10
CLOSE_CONFIRMATION_QUESTION = "Apakah mau diteruskan ke pendaftaran?"
CLOSE_HANDOFF_MESSAGE = "Baik, saya akan hubungkan ke admin."
CLOSE_DECLINED_MESSAGE = (
    "Baik kak, saya tetap bisa membantu menjawab pertanyaan seputar Rumah Privat Madani "
    "jika masih ada yang ingin ditanyakan."
)
SESSION_ALREADY_TRANSFERRED_MESSAGE = (
    "Percakapan ini sudah diteruskan ke admin. Mohon tunggu admin manusia untuk melanjutkan."
)
OUT_OF_SCOPE_MESSAGE = (
    "Maaf kak, aku hanya bisa membantu pertanyaan seputar Rumah Privat Madani, seperti paket les, "
    "harga, area layanan, materi belajar, kontak, dan pendaftaran."
)
CORE_KB_REFERENCES = (
    "rumah_privat_madani_chatbot_knowledge.md#greeting",
    "rumah_privat_madani_chatbot_knowledge.md#packages",
    "rumah_privat_madani_chatbot_knowledge.md#calistung",
    "rumah_privat_madani_chatbot_knowledge.md#btq-al-quran",
    "rumah_privat_madani_chatbot_knowledge.md#english",
    "rumah_privat_madani_chatbot_knowledge.md#english-price",
    "rumah_privat_madani_chatbot_knowledge.md#matematika",
    "rumah_privat_madani_chatbot_knowledge.md#coverage",
)


@dataclass(frozen=True)
class SimulationReply:
    message: str
    intent: str
    stage: str
    matched_reference: str
    confidence: float
    needs_review: bool
    training_tags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "intent": self.intent,
            "stage": self.stage,
            "matched_reference": self.matched_reference,
            "confidence": self.confidence,
            "needs_review": self.needs_review,
            "training_tags": self.training_tags,
        }


def normalize_text(value: str) -> str:
    lowered = value.lower()
    lowered = lowered.replace("rp", "")
    lowered = lowered.replace("al-qur'an", "al quran")
    lowered = lowered.replace("al-quran", "al quran")
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip()


def simulate_provider_reply(message: str, history: list[dict[str, Any]] | None = None) -> SimulationReply:
    history = history or []
    normalized = normalize_text(message)

    lifecycle_reply = chat_lifecycle_reply(normalized, history)
    if lifecycle_reply:
        return lifecycle_reply

    package_id = detect_package(normalized)
    if is_greeting_question(normalized):
        return maybe_add_close_prompt(reply_for_reference("greeting", confidence=0.96), history)

    if is_coverage_question(normalized):
        return maybe_add_close_prompt(reply_for_reference("coverage_area", confidence=0.94), history)

    if is_list_packages_question(normalized):
        return maybe_add_close_prompt(reply_for_reference("list_packages", confidence=0.94), history)

    if is_registration_question(normalized):
        return close_prompt_reply("registration_request", confidence=0.95)

    if is_contact_question(normalized):
        return maybe_add_close_prompt(contact_info_reply(confidence=0.92), history)

    if is_price_question(normalized):
        if package_id:
            return maybe_add_close_prompt(reply_for_price(package_id, confidence=0.94), history)
        return maybe_add_close_prompt(SimulationReply(
            message=(
                "Boleh kak, harga ingin ditanyakan untuk paket apa? Pilihan paketnya Calistung, BTQ, "
                "English Private for Children, atau Matematika."
            ),
            intent="package_price",
            stage="clarify_package",
            matched_reference="rumah_privat_madani_chatbot_knowledge.md#package-price",
            confidence=0.78,
            needs_review=False,
            training_tags=["price", "clarification"],
        ), history)

    if package_id:
        return maybe_add_close_prompt(reply_for_package(package_id, normalized), history)

    return SimulationReply(
        message=OUT_OF_SCOPE_MESSAGE,
        intent="out_of_scope",
        stage="out_of_scope",
        matched_reference="guardrail/out-of-scope",
        confidence=0.85,
        needs_review=False,
        training_tags=["guardrail", "out-of-scope"],
    )


def chat_lifecycle_reply(normalized: str, history: list[dict[str, Any]]) -> SimulationReply | None:
    if is_session_transferred_to_admin(history):
        return SimulationReply(
            message=SESSION_ALREADY_TRANSFERRED_MESSAGE,
            intent="admin_handoff_already_transferred",
            stage="transferred_to_admin",
            matched_reference="chatbot_close_policy#already-transferred",
            confidence=0.99,
            needs_review=False,
            training_tags=["close", "admin-handoff", "already-transferred"],
        )

    if is_waiting_for_close_confirmation(history):
        if is_negative_response(normalized):
            return SimulationReply(
                message=CLOSE_DECLINED_MESSAGE,
                intent="admin_handoff_declined",
                stage="continue_qa",
                matched_reference="chatbot_close_policy#declined",
                confidence=0.96,
                needs_review=False,
                training_tags=["close", "admin-handoff", "declined"],
            )
        if is_affirmative_response(normalized):
            return close_handoff_reply()

    return None


def maybe_add_close_prompt(reply: SimulationReply, history: list[dict[str, Any]]) -> SimulationReply:
    if not should_prompt_close(history, reply):
        return reply

    return SimulationReply(
        message=f"{reply.message}\n\n{CLOSE_CONFIRMATION_QUESTION}",
        intent="close_confirmation_prompt",
        stage="close_confirmation_prompt",
        matched_reference=f"{reply.matched_reference}, chatbot_close_policy#auto-close",
        confidence=min(reply.confidence, 0.88),
        needs_review=reply.needs_review,
        training_tags=[*reply.training_tags, "close", "handoff-consent", close_trigger(history, reply)],
    )


def should_prompt_close(history: list[dict[str, Any]], reply: SimulationReply) -> bool:
    if reply.needs_review:
        return False
    if reply.intent in {
        "close_confirmation_prompt",
        "admin_handoff_confirmed",
        "admin_handoff_declined",
        "admin_handoff_already_transferred",
        "out_of_scope",
        "needs_provider_review",
    }:
        return False
    if has_close_prompted(history) or is_session_transferred_to_admin(history):
        return False
    return user_question_count(history) + 1 >= question_close_threshold() or knowledge_context_exhausted(history, reply)


def close_trigger(history: list[dict[str, Any]], reply: SimulationReply) -> str:
    if knowledge_context_exhausted(history, reply):
        return "knowledge-exhausted"
    if user_question_count(history) + 1 >= question_close_threshold():
        return "question-threshold"
    return "manual"


def question_close_threshold() -> int:
    value = load_chatbot_knowledge().get("chat_closing", {}).get("question_threshold")
    try:
        threshold = int(value)
    except (TypeError, ValueError):
        return DEFAULT_QUESTION_CLOSE_THRESHOLD
    return max(1, threshold)


def close_prompt_reply(trigger: str, confidence: float = 0.95) -> SimulationReply:
    return SimulationReply(
        message=(
            "Untuk pendaftaran, admin manusia yang akan membantu prosesnya.\n\n"
            f"{CLOSE_CONFIRMATION_QUESTION}"
        ),
        intent="close_confirmation_prompt",
        stage="close_confirmation_prompt",
        matched_reference=f"chatbot_close_policy#{trigger}",
        confidence=confidence,
        needs_review=False,
        training_tags=["close", "handoff-consent", trigger],
    )


def close_handoff_reply() -> SimulationReply:
    return SimulationReply(
        message=CLOSE_HANDOFF_MESSAGE,
        intent="admin_handoff_confirmed",
        stage="transferred_to_admin",
        matched_reference="chatbot_close_policy#confirmed",
        confidence=0.98,
        needs_review=False,
        training_tags=["close", "admin-handoff", "confirmed"],
    )


def contact_info_reply(confidence: float) -> SimulationReply:
    knowledge = load_chatbot_knowledge()
    contact = knowledge["business"]["contact"]
    return SimulationReply(
        message=(
            f"Kontak Rumah Privat Madani yang tercantum adalah WhatsApp {contact['whatsapp']} "
            f"dan Instagram {contact['instagram']}."
        ),
        intent="contact_info",
        stage="answered_contact_info",
        matched_reference="rumah_privat_madani_chatbot_knowledge.md#contact",
        confidence=confidence,
        needs_review=False,
        training_tags=["contact", "knowledge-base"],
    )


def is_waiting_for_close_confirmation(history: list[dict[str, Any]]) -> bool:
    last_assistant = last_assistant_message(history)
    if not last_assistant:
        return False
    return last_assistant.get("intent") == "close_confirmation_prompt" or last_assistant.get("stage") == "close_confirmation_prompt"


def is_session_transferred_to_admin(history: list[dict[str, Any]]) -> bool:
    return any(
        item.get("role") == "assistant"
        and (item.get("intent") == "admin_handoff_confirmed" or item.get("stage") == "transferred_to_admin")
        for item in history
    )


def has_close_prompted(history: list[dict[str, Any]]) -> bool:
    return any(
        item.get("role") == "assistant" and item.get("intent") == "close_confirmation_prompt"
        for item in history
    )


def last_assistant_message(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((item for item in reversed(history) if item.get("role") == "assistant"), None)


def user_question_count(history: list[dict[str, Any]]) -> int:
    return sum(1 for item in history if item.get("role") == "parent")


def knowledge_context_exhausted(history: list[dict[str, Any]], reply: SimulationReply) -> bool:
    reference_text = "\n".join(
        str(item.get("matched_reference") or "")
        for item in history
        if item.get("role") == "assistant"
    )
    reference_text = f"{reference_text}\n{reply.matched_reference}"
    return all(reference in reference_text for reference in CORE_KB_REFERENCES)


def is_affirmative_response(normalized: str) -> bool:
    if is_negative_response(normalized):
        return False
    affirmative_tokens = {
        "ya",
        "iya",
        "boleh",
        "mau",
        "lanjut",
        "teruskan",
        "hubungkan",
        "ok",
        "oke",
        "baik",
        "setuju",
        "yes",
        "y",
    }
    affirmative_phrases = (
        "lanjutkan",
        "mau diteruskan",
        "teruskan ke admin",
        "hubungkan ke admin",
    )
    tokens = set(normalized.split())
    return bool(tokens & affirmative_tokens) or any(phrase in normalized for phrase in affirmative_phrases)


def is_negative_response(normalized: str) -> bool:
    negative_tokens = {
        "tidak",
        "nggak",
        "ga",
        "gak",
        "belum",
        "jangan",
        "nanti",
        "skip",
        "no",
    }
    negative_phrases = (
        "tidak dulu",
        "nggak dulu",
        "gak dulu",
        "ga dulu",
        "nanti dulu",
    )
    tokens = set(normalized.split())
    return bool(tokens & negative_tokens) or any(phrase in normalized for phrase in negative_phrases)


def reply_for_reference(intent: str, confidence: float) -> SimulationReply:
    item = next((example for example in FAQ_SIMULATION_SCRIPT if example["intent"] == intent), None)
    if item is None:
        raise ValueError(f"Training example intent tidak ditemukan: {intent}")
    return SimulationReply(
        message=item["expected_reply"],
        intent=item["intent"],
        stage=item["stage"],
        matched_reference=item["matched_reference"],
        confidence=confidence,
        needs_review=False,
        training_tags=list(item["training_tags"]),
    )


def reply_for_price(package_id: str, confidence: float) -> SimulationReply:
    if package_id == "english":
        return reply_for_reference("package_price", confidence)

    package = package_by_id(package_id)
    if package is None:
        return reply_for_reference("package_price", confidence)
    price = package["price"]
    return SimulationReply(
        message=f"Harga {package['name']} adalah {price['display']}.",
        intent="package_price",
        stage="answered_price",
        matched_reference=f"rumah_privat_madani_chatbot_knowledge.md#{package_id}-price",
        confidence=confidence,
        needs_review=False,
        training_tags=["price", package_id],
    )


def reply_for_package(package_id: str, normalized: str) -> SimulationReply:
    if package_id == "calistung":
        return reply_by_sequence(1, confidence=0.93)
    if package_id == "btq":
        return reply_by_sequence(3, confidence=0.93)
    if package_id == "english" and is_price_question(normalized):
        return reply_by_sequence(2, confidence=0.94)
    if package_id == "english":
        return SimulationReply(
            message=(
                "English Private for Children berisi pembelajaran fun and interactive, latihan speaking, "
                "reading, writing, serta vocabulary melalui permainan dan lagu. Pembelajaran bersifat "
                "personalized 1-on-1 dan disesuaikan dengan usia serta perkembangan anak."
            ),
            intent="learning_materials",
            stage="answered_package_materials",
            matched_reference="rumah_privat_madani_chatbot_knowledge.md#english",
            confidence=0.9,
            needs_review=False,
            training_tags=["english", "materials"],
        )
    if package_id == "matematika":
        return SimulationReply(
            message=(
                "Les Privat Matematika mencakup konsultasi PR dan ujian, modul serta latihan soal, "
                "dari tingkat mudah, HOTS, hingga soal lomba. Materi juga dapat disesuaikan dengan "
                "kurikulum Singapura atau Cambridge."
            ),
            intent="learning_materials",
            stage="answered_package_materials",
            matched_reference="rumah_privat_madani_chatbot_knowledge.md#matematika",
            confidence=0.9,
            needs_review=False,
            training_tags=["matematika", "materials"],
        )

    return reply_for_reference("list_packages", confidence=0.8)


def reply_by_sequence(sequence: int, confidence: float) -> SimulationReply:
    item = next((example for example in FAQ_SIMULATION_SCRIPT if int(example["sequence"]) == sequence), None)
    if item is None:
        raise ValueError(f"Training example sequence tidak ditemukan: {sequence}")
    return SimulationReply(
        message=item["expected_reply"],
        intent=item["intent"],
        stage=item["stage"],
        matched_reference=item["matched_reference"],
        confidence=confidence,
        needs_review=False,
        training_tags=list(item["training_tags"]),
    )


def detect_package(normalized: str) -> str | None:
    for package in package_catalog():
        aliases = [normalize_text(alias) for alias in package.get("aliases", [])]
        if any(alias and alias in normalized for alias in aliases):
            return package["id"]
    return None


def is_list_packages_question(normalized: str) -> bool:
    return any(phrase in normalized for phrase in ("paket apa", "paket les", "program apa", "daftar paket", "ada paket"))


def is_price_question(normalized: str) -> bool:
    if any(word in normalized for word in ("harga", "biaya", "tarif", "bayar")):
        return True
    price_context = ("sesi", "pertemuan", "les", "paket", "calistung", "btq", "english", "inggris", "matematika")
    return "berapa" in normalized and any(word in normalized for word in price_context)


def is_coverage_question(normalized: str) -> bool:
    return any(word in normalized for word in ("area", "wilayah", "lokasi", "daerah", "tasikmalaya", "ciamis", "singaparna"))


def is_registration_question(normalized: str) -> bool:
    return any(word in normalized for word in ("daftar", "pendaftaran", "mendaftar", "registrasi", "gabung"))


def is_contact_question(normalized: str) -> bool:
    contact_terms = ("kontak", "whatsapp", "wa", "nomor", "no hp", "instagram", "ig")
    return any(term in normalized for term in contact_terms)


def is_greeting_question(normalized: str) -> bool:
    greetings = (
        "halo",
        "hallo",
        "hai",
        "hi",
        "assalamualaikum",
        "selamat pagi",
        "selamat siang",
        "selamat sore",
        "selamat malam",
    )
    return any(greeting in normalized for greeting in greetings)
