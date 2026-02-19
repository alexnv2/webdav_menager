# utils/helpers.py
"""Helper functions for WebDAV Manager."""

import os
import logging
from typing import Union, Optional, List, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


def format_size(size_bytes: Union[int, str, None]) -> str:
    """Format size in bytes to human-readable string."""
    try:
        if isinstance(size_bytes, str):
            size_bytes = int(size_bytes) if size_bytes.strip() else 0
        elif size_bytes is None:
            size_bytes = 0
        elif not isinstance(size_bytes, (int, float)):
            size_bytes = 0

        if size_bytes == 0:
            return "0 Б"

        units = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']
        i = 0
        size = float(size_bytes)

        while size >= 1024.0 and i < len(units) - 1:
            size /= 1024.0
            i += 1

        return f"{size:.1f} {units[i]}"

    except (ValueError, TypeError):
        return "0 Б"


def normalize_path(path: str) -> str:
    """Normalize path to use forward slashes."""
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


def join_path(parent: str, child: str) -> str:
    """Join path components with forward slashes."""
    parent = normalize_path(parent)
    child = child.lstrip('/')

    if parent == '/':
        return f"/{child}"
    return f"{parent}/{child}"


def get_parent_path(path: str) -> str:
    """Get parent directory path."""
    path = normalize_path(path)
    if path == '/':
        return '/'

    parent = os.path.dirname(path.rstrip('/'))
    return parent or '/'


def get_filename(path: str) -> str:
    """Get filename from path."""
    path = normalize_path(path)
    return os.path.basename(path.rstrip('/')) or path


def format_error(error: Exception) -> str:
    """Format error message for user display."""
    error_str = str(error)

    # Common error patterns
    if "timed out" in error_str.lower():
        return "Превышен таймаут. Проверьте соединение и попробуйте снова."
    elif "connection" in error_str.lower() and "refused" in error_str.lower():
        return "Соединение отклонено. Проверьте адрес сервера."
    elif "connection" in error_str.lower() and "reset" in error_str.lower():
        return "Соединение сброшено. Проверьте сеть."
    elif "name resolution" in error_str.lower():
        return "Не удается разрешить имя сервера. Проверьте URL."
    elif "permission denied" in error_str.lower():
        return "Отказано в доступе. Проверьте логин и пароль."
    elif "not found" in error_str.lower():
        return "Файл или папка не найдены."
    elif "already exists" in error_str.lower():
        return "Файл уже существует."

    # Return original if no pattern matches
    return error_str


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


def validate_url(url: str) -> bool:
    """Validate URL format."""
    if not url:
        return False

    url = url.strip()

    # Check scheme
    if not url.startswith(('http://', 'https://', 'webdav://')):
        return False

    # Check for basic domain format
    domain_part = url.split('://', 1)[-1]
    if not domain_part or '.' not in domain_part:
        return False

    return True


def validate_password(password: str, min_length: int = 8,
                      require_upper: bool = True,
                      require_digit: bool = True) -> Tuple[bool, str]:
    """Validate password strength."""
    if len(password) < min_length:
        return False, f"Минимум {min_length} символов"

    if require_upper and not any(c.isupper() for c in password):
        return False, "Хотя бы одна заглавная буква"

    if require_digit and not any(c.isdigit() for c in password):
        return False, "Хотя бы одна цифра"

    return True, ""


def truncate_filename(filename: str, max_length: int = 50) -> str:
    """Truncate filename to max length."""
    if len(filename) <= max_length:
        return filename

    half = (max_length - 3) // 2
    return f"{filename[:half]}...{filename[-half:]}"


def safe_filename(filename: str) -> str:
    """Remove unsafe characters from filename."""
    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')

    # Remove other unsafe characters
    unsafe_chars = '<>:"|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')

    return filename.strip()


def format_list(items: List[Any], max_items: int = 5) -> str:
    """Format list for display."""
    if not items:
        return ""

    count = len(items)
    if count <= max_items:
        return ", ".join(str(i) for i in items)

    first = items[:max_items]
    return f"{', '.join(str(i) for i in first)} и еще {count - max_items}"


def get_file_icon_name(filename: str, is_dir: bool = False) -> str:
    """Get icon name for file type."""
    if is_dir:
        return "folder"

    ext = os.path.splitext(filename)[1].lower()
    icon_map = {
        '.txt': 'text',
        '.py': 'python',
        '.jpg': 'image',
        '.jpeg': 'image',
        '.png': 'image',
        '.gif': 'image',
        '.pdf': 'pdf',
        '.doc': 'word',
        '.docx': 'word',
        '.xls': 'excel',
        '.xlsx': 'excel',
        '.zip': 'archive',
        '.rar': 'archive',
        '.7z': 'archive',
    }
    return icon_map.get(ext, 'file')