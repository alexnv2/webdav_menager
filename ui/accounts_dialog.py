# ui/accounts_dialog.py
"""Accounts management dialog."""

import logging
import uuid
from typing import Optional, List

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QPushButton, QHeaderView,
                             QMessageBox, QLineEdit, QFormLayout,
                             QDialogButtonBox, QComboBox, QCheckBox,
                             QWidget, QLabel, QApplication)
from PyQt5.QtCore import Qt, pyqtSignal

from core.config import ConfigManager
from core.models import Account

logger = logging.getLogger(__name__)


class AccountsDialog(QDialog):
    """Dialog for managing WebDAV accounts."""

    accountsChanged = pyqtSignal()

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self.accounts: List[Account] = []

        self.setWindowTitle("Управление аккаунтами")
        self.resize(800, 400)

        self._setup_ui()
        self._load_accounts()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)

        # Accounts table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Имя", "Тип", "URL", "Логин", "Статус"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()

        self.add_btn = QPushButton("Добавить")
        self.add_btn.clicked.connect(self._add_account)
        button_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Изменить")
        self.edit_btn.clicked.connect(self._edit_account)
        button_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.clicked.connect(self._delete_account)
        button_layout.addWidget(self.delete_btn)

        self.test_btn = QPushButton("Проверить подключение")
        self.test_btn.clicked.connect(self._test_connection)
        button_layout.addWidget(self.test_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _load_accounts(self):
        """Load accounts from config."""
        accounts_data = self.config.load_accounts()
        self.accounts = [Account.from_dict(acc) for acc in accounts_data]
        self._refresh_table()

    def _refresh_table(self):
        """Refresh table with current accounts."""
        self.table.setRowCount(len(self.accounts))

        for i, account in enumerate(self.accounts):
            self.table.setItem(i, 0, QTableWidgetItem(account.name))
            self.table.setItem(i, 1, QTableWidgetItem(account.type))
            self.table.setItem(i, 2, QTableWidgetItem(account.url))
            self.table.setItem(i, 3, QTableWidgetItem(account.login))

            status_item = QTableWidgetItem(
                "Активен" if account.enabled else "Отключен")
            status_item.setForeground(Qt.green if account.enabled else Qt.red)
            self.table.setItem(i, 4, status_item)

        self.table.resizeColumnsToContents()

    def _get_selected_account(self) -> Optional[Account]:
        """Get currently selected account."""
        row = self.table.currentRow()
        if 0 <= row < len(self.accounts):
            return self.accounts[row]
        return None

    def _add_account(self):
        """Add new account."""
        dialog = AccountEditDialog(self.config, self)
        if dialog.exec_():
            account = dialog.get_account()
            account.id = str(uuid.uuid4())
            self.accounts.append(account)
            self._refresh_table()
            self.accountsChanged.emit()

    def _edit_account(self):
        """Edit selected account."""
        account = self._get_selected_account()
        if not account:
            QMessageBox.warning(self, "Предупреждение",
                                "Выберите аккаунт для редактирования")
            return

        dialog = AccountEditDialog(self.config, self, account)
        if dialog.exec_():
            updated = dialog.get_account()
            # Update account
            account.name = updated.name
            account.type = updated.type
            account.url = updated.url
            account.login = updated.login
            account.password = updated.password
            account.default_path = updated.default_path
            account.enabled = updated.enabled

            self._refresh_table()
            self.accountsChanged.emit()

    def _delete_account(self):
        """Delete selected account."""
        account = self._get_selected_account()
        if not account:
            QMessageBox.warning(self, "Предупреждение",
                                "Выберите аккаунт для удаления")
            return

        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Удалить аккаунт '{account.name}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.accounts.remove(account)
            self._refresh_table()
            self.accountsChanged.emit()

    def _test_connection(self):
        """Test connection for selected account."""
        account = self._get_selected_account()
        if not account:
            QMessageBox.warning(self, "Предупреждение",
                                "Выберите аккаунт для проверки")
            return

        # Show testing message
        self.test_btn.setEnabled(False)
        self.test_btn.setText("Проверка...")
        QApplication.processEvents()

        try:
            # Decrypt password
            password = self.config.decrypt_password(account.password)

            # Test connection (simplified - you might want to use a proper
            # test)
            import requests
            from requests.auth import HTTPBasicAuth

            url = account.url.rstrip('/') + '/'
            response = requests.get(
                url,
                auth=HTTPBasicAuth(account.login, password),
                timeout=10
            )

            if response.status_code in (200, 201, 207):
                QMessageBox.information(self, "Успех", "Подключение успешно!")
            else:
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    f"Ошибка подключения: HTTP {response.status_code}"
                )

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка подключения: {e}")

        finally:
            self.test_btn.setEnabled(True)
            self.test_btn.setText("Проверить подключение")

    def accept(self):
        """Save accounts and close dialog."""
        try:
            # Save accounts
            accounts_data = [acc.to_dict() for acc in self.accounts]
            self.config.save_accounts(accounts_data)
            logger.info(f"Saved {len(accounts_data)} accounts")
            super().accept()

        except Exception as e:
            logger.exception("Error saving accounts")
            QMessageBox.critical(self, "Ошибка",
                                 f"Не удалось сохранить аккаунты: {e}")


class AccountEditDialog(QDialog):
    """Dialog for editing account details."""

    def __init__(self, config: ConfigManager, parent=None,
                 account: Optional[Account] = None):
        super().__init__(parent)
        self.config = config
        self.account = account
        self.result_account: Optional[Account] = None

        self.setWindowTitle(
            "Новый аккаунт" if not account else "Редактирование аккаунта")
        self.resize(500, 400)

        self._setup_ui()
        self._load_account_data()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)

        # Form layout for inputs
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        # Account name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: Мой Яндекс.Диск")
        form_layout.addRow("Имя аккаунта:", self.name_edit)

        # Account type
        self.type_combo = QComboBox()
        self.type_combo.addItems(
            ["webdav", "yandex", "mailru", "nextcloud", "owncloud", "other"])
        form_layout.addRow("Тип:", self.type_combo)

        # URL
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://webdav.yandex.ru")
        form_layout.addRow("URL сервера:", self.url_edit)

        # Login
        self.login_edit = QLineEdit()
        self.login_edit.setPlaceholderText("Логин или email")
        form_layout.addRow("Логин:", self.login_edit)

        # Password
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("Пароль")
        form_layout.addRow("Пароль:", self.password_edit)

        # Show password checkbox
        self.show_password_check = QCheckBox("Показать пароль")
        self.show_password_check.stateChanged.connect(
            self._toggle_password_visibility)
        form_layout.addRow("", self.show_password_check)

        # Default path
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("/")
        form_layout.addRow("Путь по умолчанию:", self.path_edit)

        # Enabled
        self.enabled_check = QCheckBox("Аккаунт активен")
        self.enabled_check.setChecked(True)
        form_layout.addRow("", self.enabled_check)

        layout.addLayout(form_layout)
        layout.addStretch()

        # Button box
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self._validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _load_account_data(self):
        """Load account data into form."""
        if self.account:
            self.name_edit.setText(self.account.name)

            index = self.type_combo.findText(self.account.type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)

            self.url_edit.setText(self.account.url)
            self.login_edit.setText(self.account.login)

            # Decrypt password for editing
            try:
                decrypted = self.config.decrypt_password(self.account.password)
                self.password_edit.setText(decrypted)
            except Exception as e:
                logger.warning(f"Could not decrypt password: {e}")

            self.path_edit.setText(self.account.default_path)
            self.enabled_check.setChecked(self.account.enabled)

    def _toggle_password_visibility(self, state):
        """Toggle password visibility."""
        if state == Qt.Checked:
            self.password_edit.setEchoMode(QLineEdit.Normal)
        else:
            self.password_edit.setEchoMode(QLineEdit.Password)

    def _validate_and_accept(self):
        """Validate input and accept dialog."""
        # Validate required fields
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Введите имя аккаунта")
            return

        if not self.url_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Введите URL сервера")
            return

        if not self.login_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Введите логин")
            return

        if not self.password_edit.text().strip() and not self.account:
            QMessageBox.warning(self, "Ошибка", "Введите пароль")
            return

        # Create account object
        password = self.password_edit.text().strip()
        if password and self.account and password != self.config.decrypt_password(
                self.account.password):
            # New password entered, encrypt it
            encrypted_password = self.config.encrypt_password(password)
        elif password and not self.account:
            encrypted_password = self.config.encrypt_password(password)
        else:
            # Keep existing encrypted password
            encrypted_password = self.account.password if self.account else ""

        self.result_account = Account(
            id=self.account.id if self.account else "",
            name=self.name_edit.text().strip(),
            type=self.type_combo.currentText(),
            url=self.url_edit.text().strip().rstrip('/'),
            login=self.login_edit.text().strip(),
            password=encrypted_password,
            default_path=self.path_edit.text().strip() or '/',
            enabled=self.enabled_check.isChecked()
        )

        self.accept()

    def get_account(self) -> Account:
        """Get the created/edited account."""
        return self.result_account
