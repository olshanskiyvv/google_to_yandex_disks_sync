import logging
import os
import sys
from pathlib import Path

from config import get_config


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("disks_sync")

    # Try to get log level from config, fallback to env or default
    try:
        app_config = get_config()
        log_level = app_config.logging.get("level", "INFO").upper()
        log_file = app_config.logging.get("file")
    except Exception:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        log_file = os.getenv("LOG_FILE")

    logger.setLevel(getattr(logging, log_level, logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


logger = setup_logger()
