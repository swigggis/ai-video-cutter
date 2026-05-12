from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config import settings


def configure_logging() -> None:
    log_path = settings.logs_dir / "backend.log"
    handler = RotatingFileHandler(log_path, maxBytes=10_000_000, backupCount=5)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)
