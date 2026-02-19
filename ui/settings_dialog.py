# ui/settings_dialog.py
"""Settings dialog for WebDAV Manager."""

import logging
import os
from typing import Dict, Any

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget,
                             QFormLayout, QCheckBox, QSpinBox, QLineEdit,
                             QPushButton, QComboBox, QFileDialog, QGroupBox,
                             QHBoxLayout, QMessageBox, QLabel)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QApplication

from core.config import ConfigManager
from utils.theme_helper import change_theme

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Dialog for application settings."""

    settingsChanged = pyqtSignal()

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)

        self.config = config
        self.theme_changed = False

        self.setWindowTitle("Настройки")
        self.resize(600, 600)

        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)

        # Create tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.general_tab = self._create_general_tab()
        self.paths_tab = self._create_paths_tab()
        self.appearance_tab = self._create_appearance_tab()
        self.network_tab = self._create_network_tab()
        self.advanced_tab = self._create_advanced_tab()

        self.tabs.addTab(self.general_tab, "Общие")
        self.tabs.addTab(self.paths_tab, "Пути")
        self.tabs.addTab(self.appearance_tab, "Внешний вид")
        self.tabs.addTab(self.network_tab, "Сеть")
        self.tabs.addTab(self.advanced_tab, "Дополнительно")

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)

        self.apply_button = QPushButton("Применить")
        self.apply_button.clicked.connect(self._apply_settings)
        button_layout.addWidget(self.apply_button)

        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def _create_general_tab(self) -> QWidget:
        """Create general settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form_layout = QFormLayout()

        # Auto-connect
        self.auto_connect_check = QCheckBox(
            "Автоматически подключаться при выборе аккаунта")
        form_layout.addRow(self.auto_connect_check)

        # Confirm on exit
        self.confirm_exit_check = QCheckBox("Подтверждать выход из программы")
        form_layout.addRow(self.confirm_exit_check)

        # Auto-refresh
        self.auto_refresh_check = QCheckBox(
            "Автоматически обновлять содержимое папок")
        form_layout.addRow(self.auto_refresh_check)

        # Refresh interval
        self.refresh_interval_spin = QSpinBox()
        self.refresh_interval_spin.setSuffix(" сек")
        self.refresh_interval_spin.setRange(5, 3600)
        self.refresh_interval_spin.setSingleStep(5)
        form_layout.addRow("Интервал обновления:", self.refresh_interval_spin)

        # Show hidden files
        self.show_hidden_check = QCheckBox("Показывать скрытые файлы")
        form_layout.addRow(self.show_hidden_check)

        layout.addLayout(form_layout)
        layout.addStretch()

        return widget

    def _create_paths_tab(self) -> QWidget:
        """Create paths settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form_layout = QFormLayout()

        # Download folder
        download_layout = QHBoxLayout()
        self.download_path_edit = QLineEdit()
        self.download_path_edit.setReadOnly(True)
        download_browse = QPushButton("Обзор...")
        download_browse.clicked.connect(
            lambda: self._browse_path(self.download_path_edit))
        download_layout.addWidget(self.download_path_edit)
        download_layout.addWidget(download_browse)
        form_layout.addRow("Папка для загрузок:", download_layout)

        # Temp folder
        temp_layout = QHBoxLayout()
        self.temp_path_edit = QLineEdit()
        self.temp_path_edit.setReadOnly(True)
        temp_browse = QPushButton("Обзор...")
        temp_browse.clicked.connect(
            lambda: self._browse_path(self.temp_path_edit))
        temp_layout.addWidget(self.temp_path_edit)
        temp_layout.addWidget(temp_browse)
        form_layout.addRow("Временная папка:", temp_layout)

        # Clean temp on exit
        self.clean_temp_check = QCheckBox("Очищать временную папку при выходе")
        form_layout.addRow(self.clean_temp_check)

        layout.addLayout(form_layout)
        layout.addStretch()

        return widget

    def _create_appearance_tab(self) -> QWidget:
        """Create appearance settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form_layout = QFormLayout()

        # Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Тёмная", "dark")
        self.theme_combo.addItem("Светлая", "light")
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        form_layout.addRow("Тема оформления:", self.theme_combo)

        # Language
        self.language_combo = QComboBox()
        self.language_combo.addItem("Русский", "ru")
        self.language_combo.addItem("English", "en")
        form_layout.addRow("Язык интерфейса:", self.language_combo)

        # Font size
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setSuffix(" pt")
        form_layout.addRow("Размер шрифта:", self.font_size_spin)

        # Icons size
        self.icon_size_combo = QComboBox()
        self.icon_size_combo.addItem("Маленькие (16x16)", 16)
        self.icon_size_combo.addItem("Средние (24x24)", 24)
        self.icon_size_combo.addItem("Большие (32x32)", 32)
        form_layout.addRow("Размер иконок:", self.icon_size_combo)

        layout.addLayout(form_layout)
        layout.addStretch()

        return widget

    def _create_network_tab(self) -> QWidget:
        """Create network settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form_layout = QFormLayout()

        # Timeouts
        self.conn_timeout_spin = QSpinBox()
        self.conn_timeout_spin.setSuffix(" сек")
        self.conn_timeout_spin.setRange(5, 120)
        form_layout.addRow("Таймаут соединения:", self.conn_timeout_spin)

        self.read_timeout_spin = QSpinBox()
        self.read_timeout_spin.setSuffix(" сек")
        self.read_timeout_spin.setRange(10, 300)
        form_layout.addRow("Таймаут чтения:", self.read_timeout_spin)

        # Retry count
        self.retry_count_spin = QSpinBox()
        self.retry_count_spin.setRange(0, 10)
        self.retry_count_spin.setSuffix(" попыток")
        form_layout.addRow("Количество повторов:", self.retry_count_spin)

        # Retry delay
        self.retry_delay_spin = QSpinBox()
        self.retry_delay_spin.setSuffix(" сек")
        self.retry_delay_spin.setRange(1, 30)
        form_layout.addRow("Задержка между повторами:", self.retry_delay_spin)

        layout.addLayout(form_layout)

        # Proxy settings group
        proxy_group = QGroupBox("Прокси-сервер")
        proxy_layout = QFormLayout(proxy_group)

        self.proxy_enable_check = QCheckBox("Использовать прокси")
        proxy_layout.addRow(self.proxy_enable_check)

        self.proxy_type_combo = QComboBox()
        self.proxy_type_combo.addItem("HTTP", "http")
        self.proxy_type_combo.addItem("HTTPS", "https")
        self.proxy_type_combo.addItem("SOCKS5", "socks5")
        proxy_layout.addRow("Тип:", self.proxy_type_combo)

        self.proxy_host_edit = QLineEdit()
        self.proxy_host_edit.setPlaceholderText("proxy.example.com")
        proxy_layout.addRow("Хост:", self.proxy_host_edit)

        self.proxy_port_spin = QSpinBox()
        self.proxy_port_spin.setRange(1, 65535)
        self.proxy_port_spin.setValue(8080)
        proxy_layout.addRow("Порт:", self.proxy_port_spin)

        self.proxy_login_edit = QLineEdit()
        self.proxy_login_edit.setPlaceholderText("(опционально)")
        proxy_layout.addRow("Логин:", self.proxy_login_edit)

        self.proxy_password_edit = QLineEdit()
        self.proxy_password_edit.setEchoMode(QLineEdit.Password)
        self.proxy_password_edit.setPlaceholderText("(опционально)")
        proxy_layout.addRow("Пароль:", self.proxy_password_edit)

        layout.addWidget(proxy_group)
        layout.addStretch()

        return widget

    def _create_advanced_tab(self) -> QWidget:
        """Create advanced settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Master key settings
        master_key_group = QGroupBox("Мастер-ключ")
        master_key_layout = QVBoxLayout(master_key_group)

        master_key_info = QLabel(
            "Мастер-ключ используется для входа в приложение. "
            "Без него невозможно получить доступ к зашифрованным данным."
        )
        master_key_info.setWordWrap(True)
        master_key_layout.addWidget(master_key_info)

        master_key_buttons = QHBoxLayout()

        self.change_password_btn = QPushButton("Изменить мастер-пароль")
        self.change_password_btn.clicked.connect(self._change_master_password)
        master_key_buttons.addWidget(self.change_password_btn)

        self.backup_key_btn = QPushButton("Создать резервную копию")
        self.backup_key_btn.clicked.connect(self._backup_master_key)
        master_key_buttons.addWidget(self.backup_key_btn)

        master_key_layout.addLayout(master_key_buttons)

        # Добавляем кнопку восстановления
        restore_layout = QHBoxLayout()
        self.restore_key_btn = QPushButton("Восстановить из резервной копии")
        self.restore_key_btn.clicked.connect(self._restore_master_key)
        restore_layout.addWidget(self.restore_key_btn)

        master_key_layout.addLayout(restore_layout)

        # Добавляем предупреждение
        warning_label = QLabel(
            "⚠️ Внимание! Восстановление ключа перезапишет текущий мастер-ключ.\n"
            "Используйте эту функцию только если вы забыли пароль."
        )
        warning_label.setWordWrap(True)
        master_key_layout.addWidget(warning_label)

        layout.addWidget(master_key_group)

        # Encryption settings
        encryption_group = QGroupBox("Шифрование файлов")
        encryption_layout = QFormLayout(encryption_group)

        self.encryption_enable_check = QCheckBox(
            "Включить режим шифрования (глобально)")
        encryption_layout.addRow(self.encryption_enable_check)

        self.encryption_delete_original_check = QCheckBox(
            "Удалять исходные файлы после шифрования")
        encryption_layout.addRow(self.encryption_delete_original_check)

        info_label = QLabel(
            "⚠️ Включение шифрования в настройках автоматически активирует "
            "соответствующий пункт в меню Настройки → Шифрование"
        )
        info_label.setWordWrap(True)
        encryption_layout.addRow(info_label)

        layout.addWidget(encryption_group)

        # Cache settings
        cache_group = QGroupBox("Кэширование")
        cache_layout = QFormLayout(cache_group)

        self.cache_enable_check = QCheckBox("Использовать кэширование")
        cache_layout.addRow(self.cache_enable_check)

        self.cache_ttl_spin = QSpinBox()
        self.cache_ttl_spin.setSuffix(" сек")
        self.cache_ttl_spin.setRange(10, 3600)
        self.cache_ttl_spin.setSingleStep(10)
        cache_layout.addRow("Время жизни кэша:", self.cache_ttl_spin)

        self.cache_size_spin = QSpinBox()
        self.cache_size_spin.setSuffix(" элементов")
        self.cache_size_spin.setRange(10, 1000)
        self.cache_size_spin.setSingleStep(10)
        cache_layout.addRow("Макс. размер кэша:", self.cache_size_spin)

        layout.addWidget(cache_group)

        # Logging settings
        logging_group = QGroupBox("Логирование")
        logging_layout = QFormLayout(logging_group)

        self.logging_enable_check = QCheckBox("Вести логирование")
        logging_layout.addRow(self.logging_enable_check)

        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        logging_layout.addRow("Уровень логирования:", self.log_level_combo)

        layout.addWidget(logging_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.clear_cache_btn = QPushButton("Очистить кэш")
        self.clear_cache_btn.clicked.connect(self._clear_cache)
        button_layout.addWidget(self.clear_cache_btn)

        self.reset_settings_btn = QPushButton("Сбросить настройки")
        self.reset_settings_btn.clicked.connect(self._reset_settings)
        button_layout.addWidget(self.reset_settings_btn)

        layout.addLayout(button_layout)
        layout.addStretch()

        return widget

    def _browse_path(self, line_edit: QLineEdit):
        """Browse for directory and update line edit."""
        path = QFileDialog.getExistingDirectory(
            self, "Выберите папку", line_edit.text()
        )
        if path:
            line_edit.setText(path)

    def _on_theme_changed(self, index: int):
        """Handle theme change."""
        self.theme_changed = True

    def _clear_cache(self):
        """Clear application cache."""
        try:
            if hasattr(self.parent(), 'client'):
                self.parent().client._cache.clear()
                QMessageBox.information(self, "Кэш", "Кэш успешно очищен")
                logger.info("Cache cleared by user")
            else:
                QMessageBox.information(self, "Кэш",
                                        "Кэш будет очищен при следующем запуске")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            QMessageBox.warning(self, "Ошибка",
                                f"Не удалось очистить кэш: {e}")

    def _change_master_password(self):
        """Open change master password dialog."""
        try:
            from ui.change_password_dialog import ChangePasswordDialog
            from core.master_key import MasterKeyManager

            logger.info("Opening change password dialog")

            config_dir = os.path.join(os.path.expanduser("~"),
                                      ".webdav_manager")
            master_key_manager = MasterKeyManager(config_dir)

            if not master_key_manager.is_initialized():
                QMessageBox.warning(
                    self,
                    "Мастер-ключ не создан",
                    "Мастер-ключ еще не создан. Он будет создан при первом входе в приложение."
                )
                return

            dialog = ChangePasswordDialog(master_key_manager, self)
            if dialog.exec_():
                QMessageBox.information(self, "Успех",
                                        "Мастер-пароль успешно изменен")

        except Exception as e:
            logger.error(f"Error in change password dialog: {e}")
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Произошла ошибка при открытии диалога смены пароля:\n{str(e)}"
            )

    def _backup_master_key(self):
        """Create backup of master key."""
        from PyQt5.QtWidgets import QFileDialog
        import shutil

        config_dir = os.path.join(os.path.expanduser("~"), ".webdav_manager")
        master_key_file = os.path.join(config_dir, '.master_key.bin')

        if not os.path.exists(master_key_file):
            QMessageBox.warning(
                self,
                "Мастер-ключ не найден",
                "Мастер-ключ еще не создан. Он будет создан при первом входе в приложение."
            )
            return

        backup_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить резервную копию мастер-ключа",
            os.path.expanduser("~/master_key_backup.bin"),
            "Binary files (*.bin)"
        )

        if backup_path:
            try:
                shutil.copy2(master_key_file, backup_path)
                QMessageBox.information(
                    self,
                    "Успех",
                    f"Резервная копия сохранена:\n{backup_path}"
                )
                logger.info(f"Master key backup created: {backup_path}")
            except Exception as e:
                logger.error(f"Failed to create backup: {e}")
                QMessageBox.critical(self, "Ошибка",
                                     f"Не удалось создать резервную копию: {e}")

    def _restore_master_key(self):
        """Open restore master key dialog."""
        try:
            from ui.restore_dialog import RestoreDialog
            from core.master_key import MasterKeyManager

            config_dir = os.path.join(os.path.expanduser("~"),
                                      ".webdav_manager")
            master_key_manager = MasterKeyManager(config_dir)

            dialog = RestoreDialog(master_key_manager, self)
            if dialog.exec_():
                QMessageBox.information(
                    self,
                    "Ключ восстановлен",
                    "Мастер-ключ успешно восстановлен.\n"
                    "Приложение будет закрыто. Запустите его снова и войдите с новым паролем."
                )
                if self.parent():
                    self.parent().close()

        except Exception as e:
            logger.error(f"Error in restore dialog: {e}")
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Произошла ошибка при открытии диалога восстановления:\n{str(e)}"
            )

    def _reset_settings(self):
        """Reset settings to defaults."""
        reply = QMessageBox.question(
            self,
            "Сброс настроек",
            "Сбросить все настройки к значениям по умолчанию?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Reset to defaults
            self.auto_connect_check.setChecked(False)
            self.confirm_exit_check.setChecked(True)
            self.auto_refresh_check.setChecked(True)
            self.refresh_interval_spin.setValue(30)
            self.show_hidden_check.setChecked(False)

            self.download_path_edit.setText("")
            self.temp_path_edit.setText("")
            self.clean_temp_check.setChecked(False)

            self.theme_combo.setCurrentIndex(0)  # Dark theme
            self.language_combo.setCurrentIndex(0)  # Russian
            self.font_size_spin.setValue(9)
            self.icon_size_combo.setCurrentIndex(0)  # 16x16

            self.conn_timeout_spin.setValue(30)
            self.read_timeout_spin.setValue(60)
            self.retry_count_spin.setValue(3)
            self.retry_delay_spin.setValue(2)

            self.proxy_enable_check.setChecked(False)

            # Advanced
            self.encryption_enable_check.setChecked(False)
            self.encryption_delete_original_check.setChecked(False)
            self.cache_enable_check.setChecked(True)
            self.cache_ttl_spin.setValue(300)
            self.cache_size_spin.setValue(100)
            self.logging_enable_check.setChecked(True)
            self.log_level_combo.setCurrentIndex(1)  # INFO

            logger.info("Settings reset to defaults")

    def _load_settings(self):
        """Load settings from config."""
        settings = self.config.settings

        # General
        self.auto_connect_check.setChecked(settings.get("auto_connect", False))
        self.confirm_exit_check.setChecked(
            settings.get("confirm_on_exit", True))
        self.auto_refresh_check.setChecked(settings.get("auto_refresh", True))
        self.refresh_interval_spin.setValue(
            settings.get("refresh_interval", 30))
        self.show_hidden_check.setChecked(settings.get("show_hidden", False))

        # Paths
        self.download_path_edit.setText(settings.get("download_folder", ""))
        self.temp_path_edit.setText(settings.get("temp_folder", ""))
        self.clean_temp_check.setChecked(settings.get("clean_temp", False))

        # Appearance
        theme = settings.get("theme", "dark")
        index = self.theme_combo.findData(theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)

        lang = settings.get("language", "ru")
        index = self.language_combo.findData(lang)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)

        self.font_size_spin.setValue(settings.get("font_size", 9))

        icon_size = settings.get("icon_size", 16)
        index = self.icon_size_combo.findData(icon_size)
        if index >= 0:
            self.icon_size_combo.setCurrentIndex(index)

        # Network
        self.conn_timeout_spin.setValue(settings.get("connection_timeout", 30))
        self.read_timeout_spin.setValue(settings.get("read_timeout", 60))
        self.retry_count_spin.setValue(settings.get("retry_count", 3))
        self.retry_delay_spin.setValue(settings.get("retry_delay", 2))

        self.proxy_enable_check.setChecked(
            settings.get("proxy_enabled", False))

        proxy_type = settings.get("proxy_type", "http")
        index = self.proxy_type_combo.findData(proxy_type)
        if index >= 0:
            self.proxy_type_combo.setCurrentIndex(index)

        self.proxy_host_edit.setText(settings.get("proxy_host", ""))
        self.proxy_port_spin.setValue(settings.get("proxy_port", 8080))
        self.proxy_login_edit.setText(settings.get("proxy_login", ""))
        self.proxy_password_edit.setText(settings.get("proxy_password", ""))

        # Advanced
        self.encryption_enable_check.setChecked(
            settings.get("encryption_enabled", False))
        self.encryption_delete_original_check.setChecked(
            settings.get("encryption_delete_original", False))
        self.cache_enable_check.setChecked(settings.get("cache_enabled", True))
        self.cache_ttl_spin.setValue(settings.get("cache_ttl", 300))
        self.cache_size_spin.setValue(settings.get("cache_size", 100))
        self.logging_enable_check.setChecked(
            settings.get("logs_enabled", True))

        log_level = settings.get("log_level", "INFO")
        index = self.log_level_combo.findText(log_level)
        if index >= 0:
            self.log_level_combo.setCurrentIndex(index)

    def _apply_settings(self):
        """Apply settings to config."""
        try:
            settings = self.config.settings

            # General
            settings["auto_connect"] = self.auto_connect_check.isChecked()
            settings["confirm_on_exit"] = self.confirm_exit_check.isChecked()
            settings["auto_refresh"] = self.auto_refresh_check.isChecked()
            settings["refresh_interval"] = self.refresh_interval_spin.value()
            settings["show_hidden"] = self.show_hidden_check.isChecked()

            # Paths
            settings["download_folder"] = self.download_path_edit.text()
            settings["temp_folder"] = self.temp_path_edit.text()
            settings["clean_temp"] = self.clean_temp_check.isChecked()

            # Appearance
            old_theme = settings.get("theme", "dark")
            new_theme = self.theme_combo.currentData()
            if old_theme != new_theme:
                self.theme_changed = True

            settings["theme"] = new_theme
            settings["language"] = self.language_combo.currentData()
            settings["font_size"] = self.font_size_spin.value()
            settings["icon_size"] = self.icon_size_combo.currentData()

            # Network
            settings["connection_timeout"] = self.conn_timeout_spin.value()
            settings["read_timeout"] = self.read_timeout_spin.value()
            settings["retry_count"] = self.retry_count_spin.value()
            settings["retry_delay"] = self.retry_delay_spin.value()

            settings["proxy_enabled"] = self.proxy_enable_check.isChecked()
            settings["proxy_type"] = self.proxy_type_combo.currentData()
            settings["proxy_host"] = self.proxy_host_edit.text()
            settings["proxy_port"] = self.proxy_port_spin.value()
            settings["proxy_login"] = self.proxy_login_edit.text()
            settings["proxy_password"] = self.proxy_password_edit.text()

            # Advanced
            settings["encryption_enabled"] = self.encryption_enable_check.isChecked()
            settings["encryption_delete_original"] = self.encryption_delete_original_check.isChecked()
            settings["cache_enabled"] = self.cache_enable_check.isChecked()
            settings["cache_ttl"] = self.cache_ttl_spin.value()
            settings["cache_size"] = self.cache_size_spin.value()
            settings["logs_enabled"] = self.logging_enable_check.isChecked()
            settings["log_level"] = self.log_level_combo.currentText()

            # Save to file
            self.config.save_config()

            # Если тема изменилась, применяем глобально
            if self.theme_changed:
                change_theme(QApplication.instance(), new_theme)
                logger.info(f"Theme changed from {old_theme} to {new_theme}")

            logger.info("Settings saved successfully")
            self.settingsChanged.emit()

        except Exception as e:
            logger.exception("Error saving settings")
            QMessageBox.critical(self, "Ошибка",
                                 f"Не удалось сохранить настройки: {e}")

    def accept(self):
        """Save settings and close dialog."""
        self._apply_settings()
        super().accept()