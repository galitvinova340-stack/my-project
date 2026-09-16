from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config import PROJECT_ROOT


def setup_logging() -> None:
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    if root.handlers:
        return  # уже настроено (например, при повторном импорте)
    root.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    file_handler = RotatingFileHandler(
        log_dir / "monitor.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    root.addHandler(console_handler)
