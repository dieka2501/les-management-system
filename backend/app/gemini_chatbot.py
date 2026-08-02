from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib import error, request
from urllib.parse import quote

from .chat_simulation import (
    SimulationReply,
    chat_lifecycle_reply,
    close_prompt_reply,
    detect_package,
    is_contact_question,
    is_coverage_question,
    is_greeting_question,
    is_list_packages_question,
    is_price_question,
    is_registration_question,
    load_chatbot_knowledge,
    maybe_add_close_prompt,
    normalize_text,
    OUT_OF_SCOPE_MESSAGE,
)


DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
GEMINI_ENDPOINT_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
UNRELATED_TOPIC_TERMS = (
    "saham",
    "crypto",
    "kripto",
    "bitcoin",
    "emas",
    "forex",
    "presiden",
    "politik",
    "pemilu",
    "cuaca",
    "film",
    "musik",
    "resep",
    "masak",
    "bola",
    "kuliah",
    "kampus",
    "universitas",
    "coding",
    "programming",
    "robotik",
    "antar jemput",
)


class GeminiConfigurationError(Exception):
    """Raised when Gemini integration is not configured correctly."""


class GeminiServiceError(Exception):
    """Raised when the Gemini API cannot return a usable response."""


@dataclass(frozen=True)
class KnowledgeContext:
    is_relevant: bool
    intent: str
    stage: str
    references: list[str]
    sections: list[str]
    training_tags: list[str]
    confidence: float


GenerateContent = Callable[[str], str]


def simulate_provider_ai_reply(
    message: str,
    history: list[dict[str, Any]] | None = None,
    *,
    generate_content: GenerateContent | None = None,
) -> SimulationReply:
    history = history or []
    normalized = normalize_text(message)
    lifecycle_reply = chat_lifecycle_reply(normalized, history)
    if lifecycle_reply:
        return lifecycle_reply

    if is_registration_question(normalized):
        return close_prompt_reply("registration_request", confidence=0.95)

    context = select_knowledge_context(message, history)
    if not context.is_relevant:
        return SimulationReply(
            message=OUT_OF_SCOPE_MESSAGE,
            intent="out_of_scope",
            stage="out_of_scope",
            matched_reference="guardrail/out-of-scope",
            confidence=0.99,
            needs_review=False,
            training_tags=["guardrail", "out-of-scope"],
        )

    prompt = build_gemini_prompt(message, history, context)
    model_text = generate_content(prompt) if generate_content else call_gemini_generate_content(prompt)
    answer = normalize_model_answer(model_text)
    if not answer:
        raise GeminiServiceError("Gemini tidak mengembalikan jawaban yang bisa dipakai.")

    reply = SimulationReply(
        message=answer,
        intent=context.intent,
        stage=context.stage,
        matched_reference=", ".join(context.references) if context.references else "rumah_privat_madani_chatbot_knowledge.md",
        confidence=context.confidence,
        needs_review=False,
        training_tags=["gemini", *context.training_tags],
    )
    return maybe_add_close_prompt(reply, history)


def gemini_api_key() -> str:
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise GeminiConfigurationError(
            "GEMINI_API_KEY atau GOOGLE_API_KEY belum diset. Jalankan server dengan salah satu environment variable itu."
        )
    return api_key


def gemini_model_name() -> str:
    model = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
    return normalize_gemini_model_name(model)


def normalize_gemini_model_name(value: str) -> str:
    model = value.strip().strip("\"'")
    model = model.split("?", 1)[0]
    model = model.removesuffix(":generateContent")
    if "/models/" in model:
        model = model.rsplit("/models/", 1)[-1]
    model = model.removeprefix("models/")
    model = model.removesuffix(":generateContent")
    model = model.strip().strip("\"'")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", model):
        raise GeminiConfigurationError(
            "Format GEMINI_MODEL tidak valid. Isi dengan model id saja, contoh: gemini-3.1-flash-lite."
        )
    return model


def call_gemini_generate_content(prompt: str) -> str:
    model = quote(gemini_model_name(), safe="-_.~")
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt,
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.8,
            "maxOutputTokens": 640,
        },
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    api_request = request.Request(
        GEMINI_ENDPOINT_TEMPLATE.format(model=model),
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": gemini_api_key(),
        },
        method="POST",
    )
    try:
        with request.urlopen(api_request, timeout=20) as response:
            response_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        raise GeminiServiceError(f"Gemini API gagal ({exc.code}): {extract_gemini_error(raw_body)}") from exc
    except error.URLError as exc:
        raise GeminiServiceError(f"Tidak bisa menghubungi Gemini API: {exc.reason}") from exc
    except TimeoutError as exc:
        raise GeminiServiceError("Request ke Gemini API timeout.") from exc

    try:
        payload = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise GeminiServiceError("Respons Gemini bukan JSON valid.") from exc

    return extract_gemini_text(payload)


def extract_gemini_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        prompt_feedback = payload.get("promptFeedback") or {}
        block_reason = prompt_feedback.get("blockReason")
        if block_reason:
            raise GeminiServiceError(f"Gemini memblokir prompt: {block_reason}.")
        raise GeminiServiceError("Gemini tidak mengembalikan kandidat jawaban.")

    parts = ((candidates[0].get("content") or {}).get("parts")) or []
    text = "\n".join(str(part.get("text", "")).strip() for part in parts if part.get("text"))
    if not text:
        raise GeminiServiceError("Gemini mengembalikan kandidat tanpa teks.")
    return text


def extract_gemini_error(raw_body: str) -> str:
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return raw_body[:300] or "Tidak ada detail error."
    message = ((payload.get("error") or {}).get("message")) or raw_body
    return str(message)[:500]


def select_knowledge_context(message: str, history: list[dict[str, Any]] | None = None) -> KnowledgeContext:
    knowledge = load_chatbot_knowledge()
    normalized = normalize_text(message)
    history_context = normalize_text(recent_parent_history(history or []))
    package_id = detect_package(normalized) or detect_package(history_context)

    base_sections = [format_business_context(knowledge), format_answer_rules(knowledge)]

    if is_greeting_question(normalized):
        return KnowledgeContext(
            is_relevant=True,
            intent="greeting",
            stage="greeting",
            references=["rumah_privat_madani_chatbot_knowledge.md#greeting"],
            sections=[*base_sections, format_package_list(knowledge)],
            training_tags=["greeting", "introduction"],
            confidence=0.9,
        )

    if is_coverage_question(normalized):
        return KnowledgeContext(
            is_relevant=True,
            intent="coverage_area",
            stage="answered_coverage",
            references=["rumah_privat_madani_chatbot_knowledge.md#coverage"],
            sections=base_sections,
            training_tags=["coverage", "location"],
            confidence=0.88,
        )

    if is_list_packages_question(normalized):
        return KnowledgeContext(
            is_relevant=True,
            intent="list_packages",
            stage="ask_package_selection",
            references=["rumah_privat_madani_chatbot_knowledge.md#packages"],
            sections=[*base_sections, format_package_list(knowledge)],
            training_tags=["packages", "opening"],
            confidence=0.88,
        )

    if is_contact_question(normalized):
        return KnowledgeContext(
            is_relevant=True,
            intent="contact_info",
            stage="answered_contact_info",
            references=["rumah_privat_madani_chatbot_knowledge.md#contact"],
            sections=base_sections,
            training_tags=["contact", "knowledge-base"],
            confidence=0.9,
        )

    if not package_id and has_unrelated_topic(normalized):
        return out_of_scope_context()

    if is_price_question(normalized) and is_price_context_relevant(normalized, history_context, package_id):
        sections = [*base_sections]
        references = ["rumah_privat_madani_chatbot_knowledge.md#package-price"]
        if package_id:
            package = package_by_id_from_knowledge(knowledge, package_id)
            if package:
                sections.append(format_package_context(package))
                references = [f"rumah_privat_madani_chatbot_knowledge.md#{package_id}-price"]
        else:
            sections.append(format_package_price_list(knowledge))
        return KnowledgeContext(
            is_relevant=True,
            intent="package_price",
            stage="answered_price",
            references=references,
            sections=sections,
            training_tags=["price", package_id or "clarification"],
            confidence=0.86,
        )

    if package_id:
        package = package_by_id_from_knowledge(knowledge, package_id)
        if package:
            return KnowledgeContext(
                is_relevant=True,
                intent="learning_materials",
                stage="answered_package_materials",
                references=[f"rumah_privat_madani_chatbot_knowledge.md#{package_id}"],
                sections=[*base_sections, format_package_context(package)],
                training_tags=[package_id, "materials"],
                confidence=0.84,
            )

    if looks_like_related_learning_question(normalized):
        return KnowledgeContext(
            is_relevant=True,
            intent="knowledge_base_boundary",
            stage="answered_with_boundary",
            references=["rumah_privat_madani_chatbot_knowledge.md#packages"],
            sections=[*base_sections, format_package_list(knowledge), format_unknown_items(knowledge)],
            training_tags=["guardrail", "knowledge-boundary"],
            confidence=0.72,
        )

    return out_of_scope_context()


def build_gemini_prompt(message: str, history: list[dict[str, Any]], context: KnowledgeContext) -> str:
    recent_history = format_recent_history(history)
    selected_context = "\n\n".join(context.sections)
    references = ", ".join(context.references)
    return f"""Kamu adalah chatbot resmi Rumah Privat Madani.

Tugas:
- Sapa calon orang tua dengan ramah saat mereka menyapa.
- Perkenalkan diri secara singkat sebagai chatbot Rumah Privat Madani saat konteksnya opening/greeting.
- Cari konteks dari KNOWLEDGE BASE TERPILIH di bawah.
- Jawab pertanyaan hanya berdasarkan knowledge base tersebut.
- MVP chatbot hanya menjawab pertanyaan. Jangan menawarkan promo, jangan mengajak daftar, dan jangan membuat aksi sales.
- Jangan menghubungkan pengguna ke admin dari jawaban Gemini. Proses close chat dan handoff admin ditangani oleh sistem setelah ada persetujuan pengguna.
- Jika informasi tidak ada, belum dikonfirmasi, atau ambigu, katakan perlu konfirmasi admin. Jangan mengarang.
- Jika pertanyaan tidak berhubungan dengan Rumah Privat Madani atau paket les di knowledge base, jawab persis:
  "{OUT_OF_SCOPE_MESSAGE}"
- Jangan menyebut "Bapak". Gunakan sapaan netral seperti "kak".
- Jawaban ringkas, jelas, dan dalam Bahasa Indonesia.

Intent terdeteksi: {context.intent}
Referensi konteks: {references}

RIWAYAT PERCAKAPAN TERAKHIR:
{recent_history or "- Belum ada riwayat."}

KNOWLEDGE BASE TERPILIH:
{selected_context}

PERTANYAAN PENGGUNA:
{message}

Jawab sebagai chatbot Rumah Privat Madani:"""


def normalize_model_answer(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
    return text


def recent_parent_history(history: list[dict[str, Any]]) -> str:
    messages = [item.get("message", "") for item in history[-6:] if item.get("role") == "parent"]
    return " ".join(str(message) for message in messages)


def format_recent_history(history: list[dict[str, Any]]) -> str:
    if not history:
        return ""
    rows = []
    for item in history[-8:]:
        role = "Calon orang tua" if item.get("role") == "parent" else "Asisten"
        rows.append(f"- {role}: {item.get('message', '')}")
    return "\n".join(rows)


def out_of_scope_context() -> KnowledgeContext:
    return KnowledgeContext(
        is_relevant=False,
        intent="out_of_scope",
        stage="out_of_scope",
        references=["guardrail/out-of-scope"],
        sections=[],
        training_tags=["guardrail", "out-of-scope"],
        confidence=0.99,
    )


def has_unrelated_topic(normalized: str) -> bool:
    return any(term in normalized for term in UNRELATED_TOPIC_TERMS)


def is_price_context_relevant(normalized: str, history_context: str, package_id: str | None) -> bool:
    if package_id:
        return True
    related_terms = ("rumah privat", "madani", "les", "privat", "paket", "sesi", "pertemuan", "anak", "guru", "tutor")
    if any(term in normalized for term in related_terms):
        return True
    if any(term in history_context for term in related_terms):
        return True
    if has_unrelated_topic(normalized):
        return False
    tokens = normalized.split()
    return len(tokens) <= 3 and any(token in tokens for token in ("harga", "biaya", "tarif", "bayar", "berapa"))


def looks_like_related_learning_question(normalized: str) -> bool:
    related_terms = (
        "rumah privat",
        "madani",
        "les",
        "privat",
        "paket",
        "belajar",
        "anak",
        "guru",
        "tutor",
        "jadwal",
        "materi",
        "kurikulum",
        "laporan",
        "daftar",
        "pendaftaran",
    )
    return any(term in normalized for term in related_terms)


def package_by_id_from_knowledge(knowledge: dict[str, Any], package_id: str) -> dict[str, Any] | None:
    return next((item for item in knowledge.get("packages", []) if item.get("id") == package_id), None)


def format_business_context(knowledge: dict[str, Any]) -> str:
    business = knowledge["business"]
    contact = business["contact"]
    areas = ", ".join(business["coverage_areas"])
    return (
        "Business:\n"
        f"- Nama: {business['name']}\n"
        f"- Jenis layanan: {business['service_type']}\n"
        f"- Format belajar: {business['teaching_format']}\n"
        f"- Area layanan: {areas}\n"
        f"- WhatsApp: {contact['whatsapp']}\n"
        f"- Instagram: {contact['instagram']}"
    )


def format_answer_rules(knowledge: dict[str, Any]) -> str:
    rules = "\n".join(f"- {rule}" for rule in knowledge.get("answer_rules", []))
    return f"Answer rules:\n{rules}"


def format_unknown_items(knowledge: dict[str, Any]) -> str:
    items = "\n".join(f"- {item}" for item in knowledge.get("admin_confirmation_needed", []))
    return f"Informasi yang perlu konfirmasi admin:\n{items}"


def format_package_list(knowledge: dict[str, Any]) -> str:
    rows = []
    for package in knowledge.get("packages", []):
        price = package.get("price", {})
        rows.append(f"- {package['name']} ({package['id']}): {price.get('display', 'harga belum tersedia')}")
    return "Daftar paket:\n" + "\n".join(rows)


def format_package_price_list(knowledge: dict[str, Any]) -> str:
    return format_package_list(knowledge)


def format_package_context(package: dict[str, Any]) -> str:
    chunks = [
        f"Paket: {package['name']} ({package['id']})",
        f"Aliases: {', '.join(package.get('aliases', []))}",
    ]
    for key in ("best_for", "features", "materials", "methods", "supporting_materials"):
        values = package.get(key)
        if values:
            chunks.append(f"{key}: " + "; ".join(str(item) for item in values))

    if package.get("levels"):
        level_rows = []
        for level in package["levels"]:
            level_rows.append(f"{level['name']}: " + "; ".join(level.get("materials", [])))
        chunks.append("levels: " + " | ".join(level_rows))

    price = package.get("price", {})
    if price:
        chunks.append(f"price_status: {price.get('status')}")
        chunks.append(f"price: {price.get('display')}")
    if package.get("tagline"):
        chunks.append(f"tagline: {package['tagline']}")
    if package.get("source_notes"):
        chunks.append("source_notes: " + "; ".join(package["source_notes"]))
    return "\n".join(chunks)
