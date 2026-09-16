"""Извлечение фактов о назначениях из сырых текстов источников (этап 1, раздел 3.1 PRD).

Использует LLM (Anthropic API) со структурированным выводом через tool-use:
модель получает пачку текстов-кандидатов и возвращает только те, что
действительно являются новостью о новом кадровом назначении в Костанайской
области, на должность из целевого диапазона (раздел 3.1).
"""
from __future__ import annotations

import logging

import anthropic

from .config import Settings
from .models import AppointmentCandidate, RawMention

logger = logging.getLogger(__name__)

MAX_TEXT_LEN = 1500
BATCH_SIZE = 20

SYSTEM_PROMPT = """\
Ты помогаешь отслеживать новости о новых кадровых назначениях в Костанайской \
области Республики Казахстан.

Целевой диапазон должностей: аким области, акимы районов/городов области, \
руководители областных управлений/департаментов/отделов, руководители \
профильных государственных предприятий и организаций квазигосударственного \
сектора региона.

Тебе дают пронумерованный список фрагментов текста из новостных источников. \
Для каждого фрагмента определи, идёт ли речь именно о НОВОМ назначении \
конкретного человека на такую должность (не увольнение, не рабочая встреча, \
не общая новость без факта назначения, не назначение вне Костанайской области).

Верни результат только через вызов инструмента report_appointments."""

TOOL_SCHEMA = {
    "name": "report_appointments",
    "description": "Список найденных фактов о назначениях в присланных фрагментах.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "mention_index": {"type": "integer"},
                        "is_relevant": {
                            "type": "boolean",
                            "description": "true, если это факт нового назначения в целевом диапазоне",
                        },
                        "full_name": {"type": "string"},
                        "new_position": {"type": "string"},
                        "organization": {"type": "string"},
                        "appointment_date": {
                            "type": "string",
                            "description": "Дата назначения в формате из текста, иначе пусто",
                        },
                        "verified_official": {
                            "type": "boolean",
                            "description": "true, если источник — официальный (сайт акимата, Aqorda, UKIMET)",
                        },
                    },
                    "required": ["mention_index", "is_relevant"],
                },
            }
        },
        "required": ["items"],
    },
}

OFFICIAL_SOURCE_MARKERS = ("kostanay.gov.kz", "aqorda_resmi", "KZgovernment")


def _truncate(text: str) -> str:
    text = text.strip().replace("\n", " ")
    return text[:MAX_TEXT_LEN]


def _batches(mentions: list[RawMention], size: int):
    for i in range(0, len(mentions), size):
        yield mentions[i : i + size]


def extract_appointments(
    mentions: list[RawMention], settings: Settings
) -> list[AppointmentCandidate]:
    if not mentions:
        return []
    if not settings.anthropic_api_key:
        logger.warning(
            "ANTHROPIC_API_KEY не задан — извлечение фактов пропущено (см. .env)."
        )
        return []

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    candidates: list[AppointmentCandidate] = []

    for batch in _batches(mentions, BATCH_SIZE):
        numbered = "\n\n".join(
            f"[{i}] Источник: {m.source_name} ({m.source_url})\nТекст: {_truncate(m.text)}"
            for i, m in enumerate(batch)
        )
        try:
            response = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=[TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": "report_appointments"},
                messages=[{"role": "user", "content": numbered}],
            )
        except Exception as exc:
            logger.error("Ошибка вызова LLM при извлечении фактов: %s", exc)
            continue

        tool_use = next(
            (b for b in response.content if b.type == "tool_use"), None
        )
        if not tool_use:
            continue

        for item in tool_use.input.get("items", []):
            if not item.get("is_relevant"):
                continue
            idx = item.get("mention_index")
            if idx is None or not (0 <= idx < len(batch)):
                continue
            mention = batch[idx]
            full_name = (item.get("full_name") or "").strip()
            new_position = (item.get("new_position") or "").strip()
            if not full_name or not new_position:
                continue
            candidates.append(
                AppointmentCandidate(
                    full_name=full_name,
                    new_position=new_position,
                    organization=(item.get("organization") or "").strip(),
                    appointment_date=(item.get("appointment_date") or "").strip(),
                    source_urls=[mention.source_url],
                    verified_official=bool(item.get("verified_official"))
                    or any(marker in mention.source_url for marker in OFFICIAL_SOURCE_MARKERS),
                )
            )

    logger.info("Извлечено кандидатов-назначений: %d из %d фрагментов", len(candidates), len(mentions))
    return candidates
