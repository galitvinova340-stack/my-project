"""Мониторинг Telegram-каналов через Telethon (клиент личного аккаунта).

Bot API не подходит: бот не может читать историю произвольных публичных
каналов, на которые он не добавлен администратором (раздел 7.2 PRD).
Telethon подключается от имени личного Telegram-аккаунта пользователя,
который достаточно один раз авторизовать (см. scripts/telegram_login.py).
"""
from __future__ import annotations

import logging

from telethon import TelegramClient

from ..config import Settings, TelegramChannel
from ..models import RawMention
from ..state import StateStore

logger = logging.getLogger(__name__)


def build_client(settings: Settings) -> TelegramClient:
    if not (settings.telegram_api_id and settings.telegram_api_hash):
        raise RuntimeError(
            "TELEGRAM_API_ID/TELEGRAM_API_HASH не заданы в .env — "
            "получите их на https://my.telegram.org"
        )
    return TelegramClient(
        settings.telegram_session_path,
        int(settings.telegram_api_id),
        settings.telegram_api_hash,
    )


async def fetch_new_messages(
    client: TelegramClient,
    channel: TelegramChannel,
    state: StateStore,
    limit: int = 100,
) -> list[RawMention]:
    """Возвращает сообщения канала со времени последнего успешного прогона
    (курсор — id последнего просмотренного сообщения), чтобы не перечитывать
    всю историю каждый раз."""
    cursor_key = f"tg:{channel.handle}"
    last_id_raw = state.get_cursor(cursor_key)
    last_id = int(last_id_raw) if last_id_raw else None

    mentions: list[RawMention] = []
    max_id_seen = last_id or 0

    try:
        entity = await client.get_entity(channel.handle)
        async for message in client.iter_messages(entity, limit=limit, min_id=last_id or 0):
            if not message.text:
                continue
            max_id_seen = max(max_id_seen, message.id)
            mentions.append(
                RawMention(
                    source_name=channel.label,
                    source_url=f"https://t.me/{channel.handle}/{message.id}",
                    published_at=message.date,
                    text=message.text,
                )
            )
    except Exception as exc:  # сбой одного канала не должен останавливать весь прогон
        logger.warning("Канал %s недоступен: %s", channel.handle, exc)
        return []

    if max_id_seen:
        state.set_cursor(cursor_key, str(max_id_seen))

    logger.info("%s: получено %d новых сообщений", channel.label, len(mentions))
    return mentions


async def fetch_all(
    settings: Settings, channels: list[TelegramChannel], state: StateStore
) -> list[RawMention]:
    client = build_client(settings)
    all_mentions: list[RawMention] = []
    async with client:
        if not await client.is_user_authorized():
            raise RuntimeError(
                "Telegram-сессия не авторизована. Запустите один раз: "
                "python scripts/telegram_login.py"
            )
        for channel in channels:
            all_mentions.extend(await fetch_new_messages(client, channel, state))
    return all_mentions
