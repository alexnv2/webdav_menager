# ui/key_dialog.py
"""Key management dialog."""

import json
import logging

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QPushButton, QHeaderView,
                             QMessageBox, QLineEdit, QFormLayout,
                             QDialogButtonBox, QTextEdit, QLabel)

from core.encryption import FileEncryptor
from core.key_manager import KeyManager

logger = logging.getLogger(__name__)


class KeyDialog(QDialog):
    def __init__(self, key_manager: KeyManager, parent=None):
        super().__init__(parent)
        self.key_manager = key_manager
        self.setWindowTitle("Управление ключами шифрования")
        self.resize(800, 400)

        self._setup_ui()
        self._load_keys()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Имя", "ID", "Создан", "Тип"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        button_layout = QHBoxLayout()
        self.new_random_btn = QPushButton("Случайный ключ")
        self.new_random_btn.clicked.connect(self._create_random_key)
        button_layout.addWidget(self.new_random_btn)

        self.new_password_btn = QPushButton("Из пароля")
        self.new_password_btn.clicked.connect(self._create_password_key)
        button_layout.addWidget(self.new_password_btn)

        self.export_btn = QPushButton("Экспорт")
        self.export_btn.clicked.connect(self._export_key)
        button_layout.addWidget(self.export_btn)

        self.import_btn = QPushButton("Импорт")
        self.import_btn.clicked.connect(self._import_key)
        button_layout.addWidget(self.import_btn)

        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.clicked.connect(self._delete_key)
        button_layout.addWidget(self.delete_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Close)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _load_keys(self):
        keys = self.key_manager.get_all_keys()
        self.table.setRowCount(len(keys))
        for i, (key_id, key_info) in enumerate(keys.items()):
            self.table.setItem(i, 0, QTableWidgetItem(key_info.get('name', 'Без имени')))
            self.table.setItem(i, 1, QTableWidgetItem(key_id[:8]))
            created = key_info.get('created', 'Неизвестно')
            if len(created) > 10:
                created = created[:10]
            self.table.setItem(i, 2, QTableWidgetItem(created))
            key_type = "Пароль" if key_info.get('password_derived') else "Случайный"
            self.table.setItem(i, 3, QTableWidgetItem(key_type))

    def _create_random_key(self):
        name, ok = QLineEdit.getText(self, "Имя ключа", "Введите имя для ключа:")
        if ok and name:
            encryptor = FileEncryptor.create_random(name)
            self.key_manager.save_key(encryptor.key.to_dict())
            self._load_keys()
            QMessageBox.information(self, "Успех", f"Ключ создан!\nID: {encryptor.key.id[:8]}")

    def _create_password_key(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Создание ключа из пароля")
        layout = QFormLayout(dialog)

        name_edit = QLineEdit()
        layout.addRow("Имя ключа:", name_edit)

        password_edit = QLineEdit()
        password_edit.setEchoMode(QLineEdit.Password)
        layout.addRow("Пароль:", password_edit)

        confirm_edit = QLineEdit()
        confirm_edit.setEchoMode(QLineEdit.Password)
        layout.addRow("Подтверждение:", confirm_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec_():
            name = name_edit.text().strip()
            password = password_edit.text()
            confirm = confirm_edit.text()
            if not name or not password:
                QMessageBox.warning(self, "Ошибка", "Заполните все поля")
                return
            if password != confirm:
                QMessageBox.warning(self, "Ошибка", "Пароли не совпадают")
                return
            encryptor = FileEncryptor.create_from_password(password, name)
            self.key_manager.save_key(encryptor.key.to_dict())
            self._load_keys()
            QMessageBox.information(self, "Успех", f"Ключ создан!\nID: {encryptor.key.id[:8]}")

    def _export_key(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите ключ для экспорта")
            return
        key_id = list(self.key_manager.get_all_keys().keys())[row]
        key_data = self.key_manager.export_key(key_id)
        if key_data:
            dialog = QDialog(self)
            dialog.setWindowTitle("Экспорт ключа")
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel("Ключ (скопируйте и сохраните в "
                                    "безопасном месте):"))
            text_edit = QTextEdit()
            text_edit.setPlainText(json.dumps(key_data, indent=2))
            text_edit.setReadOnly(True)
            layout.addWidget(text_edit)
            layout.addWidget(QLabel("Внимание! Ключ виден на экране. "
                                    "Закройте диалог после копирования."))
            buttons = QDialogButtonBox(QDialogButtonBox.Close)
            buttons.rejected.connect(dialog.accept)
            layout.addWidget(buttons)
            QTimer.singleShot(30000, dialog.accept)
            dialog.exec_()

    def _import_key(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Импорт ключа")
        dialog.resize(600, 400)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Вставьте JSON ключа:"))
        text_edit = QTextEdit()
        layout.addWidget(text_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec_():
            try:
                key_data = json.loads(text_edit.toPlainText())
                key_id = self.key_manager.import_key(key_data)
                if key_id:
                    self._load_keys()
                    QMessageBox.information(self, "Успех", f"Ключ импортирован!\nID: {key_id[:8]}")
                else:
                    QMessageBox.warning(self, "Ошибка", "Не удалось импортировать ключ")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Неверный формат данных: {e}")

    def _delete_key(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите ключ для удаления")
            return
        keys = self.key_manager.get_all_keys()
        key_id = list(keys.keys())[row]
        key_name = keys[key_id].get('name', 'Без имени')
        reply = QMessageBox.question(self, "Подтверждение",
            f"Удалить ключ '{key_name}'?\nЗашифрованные файлы будет невозможно расшифровать без этого ключа!",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.key_manager.delete_key(key_id):
                self._load_keys()
                QMessageBox.information(self, "Успех", "Ключ удален")