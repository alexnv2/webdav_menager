# ui/accounts_dialog.py
"""Accounts management dialog."""

import logging
import uuid
import json
from typing import Optional, List, Dict
from contextlib import contextmanager
from functools import wraps

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QPushButton, QHeaderView,
                             QMessageBox, QLineEdit, QFormLayout,
                             QDialogButtonBox, QComboBox, QCheckBox,
                             QApplication, QWidget, QLabel, QFileDialog,
                             QMenu)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QPalette

from core.config import ConfigManager
from core.models import Account

logger = logging.getLogger(__name__)


def log_errors(func):
    """Декоратор для логирования ошибок в методах."""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            self._show_error(f"Ошибка в {func.__name__}", e)
            return None

    return wrapper


class LoadingOverlay(QWidget):
    """Простой оверлей для индикации загрузки."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            LoadingOverlay {
                background-color: rgba(0, 0, 0, 100);
            }
            QLabel {
                color: white;
                font-size: 16px;
                font-weight: bold;
                background-color: rgba(0, 0, 0, 150);
                padding: 20px;
                border-radius: 10px;
            }
        """)
        self.hide()

        layout = QVBoxLayout(self)
        self.label = QLabel("Загрузка...")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

    def set_text(self, text: str):
        """Установка текста загрузки."""
        self.label.setText(text)


class AccountsDialog(QDialog):
    """Диалог управления аккаунтами."""

    accountsChanged = pyqtSignal()

    # Константы для колонок таблицы
    COLUMN_NAME = 0
    COLUMN_TYPE = 1
    COLUMN_URL = 2
    COLUMN_LOGIN = 3
    COLUMN_STATUS = 4
    COLUMN_COUNT = 5

    # Ширины колонок по умолчанию
    DEFAULT_COLUMN_WIDTHS = {
        'name': 200,
        'type': 120,
        'url': 300,
        'login': 150,
        'status': 100
    }

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self.accounts: List[Account] = []
        self._loading = False
        self._password_cache = {}
        self._undo_stack = []
        self._redo_stack = []
        self._max_undo_steps = 20
        self._auto_save_timer = QTimer()
        self._auto_save_timer.setInterval(3000)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.timeout.connect(self._auto_save)

        self.setWindowTitle("Управление аккаунтами")
        self.resize(900, 500)
        self.setModal(True)

        self._setup_ui()
        self._setup_signals()
        self._load_accounts()
        self._load_column_widths()

    def _setup_ui(self):
        """Настройка пользовательского интерфейса."""
        layout = QVBoxLayout(self)

        # Таблица аккаунтов
        self._setup_table()
        layout.addWidget(self.table)

        # Кнопки управления
        layout.addLayout(self._create_button_layout())

        # Кнопки диалога
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Оверлей загрузки
        self.overlay = LoadingOverlay(self)
        self.overlay.resize(self.size())

    def _setup_table(self):
        """Настройка таблицы аккаунтов."""
        self.table = QTableWidget()
        self.table.setColumnCount(self.COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(
            ["Имя", "Тип", "URL", "Логин", "Статус"])

        # Стили для таблицы с темными заголовками
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #2c3e50;
                color: white;
                padding: 8px;
                border: 1px solid #1a252f;
                font-weight: bold;
                font-size: 12px;
            }
            QHeaderView::section:hover {
                background-color: #34495e;
            }
            QHeaderView::section:checked {
                background-color: #2980b9;
            }
            QTableWidget QTableCornerButton::section {
                background-color: #2c3e50;
                border: 1px solid #1a252f;
            }
        """)

        header = self.table.horizontalHeader()

        # Настраиваем поведение столбцов
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)

        # Устанавливаем начальные ширины
        self._reset_column_widths()

        # Разрешаем сортировку
        self.table.setSortingEnabled(True)

        # Настройки выделения
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        # Двойной клик для редактирования
        self.table.doubleClicked.connect(self._edit_account)

        # Контекстное меню
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        # Контекстное меню для заголовка
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(
            self._show_header_context_menu)

    def _create_button_layout(self) -> QHBoxLayout:
        """Создание панели с кнопками."""
        button_layout = QHBoxLayout()

        # Создаем кнопки
        self.add_btn = QPushButton("➕ Добавить")
        self.edit_btn = QPushButton("✏️ Изменить")
        self.delete_btn = QPushButton("🗑️ Удалить")
        self.duplicate_btn = QPushButton("📋 Дублировать")
        self.test_btn = QPushButton("🔌 Проверить")
        self.export_btn = QPushButton("📤 Экспорт")
        self.import_btn = QPushButton("📥 Импорт")

        # Устанавливаем подсказки
        self.add_btn.setToolTip("Добавить новый аккаунт (Ctrl+N)")
        self.edit_btn.setToolTip("Редактировать выбранный аккаунт (Enter)")
        self.delete_btn.setToolTip("Удалить выбранный аккаунт (Del)")
        self.duplicate_btn.setToolTip("Дублировать выбранный аккаунт (Ctrl+D)")
        self.test_btn.setToolTip("Проверить подключение (Ctrl+T)")
        self.export_btn.setToolTip("Экспортировать аккаунты в файл")
        self.import_btn.setToolTip("Импортировать аккаунты из файла")

        # Подключаем сигналы
        self.add_btn.clicked.connect(lambda: self._add_account())
        self.edit_btn.clicked.connect(lambda: self._edit_account())
        self.delete_btn.clicked.connect(lambda: self._delete_account())
        self.duplicate_btn.clicked.connect(lambda: self._duplicate_account())
        self.test_btn.clicked.connect(lambda: self._test_connection())
        self.export_btn.clicked.connect(lambda: self._export_accounts())
        self.import_btn.clicked.connect(lambda: self._import_accounts())

        # Добавляем кнопки в макет
        buttons = [self.add_btn, self.edit_btn, self.delete_btn,
                   self.duplicate_btn, self.test_btn, self.export_btn,
                   self.import_btn]

        for btn in buttons:
            button_layout.addWidget(btn)

        button_layout.addStretch()
        return button_layout

    def _setup_signals(self):
        """Настройка дополнительных сигналов."""
        self.table.itemSelectionChanged.connect(self._update_buttons_state)
        self.accountsChanged.connect(self._on_accounts_changed)

    def _update_buttons_state(self):
        """Обновление состояния кнопок в зависимости от выделения."""
        selected_rows = set(item.row() for item in self.table.selectedItems())
        has_selection = len(selected_rows) > 0
        single_selection = len(selected_rows) == 1

        self.edit_btn.setEnabled(single_selection and not self._loading)
        self.delete_btn.setEnabled(has_selection and not self._loading)
        self.duplicate_btn.setEnabled(single_selection and not self._loading)
        self.test_btn.setEnabled(single_selection and not self._loading)

    def _on_accounts_changed(self):
        """Обработка изменения аккаунтов."""
        self._auto_save_timer.start()

    @contextmanager
    def _loading_state(self, message: str = "Загрузка..."):
        """Контекстный менеджер для состояния загрузки."""
        self._loading = True
        self._update_buttons_state()
        self.overlay.set_text(message)
        self.overlay.show()
        QApplication.processEvents()
        try:
            yield
        finally:
            self._loading = False
            self._update_buttons_state()
            self.overlay.hide()

    def _auto_save(self):
        """Автосохранение изменений."""
        try:
            accounts_data = [acc.to_dict() for acc in self.accounts]
            self.config.save_accounts(accounts_data)
            logger.debug("Auto-saved accounts")
        except Exception as e:
            logger.warning(f"Auto-save failed: {e}")

    def _add_to_undo_stack(self, action: str, old_data: List[Dict],
                           new_data: List[Dict]):
        """Добавление действия в историю отмены."""
        self._undo_stack.append({
            'action': action,
            'old': old_data,
            'new': new_data
        })
        self._redo_stack.clear()

        if len(self._undo_stack) > self._max_undo_steps:
            self._undo_stack.pop(0)

    def _load_column_widths(self):
        """Загрузка сохраненных ширин столбцов."""
        try:
            settings = self.config.get_settings()
            widths = settings.get('accounts_dialog_column_widths', {})

            if widths:
                self.table.setColumnWidth(self.COLUMN_NAME, widths.get('name',
                                                                       self.DEFAULT_COLUMN_WIDTHS[
                                                                           'name']))
                self.table.setColumnWidth(self.COLUMN_TYPE, widths.get('type',
                                                                       self.DEFAULT_COLUMN_WIDTHS[
                                                                           'type']))
                self.table.setColumnWidth(self.COLUMN_URL, widths.get('url',
                                                                      self.DEFAULT_COLUMN_WIDTHS[
                                                                          'url']))
                self.table.setColumnWidth(self.COLUMN_LOGIN,
                                          widths.get('login',
                                                     self.DEFAULT_COLUMN_WIDTHS[
                                                         'login']))
                self.table.setColumnWidth(self.COLUMN_STATUS,
                                          widths.get('status',
                                                     self.DEFAULT_COLUMN_WIDTHS[
                                                         'status']))
        except Exception as e:
            logger.warning(f"Failed to load column widths: {e}")

    def _save_column_widths(self):
        """Сохранение ширин столбцов."""
        try:
            widths = {
                'name': self.table.columnWidth(self.COLUMN_NAME),
                'type': self.table.columnWidth(self.COLUMN_TYPE),
                'url': self.table.columnWidth(self.COLUMN_URL),
                'login': self.table.columnWidth(self.COLUMN_LOGIN),
                'status': self.table.columnWidth(self.COLUMN_STATUS),
            }

            settings = self.config.get_settings()
            settings['accounts_dialog_column_widths'] = widths
            self.config.save_settings(settings)
            logger.debug(f"Saved column widths: {widths}")
        except Exception as e:
            logger.warning(f"Failed to save column widths: {e}")

    def _reset_column_widths(self):
        """Сброс ширины столбцов к значениям по умолчанию."""
        self.table.setColumnWidth(self.COLUMN_NAME,
                                  self.DEFAULT_COLUMN_WIDTHS['name'])
        self.table.setColumnWidth(self.COLUMN_TYPE,
                                  self.DEFAULT_COLUMN_WIDTHS['type'])
        self.table.setColumnWidth(self.COLUMN_URL,
                                  self.DEFAULT_COLUMN_WIDTHS['url'])
        self.table.setColumnWidth(self.COLUMN_LOGIN,
                                  self.DEFAULT_COLUMN_WIDTHS['login'])
        self.table.setColumnWidth(self.COLUMN_STATUS,
                                  self.DEFAULT_COLUMN_WIDTHS['status'])
        self._save_column_widths()

    def _show_header_context_menu(self, pos):
        """Показ контекстного меню для заголовка таблицы."""
        menu = QMenu()
        menu.addAction("Сбросить ширину столбцов", self._reset_column_widths)
        menu.exec_(self.table.horizontalHeader().mapToGlobal(pos))

    def _load_accounts(self):
        """Загрузка аккаунтов из конфигурации."""
        logger.info("Loading accounts...")
        try:
            accounts_data = self.config.load_accounts()
            self.accounts = [Account.from_dict(acc) for acc in accounts_data]
            logger.info(f"Loaded {len(self.accounts)} accounts")
            self._refresh_table()
        except Exception as e:
            logger.exception(f"Error loading accounts: {e}")
            self._show_error("Не удалось загрузить аккаунты", e)

    def _refresh_table(self):
        """Обновление таблицы с текущими аккаунтами."""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.accounts))

        for i, account in enumerate(self.accounts):
            self._set_table_row(i, account)

        self.table.setSortingEnabled(True)
        self._update_buttons_state()

    def _set_table_row(self, row: int, account: Account):
        """Заполнение строки таблицы данными аккаунта."""
        items = [
            (self.COLUMN_NAME, account.name),
            (self.COLUMN_TYPE, account.type),
            (self.COLUMN_URL, account.url),
            (self.COLUMN_LOGIN, account.login),
            (self.COLUMN_STATUS, "Активен" if account.enabled else "Отключен")
        ]

        for col, value in items:
            item = QTableWidgetItem(value)
            if col == self.COLUMN_STATUS:
                color = "#4CAF50" if account.enabled else "#ff6b6b"
                item.setForeground(QColor(color))
                item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, col, item)

    def _get_selected_accounts(self) -> List[Account]:
        """Получение всех выбранных аккаунтов."""
        selected_rows = set(item.row() for item in self.table.selectedItems())
        return [self.accounts[row] for row in selected_rows if
                0 <= row < len(self.accounts)]

    def _get_selected_account(self) -> Optional[Account]:
        """Получение первого выбранного аккаунта."""
        accounts = self._get_selected_accounts()
        return accounts[0] if accounts else None

    @log_errors
    def _add_account(self, *args, **kwargs):
        """Добавление нового аккаунта."""
        dialog = AccountEditDialog(self.config, self)
        if dialog.exec_() == QDialog.Accepted:
            account = dialog.get_account()
            if account:
                old_data = [acc.to_dict() for acc in self.accounts]

                account.id = str(uuid.uuid4())
                self.accounts.append(account)

                new_data = [acc.to_dict() for acc in self.accounts]
                self._add_to_undo_stack("add", old_data, new_data)

                self._refresh_table()
                self.accountsChanged.emit()

    @log_errors
    def _edit_account(self, *args, **kwargs):
        """Редактирование выбранного аккаунта."""
        account = self._get_selected_account()
        if not account:
            self._show_warning("Выберите аккаунт для редактирования")
            return

        old_data = [acc.to_dict() for acc in self.accounts]

        dialog = AccountEditDialog(self.config, self, account)
        if dialog.exec_() == QDialog.Accepted:
            updated = dialog.get_account()
            if updated:
                for key, value in updated.__dict__.items():
                    setattr(account, key, value)

                new_data = [acc.to_dict() for acc in self.accounts]
                self._add_to_undo_stack("edit", old_data, new_data)

                self._refresh_table()
                self.accountsChanged.emit()

    @log_errors
    def _delete_account(self, *args, **kwargs):
        """Удаление выбранных аккаунтов."""
        selected = self._get_selected_accounts()
        if not selected:
            self._show_warning("Выберите аккаунты для удаления")
            return

        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Удалить {len(selected)} аккаунт(ов)?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            old_data = [acc.to_dict() for acc in self.accounts]

            for account in selected:
                self.accounts.remove(account)

            new_data = [acc.to_dict() for acc in self.accounts]
            self._add_to_undo_stack("delete", old_data, new_data)

            self._refresh_table()
            self.accountsChanged.emit()

    @log_errors
    def _duplicate_account(self, *args, **kwargs):
        """Дублирование выбранного аккаунта."""
        account = self._get_selected_account()
        if not account:
            self._show_warning("Выберите аккаунт для дублирования")
            return

        old_data = [acc.to_dict() for acc in self.accounts]

        new_account = Account(
            id=str(uuid.uuid4()),
            name=f"{account.name} (копия)",
            type=account.type,
            url=account.url,
            login=account.login,
            password=account.password,
            default_path=account.default_path,
            enabled=account.enabled
        )

        self.accounts.append(new_account)

        new_data = [acc.to_dict() for acc in self.accounts]
        self._add_to_undo_stack("duplicate", old_data, new_data)

        self._refresh_table()
        self.accountsChanged.emit()

    @log_errors
    def _enable_selected(self, enabled: bool, *args, **kwargs):
        """Включение/отключение выбранных аккаунтов."""
        selected = self._get_selected_accounts()
        if not selected:
            return

        old_data = [acc.to_dict() for acc in self.accounts]

        for account in selected:
            account.enabled = enabled

        new_data = [acc.to_dict() for acc in self.accounts]
        self._add_to_undo_stack("enable" if enabled else "disable", old_data,
                                new_data)

        self._refresh_table()
        self.accountsChanged.emit()

    @log_errors
    def _test_connection(self, *args, **kwargs):
        """Проверка подключения к выбранному аккаунту."""
        account = self._get_selected_account()
        if not account:
            self._show_warning("Выберите аккаунт для проверки")
            return

        with self._loading_state("Проверка подключения..."):
            try:
                password = self.config.decrypt_password(account.password)
                success, message = self._check_webdav_connection(
                    account.url,
                    account.login,
                    password
                )

                if success:
                    self._show_info("Успех", message)
                else:
                    self._show_warning(message)

            except Exception as e:
                self._show_error("Ошибка подключения", e)

    def _check_webdav_connection(self, url: str, login: str,
                                 password: str) -> tuple:
        """Проверка WebDAV подключения."""
        import requests
        from requests.auth import HTTPBasicAuth
        from requests.exceptions import RequestException

        url = url.rstrip('/') + '/'

        try:
            response = requests.request(
                'PROPFIND',
                url,
                auth=HTTPBasicAuth(login, password),
                headers={'Depth': '0'},
                timeout=10
            )

            if response.status_code in (200, 201, 207):
                return True, "Подключение успешно!"
            elif response.status_code == 401:
                return False, "Ошибка авторизации: неверный логин или пароль"
            elif response.status_code == 404:
                return False, "URL не найден. Проверьте адрес сервера"
            elif response.status_code == 405:
                return self._check_with_get(url, login, password)
            else:
                return False, f"Ошибка HTTP {response.status_code}"

        except requests.ConnectionError:
            return False, "Не удалось подключиться к серверу"
        except requests.Timeout:
            return False, "Превышено время ожидания"
        except RequestException as e:
            return False, f"Ошибка запроса: {str(e)}"

    def _check_with_get(self, url: str, login: str, password: str) -> tuple:
        """Проверка подключения через GET запрос."""
        try:
            import requests
            from requests.auth import HTTPBasicAuth

            response = requests.get(
                url,
                auth=HTTPBasicAuth(login, password),
                timeout=10
            )

            if response.status_code == 200:
                return True, "Подключение успешно (режим совместимости)"
            else:
                return False, f"Ошибка HTTP {response.status_code}"
        except:
            return False, "Сервер не поддерживает WebDAV методы"

    @log_errors
    def _export_accounts(self, *args, **kwargs):
        """Экспорт аккаунтов в файл."""
        if not self.accounts:
            self._show_warning("Нет аккаунтов для экспорта")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт аккаунтов",
            "accounts_backup.json",
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        try:
            accounts_data = []
            for acc in self.accounts:
                acc_dict = acc.to_dict()
                acc_dict['_export_info'] = {
                    'version': '1.0',
                    'timestamp': str(uuid.uuid4()),
                    'app': 'FileBridge'
                }
                accounts_data.append(acc_dict)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(accounts_data, f, ensure_ascii=False, indent=2)

            self._show_info("Успех",
                            f"Экспортировано {len(accounts_data)} аккаунтов")
            logger.info(
                f"Exported {len(accounts_data)} accounts to {file_path}")

        except Exception as e:
            logger.exception("Export error")
            self._show_error("Ошибка экспорта", e)

    @log_errors
    def _import_accounts(self, *args, **kwargs):
        """Импорт аккаунтов из файла."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Импорт аккаунтов",
            "",
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                accounts_data = json.load(f)

            if not accounts_data:
                self._show_warning("Файл не содержит аккаунтов")
                return

            logger.info(
                f"Importing {len(accounts_data)} accounts from {file_path}")

            reply = QMessageBox.question(
                self,
                "Импорт аккаунтов",
                f"Найдено {len(accounts_data)} аккаунтов.\n\n"
                "Заменить существующие или добавить к текущим?\n\n"
                "Yes: Заменить все текущие аккаунты\n"
                "No: Добавить к существующим\n"
                "Cancel: Отмена",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Cancel:
                return

            old_data = [acc.to_dict() for acc in self.accounts]
            imported = []
            errors = []

            for i, acc_data in enumerate(accounts_data):
                try:
                    acc_data.pop('_export_info', None)

                    required_fields = ['id', 'name', 'type', 'url', 'login',
                                       'password']
                    missing_fields = [f for f in required_fields if
                                      f not in acc_data]

                    if missing_fields:
                        raise ValueError(
                            f"Отсутствуют поля: {', '.join(missing_fields)}")

                    old_id = acc_data.get('id', 'unknown')
                    acc_data['id'] = str(uuid.uuid4())

                    account = Account.from_dict(acc_data)
                    imported.append(account)
                    logger.debug(
                        f"Imported account: {account.name} (was: {old_id}, now: {account.id})")

                except Exception as e:
                    error_msg = f"Аккаунт {i + 1}: {str(e)}"
                    errors.append(error_msg)
                    logger.warning(f"Failed to import account {i + 1}: {e}")

            if not imported:
                self._show_error("Импорт не удался",
                                 Exception(
                                     "Не удалось импортировать ни одного "
                                     "аккаунта"))
                return

            if reply == QMessageBox.Yes:
                self.accounts = imported
                action_msg = "заменены"
            else:
                self.accounts.extend(imported)
                action_msg = "добавлены"

            new_data = [acc.to_dict() for acc in self.accounts]
            self._add_to_undo_stack("import", old_data, new_data)

            self._refresh_table()
            self.accountsChanged.emit()

            success_msg = (f"Успешно импортировано {len(imported)} аккаунтов "
                           f"(импортированные {action_msg})")
            if errors:
                success_msg += f"\n\nОшибки при импорте {len(errors)} аккаунтов:\n" + "\n".join(
                    errors[:5])
                if len(errors) > 5:
                    success_msg += f"\n... и еще {len(errors) - 5} ошибок"

            self._show_info("Результат импорта", success_msg)
            logger.info(
                f"Import completed: {len(imported)} success, {len(errors)} failed")

        except json.JSONDecodeError as e:
            self._show_error("Ошибка формата JSON", e)
        except Exception as e:
            logger.exception("Import error")
            self._show_error("Ошибка импорта", e)

    def _show_context_menu(self, position):
        """Показ контекстного меню."""
        menu = QMenu()

        selected = self._get_selected_accounts()
        selected_count = len(selected)

        if selected_count == 1:
            menu.addAction("✏️ Редактировать", lambda: self._edit_account())
            menu.addAction("📋 Дублировать", lambda: self._duplicate_account())

        if selected_count > 0:
            menu.addAction("🗑️ Удалить", lambda: self._delete_account())
            menu.addSeparator()
            menu.addAction("✅ Включить", lambda: self._enable_selected(True))
            menu.addAction("❌ Отключить", lambda: self._enable_selected(False))

        menu.addSeparator()
        menu.addAction("📤 Экспорт", lambda: self._export_accounts())
        menu.addAction("📥 Импорт", lambda: self._import_accounts())

        if self._undo_stack:
            menu.addSeparator()
            menu.addAction("↩️ Отменить", lambda: self._undo())

        if self._redo_stack:
            menu.addAction("↪️ Повторить", lambda: self._redo())

        menu.exec_(self.table.viewport().mapToGlobal(position))

    def _undo(self, *args, **kwargs):
        """Отмена последнего действия."""
        if not self._undo_stack:
            return

        action = self._undo_stack.pop()
        self._redo_stack.append(action)

        self.accounts = [Account.from_dict(data) for data in action['old']]
        self._refresh_table()
        self.accountsChanged.emit()

    def _redo(self, *args, **kwargs):
        """Повтор отмененного действия."""
        if not self._redo_stack:
            return

        action = self._redo_stack.pop()
        self._undo_stack.append(action)

        self.accounts = [Account.from_dict(data) for data in action['new']]
        self._refresh_table()
        self.accountsChanged.emit()

    def keyPressEvent(self, event):
        """Обработка горячих клавиш."""
        if event.modifiers() == Qt.ControlModifier:
            if event.key() == Qt.Key_N:
                self._add_account()
            elif event.key() == Qt.Key_D:
                self._duplicate_account()
            elif event.key() == Qt.Key_T:
                self._test_connection()
            elif event.key() == Qt.Key_Z and self._undo_stack:
                self._undo()
            elif event.key() == Qt.Key_Y and self._redo_stack:
                self._redo()
        elif event.key() == Qt.Key_Delete:
            self._delete_account()
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self._edit_account()
        else:
            super().keyPressEvent(event)

    def accept(self):
        """Сохранение изменений и закрытие диалога."""
        try:
            accounts_data = [acc.to_dict() for acc in self.accounts]
            self.config.save_accounts(accounts_data)
            super().accept()
        except Exception as e:
            logger.exception("Error saving accounts")
            self._show_error("Не удалось сохранить аккаунты", e)

    def resizeEvent(self, event):
        """Обработка изменения размера окна."""
        super().resizeEvent(event)
        self.overlay.resize(self.size())

    def closeEvent(self, event):
        """Обработка закрытия окна."""
        self._save_column_widths()
        self._password_cache.clear()
        super().closeEvent(event)

    def _show_error(self, message: str, error: Optional[Exception] = None):
        """Показ сообщения об ошибке."""
        text = f"{message}: {error}" if error else message
        QMessageBox.critical(self, "Ошибка", text)

    def _show_warning(self, message: str):
        """Показ предупреждения."""
        QMessageBox.warning(self, "Предупреждение", message)

    def _show_info(self, title: str, message: str):
        """Показ информационного сообщения."""
        QMessageBox.information(self, title, message)


class AccountEditDialog(QDialog):
    """Диалог редактирования аккаунта."""

    ACCOUNT_TYPES = {
        "webdav": "Стандартный WebDAV",
        "yandex": "Яндекс.Диск",
        "mailru": "Облако Mail.ru",
        "nextcloud": "Nextcloud",
        "owncloud": "OwnCloud",
        "other": "Другой"
    }

    def __init__(self, config: ConfigManager, parent=None,
                 account: Optional[Account] = None):
        super().__init__(parent)
        self.config = config
        self.account = account
        self.result_account: Optional[Account] = None

        self.setWindowTitle(
            "Новый аккаунт" if not account else "Редактирование аккаунта")
        self.resize(550, 500)
        self.setModal(True)

        self._setup_ui()
        self._setup_validators()
        self._load_account_data()
        self._setup_signals()

    def _setup_ui(self):
        """Настройка пользовательского интерфейса."""
        layout = QVBoxLayout(self)

        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form_layout.setLabelAlignment(Qt.AlignRight)
        form_layout.setSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: Мой Яндекс.Диск")
        self.name_edit.setMaxLength(100)
        form_layout.addRow("Имя аккаунта:*", self.name_edit)

        self.type_combo = QComboBox()
        for value, label in self.ACCOUNT_TYPES.items():
            self.type_combo.addItem(label, value)
        form_layout.addRow("Тип:", self.type_combo)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://webdav.yandex.ru")
        form_layout.addRow("URL сервера:*", self.url_edit)

        self.login_edit = QLineEdit()
        self.login_edit.setPlaceholderText("Логин или email")
        form_layout.addRow("Логин:*", self.login_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("Пароль")
        form_layout.addRow("Пароль:*", self.password_edit)

        self.password_strength_label = QLabel()
        form_layout.addRow("Сложность:", self.password_strength_label)

        self.show_password_check = QCheckBox("Показать пароль")
        form_layout.addRow("", self.show_password_check)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("/ (корневая директория)")
        form_layout.addRow("Путь по умолчанию:", self.path_edit)

        self.enabled_check = QCheckBox("Аккаунт активен")
        self.enabled_check.setChecked(True)
        form_layout.addRow("", self.enabled_check)

        layout.addWidget(form_widget)

        hint_label = QLabel("* обязательные поля")
        hint_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(hint_label)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _setup_validators(self):
        """Настройка валидаторов для полей ввода."""
        self.name_edit.textChanged.connect(
            lambda: self._validate_field(self.name_edit,
                                         bool(self.name_edit.text().strip())))
        self.url_edit.textChanged.connect(
            lambda: self._validate_field(self.url_edit, self._is_valid_url(
                self.url_edit.text())))
        self.login_edit.textChanged.connect(
            lambda: self._validate_field(self.login_edit,
                                         bool(self.login_edit.text().strip())))

    def _validate_field(self, field: QLineEdit, is_valid: bool):
        """Визуальная индикация валидации поля."""
        if is_valid:
            field.setStyleSheet("")
        else:
            field.setStyleSheet("border: 1px solid red;")

    def _setup_signals(self):
        """Настройка сигналов."""
        self.show_password_check.stateChanged.connect(
            self._toggle_password_visibility)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        self.password_edit.textChanged.connect(self._update_password_strength)

    def _toggle_password_visibility(self, state):
        """Переключение видимости пароля."""
        self.password_edit.setEchoMode(
            QLineEdit.Normal if state == Qt.Checked else QLineEdit.Password
        )

    def _on_type_changed(self, index):
        """Обработка смены типа аккаунта."""
        account_type = self.type_combo.currentData()

        urls = {
            "yandex": "https://webdav.yandex.ru",
            "mailru": "https://webdav.cloud.mail.ru",
        }

        if account_type in urls and not self.url_edit.text():
            self.url_edit.setText(urls[account_type])

    def _update_password_strength(self):
        """Обновление индикатора сложности пароля."""
        password = self.password_edit.text()

        if not password:
            self.password_strength_label.setText("")
            self.password_strength_label.setStyleSheet("")
            return

        strength = 0
        if len(password) >= 8:
            strength += 1
        if any(c.isupper() for c in password):
            strength += 1
        if any(c.islower() for c in password):
            strength += 1
        if any(c.isdigit() for c in password):
            strength += 1
        if any(c in "!@#$%^&*()_+-=[]{};:,.<>?" for c in password):
            strength += 1

        if strength <= 2:
            text = "Слабый"
            color = "red"
        elif strength <= 4:
            text = "Средний"
            color = "orange"
        else:
            text = "Сильный"
            color = "green"

        self.password_strength_label.setText(text)
        self.password_strength_label.setStyleSheet(
            f"color: {color}; font-weight: bold;")

    def _load_account_data(self):
        """Загрузка данных аккаунта в форму."""
        if not self.account:
            return

        self.name_edit.setText(self.account.name)

        index = self.type_combo.findData(self.account.type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)

        self.url_edit.setText(self.account.url)
        self.login_edit.setText(self.account.login)

        try:
            decrypted = self.config.decrypt_password(self.account.password)
            self.password_edit.setText(decrypted)
            self._update_password_strength()
        except Exception as e:
            logger.warning(f"Could not decrypt password: {e}")

        self.path_edit.setText(self.account.default_path or "/")
        self.enabled_check.setChecked(self.account.enabled)

    def _validate_and_accept(self):
        """Валидация полей и принятие диалога."""
        errors = []

        if not self.name_edit.text().strip():
            errors.append("• Введите имя аккаунта")

        if not self.url_edit.text().strip():
            errors.append("• Введите URL сервера")
        elif not self._is_valid_url(self.url_edit.text().strip()):
            errors.append(
                "• Введите корректный URL (начинается с http:// или https://)")

        if not self.login_edit.text().strip():
            errors.append("• Введите логин")

        if not self.password_edit.text().strip() and not self.account:
            errors.append("• Введите пароль")

        if errors:
            QMessageBox.warning(
                self,
                "Ошибка валидации",
                "Пожалуйста, исправьте следующие ошибки:\n\n" + "\n".join(
                    errors)
            )
            return

        if not self.account and len(self.password_edit.text()) < 6:
            reply = QMessageBox.question(
                self,
                "Слабый пароль",
                "Пароль слишком короткий. Продолжить?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        try:
            self.result_account = self._create_account_from_form()
            self.accept()
        except Exception as e:
            logger.exception("Error creating account")
            QMessageBox.critical(self, "Ошибка",
                                 f"Не удалось сохранить аккаунт: {e}")

    def _is_valid_url(self, url: str) -> bool:
        """Проверка корректности URL."""
        return url.startswith(('http://', 'https://'))

    def _create_account_from_form(self) -> Account:
        """Создание объекта Account из данных формы."""
        password = self.password_edit.text().strip()

        if password and (not self.account or
                         password != self.config.decrypt_password(
                    self.account.password)):
            encrypted_password = self.config.encrypt_password(password)
        else:
            encrypted_password = self.account.password if self.account else ""

        return Account(
            id=self.account.id if self.account else "",
            name=self.name_edit.text().strip(),
            type=self.type_combo.currentData(),
            url=self.url_edit.text().strip().rstrip('/'),
            login=self.login_edit.text().strip(),
            password=encrypted_password,
            default_path=self.path_edit.text().strip() or '/',
            enabled=self.enabled_check.isChecked()
        )

    def get_account(self) -> Optional[Account]:
        """Получение созданного/отредактированного аккаунта."""
        return self.result_account

    def _show_info(self, title: str, message: str):
        """Показ информационного сообщения."""
        QMessageBox.information(self, title, message)
