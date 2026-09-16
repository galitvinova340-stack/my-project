"""Точка входа проекта. Запускать из корня:
    .venv\\Scripts\\python run.py
или через Task Scheduler (см. scripts/register_task_scheduler.ps1).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from monitor.run import main  # noqa: E402

if __name__ == "__main__":
    main()
