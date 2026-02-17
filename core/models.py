# core/models.py (исправленный)
"""Data models for WebDAV Manager."""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class FileInfo:
    """Information about a file or directory."""
    name: str
    path: str
    isdir: bool
    size: int = 0
    modified: str = ""
    islink: bool = False

    @classmethod
    def from_webdav_info(cls, info: dict) -> 'FileInfo':
        """Create FileInfo from webdav client info dict."""
        return cls(
            name=info.get('name', ''),
            path=info['path'],
            isdir=info['isdir'],
            size=int(info.get('size', 0) or 0),
            modified=info.get('modified', ''),
            islink=info.get('islink', False)
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileInfo':
        """Create FileInfo from dictionary."""
        return cls(
            name=data.get('name', ''),
            path=data.get('path', ''),
            isdir=data.get('isdir', False),
            size=int(data.get('size', 0) or 0),
            modified=data.get('modified', ''),
            islink=data.get('islink', False)
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'path': self.path,
            'isdir': self.isdir,
            'size': self.size,
            'modified': self.modified,
            'islink': self.islink
        }

    @property
    def extension(self) -> str:
        """Get file extension."""
        if self.isdir or '.' not in self.name:
            return ""
        return self.name.split('.')[-1].upper()

    @property
    def type_name(self) -> str:
        """Get human-readable type name."""
        if self.isdir:
            return "Папка"
        if self.islink:
            return "Ссылка"
        ext = self.extension
        return f"Файл ({ext})" if ext else "Файл"


@dataclass
class Account:
    """WebDAV account information."""
    id: str
    name: str
    url: str
    login: str
    password: str  # Encrypted
    type: str = "webdav"
    default_path: str = "/"
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> 'Account':
        """Create Account from dictionary."""
        return cls(
            id=data.get('id', ''),
            name=data['name'],
            url=data['url'],
            login=data['login'],
            password=data['password'],
            type=data.get('type', 'webdav'),
            default_path=data.get('default_path', '/'),
            enabled=data.get('enabled', True)
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'login': self.login,
            'password': self.password,
            'type': self.type,
            'default_path': self.default_path,
            'enabled': self.enabled
        }
