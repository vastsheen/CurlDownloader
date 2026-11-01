"""应用日志：写入项目根目录（打包后为 exe 同级）下的 logs 文件夹。"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .paths import resource_path

LOGGER_NAME = "curldownloader"
LOG_DIR_NAME = "logs"
LOG_FILE_NAME = "curldownloader.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(threadName)s %(message)s"


def log_directory() -> Path:
    """日志目录：源码运行用项目根目录，打包运行用 exe 所在目录。"""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = resource_path()
    return base / LOG_DIR_NAME


def log_file() -> Path:
    """日志文件完整路径。"""
    return log_directory() / LOG_FILE_NAME


def setup_logging() -> logging.Logger:
    """创建写文件的 logger；目录不可写时退化为不落盘，不影响程序启动。"""
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter(LOG_FORMAT)

    handler: logging.Handler
    try:
        directory = log_directory()
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_file(),
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
    except OSError:
        handler = logging.NullHandler()

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
