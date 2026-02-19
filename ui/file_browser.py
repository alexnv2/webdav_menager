# ui/file_browser.py (исправленный)
import logging
from typing import Optional, List, Dict, Any

from PyQt5.QtCore import (QAbstractItemModel, QModelIndex, Qt, QThread,
                          QObject, pyqtSignal)
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QTreeView, QMenu, QApplication,
                             QStyle)

from core.client import WebDAVClient
from core.models import FileInfo
from utils.helpers import format_size

logger = logging.getLogger(__name__)


class DirectoryLoader(QObject):
    """Background directory loader."""

    loaded = pyqtSignal(str, list)  # path, files
    error = pyqtSignal(str, str)  # path, error

    def __init__(self, client: WebDAVClient):
        super().__init__()
        self.client = client

    def load_path(self, path: str, force: bool = False):
        """Load directory contents in background."""
        logger.info(f"Loading directory: {path} (force={force})")
        try:
            if force:
                files = self.client.list_files_no_cache(path)
            else:
                files = self.client.list_files(path)

            # Convert to dict for Qt if they're FileInfo objects
            if files and hasattr(files[0], 'to_dict'):
                files_dict = [f.to_dict() for f in files]
            else:
                files_dict = files

            self.loaded.emit(path, files_dict)

        except Exception as e:
            logger.exception(f"Error loading {path}")
            self.error.emit(path, str(e))


class FileSystemItem:
    """Internal tree item for file browser."""

    def __init__(self, parent: Optional['FileSystemItem'] = None,
                 file_info: Optional[FileInfo] = None):
        self.parent = parent
        self.file_info = file_info
        self.children: List['FileSystemItem'] = []
        self.is_loaded = False

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
                pass
        return 0


class FileBrowserModel(QAbstractItemModel):
    """Model for file browser tree view."""

    requestLoad = pyqtSignal(str, bool)  # path, force
    directoryLoaded = pyqtSignal(str)

    def __init__(self, client: WebDAVClient):
        super().__init__()
        self.client = client
        self.root_item = FileSystemItem(file_info=FileInfo(
            name="/", path="/", isdir=True
        ))
        self.current_path = "/"

        # Setup loader thread
        self._loader_thread = QThread()
        self._loader = DirectoryLoader(client)
        self._loader.moveToThread(self._loader_thread)

        # Connect signals - ИСПРАВЛЕНО: используем правильные имена методов
        self.requestLoad.connect(self._loader.load_path, Qt.QueuedConnection)
        self._loader.loaded.connect(self.on_directory_loaded,
                                    Qt.QueuedConnection)  # Было _on_directory_loaded
        self._loader.error.connect(self.on_directory_error,
                                   Qt.QueuedConnection)  # Было _on_directory_error

        self._loader_thread.start()

    def shutdown(self):
        """Clean up loader thread."""
        if self._loader_thread.isRunning():
            self._loader_thread.quit()
            self._loader_thread.wait(2000)

    def set_root(self, path: str):
        """Set current root path."""
        if path != self.current_path:
            self.current_path = path
            self._load_directory(path)

    def refresh(self):
        """Refresh current directory."""
        self._load_directory(self.current_path, force=True)

    def _load_directory(self, path: str, force: bool = False):
        """Request directory loading."""
        self.requestLoad.emit(path, force)

    def on_directory_loaded(self, path: str, files: List[Dict]):
        """Handle directory loaded."""
        if path != self.current_path:
            return

        self.beginResetModel()

        # Find or create item for path
        item = self._get_item_for_path(path)
        if not item:
            item = self.root_item

        # Clear existing children
        item.children.clear()
        item.is_loaded = True

        # Add new children
        for f in files:
            try:
                file_info = FileInfo.from_dict(f)
                child = FileSystemItem(parent=item, file_info=file_info)
                item.add_child(child)
            except Exception as e:
                logger.exception(f"Error creating item for {f}")

        self.endResetModel()
        self.directoryLoaded.emit(path)

    def on_directory_error(self, path: str, error: str):
        """Handle directory loading error."""
        logger.error(f"Error loading {path}: {error}")
        # Show empty directory
        self.on_directory_loaded(path, [])

    def _get_item_for_path(self, path: str) -> Optional[FileSystemItem]:
        """Get item for path."""
        if path == "/":
            return self.root_item
        # This is simplified - you might need to traverse the tree
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
        return 4

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Get data for index."""
        if not index.isValid():
            return None

        item = index.internalPointer()
        if not item or not item.file_info:
            return None

        col = index.column()
        info = item.file_info

        try:
            if role == Qt.DisplayRole:
                if col == 0:
                    return info.name
                elif col == 1:
                    return "" if info.isdir else format_size(info.size)
                elif col == 2:
                    return info.type_name
                elif col == 3:
                    return info.modified

            elif role == Qt.DecorationRole and col == 0:
                style = QApplication.style()
                if info.isdir:
                    if info.islink:
                        return style.standardIcon(QStyle.SP_DirLinkIcon)
                    return style.standardIcon(QStyle.SP_DirIcon)
                else:
                    if info.islink:
                        return style.standardIcon(QStyle.SP_FileLinkIcon)
                    return style.standardIcon(QStyle.SP_FileIcon)

            elif role == Qt.FontRole and col == 0 and info.isdir:
                font = QFont()
                font.setBold(True)
                return font

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
        if item and item.file_info:
            return item.file_info.to_dict()
        return None


class FileBrowserView(QTreeView):
    """Tree view for file browser."""

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

    def __init__(self, model: FileBrowserModel, parent=None):
        super().__init__(parent)
        self.setModel(model)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup view UI."""
        self.setHeaderHidden(False)
        self.setAlternatingRowColors(True)
        self.setExpandsOnDoubleClick(False)
        self.setSelectionBehavior(QTreeView.SelectRows)
        self.setSortingEnabled(True)

        # Set column widths
        self.setColumnWidth(0, 250)  # Name
        self.setColumnWidth(1, 80)  # Size
        self.setColumnWidth(2, 100)  # Type
        self.setColumnWidth(3, 150)  # Modified

        # Enable context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _connect_signals(self):
        """Connect internal signals."""
        self.doubleClicked.connect(self._on_double_clicked)

    def set_theme(self, theme: str):
        """Apply theme to view."""
        from ui.theme import get_color

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

    def _get_theme_style(self, theme: str) -> str:
        """Get stylesheet for theme."""
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

    # В ui/file_browser.py, обновите метод _show_context_menu:

    def _show_context_menu(self, position):
        """Show context menu at position."""
        index = self.indexAt(position)
        if not index.isValid():
            return

        item = self.model().file_info(index)
        if not item:
            return

        menu = QMenu(self)
        # Тема применяется глобально, не нужно устанавливать стили вручную

        # Add actions based on item type
        if not item['isdir']:
            download_action = menu.addAction("Скачать")
            download_action.triggered.connect(
                lambda: self.downloadRequested.emit(item)
            )

        if item['isdir']:
            upload_action = menu.addAction("Загрузить сюда")
            upload_action.triggered.connect(
                lambda: self.uploadRequested.emit(item)
            )

        menu.addSeparator()

        copy_action = menu.addAction("Копировать")
        copy_action.triggered.connect(
            lambda: self.copyRequested.emit(item)
        )

        cut_action = menu.addAction("Вырезать")
        cut_action.triggered.connect(
            lambda: self.cutRequested.emit(item)
        )

        paste_action = menu.addAction("Вставить")
        paste_action.triggered.connect(
            lambda: self.pasteRequested.emit(item)
        )

        menu.addSeparator()

        rename_action = menu.addAction("Переименовать")
        rename_action.triggered.connect(
            lambda: self.renameRequested.emit(item)
        )

        delete_action = menu.addAction("Удалить")
        delete_action.triggered.connect(
            lambda: self.deleteRequested.emit(item)
        )

        menu.addSeparator()

        properties_action = menu.addAction("Свойства")
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