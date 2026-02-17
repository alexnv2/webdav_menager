# ui/login_dialog.py
"""Login dialog for master key authentication."""

import os
import logging
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QMessageBox,
                             QDialogButtonBox, QCheckBox, QApplication)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon, QPixmap

from core.master_key import MasterKeyManager

logger = logging.getLogger(__name__)


class LoginDialog(QDialog):
    """Dialog for master key login."""

    login_successful = pyqtSignal()

    def __init__(self, master_key_manager: MasterKeyManager, parent=None):
        super().__init__(parent)
        self.master_key_manager = master_key_manager
        self.attempts = 0
        self.max_attempts = 3
        self.locked_until = None

        self.setWindowTitle("Вход в WebDAV Manager")
        self.setFixedSize(450, 400)
        self.setWindowFlags(Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint)

        self._setup_ui()
        self._check_initialized()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Logo/Icon
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setText("🔐")
        icon_label.setStyleSheet("font-size: 64px;")
        layout.addWidget(icon_label)

        # Title
        title = QLabel("WebDAV Manager")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # Subtitle
        self.subtitle = QLabel(
            "Введите мастер-пароль для доступа к приложению")
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setStyleSheet("color: #666; margin-bottom: 20px;")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)

        # Password field
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("Мастер-пароль")
        self.password_edit.returnPressed.connect(self._try_login)
        layout.addWidget(self.password_edit)

        # Show password checkbox
        self.show_password_check = QCheckBox("Показать пароль")
        self.show_password_check.stateChanged.connect(
            self._toggle_password_visibility)
        layout.addWidget(self.show_password_check)

        # Status label
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #ff6b6b; font-size: 10pt;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()

        self.login_button = QPushButton("Войти")
        self.login_button.setDefault(True)
        self.login_button.clicked.connect(self._try_login)
        button_layout.addWidget(self.login_button)

        self.restore_button = QPushButton("Восстановить ключ")
        self.restore_button.clicked.connect(self._restore_key)
        button_layout.addWidget(self.restore_button)

        self.cancel_button = QPushButton("Выход")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        # First time setup hint
        if not self.master_key_manager.is_initialized():
            hint = QLabel(
                "👋 Первый запуск: нажмите 'Войти' для создания мастер-ключа")
            hint.setAlignment(Qt.AlignCenter)
            hint.setStyleSheet(
                "color: #4CAF50; font-size: 10pt; margin-top: 10px;")
            hint.setWordWrap(True)
            layout.addWidget(hint)

    def _check_initialized(self):
        """Check if master key is initialized."""
        if not self.master_key_manager.is_initialized():
            self.login_button.setText("Создать ключ")
            self.subtitle.setText("Создайте мастер-ключ для защиты приложения")
            self.restore_button.setEnabled(False)
            self.restore_button.setVisible(False)

    def _toggle_password_visibility(self, state):
        """Toggle password visibility."""
        if state == Qt.Checked:
            self.password_edit.setEchoMode(QLineEdit.Normal)
        else:
            self.password_edit.setEchoMode(QLineEdit.Password)

    def _try_login(self):
        """Try to login with entered password."""
        password = self.password_edit.text()

        if not password:
            self.status_label.setText("Введите пароль")
            return

        # Check if first time setup
        if not self.master_key_manager.is_initialized():
            self._create_master_key(password)
            return

        # Verify password
        if self.master_key_manager.verify_password(password):
            logger.info("Login successful")
            self.login_successful.emit()
            self.accept()
        else:
            self.attempts += 1
            remaining = self.max_attempts - self.attempts

            if remaining <= 0:
                self.status_label.setText(
                    "Превышено количество попыток. Приложение будет закрыто.")
                self.login_button.setEnabled(False)
                self.restore_button.setEnabled(False)
                self.password_edit.setEnabled(False)
                QTimer.singleShot(3000, QApplication.quit)
            else:
                self.status_label.setText(
                    f"Неверный пароль. Осталось попыток: {remaining}")
                self.password_edit.clear()
                self.password_edit.setFocus()

    def _create_master_key(self, password: str):
        """Create new master key."""
        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Создание мастер-ключа",
            "Будет создан новый мастер-ключ. Убедитесь, что вы запомните пароль!\n\n"
            f"Пароль: {password}\n\n"
            "Продолжить?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success, message = self.master_key_manager.create_master_key(
                password)
            if success:
                QMessageBox.information(
                    self,
                    "Успех",
                    "Мастер-ключ успешно создан!\n\n"
                    "Запомните пароль - он потребуется для каждого входа в приложение."
                )
                self.login_successful.emit()
                self.accept()
            else:
                QMessageBox.critical(self, "Ошибка", message)

    def _restore_key(self):
        """Open restore dialog."""
        from ui.restore_dialog import RestoreDialog

        restore_dialog = RestoreDialog(self.master_key_manager, self)
        if restore_dialog.exec_() == RestoreDialog.Accepted:
            QMessageBox.information(
                self,
                "Ключ восстановлен",
                "Мастер-ключ успешно восстановлен.\n"
                "Теперь вы можете войти с новым паролем."
            )
            # Очищаем поле пароля
            self.password_edit.clear()
            self.status_label.setText("")