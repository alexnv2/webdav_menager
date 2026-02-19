# ui/restore_dialog.py
"""Restore master key from backup dialog."""

import os
import logging
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QMessageBox,
                             QFileDialog, QCheckBox)
from PyQt5.QtCore import Qt

from core.master_key import MasterKeyManager

logger = logging.getLogger(__name__)


class RestoreDialog(QDialog):
    """Dialog for restoring master key from backup."""

    def __init__(self, master_key_manager: MasterKeyManager, parent=None):
        super().__init__(parent)
        self.master_key_manager = master_key_manager
        self.setWindowTitle("Восстановление мастер-ключа")
        self.setFixedSize(600, 600)

        self._setup_ui()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(25, 20, 25, 20)

        # Title
        title = QLabel("Восстановление мастер-ключа из резервной копии")
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #4CAF50; margin-bottom: 5px;")
        layout.addWidget(title)

        # Info
        info = QLabel(
            "Используйте этот диалог, если вы забыли мастер-пароль.\n"
            "Вам потребуется файл резервной копии мастер-ключа, который вы создали ранее."
        )
        info.setWordWrap(True)
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet("color: #666; padding: 8px; background-color: #f5f5f5; border-radius: 5px; font-size: 11px;")
        layout.addWidget(info)

        # Backup file selection
        file_label = QLabel("Файл резервной копии:")
        layout.addWidget(file_label)

        file_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Выберите файл резервной копии...")
        self.browse_btn = QPushButton("Обзор...")
        self.browse_btn.clicked.connect(self._browse_backup)
        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(self.browse_btn)
        layout.addLayout(file_layout)

        # New password
        layout.addWidget(QLabel("Новый мастер-пароль:"))
        self.new_password_edit = QLineEdit()
        self.new_password_edit.setEchoMode(QLineEdit.Password)
        self.new_password_edit.setPlaceholderText("Введите новый пароль")
        layout.addWidget(self.new_password_edit)

        # Confirm password
        layout.addWidget(QLabel("Подтверждение пароля:"))
        self.confirm_password_edit = QLineEdit()
        self.confirm_password_edit.setEchoMode(QLineEdit.Password)
        self.confirm_password_edit.setPlaceholderText("Подтвердите новый пароль")
        layout.addWidget(self.confirm_password_edit)

        # Show password checkbox
        self.show_password_check = QCheckBox("Показать пароли")
        self.show_password_check.stateChanged.connect(self._toggle_password_visibility)
        layout.addWidget(self.show_password_check)

        # Password requirements
        requirements = QLabel(
            "Требования к паролю:\n"
            "• Минимум 8 символов\n"
            "• Хотя бы одна заглавная буква\n"
            "• Хотя бы одна цифра"
        )
        requirements.setWordWrap(True)
        requirements.setStyleSheet("color: #666; font-size: 10px; padding: 6px; background-color: #f0f0f0; border-radius: 4px; margin-top: 5px;")
        layout.addWidget(requirements)

        # Warning
        warning = QLabel(
            "⚠️ Внимание! Восстановление ключа перезапишет текущий мастер-ключ.\n"
            "Убедитесь, что у вас есть резервная копия, и вы действительно хотите продолжить."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #ff6b6b; font-size: 10px; padding: 6px; background-color: #ff6b6b20; border-radius: 4px; margin-top: 8px;")
        layout.addWidget(warning)

        # Buttons
        button_layout = QHBoxLayout()
        self.restore_btn = QPushButton("Восстановить ключ")
        self.restore_btn.clicked.connect(self._restore)
        button_layout.addWidget(self.restore_btn)

        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _browse_backup(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл резервной копии мастер-ключа",
            os.path.expanduser("~"), "Backup files (*.bin);;All files (*.*)")
        if file_path:
            self.file_path_edit.setText(file_path)

    def _toggle_password_visibility(self, state):
        mode = QLineEdit.Normal if state == Qt.Checked else QLineEdit.Password
        self.new_password_edit.setEchoMode(mode)
        self.confirm_password_edit.setEchoMode(mode)

    def _validate_password(self, password: str) -> bool:
        if len(password) < 8:
            return False
        if not any(c.isupper() for c in password):
            return False
        if not any(c.isdigit() for c in password):
            return False
        return True

    def _restore(self):
        backup_file = self.file_path_edit.text().strip()
        new_password = self.new_password_edit.text()
        confirm_password = self.confirm_password_edit.text()

        if not backup_file:
            QMessageBox.warning(self, "Ошибка", "Выберите файл резервной копии")
            return
        if not os.path.exists(backup_file):
            QMessageBox.warning(self, "Ошибка", "Файл резервной копии не найден")
            return
        if not new_password:
            QMessageBox.warning(self, "Ошибка", "Введите новый пароль")
            return
        if new_password != confirm_password:
            QMessageBox.warning(self, "Ошибка", "Пароли не совпадают")
            return
        if not self._validate_password(new_password):
            QMessageBox.warning(self, "Ошибка", "Пароль не соответствует требованиям:\n• Минимум 8 символов\n• Хотя бы одна заглавная буква\n• Хотя бы одна цифра")
            return

        reply = QMessageBox.question(self, "Подтверждение",
            "Восстановление мастер-ключа перезапишет текущий ключ.\nВы уверены, что хотите продолжить?",
            QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        success, message = self.master_key_manager.restore_from_backup(backup_file, new_password)
        if success:
            QMessageBox.information(self, "Успех",
                "Мастер-ключ успешно восстановлен!\n\nТеперь вы можете войти в приложение с новым паролем.")
            self.accept()
        else:
            QMessageBox.critical(self, "Ошибка", message)