# ui/main_window.py (оптимизированная версия с улучшенной структурой и
# полным функционалом выделения)

import logging
import os
import threading
from typing import Optional, List, Dict

from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal, QMetaObject, Q_ARG, \
    pyqtSlot, QPoint, QItemSelection, QItemSelectionModel
from PyQt5.QtGui import QIcon, QKeySequence, QMouseEvent
from PyQt5.QtWidgets import (QMainWindow, QAction, QToolBar, QComboBox,
                             QStatusBar, QVBoxLayout, QWidget, QMessageBox,
                             QFileDialog, QProgressBar,
                             QInputDialog, QLabel,
                             QStyle, QMenu, QAbstractItemView)

from core import FileEncryptor
from core.client import WebDAVClient
from core.config import ConfigManager
from core.models import Account
from services.cloud_info import CloudInfoFetcher
from services.file_operations import FileOperationService
from ui.accounts_dialog import AccountsDialog
from ui.file_browser import FileBrowserModel, FileBrowserView
from ui.login_dialog import LoginDialog
from ui.settings_dialog import SettingsDialog
from ui.widgets import PathBar, ProgressWidget
from utils.helpers import format_size, normalize_path, join_path, format_error

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window."""

    operation_completed = pyqtSignal(str)

    def __init__(self, config: ConfigManager):
        super().__init__()
        self.config = config
        self.client = WebDAVClient(
            cache_ttl=config.get_setting("cache_ttl", 300),
            cache_size=config.get_setting("cache_size", 100)
        )
        self.file_ops = FileOperationService(self.client)

        # State
        self.current_account: Optional[Account] = None
        self.clipboard_item: Optional[Dict] = None
        self.clipboard_action: Optional[str] = None  # 'copy' or 'move'
        self.navigation_history: List[str] = []
        self.history_index: int = -1

        # Operation tracking
        self._pending_operations = 0
        self._operation_lock = threading.Lock()

        # Encryption state
        self.encryption_enabled = False
        self.encryptor = None
        self.secure_transfer = None
        self.key_manager = None

        # Mouse selection tracking
        self._mouse_pressed = False
        self._drag_start_pos: Optional[QPoint] = None
        self._drag_start_index = None

        self._setup_ui()
        self._connect_signals()
        self._load_accounts()
        self._apply_theme()

        # Update client settings
        self.client.update_settings(self.config.settings)

        # Connect operation completed signal
        self.operation_completed.connect(self._on_operation_completed)

        # Load encryption state from settings
        self._init_encryption_from_settings()

    def _setup_ui(self):
        """Setup main window UI."""
        self.setWindowTitle("WebDAV Manager")
        self.resize(900, 600)
        self._set_window_icon()

        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_status_bar()
        self._create_central_widget()

    def _set_window_icon(self):
        """Set window icon."""
        from main import get_icon_path

        icon_path = get_icon_path('app.ico')
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        else:
            self.setWindowIcon(
                self.style().standardIcon(QStyle.SP_ComputerIcon)
            )

    def _create_actions(self):
        """Create actions for menus and toolbars."""
        # File actions
        self.new_folder_action = self._create_action(
            "Новая папка", self.new_folder, QKeySequence.New
        )
        self.upload_action = self._create_action(
            "Загрузить файлы", self.upload_file, "Ctrl+U"
        )
        self.download_action = self._create_action(
            "Скачать", self.download_selected, "Ctrl+D"
        )
        self.delete_action = self._create_action(
            "Удалить", self.delete_selected, QKeySequence.Delete
        )
        self.exit_action = self._create_action(
            "Выход", self.close, QKeySequence.Quit
        )

        # Edit actions
        self.copy_action = self._create_action(
            "Копировать", self.copy_to_clipboard, QKeySequence.Copy
        )
        self.cut_action = self._create_action(
            "Вырезать", self.cut_to_clipboard, QKeySequence.Cut
        )
        self.paste_action = self._create_action(
            "Вставить", self.paste_from_clipboard, QKeySequence.Paste
        )
        self.select_all_action = self._create_action(
            "Выделить всё", self.select_all_items, QKeySequence.SelectAll
        )
        self.deselect_all_action = self._create_action(
            "Снять выделение", self.deselect_all_items, "Ctrl+Shift+A"
        )
        self.invert_selection_action = self._create_action(
            "Инвертировать выделение", self.invert_selection, "Ctrl+I"
        )
        self.properties_action = self._create_action(
            "Свойства", self._show_properties_for_selected, None
        )

        # Navigation actions
        self.back_action = self._create_action(
            "Назад", self.go_back, enabled=False
        )
        self.forward_action = self._create_action(
            "Вперёд", self.go_forward, enabled=False
        )
        self.up_action = self._create_action(
            "Вверх", self.go_up, enabled=False
        )
        self.home_action = self._create_action("Домой", self.go_home)
        self.refresh_action = self._create_action(
            "Обновить", self.refresh_current, QKeySequence.Refresh
        )

        # Settings actions
        self.accounts_action = self._create_action(
            "Аккаунты", self.open_accounts_dialog
        )
        self.settings_action = self._create_action(
            "Настройки", self.open_settings_dialog
        )

        # Encryption actions
        self.encryption_action = QAction("Шифрование", self)
        self.encryption_action.setCheckable(True)
        self.encryption_action.triggered.connect(self.toggle_encryption)

        self.manage_keys_action = self._create_action(
            "Управление ключами", self.open_key_dialog
        )

        # Lock action
        self.lock_action = self._create_action(
            "Заблокировать", self.lock_application, "Ctrl+L"
        )

        # Help actions
        self.about_action = self._create_action(
            "О программе", self.about
        )

        # Set icons
        self._set_action_icon(self.back_action, 'back.png', '←')
        self._set_action_icon(self.forward_action, 'forward.png', '→')
        self._set_action_icon(self.up_action, 'up.png', '↑')
        self._set_action_icon(self.home_action, 'home.png', '⌂')
        self._set_action_icon(self.refresh_action, 'refresh.png', '↻')
        self._set_action_icon(self.lock_action, 'lock.png', '🔒')

    def _create_action(self, text: str, slot, shortcut=None,
                       enabled=True) -> QAction:
        """Create a standard action."""
        action = QAction(text, self)
        action.triggered.connect(slot)
        if shortcut:
            if isinstance(shortcut, str):
                action.setShortcut(QKeySequence(shortcut))
            else:
                action.setShortcut(shortcut)
        action.setEnabled(enabled)
        return action

    def _set_action_icon(self, action: QAction, icon_name: str,
                         fallback_text: str):
        """Set action icon with fallback."""
        from main import get_icon_path

        icon_path = get_icon_path(icon_name)
        if icon_path:
            action.setIcon(QIcon(icon_path))
            action.setIconVisibleInMenu(True)
        else:
            action.setText(f"{fallback_text} {action.text()}")

    def _create_menus(self):
        """Create menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("Файл")
        file_menu.addAction(self.new_folder_action)
        file_menu.addSeparator()
        file_menu.addAction(self.upload_action)
        file_menu.addAction(self.download_action)
        file_menu.addAction(self.delete_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("Правка")
        edit_menu.addAction(self.copy_action)
        edit_menu.addAction(self.cut_action)
        edit_menu.addAction(self.paste_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.select_all_action)
        edit_menu.addAction(self.deselect_all_action)
        edit_menu.addAction(self.invert_selection_action)

        # View menu
        view_menu = menubar.addMenu("Вид")
        view_menu.addAction(self.refresh_action)

        # Navigation menu
        nav_menu = menubar.addMenu("Навигация")
        nav_menu.addAction(self.back_action)
        nav_menu.addAction(self.forward_action)
        nav_menu.addAction(self.up_action)
        nav_menu.addAction(self.home_action)

        # Settings menu
        settings_menu = menubar.addMenu("Настройки")
        settings_menu.addAction(self.accounts_action)
        settings_menu.addAction(self.settings_action)
        settings_menu.addSeparator()
        settings_menu.addAction(self.encryption_action)
        settings_menu.addAction(self.manage_keys_action)
        settings_menu.addSeparator()
        settings_menu.addAction(self.lock_action)

        # Help menu
        help_menu = menubar.addMenu("Помощь")
        help_menu.addAction(self.about_action)

    def _create_toolbars(self):
        """Create toolbars."""
        # Account toolbar
        account_toolbar = QToolBar("Аккаунты")
        account_toolbar.setMovable(True)
        account_toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(account_toolbar)

        account_toolbar.addAction(self.accounts_action)

        self.account_combo = QComboBox()
        self.account_combo.setMinimumWidth(200)
        self.account_combo.currentIndexChanged.connect(
            self._on_account_changed)
        account_toolbar.addWidget(self.account_combo)

        self.addToolBarBreak()

        # Main toolbar
        main_toolbar = QToolBar("Основные операции")
        main_toolbar.setMovable(True)
        main_toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(main_toolbar)

        # Navigation buttons
        for action in [self.back_action, self.forward_action, self.up_action,
                       self.home_action, self.refresh_action]:
            main_toolbar.addAction(action)

        main_toolbar.addSeparator()

        # Operation buttons
        for action in [self.new_folder_action, self.upload_action,
                       self.download_action, self.delete_action]:
            main_toolbar.addAction(action)

        main_toolbar.addSeparator()

        # Path bar
        self.path_bar = PathBar()
        self.path_bar.pathChanged.connect(self._on_path_entered)
        main_toolbar.addWidget(self.path_bar)

    def _create_status_bar(self):
        """Create status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Quota widgets
        self.quota_label = QLabel()
        self.status_bar.addPermanentWidget(self.quota_label)

        self.quota_progress = QProgressBar()
        self.quota_progress.setFixedWidth(150)
        self.quota_progress.setMaximum(100)
        self.quota_progress.setTextVisible(True)
        self.quota_progress.setAlignment(Qt.AlignCenter)
        self.status_bar.addPermanentWidget(self.quota_progress)

        # Progress widget
        self.progress_widget = ProgressWidget()
        self.progress_widget.hide()
        self.progress_widget.cancelled.connect(self._cancel_operation)
        self.status_bar.addPermanentWidget(self.progress_widget)

        # Encryption status
        self.encryption_status = QLabel()
        self.encryption_status.setFixedWidth(120)
        self.encryption_status.setAlignment(Qt.AlignRight)
        self.status_bar.addPermanentWidget(self.encryption_status)

        self.status_bar.showMessage("Готов")
        self._update_encryption_status()

    def _create_central_widget(self):
        """Create central widget with file browser."""
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # File browser
        self.file_model = FileBrowserModel(self.client)
        self.file_view = FileBrowserView(self.file_model)

        # Настройка режимов выделения для поддержки множественного выбора
        self.file_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.file_view.setDragEnabled(True)
        self.file_view.setDragDropMode(QAbstractItemView.DragOnly)
        self.file_view.setDefaultDropAction(Qt.MoveAction)

        # Устанавливаем политику фокуса для обработки клавиш
        self.file_view.setFocusPolicy(Qt.StrongFocus)

        # Connect signals
        self.file_view.directoryChanged.connect(self._change_directory)
        self.file_view.downloadRequested.connect(self._download_item)
        self.file_view.uploadRequested.connect(self._upload_to_folder)
        self.file_view.deleteRequested.connect(self._delete_item)
        self.file_view.renameRequested.connect(self._rename_item)
        self.file_view.copyRequested.connect(self.copy_to_clipboard)
        self.file_view.cutRequested.connect(self.cut_to_clipboard)
        self.file_view.pasteRequested.connect(self.paste_from_clipboard)
        self.file_view.propertiesRequested.connect(self._show_properties)

        self.file_model.directoryLoaded.connect(self._on_directory_loaded)

        # Selection changed
        self.file_view.selectionModel().currentChanged.connect(
            self._on_current_changed
        )
        self.file_view.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )

        # Устанавливаем обработчики событий мыши
        self.file_view.viewport().installEventFilter(self)

        layout.addWidget(self.file_view)
        self.setCentralWidget(central)

        # Настраиваем контекстное меню
        self._setup_context_menu()

    def _setup_context_menu(self):
        """Setup context menu for file browser."""
        self.file_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_view.customContextMenuRequested.connect(
            self._show_context_menu)

    def _show_context_menu(self, position):
        """Show context menu at position."""
        context_menu = QMenu()

        # Определяем, есть ли выделенные элементы
        has_selection = self.has_selected_items()
        index = self.file_view.indexAt(position)
        has_item = index.isValid()

        # Добавляем действия в зависимости от контекста
        if has_item:
            item = self.file_model.file_info(index)
            if item:
                if item['isdir']:
                    upload_action = context_menu.addAction("Загрузить сюда")
                    upload_action.triggered.connect(
                        lambda checked, i=item: self._upload_to_folder(i)
                    )
                    context_menu.addSeparator()

        # Стандартные действия
        context_menu.addAction(self.copy_action)
        context_menu.addAction(self.cut_action)
        context_menu.addAction(self.paste_action)
        context_menu.addSeparator()

        # Действия выделения
        select_menu = context_menu.addMenu("Выделение")
        select_menu.addAction(self.select_all_action)
        select_menu.addAction(self.deselect_all_action)
        select_menu.addAction(self.invert_selection_action)
        context_menu.addSeparator()

        if has_selection:
            context_menu.addAction(self.download_action)
            context_menu.addAction(self.delete_action)
            context_menu.addSeparator()

        context_menu.addAction(self.refresh_action)
        context_menu.addAction(self.properties_action)

        # Показываем меню
        context_menu.exec_(self.file_view.viewport().mapToGlobal(position))

    def _connect_signals(self):
        """Connect client signals."""
        self.client.list_finished.connect(self._on_list_finished)
        self.client.list_error.connect(self._on_list_error)
        self.client.operation_finished.connect(self._on_operation_finished)
        self.client.operation_error.connect(self._on_operation_error)
        self.client.progress.connect(self._on_progress)

    # -------------------------------------------------------------------------
    # Event filter for mouse handling
    # -------------------------------------------------------------------------

    def eventFilter(self, obj, event):
        """Filter events for mouse handling."""
        if obj == self.file_view.viewport():
            if event.type() == event.MouseButtonPress:
                self._handle_mouse_press(event)
            elif event.type() == event.MouseMove:
                self._handle_mouse_move(event)
            elif event.type() == event.MouseButtonRelease:
                self._handle_mouse_release(event)
        return super().eventFilter(obj, event)

    def _handle_mouse_press(self, event: QMouseEvent):
        """Handle mouse press for selection."""
        if event.button() == Qt.LeftButton:
            index = self.file_view.indexAt(event.pos())
            self._mouse_pressed = True
            self._drag_start_pos = event.pos()
            self._drag_start_index = index

    def _handle_mouse_move(self, event: QMouseEvent):
        """Handle mouse move for drag selection."""
        if self._mouse_pressed and self._drag_start_pos:
            # Проверяем, достаточно ли далеко ушла мышь для начала выделения
            if (event.pos() - self._drag_start_pos).manhattanLength() > 10:
                # Включаем режим выделения областью
                self.file_view.setSelectionMode(
                    QAbstractItemView.ExtendedSelection)

                # Создаем область выделения
                rect = self.file_view.visualRect(self._drag_start_index)
                if rect.isValid():
                    # Расширяем выделение до текущей позиции
                    end_index = self.file_view.indexAt(event.pos())
                    if end_index.isValid():
                        selection = QItemSelection()
                        selection.select(self._drag_start_index, end_index)
                        self.file_view.selectionModel().select(
                            selection,
                            QItemSelectionModel.Select | QItemSelectionModel.Rows
                        )

    def _handle_mouse_release(self, event: QMouseEvent):
        """Handle mouse release."""
        if event.button() == Qt.LeftButton:
            self._mouse_pressed = False
            self._drag_start_pos = None
            self._drag_start_index = None

    # -------------------------------------------------------------------------
    # Selection management
    # -------------------------------------------------------------------------

    def select_all_items(self):
        """Select all items in the current directory."""
        try:
            # Исправленный метод выделения всех элементов
            selection_model = self.file_view.selectionModel()
            selection_model.clearSelection()

            # Выделяем все строки
            for row in range(self.file_model.rowCount()):
                index = self.file_model.index(row, 0)
                selection_model.select(
                    index,
                    selection_model.SelectionFlag.Select |
                    selection_model.SelectionFlag.Rows
                )

            count = self.file_model.rowCount()
            self.show_status_message(f"Выделено элементов: {count}")
            logger.debug(f"Selected all items: {count}")

            # Принудительно обновляем отображение
            self.file_view.viewport().update()

        except Exception as e:
            logger.error(f"Error selecting all items: {e}")
            self.show_status_message(f"Ошибка выделения: {e}")

    def deselect_all_items(self):
        """Deselect all items."""
        try:
            self.file_view.clearSelection()
            self.show_status_message("Выделение снято")
            logger.debug("Cleared selection")
        except Exception as e:
            logger.error(f"Error deselecting items: {e}")
            self.show_status_message(f"Ошибка снятия выделения: {e}")

    def invert_selection(self):
        """Invert current selection."""
        try:
            selection_model = self.file_view.selectionModel()
            model = self.file_model

            selected_count = 0
            for row in range(model.rowCount()):
                index = model.index(row, 0)
                if selection_model.isSelected(index):
                    selection_model.select(
                        index,
                        selection_model.SelectionFlag.Deselect |
                        selection_model.SelectionFlag.Rows
                    )
                else:
                    selection_model.select(
                        index,
                        selection_model.SelectionFlag.Select |
                        selection_model.SelectionFlag.Rows
                    )
                    selected_count += 1

            self.show_status_message(f"Выделено элементов: {selected_count}")
            logger.debug(f"Inverted selection, now selected: {selected_count}")
        except Exception as e:
            logger.error(f"Error inverting selection: {e}")
            self.show_status_message(f"Ошибка инвертирования: {e}")

    def has_selected_items(self) -> bool:
        """Check if there are any selected items."""
        try:
            return len(self.file_view.selectedIndexes()) > 0
        except:
            return False

    def get_selected_count(self) -> int:
        """Get number of selected items."""
        try:
            indexes = self.file_view.selectedIndexes()
            # Уникальные строки (каждый элемент может иметь несколько колонок)
            unique_rows = set(idx.row() for idx in indexes)
            return len(unique_rows)
        except:
            return 0

    def _on_selection_changed(self, selected, deselected):
        """Handle selection change."""
        count = self.get_selected_count()
        if count > 0:
            self.show_status_message(f"Выделено элементов: {count}")
        else:
            self.show_status_message("Готов")

    def _show_properties_for_selected(self):
        """Show properties for selected item."""
        items = self._get_selected_items()
        if items:
            self._show_properties(items[0])

    # -------------------------------------------------------------------------
    # Account management
    # -------------------------------------------------------------------------

    def _load_accounts(self):
        """Load accounts from config."""
        accounts_data = self.config.load_accounts()
        self.accounts = [Account.from_dict(acc) for acc in accounts_data]
        self._update_account_combo()

        if self.accounts and self.config.get_setting("auto_connect", False):
            self.switch_account(self.accounts[0])
        else:
            self.status_bar.showMessage("Выберите аккаунт для подключения")

    def _update_account_combo(self):
        """Update account combo box."""
        self.account_combo.clear()
        for acc in self.accounts:
            self.account_combo.addItem(acc.name, acc)

    def _on_account_changed(self, index: int):
        """Handle account selection change."""
        if index >= 0:
            account = self.account_combo.itemData(index)
            if account != self.current_account:
                self.switch_account(account)

    def switch_account(self, account: Account):
        """Switch to different account."""
        try:
            # Decrypt password
            decrypted = self.config.decrypt_password(account.password)
            account_dict = account.to_dict()
            account_dict['password'] = decrypted

            self.client.set_account(account_dict)
            self.current_account = account

            # Navigate to default path
            default_path = account.default_path
            self._change_directory(default_path)
            self._add_to_history(default_path)

            self.status_bar.showMessage(f"Аккаунт: {account.name}")
            self._update_quota_info()

        except Exception as e:
            logger.exception("Error switching account")
            QMessageBox.critical(self, "Ошибка", format_error(e))

    # -------------------------------------------------------------------------
    # Navigation
    # -------------------------------------------------------------------------

    def _change_directory(self, path: str):
        """Change current directory."""
        path = normalize_path(path)
        self.file_model.set_root(path)
        self.path_bar.set_path(path)
        self._update_navigation_buttons()
        QTimer.singleShot(100, self.file_model.refresh)

    def _add_to_history(self, path: str):
        """Add path to navigation history."""
        if self.history_index >= 0 and self.history_index < len(
                self.navigation_history) - 1:
            self.navigation_history = self.navigation_history[
                                      :self.history_index + 1]

        self.navigation_history.append(path)
        self.history_index = len(self.navigation_history) - 1
        self._update_navigation_buttons()

    def _update_navigation_buttons(self):
        """Update navigation buttons state."""
        self.back_action.setEnabled(self.history_index > 0)
        self.forward_action.setEnabled(
            self.history_index < len(self.navigation_history) - 1
        )
        self.up_action.setEnabled(self.file_model.current_path != '/')

    def go_back(self):
        """Go back in history."""
        if self.history_index > 0:
            self.history_index -= 1
            self._change_directory(self.navigation_history[self.history_index])

    def go_forward(self):
        """Go forward in history."""
        if self.history_index < len(self.navigation_history) - 1:
            self.history_index += 1
            self._change_directory(self.navigation_history[self.history_index])

    def go_up(self):
        """Go to parent directory."""
        current = self.file_model.current_path
        if current != '/':
            parent = os.path.dirname(current.rstrip('/')) or '/'
            self._change_directory(parent)
            self._add_to_history(parent)

    def go_home(self):
        """Go home directory."""
        if self.current_account:
            self._change_directory(self.current_account.default_path)
            self._add_to_history(self.current_account.default_path)

    def refresh_current(self):
        """Refresh current directory."""
        self.file_model.refresh()
        self._update_quota_info()

    def _on_path_entered(self, path: str):
        """Handle path entered in path bar."""
        self._change_directory(path)
        self._add_to_history(path)

    def _on_current_changed(self, current, previous):
        """Handle current item change."""
        if current.isValid():
            item = self.file_model.file_info(current)
            if item:
                self.path_bar.set_path(item['path'])

    def _on_directory_loaded(self, path: str):
        """Handle directory loaded."""
        logger.info(f"Directory loaded: {path}")

    # -------------------------------------------------------------------------
    # File operations
    # -------------------------------------------------------------------------

    def new_folder(self):
        """Create new folder."""
        if not self._check_active_account():
            return

        name, ok = QInputDialog.getText(self, "Новая папка", "Имя папки:")
        if ok and name:
            name = name.strip()
            if not name:
                return

            new_path = join_path(self.file_model.current_path, name)
            self._execute_operation(lambda: self.client.mkdir_async(new_path),
                                    f"Создание папки {name}...")

    def upload_file(self):
        """Upload file to current directory."""
        if not self._check_active_account():
            return

        paths, _ = QFileDialog.getOpenFileNames(self,
                                                "Выберите файлы для загрузки")
        if not paths:
            return

        current_path = self.file_model.current_path
        encrypt = self._should_encrypt_upload()

        self._increment_operations(len(paths))

        for local_path in paths:
            remote_path = join_path(current_path, os.path.basename(local_path))

            if encrypt:
                self._upload_encrypted(local_path, remote_path)
            else:
                self.client.upload_async(local_path, remote_path)

        self.status_bar.showMessage(f"Загрузка {len(paths)} файлов...")

    def _should_encrypt_upload(self) -> bool:
        """Check if upload should be encrypted."""
        if not self.encryption_enabled or not self.secure_transfer:
            return False

        reply = QMessageBox.question(
            self, "Шифрование",
            "Зашифровать файлы перед загрузкой?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
        )

        if reply == QMessageBox.Cancel:
            return False

        return reply == QMessageBox.Yes

    def download_selected(self):
        """Download selected files."""
        items = self._get_selected_items()
        if not items:
            QMessageBox.warning(self, "Предупреждение",
                                "Нет выделенных файлов")
            return

        files = [item for item in items if not item['isdir']]
        if not files:
            QMessageBox.warning(self, "Предупреждение",
                                "Нет файлов для скачивания")
            return

        download_dir = self._get_download_directory()
        if not download_dir:
            return

        decrypt = self._should_decrypt_download(files)

        self._increment_operations(len(files))

        for item in files:
            if decrypt and self._is_encrypted_file(item['name']):
                self._download_decrypted(item, download_dir)
            else:
                local_path = os.path.join(download_dir, item['name'])
                self.client.download_async(item['path'], local_path)

        self.status_bar.showMessage(f"Скачивание {len(files)} файлов...")

    def _get_selected_items(self) -> List[Dict]:
        """Get unique selected items."""
        indexes = self.file_view.selectedIndexes()
        items = []
        seen_paths = set()

        for idx in indexes:
            if idx.column() == 0:
                item = self.file_model.file_info(idx)
                if item and item['path'] not in seen_paths:
                    items.append(item)
                    seen_paths.add(item['path'])

        return items

    def _get_download_directory(self) -> Optional[str]:
        """Get download directory."""
        download_dir = self.config.get_setting("download_folder", "")
        if not download_dir or not os.path.exists(download_dir):
            return QFileDialog.getExistingDirectory(
                self, "Выберите папку для сохранения"
            )
        return download_dir

    def _should_decrypt_download(self, files: List[Dict]) -> bool:
        """Check if download should be decrypted."""
        encrypted_files = [f for f in files if
                           self._is_encrypted_file(f['name'])]

        if not encrypted_files or not self.encryption_enabled or not self.secure_transfer:
            return False

        reply = QMessageBox.question(
            self, "Расшифровка",
            f"Найдено {len(encrypted_files)} зашифрованных файлов. "
            f"Расшифровать их?",
            QMessageBox.Yes | QMessageBox.No
        )

        return reply == QMessageBox.Yes

    def _is_encrypted_file(self, filename: str) -> bool:
        """Check if file is encrypted by extension."""
        return filename.endswith('.encrypted')

    def delete_selected(self):
        """Delete selected items."""
        items = self._get_selected_items()
        if not items:
            QMessageBox.warning(self, "Предупреждение",
                                "Нет выделенных элементов")
            return

        count = len(items)
        reply = QMessageBox.question(
            self, "Подтверждение удаления",
            f"Удалить {count} элемент(ов)?\nЭто действие нельзя отменить!",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._increment_operations(count)
            for item in items:
                self.client.delete_async(item['path'])
            self.status_bar.showMessage(f"Удаление {count} элемент(ов)...")

    # -------------------------------------------------------------------------
    # Clipboard operations
    # -------------------------------------------------------------------------

    def copy_to_clipboard(self, item: Optional[Dict] = None):
        """Copy item to clipboard."""
        if not item:
            items = self._get_selected_items()
            if not items:
                QMessageBox.warning(self, "Предупреждение",
                                    "Нет выделенного элемента")
                return
            item = items[0]

        self.clipboard_item = item.copy()
        self.clipboard_action = 'copy'
        self.status_bar.showMessage(f"Скопировано: {item['name']}", 3000)

    def cut_to_clipboard(self, item: Optional[Dict] = None):
        """Cut item to clipboard."""
        if not item:
            items = self._get_selected_items()
            if not items:
                QMessageBox.warning(self, "Предупреждение",
                                    "Нет выделенного элемента")
                return
            item = items[0]

        self.clipboard_item = item.copy()
        self.clipboard_action = 'move'
        self.status_bar.showMessage(f"Вырезано: {item['name']}", 3000)

    def paste_from_clipboard(self, target_item: Optional[Dict] = None):
        """Paste from clipboard."""
        if not self.clipboard_item:
            QMessageBox.warning(self, "Предупреждение", "Буфер обмена пуст")
            return

        # Determine destination
        if target_item and target_item['isdir']:
            dest_dir = target_item['path']
        else:
            dest_dir = self.file_model.current_path

        source_path = self.clipboard_item['path']
        dest_path = join_path(dest_dir, os.path.basename(source_path))

        # Handle same path for copy
        if self.clipboard_action == 'copy' and source_path == dest_path:
            dest_path = self._generate_unique_path(dest_dir, source_path)

        # Handle same path for move
        if self.clipboard_action == 'move' and source_path == dest_path:
            QMessageBox.warning(
                self, "Ошибка",
                "Источник и назначение совпадают. Перемещение невозможно."
            )
            return

        # Execute operation
        self._increment_operations(1)

        if self.clipboard_action == 'copy':
            self.client.copy_async(source_path, dest_path)
            self.status_bar.showMessage(
                f"Копирование {os.path.basename(source_path)}...")
        elif self.clipboard_action == 'move':
            self.client.move_async(source_path, dest_path)
            self.status_bar.showMessage(
                f"Перемещение {os.path.basename(source_path)}...")
            self.clipboard_item = None
            self.clipboard_action = None

    def _generate_unique_path(self, dest_dir: str, source_path: str) -> str:
        """Generate unique path for copy operation."""
        name, ext = os.path.splitext(os.path.basename(source_path))
        counter = 1
        while True:
            new_name = f"{name} (копия {counter}){ext}"
            new_path = join_path(dest_dir, new_name)
            if new_path != source_path:
                return new_path
            counter += 1

    # -------------------------------------------------------------------------
    # Single item operations
    # -------------------------------------------------------------------------

    def _download_item(self, item: Dict):
        """Download single item."""
        if item['isdir']:
            QMessageBox.warning(self, "Предупреждение", "Нельзя скачать папку")
            return

        download_dir = self._get_download_directory()
        if not download_dir:
            return

        if self._is_encrypted_file(item[
                                       'name']) and self.encryption_enabled and self.secure_transfer:
            reply = QMessageBox.question(
                self, "Расшифровка",
                f"Файл {item['name']} зашифрован. Расшифровать его?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self._download_decrypted(item, download_dir)
                return

        # Normal download
        local_path = os.path.join(download_dir, item['name'])
        self._increment_operations(1)
        self.client.download_async(item['path'], local_path)
        self.status_bar.showMessage(f"Скачивание {item['name']}...")

    def _upload_to_folder(self, item: Dict):
        """Upload to selected folder."""
        if not item['isdir']:
            return

        paths, _ = QFileDialog.getOpenFileNames(self,
                                                "Выберите файлы для загрузки")
        if not paths:
            return

        encrypt = self._should_encrypt_upload()

        self._increment_operations(len(paths))

        for local_path in paths:
            remote_path = join_path(item['path'], os.path.basename(local_path))

            if encrypt:
                self._upload_encrypted(local_path, remote_path)
            else:
                self.client.upload_async(local_path, remote_path)

        self.status_bar.showMessage(f"Загрузка {len(paths)} файлов...")

    def _delete_item(self, item: Dict):
        """Delete single item."""
        reply = QMessageBox.question(
            self, "Подтверждение удаления",
            f"Удалить {item['name']}?\nЭто действие нельзя отменить!",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._increment_operations(1)
            self.client.delete_async(item['path'])
            self.status_bar.showMessage(f"Удаление {item['name']}...")

    def _rename_item(self, item: Dict):
        """Rename item."""
        new_name, ok = QInputDialog.getText(
            self, "Переименование", "Новое имя:", text=item['name']
        )

        if ok and new_name and new_name != item['name']:
            new_name = new_name.strip()
            parent = os.path.dirname(item['path'].rstrip('/')) or '/'
            new_path = join_path(parent, new_name)

            self._increment_operations(1)
            self.client.rename_async(item['path'], new_path)
            self.status_bar.showMessage(f"Переименование {item['name']}...")

    def _show_properties(self, item: Dict):
        """Show item properties."""
        from ui.widgets import PropertiesDialog
        dialog = PropertiesDialog(item, self)
        dialog.exec_()

    def _check_active_account(self) -> bool:
        """Check if active account exists."""
        if not self.current_account:
            QMessageBox.warning(self, "Предупреждение",
                                "Нет активного аккаунта")
            return False
        return True

    def _execute_operation(self, operation, message: str):
        """Execute operation with status message."""
        self._increment_operations(1)
        operation()
        self.status_bar.showMessage(message)

    # -------------------------------------------------------------------------
    # Operation tracking
    # -------------------------------------------------------------------------

    def _increment_operations(self, count: int = 1):
        """Increment pending operations count."""
        with self._operation_lock:
            self._pending_operations += count

    def _decrement_operations(self, count: int = 1):
        """Decrement pending operations count."""
        with self._operation_lock:
            self._pending_operations = max(0, self._pending_operations - count)

    def _on_operation_completed(self, message: str):
        """Handle operation completed."""
        self._decrement_operations(1)
        self.status_bar.showMessage(message, 3000)

        if self._pending_operations == 0:
            self.progress_widget.hide()
            QTimer.singleShot(500, self.refresh_current)
            self.status_bar.showMessage("Готов", 3000)
        else:
            self.status_bar.showMessage(
                f"Выполняется операций: {self._pending_operations}", 3000
            )

    def _on_list_finished(self, path: str, files: list):
        """Handle list finished."""
        pass  # Model handles this

    def _on_list_error(self, path: str, error: str):
        """Handle list error."""
        self.status_bar.showMessage(f"Ошибка загрузки {path}: {error}")

    def _on_operation_finished(self, message: str):
        """Handle operation finished from client."""
        self._on_operation_completed(message)

    def _on_operation_error(self, error: str):
        """Handle operation error."""
        self._decrement_operations(1)
        QMessageBox.critical(self, "Ошибка операции", error)

        if self._pending_operations == 0:
            self.progress_widget.hide()
            self.status_bar.showMessage("Готов", 3000)

    def _on_progress(self, current: int, total: int):
        """Handle progress update."""
        self.progress_widget.show()
        self.progress_widget.set_progress(current, total)

    def _cancel_operation(self):
        """Cancel current operation."""
        self.client.cancel_all_operations()
        self._pending_operations = 0
        self.progress_widget.hide()
        self.status_bar.showMessage("Операция отменена", 3000)

    # -------------------------------------------------------------------------
    # Quota information
    # -------------------------------------------------------------------------

    def _update_quota_info(self):
        """Update quota information in status bar."""
        if not self.client.is_connected:
            return

        try:
            quota = CloudInfoFetcher.get_quota(self.client)
            if quota:
                used = format_size(quota['used'])
                total = format_size(quota['total'])
                percent = (quota['used'] / quota['total']) * 100 if quota[
                                                                        'total'] > 0 else 0

                self.quota_label.setText(f"Занято: {used} / {total}")
                self.quota_progress.setValue(int(percent))
                self._update_progress_color(percent)
            else:
                self.quota_label.setText("Квота не доступна")
                self.quota_progress.setValue(0)

        except Exception as e:
            logger.exception("Error updating quota")
            self.quota_label.setText("Ошибка квоты")
            self.quota_progress.setValue(0)

    def _update_progress_color(self, percent: float):
        """Update progress bar color based on usage."""
        if percent < 80:
            color = "#4CAF50"
        elif percent < 95:
            color = "#FFC107"
        else:
            color = "#F44336"

        self.quota_progress.setStyleSheet(f"""
            QProgressBar::chunk {{
                background-color: {color};
            }}
        """)

    # -------------------------------------------------------------------------
    # Encryption
    # -------------------------------------------------------------------------

    def _init_encryption_from_settings(self):
        """Initialize encryption from settings."""
        encryption_enabled = self.config.get_setting("encryption_enabled",
                                                     False)
        if encryption_enabled:
            QTimer.singleShot(100, lambda: self.toggle_encryption(True))
        else:
            self.encryption_action.setChecked(False)

    def toggle_encryption(self, enabled: bool):
        """Toggle encryption on/off."""
        self.config.set_setting("encryption_enabled", enabled)

        if enabled and not self.encryptor:
            if not self._setup_encryption():
                self.encryption_action.setChecked(False)
                self.config.set_setting("encryption_enabled", False)
                return

        elif not enabled:
            self._disable_encryption()

        self._update_encryption_status()

    def _setup_encryption(self) -> bool:
        """Setup encryption."""
        try:
            from core.key_manager import KeyManager
            from core.encryption import FileEncryptor, EncryptionKey
            from services.secure_transfer import SecureTransferService

            config_dir = os.path.join(os.path.expanduser("~"),
                                      ".webdav_manager")
            os.makedirs(config_dir, exist_ok=True)

            self.key_manager = KeyManager(config_dir)
            saved_keys = self.key_manager.get_all_keys()

            if saved_keys:
                if not self._select_key(saved_keys):
                    return False
            else:
                if not self._create_new_key():
                    return False

            if self.encryptor:
                self.secure_transfer = SecureTransferService(
                    self.client, self.key_manager, self.encryptor
                )
                self.encryption_enabled = True
                self.status_bar.showMessage("Шифрование включено", 3000)
                return True

        except Exception as e:
            logger.exception("Error initializing encryption")
            QMessageBox.critical(self, "Ошибка",
                                 f"Не удалось инициализировать шифрование: {e}")

        return False

    def _select_key(self, saved_keys: Dict) -> bool:
        """Select key from saved keys."""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, \
            QDialogButtonBox, QLabel

        dialog = QDialog(self)
        dialog.setWindowTitle("Выберите ключ шифрования")
        dialog.resize(400, 300)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Доступные ключи:"))

        key_list = QListWidget()
        for key_id, key_info in saved_keys.items():
            name = key_info.get('name', 'Без имени')
            created = key_info.get('created', 'Неизвестно')[:10]
            key_list.addItem(f"{name} (ID: {key_id[:8]}) - создан: {created}")

        layout.addWidget(key_list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec_() == QDialog.Accepted and key_list.currentRow() >= 0:
            from core.encryption import EncryptionKey
            selected_key_id = list(saved_keys.keys())[key_list.currentRow()]
            key_info = saved_keys[selected_key_id]
            self.encryptor = FileEncryptor(EncryptionKey.from_dict(key_info))
            return True

        return False

    def _create_new_key(self) -> bool:
        """Create new encryption key."""
        reply = QMessageBox.question(
            self, "Новый ключ",
            "Нет сохраненных ключей. Создать новый ключ?\n\n"
            "Да - создать случайный ключ\n"
            "Нет - ввести пароль для генерации ключа",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
        )

        if reply == QMessageBox.Cancel:
            return False

        from PyQt5.QtWidgets import QInputDialog, QLineEdit

        name, ok = QInputDialog.getText(
            self, "Имя ключа", "Введите имя для нового ключа:", text="default"
        )
        if not ok or not name:
            return False

        from core.encryption import FileEncryptor

        if reply == QMessageBox.Yes:
            self.encryptor = FileEncryptor.create_random(name.strip())
        else:
            password, ok = QInputDialog.getText(
                self, "Пароль", "Введите пароль для генерации ключа:",
                QLineEdit.Password
            )

            if not ok or not password:
                return False

            confirm, ok = QInputDialog.getText(
                self, "Подтверждение", "Подтвердите пароль:",
                QLineEdit.Password
            )

            if not ok or password != confirm:
                QMessageBox.warning(self, "Ошибка", "Пароли не совпадают")
                return False

            self.encryptor = FileEncryptor.create_from_password(password,
                                                                name.strip())

        if self.encryptor:
            self.key_manager.save_key(self.encryptor.key.to_dict())
            return True

        return False

    def _disable_encryption(self):
        """Disable encryption."""
        if self.secure_transfer:
            self.secure_transfer.cleanup()
            self.secure_transfer = None
        self.encryptor = None
        self.encryption_enabled = False
        self.key_manager = None
        logger.info("Encryption disabled")
        self.status_bar.showMessage("Шифрование отключено", 3000)

    def _update_encryption_status(self):
        """Update encryption status display."""
        if self.encryption_enabled:
            self.encryption_status.setText("🔒 Шифрование вкл")
            self.encryption_status.setStyleSheet("color: #4CAF50;")
        else:
            self.encryption_status.setText("🔓 Шифрование выкл")
            self.encryption_status.setStyleSheet("color: #999999;")

    def _upload_encrypted(self, local_path: str, remote_path: str):
        """Upload encrypted file in separate thread."""
        delete_original = self.config.get_setting("encryption_delete_original",
                                                  False)

        thread = threading.Thread(
            target=self._secure_upload_thread,
            args=(local_path, remote_path, delete_original)
        )
        thread.daemon = True
        thread.start()

    def _download_decrypted(self, item: Dict, download_dir: str):
        """Download and decrypt file."""
        original_name = item['name'][:-10]  # Remove '.encrypted'
        local_path = os.path.join(download_dir, original_name)

        thread = threading.Thread(
            target=self._secure_download_thread,
            args=(item['path'], local_path, item['name'])
        )
        thread.daemon = True
        thread.start()

    def _secure_upload_thread(self, local_path, remote_path, delete_original):
        """Upload with encryption in separate thread."""
        try:
            self.secure_transfer.operation_completed.connect(
                self._on_secure_completed, Qt.QueuedConnection
            )
            self.secure_transfer.operation_error.connect(
                self._on_secure_error, Qt.QueuedConnection
            )
            self.secure_transfer.progress_updated.connect(
                self._on_progress, Qt.QueuedConnection
            )

            self.secure_transfer.upload_encrypted(
                local_path, remote_path, delete_original=delete_original
            )

        except Exception as e:
            QMetaObject.invokeMethod(
                self, "_handle_operation_error",
                Qt.QueuedConnection, Q_ARG(str, format_error(e))
            )
        finally:
            try:
                self.secure_transfer.operation_completed.disconnect()
                self.secure_transfer.operation_error.disconnect()
                self.secure_transfer.progress_updated.disconnect()
            except:
                pass

    def _secure_download_thread(self, remote_path, local_path, original_name):
        """Download and decrypt in separate thread."""
        try:
            self.secure_transfer.operation_completed.connect(
                self._on_secure_completed, Qt.QueuedConnection
            )
            self.secure_transfer.operation_error.connect(
                self._on_secure_error, Qt.QueuedConnection
            )
            self.secure_transfer.progress_updated.connect(
                self._on_progress, Qt.QueuedConnection
            )

            self.secure_transfer.download_decrypted(remote_path, local_path)

        except Exception as e:
            QMetaObject.invokeMethod(
                self, "_handle_operation_error",
                Qt.QueuedConnection, Q_ARG(str, format_error(e))
            )
        finally:
            try:
                self.secure_transfer.operation_completed.disconnect()
                self.secure_transfer.operation_error.disconnect()
                self.secure_transfer.progress_updated.disconnect()
            except:
                pass

    def _on_secure_completed(self, message: str):
        """Handle secure transfer completion."""
        self._on_operation_completed(message)

    def _on_secure_error(self, error_msg: str):
        """Handle secure transfer error."""
        self._handle_operation_error(error_msg)

    @pyqtSlot(str)
    def _handle_operation_error(self, error_msg: str):
        """Handle operation error in main thread."""
        self._decrement_operations(1)
        QMessageBox.critical(self, "Ошибка операции", error_msg)

        if self._pending_operations == 0:
            self.progress_widget.hide()
            self.status_bar.showMessage("Готов", 3000)

    # -------------------------------------------------------------------------
    # Dialogs
    # -------------------------------------------------------------------------

    def open_accounts_dialog(self):
        """Open accounts management dialog."""
        logger.info("Opening accounts dialog")
        dialog = AccountsDialog(self.config, self)
        if dialog.exec_():
            self._load_accounts()

    def open_settings_dialog(self):
        """Open settings dialog."""
        logger.info("Opening settings dialog")
        dialog = SettingsDialog(self.config, self)
        dialog.settingsChanged.connect(self._sync_encryption_from_settings)

        if dialog.exec_():
            self._apply_theme()
            self.client.update_settings(self.config.settings)
            self._sync_encryption_from_settings()

    def open_key_dialog(self):
        """Open key management dialog."""
        if not self.key_manager:
            config_dir = os.path.join(os.path.expanduser("~"),
                                      ".webdav_manager")
            os.makedirs(config_dir, exist_ok=True)
            from core.key_manager import KeyManager
            self.key_manager = KeyManager(config_dir)

        from ui.key_dialog import KeyDialog
        dialog = KeyDialog(self.key_manager, self)
        dialog.exec_()

    def lock_application(self):
        """Lock the application and show login dialog."""
        from core.master_key import MasterKeyManager

        logger.info("Locking application")
        self.hide()

        config_dir = os.path.join(os.path.expanduser("~"), ".webdav_manager")
        master_key_manager = MasterKeyManager(config_dir)

        login_dialog = LoginDialog(master_key_manager, self)

        if login_dialog.exec_() == LoginDialog.Accepted:
            logger.info("Application unlocked")
            self.show()
        else:
            self.close()

    def about(self):
        """Show about dialog."""
        QMessageBox.about(
            self, "WebDAV Manager",
            "Менеджер для работы с WebDAV-облаками.\n\n"
            "Версия: 2.0.0\n"
            "• Шифрование файлов AES-256\n"
            "• Управление ключами шифрования\n"
            "• Мастер-ключ для входа\n"
            "• Поддержка нескольких аккаунтов\n"
            "• Кэширование и асинхронные операции\n"
            "• Тёмная и светлая темы\n"
            "• Расширенное управление выделением\n"
            "• Множественное выделение мышью"
        )

    # -------------------------------------------------------------------------
    # Theme
    # -------------------------------------------------------------------------

    def _apply_theme(self):
        """Apply current theme."""
        theme = self.config.get_setting("theme", "dark")
        self.file_view.set_theme(theme)

        # Устанавливаем голубой цвет выделения
        if theme == "dark":
            self.setStyleSheet("""
                QToolBar { background-color: #404040; border: none; }
                QStatusBar { background-color: #404040; color: #ffffff; }
                QMenuBar { background-color: #404040; color: #ffffff; }
                QMenuBar::item:selected { background-color: #0066cc; }

                /* Голубое выделение для таблицы */
                QTreeView::item:selected {
                    background-color: #3399ff;
                    color: white;
                }
                QTreeView::item:selected:focus {
                    background-color: #66b3ff;
                }
                QTreeView::item:selected:!active {
                    background-color: #66a3d2;
                }

                /* Стиль для области выделения при драге */
                QTreeView::item:hover {
                    background-color: #4d4d4d;
                }
            """)
        else:
            self.setStyleSheet("""
                QToolBar { background-color: #f0f0f0; border: none; }
                QStatusBar { background-color: #f0f0f0; color: #000000; }
                QMenuBar { background-color: #f0f0f0; color: #000000; }
                QMenuBar::item:selected { background-color: #3399ff; }

                /* Голубое выделение для таблицы */
                QTreeView::item:selected {
                    background-color: #99ccff;
                    color: black;
                }
                QTreeView::item:selected:focus {
                    background-color: #b3d9ff;
                }
                QTreeView::item:selected:!active {
                    background-color: #cce0f0;
                }

                /* Стиль для области выделения при драге */
                QTreeView::item:hover {
                    background-color: #e6f0ff;
                }
            """)

    def _sync_encryption_from_settings(self):
        """Synchronize encryption state with settings."""
        encryption_enabled = self.config.get_setting("encryption_enabled",
                                                     False)

        if encryption_enabled != self.encryption_enabled:
            self.encryption_action.setChecked(encryption_enabled)
            self.toggle_encryption(encryption_enabled)

    # -------------------------------------------------------------------------
    # Utility methods
    # -------------------------------------------------------------------------

    def show_status_message(self, message: str, timeout: int = 3000):
        """Show message in status bar."""
        if hasattr(self, 'status_bar') and self.status_bar:
            self.status_bar.showMessage(message, timeout)
        else:
            logger.info(f"STATUS: {message}")

    # -------------------------------------------------------------------------
    # Event handlers
    # -------------------------------------------------------------------------

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.matches(QKeySequence.SelectAll):
            self.select_all_items()
            event.accept()
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_A:
            self.select_all_items()
            event.accept()
        elif event.modifiers() == (
                Qt.ControlModifier | Qt.ShiftModifier) and event.key() == Qt.Key_A:
            self.deselect_all_items()
            event.accept()
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_I:
            self.invert_selection()
            event.accept()
        else:
            super().keyPressEvent(event)

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    def closeEvent(self, event):
        """Handle window close."""
        # Clean up encryption
        if self.secure_transfer:
            self.secure_transfer.cleanup()

        # Clean up file model
        self.file_model.shutdown()

        # Cancel all operations
        self.client.cancel_all_operations()

        # Confirm exit if enabled
        if self.config.get_setting("confirm_on_exit", True):
            reply = QMessageBox.question(
                self, "Подтверждение", "Закрыть приложение?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                event.ignore()
                return

        event.accept()