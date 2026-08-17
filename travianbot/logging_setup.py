"""Console + rotating file logging."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import LoggingConfig

_FORMAT = "%(asctime)s  %(levelname)-7s  %(name)-24s  %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(config: LoggingConfig, base_dir: Path) -> Path:
    level = getattr(logging, config.level, logging.INFO)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)

    console = logging.StreamHandler(stream=sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    log_path = Path(config.file)
    if not log_path.is_absolute():
        log_path = base_dir / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_path, maxBytes=config.max_bytes, backupCount=config.backup_count, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG if level <= logging.DEBUG else logging.INFO)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # These libraries are chatty and rarely interesting.
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    return log_path
