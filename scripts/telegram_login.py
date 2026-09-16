"""Одноразовая интерактивная авторизация Telegram-клиента (Telethon).

Запустите вручную один раз:
    python scripts/telegram_login.py
Введите номер телефона и код подтверждения, когда попросят.
После этого появится файл сессии (state/telegram_session.session),
и все последующие запуски run.py будут работать без участия человека.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telethon.sync import TelegramClient  # noqa: E402

from monitor.config import settings  # noqa: E402


def main() -> None:
    if not (settings.telegram_api_id and settings.telegram_api_hash):
        raise SystemExit(
            "Заполните TELEGRAM_API_ID и TELEGRAM_API_HASH в .env "
            "(получить на https://my.telegram.org)."
        )
    with TelegramClient(
        settings.telegram_session_path,
        int(settings.telegram_api_id),
        settings.telegram_api_hash,
    ) as client:
        me = client.get_me()
        print(f"Успешно авторизован как: {me.first_name} (id={me.id})")


if __name__ == "__main__":
    main()
