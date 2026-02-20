# ui/file_browser.py
"""File browser tree view with model-view architecture."""

import logging
import traceback
import time
from typing import Optional, List, Dict, Any, Union
from functools import lru_cache, wraps

from PyQt5.QtCore import (QAbstractItemModel, QModelIndex, Qt, QThread,
                          QObject, pyqtSignal, QTimer)
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (QTreeView, QMenu, QApplication,
                             QStyle, QHeaderView, QMessageBox)

from core.client import WebDAVClient
from core.models import FileInfo
from utils.helpers import format_size

logger = logging.getLogger(__name__)


def log_method_call(func):
    """Декоратор для логирования вызовов методов."""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        logger.debug(
            f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        try:
            result = func(self, *args, **kwargs)
            return result
        except Exception as e:
            logger.error(
                f"Error in {func.__name__}: {e}\n{traceback.format_exc()}")
            raise

    return wrapper


class DirectoryLoader(QObject):
    """Background directory loader with caching and retry logic."""

    loaded = pyqtSignal(str, list)  # path, files
    error = pyqtSignal(str, str)  # path, error
    progress = pyqtSignal(str, int)  # path, progress (0-100)
    not_found = pyqtSignal(str)  # path - директория не найдена

    def __init__(self, client: WebDAVClient):
        super().__init__()
        self.client = client
        self._active_requests: Dict[str, bool] = {}
        self._cache: Dict[str, tuple] = {}  # path -> (files, timestamp)
        self._cache_timeout = 30  # seconds

    @log_method_call
    def load_path(self, path: str, force: bool = False):
        """Load directory contents in background."""
        # Проверяем, не загружается ли уже эта директория
        if self._active_requests.get(path, False):
            logger.debug(f"Already loading {path}, skipping duplicate request")
            return

        logger.info(f"Loading directory: {path} (force={force})")
        self._active_requests[path] = True
        self.progress.emit(path, 10)

        try:
            # Проверяем кэш если не force
            if not force and path in self._cache:
                files, timestamp = self._cache[path]
                if time.time() - timestamp < self._cache_timeout:
                    logger.debug(f"Using cached data for {path}")
                    self.progress.emit(path, 100)
                    self.loaded.emit(path, files)
                    return

            self.progress.emit(path, 30)

            # Загружаем данные
            try:
                if force:
                    files = self.client.list_files_no_cache(path)
                else:
                    files = self.client.list_files(path)
            except Exception as e:
                error_str = str(e)
                if "not found" in error_str.lower() or "404" in error_str:
                    logger.warning(f"Directory not found: {path}")
                    self.not_found.emit(path)
                    self.loaded.emit(path, [])  # Пустая директория
                    return
                else:
                    # Другая ошибка, пробуем с force=True
                    logger.error(f"Error loading files from {path}: {e}")
                    logger.info(f"Retrying {path} with force=True")
                    files = self.client.list_files_no_cache(path)

            self.progress.emit(path, 70)

            # Конвертируем в dict для Qt
            files_dict = self._convert_to_dict(files)

            # Сохраняем в кэш
            self._cache[path] = (files_dict, time.time())

            self.progress.emit(path, 100)
            self.loaded.emit(path, files_dict)

        except Exception as e:
            error_str = str(e)
            if "not found" in error_str.lower() or "404" in error_str:
                logger.warning(f"Directory not found (final): {path}")
                self.not_found.emit(path)
                self.loaded.emit(path, [])
            else:
                logger.exception(f"Error loading {path}")
                self.error.emit(path, str(e))
        finally:
            self._active_requests.pop(path, None)

    def _convert_to_dict(self, files: List[Any]) -> List[Dict]:
        """Convert files to dict representation."""
        if not files:
            return []

        if files and hasattr(files[0], 'to_dict'):
            return [f.to_dict() for f in files]
        return files

    def clear_cache(self, path: Optional[str] = None):
        """Clear cache for path or all cache."""
        if path:
            self._cache.pop(path, None)
            logger.debug(f"Cleared cache for {path}")
        else:
            self._cache.clear()
            logger.debug("Cleared all cache")


class FileSystemItem:
    """Internal tree item for file browser with lazy loading."""

    __slots__ = (
    'parent', 'file_info', 'children', 'is_loaded', 'is_placeholder',
    '_path_cache', '_name_cache', '_row_cache', '_deleted')

    def __init__(self, parent: Optional['FileSystemItem'] = None,
                 file_info: Optional[FileInfo] = None,
                 is_placeholder: bool = False):
        self.parent = parent
        self.file_info = file_info
        self.children: List['FileSystemItem'] = []
        self.is_loaded = False
        self.is_placeholder = is_placeholder
        self._path_cache = None
        self._name_cache = None
        self._row_cache = None
        self._deleted = False

    @property
    def path(self) -> str:
        """Get item path with caching."""
        if self._deleted:
            return ""
        if self._path_cache is not None:
            return self._path_cache

        if self.file_info:
            self._path_cache = self.file_info.path
        elif self.parent and not self.parent._deleted:
            # Для корневого элемента
            self._path_cache = "/"
        else:
            self._path_cache = "/"

        return self._path_cache

    @property
    def name(self) -> str:
        """Get item name."""
        if self._deleted:
            return ""
        if self._name_cache is not None:
            return self._name_cache

        if self.file_info:
            self._name_cache = self.file_info.name
        else:
            self._name_cache = "/"

        return self._name_cache

    @property
    def isdir(self) -> bool:
        """Check if item is directory."""
        if self._deleted or not self.file_info:
            return False
        return self.file_info.isdir

    @property
    def has_children(self) -> bool:
        """Check if item can have children."""
        if self._deleted:
            return False
        return self.isdir

    def add_child(self, child: 'FileSystemItem'):
        """Add child item."""
        if self._deleted:
            return
        self.children.append(child)
        child.parent = self
        # Инвалидируем кэш
        self._row_cache = None

    def child(self, row: int) -> Optional['FileSystemItem']:
        """Get child by row."""
        if self._deleted:
            return None
        if 0 <= row < len(self.children):
            child = self.children[row]
            if child._deleted:
                # Удаляем из списка при доступе
                self.children.pop(row)
                return None
            return child
        return None

    def row(self) -> int:
        """Get row index in parent."""
        if self._deleted:
            return -1
        if self._row_cache is not None:
            return self._row_cache

        if self.parent and not self.parent._deleted:
            try:
                self._row_cache = self.parent.children.index(self)
                return self._row_cache
            except ValueError:
                return 0
        return 0

    def mark_deleted(self):
        """Mark item as deleted."""
        self._deleted = True
        self.file_info = None
        self.parent = None
        self.children.clear()
        self._path_cache = None
        self._name_cache = None
        self._row_cache = None

    def clear_cache(self):
        """Clear internal caches."""
        if self._deleted:
            return
        self._row_cache = None
        self._path_cache = None
        self._name_cache = None
        # Копируем список для безопасной итерации
        children_copy = self.children[:]
        for child in children_copy:
            if child and not child._deleted:
                child.clear_cache()

    def find_child_by_path(self, path: str) -> Optional['FileSystemItem']:
        """Find child by path recursively."""
        if self._deleted:
            return None
        if self.path == path:
            return self

        # Копируем список для безопасной итерации
        children_copy = self.children[:]
        for child in children_copy:
            if child and not child._deleted and path.startswith(child.path):
                result = child.find_child_by_path(path)
                if result:
                    return result

        return None

    def find_child_by_name(self, name: str) -> Optional['FileSystemItem']:
        """Find child by name."""
        if self._deleted:
            return None
        for child in self.children:
            if child and not child._deleted and child.name == name:
                return child
        return None


class FileBrowserModel(QAbstractItemModel):
    """Model for file browser tree view with async loading."""

    requestLoad = pyqtSignal(str, bool)  # path, force
    directoryLoaded = pyqtSignal(str)
    loadingProgress = pyqtSignal(str, int)  # path, progress
    directoryNotFound = pyqtSignal(str)  # path
    errorOccurred = pyqtSignal(str, str)  # path, error
    itemDeleted = pyqtSignal(str)  # path

    def __init__(self, client: WebDAVClient):
        super().__init__()
        self.client = client
        self._icon_cache = {}
        self._pending_loads: Dict[str, bool] = {}
        self._load_timer = QTimer()
        self._load_timer.setSingleShot(True)
        self._load_timer.setInterval(100)
        self._load_timer.timeout.connect(self._process_pending_loads)
        self._load_errors: Dict[str, int] = {}  # path -> error count
        self._max_retries = 2
        self._not_found_paths: set = set()  # пути, которые не найдены
        self._item_path_map: Dict[
            str, FileSystemItem] = {}  # карта путей для быстрого поиска
        self.current_path = "/"
        self._update_pending = False
        self._is_shutting_down = False

        # Setup loader thread
        self._loader_thread = QThread()
        self._loader = DirectoryLoader(client)
        self._loader.moveToThread(self._loader_thread)

        # Setup root item (after _item_path_map is created)
        self._setup_root_item()

        # Connect signals
        self._connect_signals()

        self._loader_thread.start()

    def _setup_root_item(self):
        """Setup root item with proper FileInfo."""
        # Создаем корневой элемент без FileInfo
        self.root_item = FileSystemItem(file_info=None)
        self._item_path_map["/"] = self.root_item

    def _connect_signals(self):
        """Connect all signals."""
        self.requestLoad.connect(
            self._loader.load_path,
            Qt.QueuedConnection
        )
        self._loader.loaded.connect(
            self.on_directory_loaded,
            Qt.QueuedConnection
        )
        self._loader.error.connect(
            self.on_directory_error,
            Qt.QueuedConnection
        )
        self._loader.progress.connect(
            self.loadingProgress,
            Qt.QueuedConnection
        )
        self._loader.not_found.connect(
            self.on_directory_not_found,
            Qt.QueuedConnection
        )

    def shutdown(self):
        """Clean up loader thread."""
        if self._is_shutting_down:
            return

        self._is_shutting_down = True
        logger.info("Shutting down model...")

        if self._loader_thread.isRunning():
            logger.info("Shutting down loader thread...")
            self._loader_thread.quit()
            if not self._loader_thread.wait(2000):
                logger.warning("Loader thread did not quit, terminating")
                self._loader_thread.terminate()
                self._loader_thread.wait()

        # Очищаем все ссылки
        self._item_path_map.clear()
        if hasattr(self, 'root_item'):
            self.root_item.mark_deleted()
            self.root_item = None

        logger.info("Model shutdown complete")

    @log_method_call
    def set_root(self, path: str):
        """Set current root path."""
        if self._is_shutting_down:
            return

        # Нормализуем путь
        path = self._normalize_path(path)

        if path != self.current_path:
            logger.info(f"Changing root from {self.current_path} to {path}")
            self.current_path = path
            # Проверяем, не помечен ли путь как не найденный
            if path in self._not_found_paths:
                logger.warning(
                    f"Path {path} is marked as not found, skipping load")
                self.directoryNotFound.emit(path)
                return
            self._queue_load(path)

    def _normalize_path(self, path: str) -> str:
        """Normalize path for consistent handling."""
        if not path:
            return "/"
        # Убираем лишние слеши
        path = path.replace("\\", "/")
        while "//" in path:
            path = path.replace("//", "/")
        # Убираем trailing slash кроме корня
        if path != "/" and path.endswith("/"):
            path = path[:-1]
        return path

    @log_method_call
    def refresh(self):
        """Refresh current directory."""
        if self._is_shutting_down:
            return

        logger.info(f"Refreshing directory: {self.current_path}")
        # При рефреше очищаем пометку о ненайденном пути
        self._not_found_paths.discard(self.current_path)
        self._queue_load(self.current_path, force=True)

    def _queue_load(self, path: str, force: bool = False):
        """Queue directory loading with debouncing."""
        if self._is_shutting_down:
            return
        self._pending_loads[path] = force
        self._load_timer.start()

    def _process_pending_loads(self):
        """Process queued directory loads."""
        if self._is_shutting_down:
            return

        for path, force in self._pending_loads.items():
            self._load_directory(path, force)
        self._pending_loads.clear()

    def _load_directory(self, path: str, force: bool = False):
        """Request directory loading."""
        if self._is_shutting_down:
            return
        logger.debug(f"Requesting load for {path} (force={force})")
        self.requestLoad.emit(path, force)

    @lru_cache(maxsize=128)
    def _get_icon(self, is_dir: bool, is_link: bool) -> QIcon:
        """Get cached icon for file type."""
        try:
            style = QApplication.style()
            if is_dir:
                if is_link:
                    return style.standardIcon(QStyle.SP_DirLinkIcon)
                return style.standardIcon(QStyle.SP_DirIcon)
            else:
                if is_link:
                    return style.standardIcon(QStyle.SP_FileLinkIcon)
                return style.standardIcon(QStyle.SP_FileIcon)
        except:
            return QIcon()

    @log_method_call
    def on_directory_loaded(self, path: str, files: List[Dict]):
        """Handle directory loaded."""
        if self._is_shutting_down:
            return

        logger.info(f"Directory loaded: {path} with {len(files)} items")

        # Сбрасываем счетчик ошибок для этого пути
        self._load_errors.pop(path, None)
        self._not_found_paths.discard(path)

        # Нормализуем путь
        path = self._normalize_path(path)

        # Находим элемент для этого пути
        item = self._get_item_for_path(path)
        if not item:
            logger.warning(
                f"Item for path {path} not found, creating new item")
            # Создаем новый элемент, если не найден
            item = FileSystemItem(file_info=None)
            # Пытаемся найти родителя
            parent_path = path.rsplit('/', 1)[0] if '/' in path else "/"
            parent_path = parent_path or "/"
            parent_item = self._get_item_for_path(parent_path)
            if parent_item and not parent_item._deleted:
                parent_item.add_child(item)
                self._item_path_map[path] = item
            else:
                # Если родитель не найден, добавляем в корень
                if self.root_item and not self.root_item._deleted:
                    self.root_item.add_child(item)
                    self._item_path_map[path] = item

        if not item or item._deleted:
            logger.warning(f"Item for path {path} is invalid or deleted")
            return

        # Очищаем детей перед обновлением
        item.children.clear()
        item.is_loaded = True

        # Separate directories and files for sorting
        dirs = []
        files_list = []

        for f in files:
            try:
                file_info = FileInfo.from_dict(f)
                # Нормализуем путь для элемента
                file_info.path = self._normalize_path(file_info.path)
                if file_info.isdir:
                    dirs.append(file_info)
                else:
                    files_list.append(file_info)
            except Exception as e:
                logger.error(f"Error creating item from {f}: {e}")

        logger.debug(
            f"Found {len(dirs)} directories and {len(files_list)} files")

        # Sort directories and files alphabetically
        dirs.sort(key=lambda x: x.name.lower())
        files_list.sort(key=lambda x: x.name.lower())

        # Add placeholder for empty directory
        if not dirs and not files_list and path != "/":
            logger.debug(f"Adding placeholder for empty directory: {path}")
            # Создаем placeholder
            placeholder = FileSystemItem(
                parent=item,
                file_info=None,
                is_placeholder=True
            )
            item.add_child(placeholder)
        else:
            # Add directories first
            for file_info in dirs:
                child = FileSystemItem(parent=item, file_info=file_info)
                item.add_child(child)
                self._item_path_map[file_info.path] = child

            # Then add files
            for file_info in files_list:
                child = FileSystemItem(parent=item, file_info=file_info)
                item.add_child(child)

        # Уведомляем модель о глобальных изменениях
        logger.debug(f"Emitting layoutChanged for path: {path}")
        self.layoutChanged.emit()

        # Эмитируем directoryLoaded для обновления представления
        self.directoryLoaded.emit(path)

    def on_directory_not_found(self, path: str):
        """Handle directory not found."""
        if self._is_shutting_down:
            return

        logger.warning(f"Directory not found: {path}")
        self._not_found_paths.add(path)

        # Если это текущая директория, сообщаем об ошибке
        if path == self.current_path:
            self.directoryNotFound.emit(path)

    @log_method_call
    def on_directory_error(self, path: str, error: str):
        """Handle directory loading error."""
        if self._is_shutting_down:
            return

        error_count = self._load_errors.get(path, 0) + 1
        self._load_errors[path] = error_count

        logger.error(
            f"Error loading {path} (attempt {error_count}/{self._max_retries}): {error}")

        # Проверяем, не превышен ли лимит попыток
        if error_count < self._max_retries and path == self.current_path:
            logger.info(f"Retrying load for {path} in 1 second...")
            QTimer.singleShot(1000,
                              lambda: self._load_directory(path, force=True))
        else:
            logger.error(f"Max retries reached for {path}")
            self.errorOccurred.emit(path, error)
            # Show empty directory with error indication
            self.on_directory_loaded(path, [])

    def handle_item_deleted(self, path: str):
        """Handle item deletion."""
        if self._is_shutting_down:
            return

        logger.info(f"Item deleted: {path}")

        # Находим и помечаем элемент как удаленный
        item = self._get_item_for_path(path)
        if item and not item._deleted:
            # Удаляем из карты путей
            if path in self._item_path_map:
                del self._item_path_map[path]

            # Помечаем как удаленный
            item.mark_deleted()

            # Обновляем родителя
            parent_path = path.rsplit('/', 1)[0] if '/' in path else "/"
            parent_path = parent_path or "/"
            parent_item = self._get_item_for_path(parent_path)
            if parent_item and not parent_item._deleted:
                # Очищаем детей родителя
                parent_item.children = [c for c in parent_item.children if
                                        not c._deleted]

            # Обновляем отображение
            self.layoutChanged.emit()
            self.itemDeleted.emit(path)

    def _get_item_for_path(self, path: str) -> Optional[FileSystemItem]:
        """Get item for path with recursive search."""
        if self._is_shutting_down or not self.root_item:
            return None

        path = self._normalize_path(path)

        # Сначала проверяем карту путей
        if path in self._item_path_map:
            item = self._item_path_map[path]
            if item and not item._deleted:
                return item
            else:
                # Удаляем из карты, если элемент удален
                del self._item_path_map[path]

        if path == "/" or path == "":
            return self.root_item if not self.root_item._deleted else None

        # Если не нашли в карте, пробуем рекурсивный поиск
        if self.root_item and not self.root_item._deleted:
            return self.root_item.find_child_by_path(path)
        return None

    # QAbstractItemModel required methods
    def index(self, row: int, column: int,
              parent: QModelIndex = QModelIndex()) -> QModelIndex:
        """Create index for item at row and column."""
        if self._is_shutting_down:
            return QModelIndex()

        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_item = self._get_item(parent)
        if not parent_item:
            return QModelIndex()

        child = parent_item.child(row)
        if child and not child._deleted:
            return self.createIndex(row, column, child)

        return QModelIndex()

    def parent(self, child: QModelIndex) -> QModelIndex:
        """Get parent index for child."""
        if self._is_shutting_down or not child.isValid():
            return QModelIndex()

        child_item = child.internalPointer()
        if not child_item or child_item._deleted:
            return QModelIndex()

        parent_item = child_item.parent
        if not parent_item or parent_item._deleted or parent_item == self.root_item:
            return QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Get number of rows under parent."""
        if self._is_shutting_down:
            return 0

        parent_item = self._get_item(parent)
        if parent_item and not parent_item._deleted:
            # Фильтруем удаленные элементы
            valid_children = [c for c in parent_item.children if
                              not c._deleted]
            return len(valid_children)
        return 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Get number of columns."""
        return 4  # Name, Size, Type, Modified

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Get data for index."""
        if self._is_shutting_down or not index.isValid():
            return None

        item = index.internalPointer()
        if not item or item._deleted:
            return None

        col = index.column()

        try:
            if role == Qt.DisplayRole:
                if item.is_placeholder:
                    return "📁 Папка пуста" if col == 0 else ""

                if not item.file_info:
                    return "Загрузка..." if col == 0 else ""

                if col == 0:
                    return item.file_info.name
                elif col == 1:
                    return "" if item.file_info.isdir else format_size(
                        item.file_info.size)
                elif col == 2:
                    return "Папка" if item.file_info.isdir else "Файл"
                elif col == 3:
                    return item.file_info.modified or ""

            elif role == Qt.DecorationRole and col == 0:
                if item.is_placeholder or not item.file_info:
                    return None
                return self._get_icon(item.file_info.isdir,
                                      item.file_info.islink)

            elif role == Qt.FontRole and col == 0 and item.file_info and item.file_info.isdir:
                font = QFont()
                font.setBold(True)
                return font

            elif role == Qt.ToolTipRole and col == 0 and item.file_info:
                return (f"Имя: {item.file_info.name}\n"
                        f"Путь: {item.file_info.path}\n"
                        f"Размер: {format_size(item.file_info.size) if not item.file_info.isdir else 'Папка'}\n"
                        f"Изменен: {item.file_info.modified or 'Неизвестно'}")

        except Exception as e:
            logger.exception(f"Error getting data for index {index}: {e}")

        return None

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.DisplayRole) -> Any:
        """Get header data."""
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            headers = ["Имя", "Размер", "Тип", "Дата изменения"]
            return headers[section] if section < len(headers) else None
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        """Get item flags."""
        if self._is_shutting_down or not index.isValid():
            return Qt.NoItemFlags

        item = index.internalPointer()
        if not item or item._deleted or item.is_placeholder:
            return Qt.NoItemFlags

        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable

        if item.file_info:
            flags |= Qt.ItemIsDragEnabled

        return flags

    def canFetchMore(self, parent: QModelIndex) -> bool:
        """Check if more data can be fetched for parent."""
        if self._is_shutting_down:
            return False

        item = self._get_item(parent)
        return bool(
            item and not item._deleted and item.has_children and not item.is_loaded)

    def fetchMore(self, parent: QModelIndex):
        """Fetch more data for parent."""
        if self._is_shutting_down:
            return

        item = self._get_item(parent)
        if item and not item._deleted and item.has_children and not item.is_loaded:
            logger.debug(f"Fetching more for {item.path}")
            self._load_directory(item.path)

    def _get_item(self, index: QModelIndex) -> Optional[FileSystemItem]:
        """Get item from index."""
        if self._is_shutting_down:
            return None

        if index.isValid():
            item = index.internalPointer()
            if item and not item._deleted:
                return item
            return None
        return self.root_item if self.root_item and not self.root_item._deleted else None

    def file_info(self, index: QModelIndex) -> Optional[Dict]:
        """Get file info for index with debug info."""
        if self._is_shutting_down or not index.isValid():
            return None

        item = index.internalPointer()
        if not item or item._deleted or item.is_placeholder or not item.file_info:
            return None

        return item.file_info.to_dict()

    def clear_cache(self):
        """Clear internal caches."""
        if self._is_shutting_down:
            return

        self._icon_cache.clear()
        self._get_icon.cache_clear()
        if hasattr(self, '_loader'):
            self._loader.clear_cache()
        self._not_found_paths.clear()

        # Очищаем кэши элементов
        if self.root_item and not self.root_item._deleted:
            self.root_item.clear_cache()

        # Перестраиваем карту путей
        self._item_path_map.clear()
        if self.root_item and not self.root_item._deleted:
            self._item_path_map["/"] = self.root_item

        logger.info("Cleared all caches")
        self.layoutChanged.emit()


class FileBrowserView(QTreeView):
    """Tree view for file browser with improved UX."""

    # Signals
    downloadRequested = pyqtSignal(dict)
    uploadRequested = pyqtSignal(dict)
    deleteRequested = pyqtSignal(dict)
    renameRequested = pyqtSignal(dict)
    copyRequested = pyqtSignal(dict)
    cutRequested = pyqtSignal(dict)
    pasteRequested = pyqtSignal(dict)
    propertiesRequested = pyqtSignal(dict)
    directoryChanged = pyqtSignal(str)
    itemActivated = pyqtSignal(dict)
    errorDisplayRequested = pyqtSignal(str, str)  # title, message

    def __init__(self, model: FileBrowserModel, parent=None):
        super().__init__(parent)
        self.setModel(model)
        self._setup_ui()
        self._connect_signals()
        self._current_theme = "light"
        self._last_double_click_time = 0
        self._last_double_click_item = None
        self._is_deleting = False
        self._current_root = "/"

    def _setup_ui(self):
        """Setup view UI with optimal defaults."""
        # Basic settings
        self.setHeaderHidden(False)
        self.setAlternatingRowColors(True)
        self.setExpandsOnDoubleClick(
            False)  # Важно: не раскрывать автоматически
        self.setSelectionBehavior(QTreeView.SelectRows)
        self.setSelectionMode(QTreeView.ExtendedSelection)
        self.setSortingEnabled(True)
        self.setAnimated(True)
        self.setAllColumnsShowFocus(True)
        self.setWordWrap(False)

        # Set column widths with smart resizing
        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Interactive)  # Name
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Size
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Type
        header.setSectionResizeMode(3,
                                    QHeaderView.ResizeToContents)  # Modified

        # Default widths
        self.setColumnWidth(0, 300)  # Name
        self.setColumnWidth(1, 80)  # Size
        self.setColumnWidth(2, 100)  # Type
        self.setColumnWidth(3, 150)  # Modified

        # Enable context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _connect_signals(self):
        """Connect internal signals."""
        self.doubleClicked.connect(self._on_double_clicked)
        self.activated.connect(self._on_activated)

        # Connect model signals
        model = self.model()
        if model:
            model.directoryNotFound.connect(self._on_directory_not_found)
            model.errorOccurred.connect(self._on_model_error)
            model.directoryLoaded.connect(self._on_directory_loaded)
            model.layoutChanged.connect(self._on_layout_changed)

    def _on_directory_loaded(self, path: str):
        """Handle directory loaded in model."""
        logger.info(f"View: directory loaded signal received for {path}")

        # Если это текущая корневая директория, обновляем отображение
        if path == self._current_root:
            # Принудительно обновляем вид
            self.viewport().update()

            # Раскрываем корневые элементы
            self.expandToDepth(1)

            # Убеждаемся, что корневой элемент виден
            root_index = self.model().index(0, 0, QModelIndex())
            if root_index.isValid():
                self.setCurrentIndex(root_index)

    def _on_layout_changed(self):
        """Handle layout changed signal."""
        if self._is_deleting:
            return
        logger.debug("View: layout changed")
        self.viewport().update()

        # Раскрываем корневые элементы для лучшей видимости
        self.expandToDepth(1)

    def _on_directory_not_found(self, path: str):
        """Handle directory not found."""
        logger.warning(f"Directory not found in view: {path}")
        self.errorDisplayRequested.emit(
            "Директория не найдена",
            f"Директория '{path}' не существует или была удалена."
        )

    def _on_model_error(self, path: str, error: str):
        """Handle model error."""
        logger.error(f"Model error for {path}: {error}")
        self.errorDisplayRequested.emit(
            "Ошибка загрузки",
            f"Не удалось загрузить {path}:\n{error}"
        )

    def set_theme(self, theme: str):
        """Apply theme to view."""
        self._current_theme = theme
        from ui.theme import get_color

        try:
            # Получаем цвета из темы
            selection_bg = get_color(theme, 'selection_bg')
            selection_text = get_color(theme, 'selection_text')
            selection_focus_bg = get_color(theme, 'selection_focus_bg')
            selection_inactive_bg = get_color(theme, 'selection_inactive_bg')
            hover_bg = get_color(theme, 'hover_bg')

            self.setStyleSheet(f"""
                QTreeView::item:selected {{
                    background-color: {selection_bg};
                    color: {selection_text};
                }}
                QTreeView::item:selected:focus {{
                    background-color: {selection_focus_bg};
                }}
                QTreeView::item:selected:!active {{
                    background-color: {selection_inactive_bg};
                }}
                QTreeView::item:hover {{
                    background-color: {hover_bg};
                }}
            """)
        except Exception as e:
            logger.warning(f"Failed to apply theme {theme}: {e}")
            # Fallback to built-in style
            self.setStyleSheet(self._get_theme_style(theme))

    def _get_theme_style(self, theme: str) -> str:
        """Get stylesheet for theme fallback."""
        if theme == "dark":
            return """
                QTreeView {
                    background-color: #2b2b2b;
                    alternate-background-color: #353535;
                    color: #ffffff;
                }
                QTreeView::item:selected {
                    background-color: #0066cc;
                }
                QTreeView::item:hover {
                    background-color: #404040;
                }
                QHeaderView::section {
                    background-color: #404040;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 4px;
                }
            """
        else:  # light theme
            return """
                QTreeView {
                    background-color: #ffffff;
                    alternate-background-color: #f5f5f5;
                    color: #000000;
                }
                QTreeView::item:selected {
                    background-color: #3399ff;
                    color: #ffffff;
                }
                QTreeView::item:hover {
                    background-color: #e0e0e0;
                }
                QHeaderView::section {
                    background-color: #d0d0d0;
                    color: #000000;
                    border: 1px solid #a0a0a0;
                    padding: 4px;
                }
            """

    def _show_context_menu(self, position):
        """Show context menu at position."""
        index = self.indexAt(position)
        if not index.isValid():
            return

        item = self.model().file_info(index)
        if not item:
            return

        menu = QMenu(self)

        # Add actions based on item type
        if not item['isdir']:
            download_action = menu.addAction("📥 Скачать")
            download_action.triggered.connect(
                lambda: self.downloadRequested.emit(item)
            )

        if item['isdir']:
            upload_action = menu.addAction("📤 Загрузить сюда")
            upload_action.triggered.connect(
                lambda: self.uploadRequested.emit(item)
            )

        menu.addSeparator()

        copy_action = menu.addAction("📋 Копировать")
        copy_action.triggered.connect(
            lambda: self.copyRequested.emit(item)
        )

        cut_action = menu.addAction("✂️ Вырезать")
        cut_action.triggered.connect(
            lambda: self.cutRequested.emit(item)
        )

        paste_action = menu.addAction("📌 Вставить")
        paste_action.triggered.connect(
            lambda: self.pasteRequested.emit(item)
        )

        menu.addSeparator()

        rename_action = menu.addAction("✏️ Переименовать")
        rename_action.triggered.connect(
            lambda: self.renameRequested.emit(item)
        )

        delete_action = menu.addAction("🗑️ Удалить")
        delete_action.triggered.connect(
            lambda: self._safe_delete(item)
        )

        menu.addSeparator()

        properties_action = menu.addAction("ℹ️ Свойства")
        properties_action.triggered.connect(
            lambda: self.propertiesRequested.emit(item)
        )

        menu.exec_(self.viewport().mapToGlobal(position))

    def _safe_delete(self, item):
        """Safe delete with protection."""
        self._is_deleting = True
        try:
            self.deleteRequested.emit(item)
        finally:
            # Используем таймер для сброса флага, чтобы дать время на обработку удаления
            QTimer.singleShot(100, lambda: self._finish_delete())

    def _finish_delete(self):
        """Finish delete operation."""
        self._is_deleting = False
        self.viewport().update()

    def _on_double_clicked(self, index: QModelIndex):
        """Handle double click with debug info."""
        if self._is_deleting:
            return

        current_time = time.time()
        time_diff = current_time - self._last_double_click_time

        logger.debug(
            f"Double click detected at {current_time}, last was {time_diff:.3f}s ago")

        item = self.model().file_info(index)
        if not item:
            logger.warning("Double click on item with no file_info")
            return

        logger.info(
            f"Double click on: {item.get('path')}, isdir={item.get('isdir')}")

        self._last_double_click_time = current_time
        self._last_double_click_item = item.get('path')

        if item['isdir']:
            logger.info(f"Emitting directoryChanged for: {item['path']}")
            self._current_root = item['path']
            self.directoryChanged.emit(item['path'])
        else:
            logger.info(f"Emitting downloadRequested for: {item['path']}")
            self.downloadRequested.emit(item)

        self.itemActivated.emit(item)

    def _on_activated(self, index: QModelIndex):
        """Handle item activation (Enter key)."""
        if self._is_deleting:
            return

        item = self.model().file_info(index)
        if not item:
            return

        logger.info(
            f"Activated: {item.get('path')}, isdir={item.get('isdir')}")

        if item['isdir']:
            self._current_root = item['path']
            self.directoryChanged.emit(item['path'])

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            index = self.currentIndex()
            if index.isValid():
                self._on_activated(index)
                return
        elif event.key() == Qt.Key_Delete:
            if self._is_deleting:
                return

            indexes = self.selectedIndexes()
            if indexes:
                # Get unique rows
                rows = set(idx.row() for idx in indexes)
                if rows:
                    # Emit delete for first selected item
                    item = self.model().file_info(indexes[0])
                    if item:
                        self._safe_delete(item)
                return
        elif event.key() == Qt.Key_F5:
            self.model().refresh()
            return
        elif event.key() == Qt.Key_F4:
            # Show properties for selected item
            index = self.currentIndex()
            if index.isValid():
                item = self.model().file_info(index)
                if item:
                    self.propertiesRequested.emit(item)
            return
        elif event.key() == Qt.Key_Space and event.modifiers() == Qt.ControlModifier:
            self.model().clear_cache()
            self.model().refresh()
            return

        super().keyPressEvent(event)

    def closeEvent(self, event):
        """Handle close event."""
        logger.info("Closing FileBrowserView")
        if hasattr(self, 'model') and self.model():
            self.model().shutdown()
        super().closeEvent(event)