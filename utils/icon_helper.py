# utils/icon_helper.py
"""Helper functions for icon management."""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_icon_path(icon_name: str) -> Optional[str]:
    """Get full path to icon file."""
    # Определяем корневую директорию проекта
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Try multiple possible locations
    possible_paths = [
        os.path.join(base_dir, 'resources', 'icons', icon_name),
        os.path.join(base_dir, 'icons', icon_name),
        os.path.join(base_dir, icon_name),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            logger.debug(f"Icon found: {path}")
            return path

    logger.warning(f"Icon not found: {icon_name}")
    return None