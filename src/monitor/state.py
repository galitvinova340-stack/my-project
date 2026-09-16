"""Локальное состояние: дедупликация, очередь отложенной записи в Excel,
курсоры источников (чтобы не перечитывать всю историю каналов каждый прогон).

Работает независимо от доступности сетевого диска — это гарантирует
требование раздела 8 PRD "отсутствие дублирования при повторных запусках"
даже если Excel был недоступен в момент обнаружения назначения.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .models import AppointmentCard

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_appointments (
    dedup_key TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    new_position TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    excel_written INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pending_cards (
    dedup_key TEXT PRIMARY KEY,
    card_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_cursor (
    source_name TEXT PRIMARY KEY,
    cursor_value TEXT NOT NULL
);
"""


class StateStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        with closing(self._connect()) as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    # --- дедупликация ---

    def is_known(self, dedup_key: str) -> bool:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT 1 FROM seen_appointments WHERE dedup_key = ?", (dedup_key,)
            ).fetchone()
            return row is not None

    def mark_seen(self, dedup_key: str, full_name: str, new_position: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO seen_appointments "
                "(dedup_key, full_name, new_position, first_seen_at, excel_written) "
                "VALUES (?, ?, ?, ?, 0)",
                (dedup_key, full_name, new_position, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def mark_excel_written(self, dedup_key: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "UPDATE seen_appointments SET excel_written = 1 WHERE dedup_key = ?",
                (dedup_key,),
            )
            conn.commit()

    def import_known_keys(self, keys: list[str]) -> None:
        """Синхронизация с ключами, уже присутствующими в Excel-файле
        (например, добавленными коллегами напрямую), чтобы не создавать дубликаты."""
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO seen_appointments "
                "(dedup_key, full_name, new_position, first_seen_at, excel_written) "
                "VALUES (?, '', '', ?, 1)",
                [(k, now) for k in keys],
            )
            conn.commit()

    # --- очередь отложенной записи (когда сетевой диск недоступен) ---

    def queue_pending(self, card: AppointmentCard) -> None:
        payload = asdict(card)
        payload["fixed_at"] = card.fixed_at.isoformat()
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO pending_cards (dedup_key, card_json, created_at) "
                "VALUES (?, ?, ?)",
                (card.dedup_key, json.dumps(payload, ensure_ascii=False),
                 datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def list_pending(self) -> list[AppointmentCard]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT card_json FROM pending_cards").fetchall()
        cards = []
        for (card_json,) in rows:
            data = json.loads(card_json)
            data["fixed_at"] = datetime.fromisoformat(data["fixed_at"])
            cards.append(AppointmentCard(**data))
        return cards

    def clear_pending(self, dedup_key: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute("DELETE FROM pending_cards WHERE dedup_key = ?", (dedup_key,))
            conn.commit()

    # --- курсоры источников (например, id последнего просмотренного сообщения канала) ---

    def get_cursor(self, source_name: str) -> str | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT cursor_value FROM source_cursor WHERE source_name = ?",
                (source_name,),
            ).fetchone()
            return row[0] if row else None

    def set_cursor(self, source_name: str, value: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO source_cursor (source_name, cursor_value) VALUES (?, ?) "
                "ON CONFLICT(source_name) DO UPDATE SET cursor_value = excluded.cursor_value",
                (source_name, value),
            )
            conn.commit()
