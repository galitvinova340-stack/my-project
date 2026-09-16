"""Модель данных карточки назначения (раздел 5 PRD)."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime


def normalize_key_part(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold().strip()
    value = re.sub(r"[^\w\s]", "", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value)
    return value


@dataclass
class RawMention:
    """Сырой фрагмент текста из источника, потенциально содержащий новость о назначении."""

    source_name: str
    source_url: str
    published_at: datetime | None
    text: str


@dataclass
class AppointmentCandidate:
    """Факт назначения, извлечённый из текста, до обогащения досье."""

    full_name: str
    new_position: str
    organization: str
    appointment_date: str  # как удалось определить: "16.09.2026" либо "сентябрь 2026"
    source_urls: list[str]
    verified_official: bool  # подтверждено официальным источником (Aqorda/UKIMET/сайт акимата)

    @property
    def dedup_key(self) -> str:
        return f"{normalize_key_part(self.full_name)}|{normalize_key_part(self.new_position)}"


@dataclass
class AppointmentCard:
    """Полная карточка (раздел 5 PRD) для записи в Excel."""

    fixed_at: datetime
    full_name: str
    photo_url: str
    new_position: str
    organization: str
    appointment_date: str
    previous_position: str
    career_path: str
    education: str
    contacts: str
    public_trace: str
    discussion_topics: str
    priority_segment: str = ""  # заполняется пользователем вручную
    interaction_status: str = "Не начат"
    sources: list[str] = field(default_factory=list)
    verification_status: str = "Требует проверки"

    @property
    def dedup_key(self) -> str:
        return f"{normalize_key_part(self.full_name)}|{normalize_key_part(self.new_position)}"

    def as_excel_row(self) -> list[str]:
        return [
            self.fixed_at.strftime("%d.%m.%Y %H:%M"),
            self.full_name,
            self.photo_url,
            self.new_position,
            self.organization,
            self.appointment_date,
            self.previous_position,
            self.career_path,
            self.education,
            self.contacts,
            self.public_trace,
            self.discussion_topics,
            self.priority_segment,
            self.interaction_status,
            "\n".join(self.sources),
            self.verification_status,
        ]


EXCEL_HEADERS = [
    "Дата фиксации",
    "ФИО",
    "Фото",
    "Новая должность",
    "Орган/организация",
    "Дата назначения",
    "Предыдущая должность",
    "Карьерный путь",
    "Образование",
    "Контакты",
    "Публичный след",
    "Резюме: темы для обсуждения",
    "Приоритет/сегмент",
    "Статус взаимодействия",
    "Источники",
    "Статус проверки",
]
