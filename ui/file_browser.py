# ui/file_browser.py
"""File browser tree view with model-view architecture."""

import logging
from typing import Optional, List, Dict, Any, Union
from functools import lru_cache

from PyQt5.QtCore import (QAbstractItemModel, QModelIndex, Qt, QThread,
                          QObject, pyqtSignal, QTimer)
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (QTreeView, QMenu, QApplication,
                             QStyle, QHeaderView)

from core.client import WebDAVClient
from core.models import FileInfo
from utils.helpers import format_size

logger = logging.getLogger(__name__)


class DirectoryLoader(QObject):
    """Background directory loader with caching and retry logic."""

    loaded = pyqtSignal(str, list)  # path, files
    error = pyqtSignal(str, str)    # path, error
    progress = pyqtSignal(str, int)  # path, progress (0-100)

    def __init__(self, client: WebDAVClient):
        super().__init__()
        self.client = client
        self._active_requests: Dict[str, bool] = {}
        self._cache: Dict[str, tuple] = {}  # path -> (files, timestamp)
        self._cache_timeout = 30  # seconds

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
                import time
                if time.time() - timestamp < self._cache_timeout:
                    logger.debug(f"Using cached data for {path}")
                    self.progress.emit(path, 100)
                    self.loaded.emit(path, files)
                    return

            self.progress.emit(path, 30)

            # Загружаем данные
            if force:
                files = self.client.list_files_no_cache(path)
            else:
                files = self.client.list_files(path)

            self.progress.emit(path, 70)

            # Конвертируем в dict для Qt
            files_dict = self._convert_to_dict(files)

            # Сохраняем в кэш
            import time
            self._cache[path] = (files_dict, time.time())

            self.progress.emit(path, 100)
            self.loaded.emit(path, files_dict)

        except Exception as e:
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
        else:
            self._cache.clear()


class FileSystemItem:
    """Internal tree item for file browser with lazy loading."""

    __slots__ = ('parent', 'file_info', 'children', 'is_loaded', 'is_placeholder')

    def __init__(self, parent: Optional['FileSystemItem'] = None,
                 file_info: Optional[FileInfo] = None,
                 is_placeholder: bool = False):
        self.parent = parent
        self.file_info = file_info
        self.children: List['FileSystemItem'] = []
        self.is_loaded = False
        self.is_placeholder = is_placeholder

    @property
    def path(self) -> str:
        """Get item path."""
        if self.file_info:
            return self.file_info.path
        return "/"

    @property
    def name(self) -> str:
        """Get item name."""
        if self.file_info:
            return self.file_info.name
        return "/"

    @property
    def isdir(self) -> bool:
        """Check if item is directory."""
        return self.file_info.isdir if self.file_info else True

    @property
    def has_children(self) -> bool:
        """Check if item can have children."""
        return self.isdir

    def add_child(self, child: 'FileSystemItem'):
        """Add child item."""
        self.children.append(child)
        child.parent = self

    def child(self, row: int) -> Optional['FileSystemItem']:
        """Get child by row."""
        if 0 <= row < len(self.children):
            return self.children[row]
        return None

    def row(self) -> int:
        """Get row index in parent."""
        if self.parent:
            try:
                return self.parent.children.index(self)
            except ValueError:
                return 0
        return 0


class FileBrowserModel(QAbstractItemModel):
    """Model for file browser tree view with async loading."""

    requestLoad = pyqtSignal(str, bool)  # path, force
    directoryLoaded = pyqtSignal(str)
    loadingProgress = pyqtSignal(str, int)  # path, progress

    def __init__(self, client: WebDAVClient):
        super().__init__()
        self.client = client
        self._setup_root_item()
        self.current_path = "/"
        self._icon_cache = {}
        self._pending_loads: Dict[str, bool] = {}
        self._load_timer = QTimer()
        self._load_timer.setSingleShot(True)
        self._load_timer.setInterval(100)
        self._load_timer.timeout.connect(self._process_pending_loads)

        # Setup loader thread
        self._loader_thread = QThread()
        self._loader = DirectoryLoader(client)
        self._loader.moveToThread(self._loader_thread)

        # Connect signals
        self._connect_signals()

        self._loader_thread.start()

    def _setup_root_item(self):
        """Setup root item with proper FileInfo."""
        # Создаем корневой элемент без FileInfo или с минимальным
        self.root_item = FileSystemItem(file_info=None)

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

    def shutdown(self):
        """Clean up loader thread."""
        if self._loader_thread.isRunning():
            self._loader_thread.quit()
            if not self._loader_thread.wait(2000):
                logger.warning("Loader thread did not quit, terminating")
                self._loader_thread.terminate()
                self._loader_thread.wait()

    def set_root(self, path: str):
        """Set current root path."""
        if path != self.current_path:
            self.current_path = path
            self._queue_load(path)

    def refresh(self):
        """Refresh current directory."""
        self._queue_load(self.current_path, force=True)

    def _queue_load(self, path: str, force: bool = False):
        """Queue directory loading with debouncing."""
        self._pending_loads[path] = force
        self._load_timer.start()

    def _process_pending_loads(self):
        """Process queued directory loads."""
        for path, force in self._pending_loads.items():
            self._load_directory(path, force)
        self._pending_loads.clear()

    def _load_directory(self, path: str, force: bool = False):
        """Request directory loading."""
        self.requestLoad.emit(path, force)

    @lru_cache(maxsize=128)
    def _get_icon(self, is_dir: bool, is_link: bool) -> QIcon:
        """Get cached icon for file type."""
        style = QApplication.style()
        if is_dir:
            if is_link:
                return style.standardIcon(QStyle.SP_DirLinkIcon)
            return style.standardIcon(QStyle.SP_DirIcon)
        else:
            if is_link:
                return style.standardIcon(QStyle.SP_FileLinkIcon)
            return style.standardIcon(QStyle.SP_FileIcon)

    def on_directory_loaded(self, path: str, files: List[Dict]):
        """Handle directory loaded."""
        # Всегда загружаем в корень, если путь не найден
        item = self._get_item_for_path(path)
        if not item:
            item = self.root_item

        self.beginResetModel()

        # Clear existing children
        item.children.clear()
        item.is_loaded = True

        # Separate directories and files for sorting
        dirs = []
        files_list = []

        for f in files:
            try:
                file_info = FileInfo.from_dict(f)
                if file_info.isdir:
                    dirs.append(file_info)
                else:
                    files_list.append(file_info)
            except Exception as e:
                logger.exception(f"Error creating item from {f}: {e}")

        # Sort directories and files alphabetically
        dirs.sort(key=lambda x: x.name.lower())
        files_list.sort(key=lambda x: x.name.lower())

        # Add placeholder for empty directory
        if not dirs and not files_list and path != "/":
            # Создаем placeholder без FileInfo
            item.add_child(FileSystemItem(
                parent=item,
                file_info=None,
                is_placeholder=True
            ))
        else:
            # Add directories first
            for file_info in dirs:
                child = FileSystemItem(parent=item, file_info=file_info)
                item.add_child(child)

            # Then add files
            for file_info in files_list:
                child = FileSystemItem(parent=item, file_info=file_info)
                item.add_child(child)

        self.endResetModel()
        self.directoryLoaded.emit(path)

    def on_directory_error(self, path: str, error: str):
        """Handle directory loading error."""
        logger.error(f"Error loading {path}: {error}")
        # Show empty directory with error indication
        self.on_directory_loaded(path, [])

    def _get_item_for_path(self, path: str) -> Optional[FileSystemItem]:
        """Get item for path."""
        if path == "/" or path == "":
            return self.root_item

        # Простой поиск - для глубоких путей нужно реализовать рекурсивный поиск
        # Пока возвращаем корень для всех не-корневых путей
        return self.root_item

    # QAbstractItemModel required methods
    def index(self, row: int, column: int,
              parent: QModelIndex = QModelIndex()) -> QModelIndex:
        """Create index for item at row and column."""
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_item = self._get_item(parent)
        if not parent_item:
            return QModelIndex()

        child = parent_item.child(row)
        if child:
            return self.createIndex(row, column, child)

        return QModelIndex()

    def parent(self, child: QModelIndex) -> QModelIndex:
        """Get parent index for child."""
        if not child.isValid():
            return QModelIndex()

        child_item = child.internalPointer()
        if not child_item:
            return QModelIndex()

        parent_item = child_item.parent
        if not parent_item or parent_item == self.root_item:
            return QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Get number of rows under parent."""
        parent_item = self._get_item(parent)
        return len(parent_item.children) if parent_item else 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Get number of columns."""
        return 4  # Name, Size, Type, Modified

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Get data for index."""
        if not index.isValid():
            return None

        item = index.internalPointer()
        if not item:
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
                    return "" if item.file_info.isdir else format_size(item.file_info.size)
                elif col == 2:
                    return "Папка" if item.file_info.isdir else "Файл"
                elif col == 3:
                    return item.file_info.modified or ""

            elif role == Qt.DecorationRole and col == 0:
                if item.is_placeholder or not item.file_info:
                    return None
                return self._get_icon(item.file_info.isdir, item.file_info.islink)

            elif role == Qt.FontRole and col == 0 and item.file_info and item.file_info.isdir:
                font = QFont()
                font.setBold(True)
                return font

            elif role == Qt.ToolTipRole and col == 0 and item.file_info:
                return f"{item.file_info.name}\nПуть: {item.file_info.path}"

        except Exception as e:
            logger.exception(f"Error getting data: {e}")

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
        if not index.isValid():
            return Qt.NoItemFlags

        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable

        item = index.internalPointer()
        if item and not item.is_placeholder and item.file_info:
            flags |= Qt.ItemIsDragEnabled

        return flags

    def canFetchMore(self, parent: QModelIndex) -> bool:
        """Check if more data can be fetched for parent."""
        item = self._get_item(parent)
        return bool(item and item.has_children and not item.is_loaded)

    def fetchMore(self, parent: QModelIndex):
        """Fetch more data for parent."""
        item = self._get_item(parent)
        if item and item.has_children and not item.is_loaded:
            self._load_directory(item.path)

    def _get_item(self, index: QModelIndex) -> Optional[FileSystemItem]:
        """Get item from index."""
        if index.isValid():
            return index.internalPointer()
        return self.root_item

    def file_info(self, index: QModelIndex) -> Optional[Dict]:
        """Get file info for index."""
        if not index.isValid():
            return None
        item = index.internalPointer()
        if item and item.file_info and not item.is_placeholder:
            return item.file_info.to_dict()
        return None

    def clear_cache(self):
        """Clear internal caches."""
        self._icon_cache.clear()
        self._get_icon.cache_clear()
        if hasattr(self, '_loader'):
            self._loader.clear_cache()


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

    def __init__(self, model: FileBrowserModel, parent=None):
        super().__init__(parent)
        self.setModel(model)
        self._setup_ui()
        self._connect_signals()
        self._current_theme = "light"

    def _setup_ui(self):
        """Setup view UI with optimal defaults."""
        # Basic settings
        self.setHeaderHidden(False)
        self.setAlternatingRowColors(True)
        self.setExpandsOnDoubleClick(False)
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
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Modified

        # Default widths
        self.setColumnWidth(0, 300)  # Name
        self.setColumnWidth(1, 80)   # Size
        self.setColumnWidth(2, 100)  # Type
        self.setColumnWidth(3, 150)  # Modified

        # Enable context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _connect_signals(self):
        """Connect internal signals."""
        self.doubleClicked.connect(self._on_double_clicked)
        self.activated.connect(self._on_activated)

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
            lambda: self.deleteRequested.emit(item)
        )

        menu.addSeparator()

        properties_action = menu.addAction("ℹ️ Свойства")
        properties_action.triggered.connect(
            lambda: self.propertiesRequested.emit(item)
        )

        menu.exec_(self.viewport().mapToGlobal(position))

    def _on_double_clicked(self, index: QModelIndex):
        """Handle double click."""
        item = self.model().file_info(index)
        if not item:
            return

        if item['isdir']:
            self.directoryChanged.emit(item['path'])
        else:
            self.downloadRequested.emit(item)

        self.itemActivated.emit(item)

    def _on_activated(self, index: QModelIndex):
        """Handle item activation (Enter key)."""
        item = self.model().file_info(index)
        if item and item['isdir']:
            self.directoryChanged.emit(item['path'])

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            index = self.currentIndex()
            if index.isValid():
                self._on_activated(index)
                return
        elif event.key() == Qt.Key_Delete:
            indexes = self.selectedIndexes()
            if indexes:
                # Get unique rows
                rows = set(idx.row() for idx in indexes)
                if rows:
                    # Emit delete for first selected item
                    item = self.model().file_info(indexes[0])
                    if item:
                        self.deleteRequested.emit(item)
                return
        elif event.key() == Qt.Key_F5:
            self.model().refresh()
            return
        elif event.key() == Qt.Key_Space and event.modifiers() == Qt.ControlModifier:
            self.model().clear_cache()
            self.model().refresh()
            return

        super().keyPressEvent(event)