# ui/accounts_dialog.py
"""Accounts management dialog."""

import logging
import uuid
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QPushButton, QHeaderView,
                             QMessageBox, QLineEdit, QFormLayout,
                             QDialogButtonBox, QComboBox, QCheckBox,
                             QApplication, QWidget, QHBoxLayout, QLabel)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QIcon

from core.config import ConfigManager
from core.models import Account
from core.webdav_client import \
    WebDAVClient  # Предполагаем наличие такого класса

logger = logging.getLogger(__name__)


class LoadingOverlay(QWidget):
    """Простой оверлей для индикации загрузки."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 100);")
        self.hide()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Загрузка..."), alignment=Qt.AlignCenter)


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

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self.accounts: List[Account] = []
        self._loading = False

        self.setWindowTitle("Управление аккаунтами")
        self.resize(800, 400)
        self.setModal(True)

        self._setup_ui()
        self._setup_signals()
        self._load_accounts()

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

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(self.COLUMN_URL, QHeaderView.Interactive)

        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)

        # Двойной клик для редактирования
        self.table.doubleClicked.connect(self._edit_account)

    def _create_button_layout(self) -> QHBoxLayout:
        """Создание панели с кнопками."""
        button_layout = QHBoxLayout()

        # Создаем кнопки с иконками (если есть ресурсы)
        self.add_btn = QPushButton("➕ Добавить")
        self.edit_btn = QPushButton("✏️ Изменить")
        self.delete_btn = QPushButton("🗑️ Удалить")
        self.test_btn = QPushButton("🔌 Проверить подключение")

        # Подключаем сигналы
        self.add_btn.clicked.connect(self._add_account)
        self.edit_btn.clicked.connect(self._edit_account)
        self.delete_btn.clicked.connect(self._delete_account)
        self.test_btn.clicked.connect(self._test_connection)

        # Добавляем кнопки в макет
        for btn in [self.add_btn, self.edit_btn, self.delete_btn,
                    self.test_btn]:
            button_layout.addWidget(btn)

        button_layout.addStretch()
        return button_layout

    def _setup_signals(self):
        """Настройка дополнительных сигналов."""
        self.table.itemSelectionChanged.connect(self._update_buttons_state)

    def _update_buttons_state(self):
        """Обновление состояния кнопок в зависимости от выделения."""
        has_selection = bool(self.table.currentRow() >= 0)
        self.edit_btn.setEnabled(has_selection and not self._loading)
        self.delete_btn.setEnabled(has_selection and not self._loading)
        self.test_btn.setEnabled(has_selection and not self._loading)

    @contextmanager
    def _loading_state(self):
        """Контекстный менеджер для состояния загрузки."""
        self._loading = True
        self._update_buttons_state()
        self.overlay.show()
        QApplication.processEvents()
        try:
            yield
        finally:
            self._loading = False
            self._update_buttons_state()
            self.overlay.hide()

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
        self.table.setSortingEnabled(
            False)  # Отключаем сортировку на время обновления
        self.table.setRowCount(len(self.accounts))

        for i, account in enumerate(self.accounts):
            self._set_table_row(i, account)

        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
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

    def _get_selected_account(self) -> Optional[Account]:
        """Получение выбранного аккаунта."""
        row = self.table.currentRow()
        if 0 <= row < len(self.accounts):
            return self.accounts[row]
        return None

    def _add_account(self):
        """Добавление нового аккаунта."""
        dialog = AccountEditDialog(self.config, self)
        if dialog.exec_() == QDialog.Accepted:
            account = dialog.get_account()
            if account:
                account.id = str(uuid.uuid4())
                self.accounts.append(account)
                self._refresh_table()
                self.accountsChanged.emit()

    def _edit_account(self):
        """Редактирование выбранного аккаунта."""
        account = self._get_selected_account()
        if not account:
            self._show_warning("Выберите аккаунт для редактирования")
            return

        dialog = AccountEditDialog(self.config, self, account)
        if dialog.exec_() == QDialog.Accepted:
            updated = dialog.get_account()
            if updated:
                # Обновляем все поля
                for key, value in updated.__dict__.items():
                    setattr(account, key, value)
                self._refresh_table()
                self.accountsChanged.emit()

    def _delete_account(self):
        """Удаление выбранного аккаунта."""
        account = self._get_selected_account()
        if not account:
            self._show_warning("Выберите аккаунт для удаления")
            return

        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить аккаунт '{account.name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.accounts.remove(account)
            self._refresh_table()
            self.accountsChanged.emit()

    # В файле ui/accounts_dialog.py замените метод _test_connection на:

    def _test_connection(self):
        """Проверка подключения к выбранному аккаунту."""
        account = self._get_selected_account()
        if not account:
            self._show_warning("Выберите аккаунт для проверки")
            return

        with self._loading_state():
            try:
                # Расшифровываем пароль
                password = self.config.decrypt_password(account.password)

                # Импортируем функцию проверки
                from core.webdav_client import test_webdav_connection

                # Проверяем подключение
                success, message = test_webdav_connection(
                    account.url,
                    account.login,
                    password
                )

                if success:
                    self._show_info("Успех", message)
                else:
                    self._show_warning(message)

            except ImportError:
                # Fallback если модуль не создан - используем прямую проверку
                self._test_connection_simple(account)
            except Exception as e:
                self._show_error("Ошибка подключения", e)

    def _test_connection_simple(self, account):
        """Простая проверка подключения (резервный вариант)."""
        try:
            password = self.config.decrypt_password(account.password)
            import requests
            from requests.auth import HTTPBasicAuth

            url = account.url.rstrip('/') + '/'
            response = requests.get(
                url,
                auth=HTTPBasicAuth(account.login, password),
                timeout=10,
                allow_redirects=True
            )

            if response.status_code in (200, 201, 207, 301, 302):
                self._show_info("Успех", "Подключение успешно!")
            else:
                self._show_warning(
                    f"Ошибка подключения: HTTP {response.status_code}")

        except requests.ConnectionError:
            self._show_warning("Не удалось подключиться к серверу")
        except requests.Timeout:
            self._show_warning("Превышено время ожидания")
        except Exception as e:
            self._show_error("Ошибка подключения", e)
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

    # Вспомогательные методы для показа сообщений
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

    # Типы аккаунтов с подсказками
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
        self.resize(500, 450)
        self.setModal(True)

        self._setup_ui()
        self._setup_validators()
        self._load_account_data()
        self._setup_signals()

    def _setup_ui(self):
        """Настройка пользовательского интерфейса."""
        layout = QVBoxLayout(self)

        # Создаем форму
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form_layout.setLabelAlignment(Qt.AlignRight)

        # Поле имени
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: Мой Яндекс.Диск")
        self.name_edit.setMaxLength(100)
        form_layout.addRow("Имя аккаунта:*", self.name_edit)

        # Поле типа
        self.type_combo = QComboBox()
        for value, label in self.ACCOUNT_TYPES.items():
            self.type_combo.addItem(label, value)
        form_layout.addRow("Тип:", self.type_combo)

        # Поле URL
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://webdav.yandex.ru")
        form_layout.addRow("URL сервера:*", self.url_edit)

        # Поле логина
        self.login_edit = QLineEdit()
        self.login_edit.setPlaceholderText("Логин или email")
        form_layout.addRow("Логин:*", self.login_edit)

        # Поле пароля
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("Пароль")
        form_layout.addRow("Пароль:*", self.password_edit)

        # Чекбокс показа пароля
        self.show_password_check = QCheckBox("Показать пароль")
        form_layout.addRow("", self.show_password_check)

        # Поле пути
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("/ (корневая директория)")
        form_layout.addRow("Путь по умолчанию:", self.path_edit)

        # Чекбокс активности
        self.enabled_check = QCheckBox("Аккаунт активен")
        self.enabled_check.setChecked(True)
        form_layout.addRow("", self.enabled_check)

        layout.addWidget(form_widget)

        # Добавляем подсказку о обязательных полях
        hint_label = QLabel("* обязательные поля")
        hint_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(hint_label)

        # Кнопки диалога
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _setup_validators(self):
        """Настройка валидаторов для полей ввода."""
        # Здесь можно добавить валидаторы, например, для URL
        pass

    def _setup_signals(self):
        """Настройка сигналов."""
        self.show_password_check.stateChanged.connect(
            self._toggle_password_visibility)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)

    def _toggle_password_visibility(self, state):
        """Переключение видимости пароля."""
        self.password_edit.setEchoMode(
            QLineEdit.Normal if state == Qt.Checked else QLineEdit.Password
        )

    def _on_type_changed(self, index):
        """Обработка смены типа аккаунта."""
        account_type = self.type_combo.currentData()

        # Автоподстановка URL для известных сервисов
        urls = {
            "yandex": "https://webdav.yandex.ru",
            "mailru": "https://webdav.cloud.mail.ru",
        }

        if account_type in urls and not self.url_edit.text():
            self.url_edit.setText(urls[account_type])

    def _load_account_data(self):
        """Загрузка данных аккаунта в форму."""
        if not self.account:
            return

        self.name_edit.setText(self.account.name)

        # Устанавливаем тип аккаунта
        index = self.type_combo.findData(self.account.type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)

        self.url_edit.setText(self.account.url)
        self.login_edit.setText(self.account.login)

        # Расшифровываем пароль
        try:
            decrypted = self.config.decrypt_password(self.account.password)
            self.password_edit.setText(decrypted)
        except Exception as e:
            logger.warning(f"Could not decrypt password: {e}")

        self.path_edit.setText(self.account.default_path or "/")
        self.enabled_check.setChecked(self.account.enabled)

    def _validate_and_accept(self):
        """Валидация полей и принятие диалога."""
        # Проверка обязательных полей
        errors = []

        if not self.name_edit.text().strip():
            errors.append("Введите имя аккаунта")

        if not self.url_edit.text().strip():
            errors.append("Введите URL сервера")
        elif not self._is_valid_url(self.url_edit.text().strip()):
            errors.append(
                "Введите корректный URL (начинается с http:// или https://)")

        if not self.login_edit.text().strip():
            errors.append("Введите логин")

        if not self.password_edit.text().strip() and not self.account:
            errors.append("Введите пароль")

        if errors:
            QMessageBox.warning(self, "Ошибка валидации",
                                "\n".join(errors))
            return

        # Сохраняем аккаунт
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

        # Шифруем пароль только если он изменился
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
            # Сохраняем значение, а не текст
            url=self.url_edit.text().strip().rstrip('/'),
            login=self.login_edit.text().strip(),
            password=encrypted_password,
            default_path=self.path_edit.text().strip() or '/',
            enabled=self.enabled_check.isChecked()
        )

    def get_account(self) -> Optional[Account]:
        """Получение созданного/отредактированного аккаунта."""
        return self.result_account