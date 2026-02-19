# ui/file_browser.py (исправленный)
import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from PyQt5.QtCore import (QAbstractItemModel, QModelIndex, Qt, QThread,
                          QObject, pyqtSignal, QTimer, QSortFilterProxyModel,
                          QDateTime)
from PyQt5.QtGui import QIcon, QFont, QColor
from PyQt5.QtWidgets import (QTreeView, QMenu, QAction, QApplication,
                             QStyle, QHeaderView)

from core.client import WebDAVClient
from core.models import FileInfo
from utils.helpers import format_size, format_datetime
from ui.widgets import PropertiesDialog

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
            for fmt in ['%Y-%m-%d %H:%M:%S', '%d.%m.%Y %H:%M', '%Y-%m-%d']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
    except Exception as e:
        logger.debug(f"Error parsing date '{date_str}': {e}")

    return datetime.min


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


class FileSystemSortFilterProxyModel(QSortFilterProxyModel):
    """Proxy model for sorting files and folders."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortCaseSensitivity(Qt.CaseInsensitive)
        self.setDynamicSortFilter(True)
        self.setSortRole(Qt.UserRole)

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        """Custom sorting logic."""
        try:
            source_model = self.sourceModel()

            # Получаем данные через UserRole для правильной сортировки
            left_data = source_model.data(left, Qt.UserRole)
            right_data = source_model.data(right, Qt.UserRole)

            if not left_data or not right_data:
                return super().lessThan(left, right)

            column = left.column()

            # Специальная сортировка для разных колонок
            if column == 0:  # Колонка имени - папки всегда сверху
                left_is_dir = left_data.get('isdir', False)
                right_is_dir = right_data.get('isdir', False)

                if left_is_dir != right_is_dir:
                    return left_is_dir  # Папки идут первыми

                # Сортировка по имени
                left_name = left_data.get('name', '').lower()
                right_name = right_data.get('name', '').lower()
                return left_name < right_name

            elif column == 1:  # Колонка размера
                left_size = left_data.get('size', 0)
                right_size = right_data.get('size', 0)
                return left_size < right_size

            elif column == 2:  # Колонка типа
                left_type = left_data.get('type_name', '').lower()
                right_type = right_data.get('type_name', '').lower()
                return left_type < right_type

            elif column == 3:  # Колонка даты изменения
                left_date = left_data.get('datetime', datetime.min)
                right_date = right_data.get('datetime', datetime.min)
                return left_date < right_date

            return super().lessThan(left, right)

        except Exception as e:
            logger.error(f"Error in sort comparison: {e}")
            return False


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


class FileBrowserModel(QAbstractItemModel):
    """Model for file browser tree view."""

    requestLoad = pyqtSignal(str, bool)  # path, force
    directoryLoaded = pyqtSignal(str)

    # Константы для колонок
    COLUMN_NAME = 0
    COLUMN_SIZE = 1
    COLUMN_TYPE = 2
    COLUMN_MODIFIED = 3

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

        # Connect signals
        self.requestLoad.connect(self._loader.load_path, Qt.QueuedConnection)
        self._loader.loaded.connect(self.on_directory_loaded,
                                    Qt.QueuedConnection)
        self._loader.error.connect(self.on_directory_error,
                                   Qt.QueuedConnection)

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
            # Парсим дату для сортировки
            dt = parse_webdav_date(info.modified)

            # UserRole - возвращаем полный словарь для сортировки
            if role == Qt.UserRole:
                return {
                    'name': info.name,
                    'isdir': info.isdir,
                    'size': info.size,
                    'type_name': info.type_name,
                    'modified': info.modified,
                    'datetime': dt,  # Добавляем datetime объект для сортировки
                    'path': info.path
                }

            if role == Qt.DisplayRole:
                if col == self.COLUMN_NAME:
                    return info.name
                elif col == self.COLUMN_SIZE:
                    return "" if info.isdir else format_size(info.size)
                elif col == self.COLUMN_TYPE:
                    return info.type_name
                elif col == self.COLUMN_MODIFIED:
                    # Форматируем дату в нужный формат
                    return format_datetime(info.modified)

            elif role == Qt.DecorationRole and col == self.COLUMN_NAME:
                style = QApplication.style()
                if info.isdir:
                    if info.islink:
                        return style.standardIcon(QStyle.SP_DirLinkIcon)
                    return style.standardIcon(QStyle.SP_DirIcon)
                else:
                    if info.islink:
                        return style.standardIcon(QStyle.SP_FileLinkIcon)
                    return style.standardIcon(QStyle.SP_FileIcon)

            elif role == Qt.FontRole and col == self.COLUMN_NAME and info.isdir:
                font = QFont()
                font.setBold(True)
                return font

            elif role == Qt.ForegroundRole:
                # Разные цвета для разных типов
                if info.isdir:
                    return QColor(0, 100, 200)  # Синий для папок
                elif info.islink:
                    return QColor(150, 150, 150)  # Серый для ссылок

            elif role == Qt.TextAlignmentRole:
                # Выравнивание для колонки размера
                if col == self.COLUMN_SIZE:
                    return Qt.AlignRight | Qt.AlignVCenter

            elif role == Qt.ToolTipRole:
                # Подсказка с полной информацией
                if col == self.COLUMN_NAME:
                    if info.isdir:
                        return f"Папка: {info.name}\nПуть: {info.path}"
                    else:
                        size = format_size(info.size)
                        modified = format_datetime(info.modified)
                        return f"Файл: {info.name}\nРазмер: {size}\nТип: {info.type_name}\nИзменён: {modified}"

        except Exception as e:
            logger.exception(f"Error getting data: {e}")

        return None

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.DisplayRole) -> Any:
        """Get header data."""
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                headers = ["Имя", "Размер", "Тип", "Дата изменения"]
                return headers[section] if section < len(headers) else None
            elif role == Qt.TextAlignmentRole:
                if section == self.COLUMN_SIZE:
                    return Qt.AlignRight | Qt.AlignVCenter
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
    """Tree view for file browser with sorting support."""

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

        # Сохраняем исходную модель
        self.source_model = model

        # Создаем прокси-модель для сортировки
        self.proxy_model = FileSystemSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(model)

        # Устанавливаем прокси-модель
        self.setModel(self.proxy_model)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup view UI."""
        self.setHeaderHidden(False)
        self.setAlternatingRowColors(True)
        self.setExpandsOnDoubleClick(False)
        self.setSelectionBehavior(QTreeView.SelectRows)

        # Включаем сортировку
        self.setSortingEnabled(True)

        # Настраиваем заголовок
        header = self.header()
        header.setStretchLastSection(True)
        header.setSectionsMovable(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(0,
                                Qt.AscendingOrder)  # Сортировка по имени по умолчанию

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

        # Подключаем сигнал сортировки
        header = self.header()
        header.sortIndicatorChanged.connect(self._on_sort_indicator_changed)

    def _on_sort_indicator_changed(self, logical_index: int,
                                   order: Qt.SortOrder):
        """Handle sort indicator change."""
        logger.debug(f"Sort changed: column {logical_index}, order {order}")

    def set_theme(self, theme: str):
        """Apply theme stylesheet."""
        self.setStyleSheet(self._get_theme_style(theme))

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
                    background-color: #3399ff;
                    color: white;
                }
                QTreeView::item:selected:focus {
                    background-color: #66b3ff;
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
                QHeaderView::section:checked {
                    background-color: #505050;
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
                    background-color: #99ccff;
                    color: black;
                }
                QTreeView::item:selected:focus {
                    background-color: #b3d9ff;
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
                QHeaderView::section:checked {
                    background-color: #e0e0e0;
                }
            """

    def _show_context_menu(self, position):
        """Show context menu at position."""
        try:
            proxy_index = self.indexAt(position)
            if not proxy_index.isValid():
                return

            # Конвертируем в индекс исходной модели
            source_index = self.proxy_model.mapToSource(proxy_index)
            item = self.source_model.file_info(source_index)

            if not item:
                return

            menu = QMenu(self)

            # Add actions based on item type
            if not item['isdir']:
                download_action = menu.addAction("Скачать")
                download_action.triggered.connect(
                    lambda checked, i=item: self.downloadRequested.emit(i)
                )

            if item['isdir']:
                upload_action = menu.addAction("Загрузить сюда")
                upload_action.triggered.connect(
                    lambda checked, i=item: self.uploadRequested.emit(i)
                )

            menu.addSeparator()

            copy_action = menu.addAction("Копировать")
            copy_action.triggered.connect(
                lambda checked, i=item: self.copyRequested.emit(i)
            )

            cut_action = menu.addAction("Вырезать")
            cut_action.triggered.connect(
                lambda checked, i=item: self.cutRequested.emit(i)
            )

            paste_action = menu.addAction("Вставить")
            paste_action.triggered.connect(
                lambda checked, i=item: self.pasteRequested.emit(i)
            )

            menu.addSeparator()

            rename_action = menu.addAction("Переименовать")
            rename_action.triggered.connect(
                lambda checked, i=item: self.renameRequested.emit(i)
            )

            delete_action = menu.addAction("Удалить")
            delete_action.triggered.connect(
                lambda checked, i=item: self.deleteRequested.emit(i)
            )

            menu.addSeparator()

            properties_action = menu.addAction("Свойства")
            properties_action.triggered.connect(
                lambda checked, i=item: self.propertiesRequested.emit(i)
            )

            menu.exec_(self.viewport().mapToGlobal(position))

        except Exception as e:
            logger.error(f"Error showing context menu: {e}")

    def _on_double_clicked(self, proxy_index: QModelIndex):
        """Handle double click."""
        try:
            # Конвертируем в индекс исходной модели
            source_index = self.proxy_model.mapToSource(proxy_index)
            item = self.source_model.file_info(source_index)

            if not item:
                return

            if item['isdir']:
                self.directoryChanged.emit(item['path'])
            else:
                self.downloadRequested.emit(item)

        except Exception as e:
            logger.error(f"Error handling double click: {e}")

    def set_root(self, path: str):
        """Set root directory."""
        self.source_model.set_root(path)

    def refresh(self):
        """Refresh current directory."""
        self.source_model.refresh()

    def selected_items(self) -> List[Dict]:
        """Get list of selected items."""
        items = []
        try:
            for proxy_index in self.selectedIndexes():
                if proxy_index.column() == 0:  # Только одна запись на строку
                    source_index = self.proxy_model.mapToSource(proxy_index)
                    item = self.source_model.file_info(source_index)
                    if item:
                        items.append(item)
        except Exception as e:
            logger.error(f"Error getting selected items: {e}")
        return items
