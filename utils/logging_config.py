# utils/logging_config.py
"""Logging configuration for WebDAV Manager."""

import logging
import os
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
    handlers = []

    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        log_file_path = str(log_path / log_file)

        # File handler
        file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        handlers.append(file_handler)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        handlers.append(console_handler)

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=handlers
    )