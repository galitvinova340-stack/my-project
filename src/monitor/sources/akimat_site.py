"""Сайт акимата Костанайской области (раздел 4.1 PRD).

Официальный сайт — единственный подтверждённый канал акимата на момент
составления PRD (Telegram-канал акимата не подтверждён, см. раздел 7.4).
"""
from __future__ import annotations

import logging

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_fixed

from ..config import WebSource
from ..models import RawMention

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppointmentsMonitor/1.0"
}


@retry(stop=stop_after_attempt(3), wait=wait_fixed(5), reraise=False)
def _fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or resp.encoding
    return resp.text


def fetch_mentions(source: WebSource) -> list[RawMention]:
    """Возвращает заголовки+ссылки последних новостей раздела.
    Дальнейшая фильтрация по релевантности (назначение/нет) выполняется
    LLM-экстрактором, здесь мы не пытаемся угадывать разметку сайта."""
    try:
        html = _fetch(source.url)
    except Exception as exc:  # сбой одного источника не должен ронять весь прогон
        logger.warning("Не удалось получить %s: %s", source.url, exc)
        return []

    soup = BeautifulSoup(html, "lxml")
    mentions: list[RawMention] = []

    for link in soup.find_all("a", href=True):
        text = link.get_text(strip=True)
        if not text or len(text) < 15:
            continue
        href = link["href"]
        if href.startswith("/"):
            from urllib.parse import urljoin
            href = urljoin(source.url, href)
        elif not href.startswith("http"):
            continue
        mentions.append(
            RawMention(
                source_name=source.name,
                source_url=href,
                published_at=None,
                text=text,
            )
        )

    logger.info("%s: получено %d кандидатов-ссылок", source.name, len(mentions))
    return mentions
