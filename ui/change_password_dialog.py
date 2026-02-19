# ui/change_password_dialog.py
"""Change master password dialog."""

import logging
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QMessageBox,
                             QDialogButtonBox, QCheckBox)
from PyQt5.QtCore import Qt

from core.master_key import MasterKeyManager

logger = logging.getLogger(__name__)


class ChangePasswordDialog(QDialog):
    """Dialog for changing master password."""

    def __init__(self, master_key_manager: MasterKeyManager, parent=None):
        super().__init__(parent)
        self.master_key_manager = master_key_manager
        self.setWindowTitle("Изменение мастер-пароля")
        self.setFixedSize(400, 300)

        self._setup_ui()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Title
        title = QLabel("Изменение мастер-пароля")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        # Current password
        layout.addWidget(QLabel("Текущий пароль:"))
        self.current_password = QLineEdit()
        self.current_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.current_password)

        # New password
        layout.addWidget(QLabel("Новый пароль:"))
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.new_password)

        # Confirm password
        layout.addWidget(QLabel("Подтверждение:"))
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.confirm_password)

        # Show passwords checkbox
        self.show_password_check = QCheckBox("Показать пароли")
        self.show_password_check.stateChanged.connect(
            self._toggle_password_visibility)
        layout.addWidget(self.show_password_check)

        # Password requirements
        requirements = QLabel(
            "Требования к паролю:\n"
            "• Минимум 8 символов\n"
            "• Хотя бы одна заглавная буква\n"
            "• Хотя бы одна цифра"
        )
        requirements.setWordWrap(True)
        layout.addWidget(requirements)

        # Buttons
        button_layout = QHBoxLayout()

        self.ok_button = QPushButton("Изменить")
        self.ok_button.clicked.connect(self._change_password)
        button_layout.addWidget(self.ok_button)

        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def _toggle_password_visibility(self, state):
        """Toggle password visibility."""
        mode = QLineEdit.Normal if state == Qt.Checked else QLineEdit.Password
        self.current_password.setEchoMode(mode)
        self.new_password.setEchoMode(mode)
        self.confirm_password.setEchoMode(mode)

    def _validate_password(self, password: str) -> bool:
        """Validate password strength."""
        if len(password) < 8:
            return False
        if not any(c.isupper() for c in password):
            return False
        if not any(c.isdigit() for c in password):
            return False
        return True

    def _change_password(self):
        """Change master password."""
        current = self.current_password.text()
        new = self.new_password.text()
        confirm = self.confirm_password.text()

        # Validate inputs
        if not current:
            QMessageBox.warning(self, "Ошибка", "Введите текущий пароль")
            return

        if not new:
            QMessageBox.warning(self, "Ошибка", "Введите новый пароль")
            return

        if new != confirm:
            QMessageBox.warning(self, "Ошибка",
                                "Новый пароль и подтверждение не совпадают")
            return

        if not self._validate_password(new):
            QMessageBox.warning(
                self,
                "Ошибка",
                "Пароль не соответствует требованиям:\n"
                "• Минимум 8 символов\n"
                "• Хотя бы одна заглавная буква\n"
                "• Хотя бы одна цифра"
            )
            return

        # Attempt to change password
        success, message = self.master_key_manager.change_password(current, new)

        if success:
            QMessageBox.information(self, "Успех", message)
            self.accept()
        else:
            QMessageBox.critical(self, "Ошибка", message)