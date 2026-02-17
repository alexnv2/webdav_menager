# utils/logging_config.py
"""Logging configuration for WebDAV Manager."""

import logging
from pathlib import Path
from typing import Optional


def setup_logging(
        log_dir: Optional[str] = None,
        log_file: str = "webdav_manager.log",
        level: str = "INFO",
        console: bool = True
):
    """
    Configure logging for the application.

    Args:
        log_dir: Directory for log files
        log_file: Log file name
        level: Log level
        console: Whether to log to console
    """
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        log_file = str(log_path / log_file)

    handlers = []

    if console:
        handlers.append(logging.StreamHandler())

    if log_dir:
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
