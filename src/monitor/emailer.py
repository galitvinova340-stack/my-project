"""Уведомления по email (раздел 3.5 PRD).

Отправляется независимо от доступности сетевого диска и указывает,
сохранилась ли карточка автоматически или требует сверки/добавления вручную.
"""
from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.mime.text import MIMEText

from .config import Settings
from .models import AppointmentCard

logger = logging.getLogger(__name__)


@dataclass
class NotifyItem:
    card: AppointmentCard
    saved_to_excel: bool


def build_message(items: list[NotifyItem]) -> str:
    lines = [
        f"Новых кадровых назначений: {len(items)}",
        "",
    ]
    for item in items:
        status = "сохранено в таблице" if item.saved_to_excel else \
            "НЕ сохранено автоматически — требуется сверка/добавление вручную"
        lines.append(f"- {item.card.full_name} — {item.card.new_position} ({item.card.organization}); {status}")
    return "\n".join(lines)


def send_notification(settings: Settings, items: list[NotifyItem]) -> None:
    if not items:
        return
    if not (settings.smtp_user and settings.smtp_password and settings.email_from):
        logger.warning(
            "SMTP не настроен (.env) — уведомление не отправлено, но карточки обработаны."
        )
        return

    body = build_message(items)
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"Новые кадровые назначения ({len(items)})"
    msg["From"] = settings.email_from
    msg["To"] = settings.email_to

    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as server:
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.email_from, [settings.email_to], msg.as_string())

    logger.info("Уведомление отправлено на %s (%d записей)", settings.email_to, len(items))
