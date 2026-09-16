"""Формирование карточки-досье (этап 2, раздел 3.2 PRD).

Двухшаговый процесс:
1) модель с инструментом веб-поиска собирает по открытым источникам всё,
   что относится к полям карточки (карьера, образование, контакты,
   публичный след, темы для обсуждения);
2) отдельным вызовом (без поиска, с принудительным tool-use) результат
   аккуратно раскладывается по полям модели данных (раздел 5 PRD).

Если официального подтверждения найдено не было — статус проверки
остаётся "Требует проверки" (раздел 7.3 PRD), карточка не выдаётся как факт.
"""
from __future__ import annotations

import logging
from datetime import datetime

import anthropic

from .config import Settings
from .models import AppointmentCandidate, AppointmentCard

logger = logging.getLogger(__name__)

RESEARCH_SYSTEM_PROMPT = """\
Ты собираешь досье на человека, недавно назначенного на руководящую должность \
в Костанайской области Казахстана, для подготовки деловой встречи.

По открытым источникам найди и кратко изложи (только факты, с указанием, \
насколько источник надёжен):
- фото (ссылка на изображение, если есть в открытом доступе)
- предыдущая должность
- карьерный путь по годам (кратко)
- образование
- контакты приёмной/email/адрес
- публичный след: упоминания в СМИ, госзакупки, аффилированные компании, награды
- 3-5 вероятных тем для первого разговора: пересечения с бизнесом, общие связи,
  актуальный контекст новой должности

Если что-то не удалось найти — так и скажи, не выдумывай. В конце перечисли
все использованные ссылки-источники."""

REPORT_TOOL = {
    "name": "report_dossier",
    "description": "Структурированные поля карточки-досье.",
    "input_schema": {
        "type": "object",
        "properties": {
            "photo_url": {"type": "string"},
            "previous_position": {"type": "string"},
            "career_path": {"type": "string"},
            "education": {"type": "string"},
            "contacts": {"type": "string"},
            "public_trace": {"type": "string"},
            "discussion_topics": {"type": "string"},
            "sources": {"type": "array", "items": {"type": "string"}},
            "has_official_confirmation": {
                "type": "boolean",
                "description": "true, если само назначение подтверждено официальным источником",
            },
        },
        "required": ["previous_position", "career_path", "education", "contacts",
                      "public_trace", "discussion_topics", "sources"],
    },
}


def _research(client: anthropic.Anthropic, settings: Settings, candidate: AppointmentCandidate) -> str:
    prompt = (
        f"ФИО: {candidate.full_name}\n"
        f"Новая должность: {candidate.new_position}\n"
        f"Орган/организация: {candidate.organization}\n"
        f"Дата назначения: {candidate.appointment_date or 'неизвестна'}\n"
    )
    try:
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=4096,
            system=RESEARCH_SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        logger.warning("Веб-поиск для досье недоступен (%s), продолжаю без него.", exc)
        return ""

    text_parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    return "\n".join(text_parts)


def _structure(client: anthropic.Anthropic, settings: Settings, research_text: str) -> dict:
    if not research_text.strip():
        return {}
    try:
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2048,
            tools=[REPORT_TOOL],
            tool_choice={"type": "tool", "name": "report_dossier"},
            messages=[{
                "role": "user",
                "content": f"Разложи это досье по полям через report_dossier:\n\n{research_text}",
            }],
        )
    except Exception as exc:
        logger.warning("Не удалось структурировать досье: %s", exc)
        return {}

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    return tool_use.input if tool_use else {}


def build_dossier(candidate: AppointmentCandidate, settings: Settings) -> AppointmentCard:
    now = datetime.now()
    base_card = AppointmentCard(
        fixed_at=now,
        full_name=candidate.full_name,
        photo_url="",
        new_position=candidate.new_position,
        organization=candidate.organization,
        appointment_date=candidate.appointment_date,
        previous_position="",
        career_path="",
        education="",
        contacts="",
        public_trace="",
        discussion_topics="",
        sources=list(candidate.source_urls),
        verification_status="Подтверждено официальным источником"
        if candidate.verified_official else "Требует проверки",
    )

    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY не задан — досье собрано только из факта назначения.")
        return base_card

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    research_text = _research(client, settings, candidate)
    fields = _structure(client, settings, research_text)
    if not fields:
        return base_card

    base_card.photo_url = fields.get("photo_url", "") or ""
    base_card.previous_position = fields.get("previous_position", "") or ""
    base_card.career_path = fields.get("career_path", "") or ""
    base_card.education = fields.get("education", "") or ""
    base_card.contacts = fields.get("contacts", "") or ""
    base_card.public_trace = fields.get("public_trace", "") or ""
    base_card.discussion_topics = fields.get("discussion_topics", "") or ""
    extra_sources = fields.get("sources") or []
    base_card.sources = list(dict.fromkeys(base_card.sources + extra_sources))
    if fields.get("has_official_confirmation"):
        base_card.verification_status = "Подтверждено официальным источником"

    return base_card
