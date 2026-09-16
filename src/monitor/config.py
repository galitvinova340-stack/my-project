"""Конфигурация: пути, расписание, список источников, секреты из .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class TelegramChannel:
    handle: str  # без @, как в username канала
    label: str


@dataclass(frozen=True)
class WebSource:
    name: str
    url: str


# Раздел 4 PRD — источники данных.
TELEGRAM_CHANNELS: list[TelegramChannel] = [
    TelegramChannel("aqorda_resmi", "Aqorda (пресс-служба Президента РК)"),
    TelegramChannel("KZgovernment", "UKIMET — Правительство РК"),
    TelegramChannel("kostanaynews", "Костанайские новости"),
    TelegramChannel("nashagazetakst", "Наша Газета (Костанай)"),
    TelegramChannel("qostanaytv", "Qostanay.TV"),
    TelegramChannel("kazinform_news", "Казинформ"),
    TelegramChannel("orda_kz", "ORDA"),
    TelegramChannel("tengrinews", "Tengrinews"),
    TelegramChannel("ktknews", "Новости КТК"),
    TelegramChannel("newsnurkz", "NUR.KZ"),
]

WEB_SOURCES: list[WebSource] = [
    WebSource("Акимат Костанайской области", "https://www.kostanay.gov.kz/ru/news"),
]

# Раздел 6 PRD — время проверки, Asia/Qyzylorda (UTC+5).
SCHEDULE_HOURS_QYZYLORDA = (8, 13, 17)
TIMEZONE = "Asia/Qyzylorda"

RELEVANT_REGION = "Костанайская область"


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    anthropic_model: str = field(
        default_factory=lambda: _env("ANTHROPIC_MODEL", "claude-sonnet-5")
    )

    telegram_api_id: str = field(default_factory=lambda: _env("TELEGRAM_API_ID"))
    telegram_api_hash: str = field(default_factory=lambda: _env("TELEGRAM_API_HASH"))
    telegram_session_name: str = field(
        default_factory=lambda: _env("TELEGRAM_SESSION_NAME", "state/telegram_session")
    )

    smtp_host: str = field(default_factory=lambda: _env("SMTP_HOST", "smtp.mail.ru"))
    smtp_port: int = field(default_factory=lambda: int(_env("SMTP_PORT", "465") or 465))
    smtp_user: str = field(default_factory=lambda: _env("SMTP_USER"))
    smtp_password: str = field(default_factory=lambda: _env("SMTP_PASSWORD"))
    email_from: str = field(default_factory=lambda: _env("EMAIL_FROM"))
    email_to: str = field(default_factory=lambda: _env("EMAIL_TO", "ga.litvinova@mail.ru"))

    excel_dir: Path = field(
        default_factory=lambda: Path(_env("EXCEL_DIR", r"C:\CKB\назначения"))
    )
    excel_filename: str = field(
        default_factory=lambda: _env("EXCEL_FILENAME", "Назначения.xlsx")
    )
    state_dir: Path = field(
        default_factory=lambda: PROJECT_ROOT / _env("STATE_DIR", "state")
    )

    @property
    def excel_path(self) -> Path:
        return self.excel_dir / self.excel_filename

    @property
    def telegram_session_path(self) -> str:
        p = Path(self.telegram_session_name)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        p.parent.mkdir(parents=True, exist_ok=True)
        return str(p)

    def __post_init__(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
