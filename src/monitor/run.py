"""Точка входа: один полный прогон мониторинга (вызывается по расписанию,
3 раза в сутки — 08:00/13:00/17:00 Asia/Qyzylorda, раздел 6 PRD).

Регистрация расписания — scripts/register_task_scheduler.ps1 (Windows Task
Scheduler; локальное время машины уже совпадает с Asia/Qyzylorda).
"""
from __future__ import annotations

import asyncio
import logging

from . import excel_store
from .config import TELEGRAM_CHANNELS, WEB_SOURCES, settings
from .dossier import build_dossier
from .emailer import NotifyItem, send_notification
from .extraction import extract_appointments
from .logging_setup import setup_logging
from .models import RawMention
from .sources import akimat_site, telegram_source
from .state import StateStore

logger = logging.getLogger(__name__)


def collect_mentions(state: StateStore) -> list[RawMention]:
    mentions: list[RawMention] = []

    for source in WEB_SOURCES:
        mentions.extend(akimat_site.fetch_mentions(source))

    try:
        tg_mentions = asyncio.run(
            telegram_source.fetch_all(settings, TELEGRAM_CHANNELS, state)
        )
        mentions.extend(tg_mentions)
    except Exception as exc:  # сбой Telegram не должен останавливать весь прогон
        logger.warning("Мониторинг Telegram недоступен в этом прогоне: %s", exc)

    return mentions


def flush_pending(state: StateStore) -> int:
    """Пытается дозаписать в Excel карточки, отложенные из-за недоступности
    сетевого диска в предыдущие прогоны (раздел 7.1 PRD)."""
    pending = state.list_pending()
    flushed = 0
    for card in pending:
        try:
            excel_store.append_card(settings.excel_path, card)
        except excel_store.ExcelUnavailable:
            continue
        state.mark_excel_written(card.dedup_key)
        state.clear_pending(card.dedup_key)
        flushed += 1
    if flushed:
        logger.info("Дозаписано в Excel отложенных карточек: %d", flushed)
    return flushed


def sync_dedup_from_excel(state: StateStore) -> None:
    if not excel_store.is_reachable(settings.excel_dir):
        return
    try:
        keys = excel_store.read_existing_dedup_keys(settings.excel_path)
        state.import_known_keys(keys)
    except Exception as exc:
        logger.warning("Не удалось прочитать Excel для сверки дублей: %s", exc)


def run_once() -> None:
    state = StateStore(settings.state_dir / "monitor_state.db")

    flush_pending(state)
    sync_dedup_from_excel(state)

    mentions = collect_mentions(state)
    candidates = extract_appointments(mentions, settings)

    notify_items: list[NotifyItem] = []
    for candidate in candidates:
        if state.is_known(candidate.dedup_key):
            continue  # раздел 3.3 — дедупликация, повторная карточка не создаётся

        state.mark_seen(candidate.dedup_key, candidate.full_name, candidate.new_position)
        card = build_dossier(candidate, settings)

        saved = False
        try:
            excel_store.append_card(settings.excel_path, card)
            state.mark_excel_written(card.dedup_key)
            saved = True
        except excel_store.ExcelUnavailable as exc:
            logger.warning(
                "Сетевой диск недоступен, карточка отложена: %s (%s)", card.full_name, exc
            )
            state.queue_pending(card)

        notify_items.append(NotifyItem(card=card, saved_to_excel=saved))

    send_notification(settings, notify_items)

    logger.info(
        "Прогон завершён: фрагментов=%d, кандидатов=%d, новых=%d",
        len(mentions), len(candidates), len(notify_items),
    )


def main() -> None:
    setup_logging()
    try:
        run_once()
    except Exception:
        logger.exception("Прогон завершился с ошибкой")
        raise


if __name__ == "__main__":
    main()
