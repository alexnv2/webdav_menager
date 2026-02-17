# services/file_operations.py
"""File operations service."""

import os
import logging
from typing import Optional, List
from dataclasses import dataclass

from core.client import WebDAVClient

logger = logging.getLogger(__name__)


@dataclass
class OperationResult:
    """Result of a file operation."""
    success: bool
    message: str
    error: Optional[str] = None


class FileOperationService:
    """Service for file operations."""

    def __init__(self, client: WebDAVClient):
        self.client = client

    def copy_items(self, sources: List[str],
                   destination: str) -> OperationResult:
        """
        Copy multiple items to destination.

        Args:
            sources: List of source paths
            destination: Destination directory path

        Returns:
            OperationResult indicating success/failure
        """
        try:
            for src in sources:
                dest_path = os.path.join(destination,
                                         os.path.basename(src)).replace('\\',
                                                                        '/')

                # Generate unique name if copying to same directory
                if os.path.dirname(src) == destination and src == dest_path:
                    name, ext = os.path.splitext(os.path.basename(src))
                    counter = 1
                    while True:
                        new_name = f"{name} (копия {counter}){ext}"
                        new_path = os.path.join(destination, new_name).replace(
                            '\\', '/')
                        if new_path != src:
                            dest_path = new_path
                            break
                        counter += 1

                self.client.copy(src, dest_path)

            return OperationResult(
                success=True,
                message=f"Скопировано {len(sources)} элементов"
            )

        except Exception as e:
            logger.exception("Error copying items")
            return OperationResult(
                success=False,
                message="Ошибка копирования",
                error=str(e)
            )

    def move_items(self, sources: List[str],
                   destination: str) -> OperationResult:
        """
        Move multiple items to destination.

        Args:
            sources: List of source paths
            destination: Destination directory path

        Returns:
            OperationResult indicating success/failure
        """
        try:
            for src in sources:
                dest_path = os.path.join(destination,
                                         os.path.basename(src)).replace('\\',
                                                                        '/')

                if src == dest_path:
                    return OperationResult(
                        success=False,
                        message="Источник и назначение совпадают",
                        error="Cannot move to same location"
                    )

                self.client.move(src, dest_path)

            return OperationResult(
                success=True,
                message=f"Перемещено {len(sources)} элементов"
            )

        except Exception as e:
            logger.exception("Error moving items")
            return OperationResult(
                success=False,
                message="Ошибка перемещения",
                error=str(e)
            )

    def delete_items(self, paths: List[str]) -> OperationResult:
        """
        Delete multiple items.

        Args:
            paths: List of paths to delete

        Returns:
            OperationResult indicating success/failure
        """
        try:
            for path in paths:
                self.client.delete(path)

            return OperationResult(
                success=True,
                message=f"Удалено {len(paths)} элементов"
            )

        except Exception as e:
            logger.exception("Error deleting items")
            return OperationResult(
                success=False,
                message="Ошибка удаления",
                error=str(e)
            )

    def create_folder(self, path: str) -> OperationResult:
        """
        Create a folder.

        Args:
            path: Folder path to create

        Returns:
            OperationResult indicating success/failure
        """
        try:
            self.client.mkdir(path)
            return OperationResult(
                success=True,
                message=f"Папка создана: {os.path.basename(path)}"
            )

        except Exception as e:
            logger.exception("Error creating folder")
            return OperationResult(
                success=False,
                message="Ошибка создания папки",
                error=str(e)
            )

    def rename_item(self, old_path: str, new_name: str) -> OperationResult:
        """
        Rename an item.

        Args:
            old_path: Current path
            new_name: New name

        Returns:
            OperationResult indicating success/failure
        """
        try:
            parent = os.path.dirname(old_path.rstrip('/')) or '/'
            new_path = os.path.join(parent, new_name).replace('\\', '/')

            self.client.move(old_path, new_path)

            return OperationResult(
                success=True,
                message=f"Переименовано в: {new_name}"
            )

        except Exception as e:
            logger.exception("Error renaming item")
            return OperationResult(
                success=False,
                message="Ошибка переименования",
                error=str(e)
            )