# utils/helpers.py
import os
import logging
from datetime import datetime
from typing import Optional

# Создаем свой логгер вместо импорта из main
logger = logging.getLogger(__name__)


def format_size(size: int) -> str:
    """Format file size to human readable string."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"


def format_datetime(dt_str: str) -> str:
    """Format datetime string for display in DD.MM.YYYY HH:MM format."""
    if not dt_str:
        return ""

    try:
        # WebDAV usually returns dates in format: "2024-01-15T14:30:00Z"
        if 'T' in dt_str:
            # Remove 'Z' and parse
            dt_str = dt_str.replace('Z', '+00:00')
            dt = datetime.fromisoformat(dt_str)
            return dt.strftime("%d.%m.%Y %H:%M")
        else:
            # Try common formats
            for fmt in ['%Y-%m-%d %H:%M:%S', '%d.%m.%Y %H:%M', '%Y-%m-%d']:
                try:
                    dt = datetime.strptime(dt_str, fmt)
                    return dt.strftime("%d.%m.%Y %H:%M")
                except ValueError:
                    continue
    except Exception as e:
        logger.debug(f"Error formatting date '{dt_str}': {e}")

    return dt_str[:16]  # Return truncated original if parsing fails


def normalize_path(path: str) -> str:
    """Normalize path to always start with / and not end with / (except root)."""
    if not path:
        return "/"

    # Replace backslashes with forward slashes
    path = path.replace('\\', '/')

    # Ensure it starts with /
    if not path.startswith('/'):
        path = '/' + path

    # Remove trailing / except for root
    if path != '/' and path.endswith('/'):
        path = path.rstrip('/')

    return path


def join_path(*parts: str) -> str:
    """Join path parts."""
    # Filter out empty parts
    parts = [p for p in parts if p]

    if not parts:
        return "/"

    # Start with first part
    result = parts[0]

    # Add remaining parts
    for part in parts[1:]:
        if result.endswith('/'):
            if part.startswith('/'):
                result += part[1:]
            else:
                result += part
        else:
            if part.startswith('/'):
                result += part
            else:
                result += '/' + part

    return normalize_path(result)


def format_error(error: Exception) -> str:
    """Format error message."""
    if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
        return f"HTTP {error.response.status_code}: {str(error)}"
    return str(error)