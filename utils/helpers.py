# utils/helpers.py (исправленный)
import os
import logging
from datetime import datetime
from typing import Optional, Union

logger = logging.getLogger(__name__)


def parse_webdav_date(date_str: str) -> datetime:
    """Parse WebDAV date format to datetime object."""
    if not date_str:
        return datetime.min

    try:
        # WebDAV usually returns dates in format: "2024-01-15T14:30:00Z"
        if 'T' in date_str:
            # Remove 'Z' and timezone info for parsing
            date_str = date_str.replace('Z', '+00:00')
            return datetime.fromisoformat(date_str)
        else:
            # Try common formats
            for fmt in ['%Y-%m-%d %H:%M:%S', '%d.%m.%Y %H:%M', '%Y-%m-%d',
                        '%a, %d %b %Y %H:%M:%S %Z', '%Y%m%dT%H%M%S']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
    except Exception as e:
        logger.debug(f"Error parsing date '{date_str}': {e}")

    return datetime.min


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


def format_datetime(dt_input: Union[str, datetime, None]) -> str:
    """
    Format datetime for display in DD.MM.YYYY HH:MM format.

    Args:
        dt_input: datetime object or string

    Returns:
        Formatted date string or empty string if input is invalid
    """
    if dt_input is None:
        return ""

    try:
        # If it's already a datetime object
        if isinstance(dt_input, datetime):
            dt = dt_input
        else:
            # Parse string to datetime
            dt = parse_webdav_date(dt_input)

        if dt and dt != datetime.min:
            return dt.strftime("%d.%m.%Y %H:%M")

    except Exception as e:
        logger.debug(f"Error formatting date: {e}")

    # Return original if parsing fails, but truncate if too long
    if isinstance(dt_input, str):
        return dt_input[:16] if len(dt_input) > 16 else dt_input
    return str(dt_input)[:16]


def normalize_path(path: str) -> str:
    """Normalize path to always start with / and not end with / (except root)."""
    if not path:
        return "/"

    # Replace backslashes with forward slashes
    path = path.replace('\\', '/')

    # Remove duplicate slashes
    while '//' in path:
        path = path.replace('//', '/')

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


def get_file_extension(filename: str) -> str:
    """Get file extension without dot."""
    if '.' in filename:
        return filename.rsplit('.', 1)[-1].lower()
    return ""


def is_hidden_file(filename: str) -> bool:
    """Check if file is hidden."""
    return filename.startswith('.')


def truncate_filename(filename: str, max_length: int = 50) -> str:
    """Truncate filename if too long."""
    if len(filename) <= max_length:
        return filename

    half = (max_length - 3) // 2
    return f"{filename[:half]}...{filename[-half:]}"