# main.py
# !/usr/bin/env python3
"""WebDAV Manager - Main entry point."""

import sys
import os
import logging
from logging.handlers import RotatingFileHandler

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

# Сначала настраиваем пути
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Импортируем утилиты
from utils.icon_helper import get_icon_path
from utils.theme_helper import apply_global_theme
from core.config import ConfigManager, get_data_dir
from core.master_key import MasterKeyManager
from ui.login_dialog import LoginDialog

# Глобальный логгер (будет инициализирован позже)
logger = None


# Настройка логирования
def setup_logging() -> logging.Logger:
    """Setup logging configuration."""
    # Определяем корневую директорию проекта
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(base_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, 'webdav_manager.log')

    # Создаем форматтер
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Root logger
    root_logger = logging.getLogger()
    # Очищаем существующие handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_file}")
    return logger


def main():
    """Main application entry point."""
    global logger

    # Setup logging FIRST
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("Starting WebDAV Manager")
    logger.info("=" * 60)

    # Setup config directory
    config_dir = get_data_dir()
    os.makedirs(config_dir, exist_ok=True)
    logger.info(f"Config directory: {config_dir}")

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("WebDAV Manager")
    app.setOrganizationName("WebDAV Manager")

    # Set application icon
    icon_path = get_icon_path('app.ico')
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    # Load config
    config = ConfigManager(config_dir)

    # Применяем тему глобально
    from ui.theme import get_theme_stylesheet
    theme = config.get_setting("theme", "dark")
    app.setStyleSheet(get_theme_stylesheet(theme))
    logger.info(f"Applied global theme: {theme}")

    # Check if master key exists
    master_key_manager = MasterKeyManager(config_dir)

    # Проверяем наличие мастер-ключа
    is_configured = master_key_manager.is_configured()
    logger.info(f"Master key configured: {is_configured}")

    # Show login dialog if needed
    if is_configured:
        logger.info("Showing login dialog")
        login_dialog = LoginDialog(master_key_manager)

        result = login_dialog.exec_()
        logger.info(f"Login dialog result: {result}")

        if result != LoginDialog.Accepted:
            logger.info("Login cancelled")
            return 1

        logger.info("Login successful")
    else:
        logger.info("No master key configured, showing first-run dialog")
        login_dialog = LoginDialog(master_key_manager)

        result = login_dialog.exec_()
        logger.info(f"First-run dialog result: {result}")

        if result != LoginDialog.Accepted:
            logger.info("First-run cancelled")
            return 1

        logger.info("Master key created successfully")

    # Импортируем MainWindow ТОЛЬКО после успешной аутентификации
    from ui.main_window import MainWindow

    # Create and show main window
    logger.info("Creating main window")
    window = MainWindow(config)
    window.show()

    # Run application
    logger.info("Starting event loop")
    exit_code = app.exec_()
    logger.info(f"Application exited with code {exit_code}")
    logger.info("=" * 60)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())