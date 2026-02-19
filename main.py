# main.py
"""Main entry point for WebDAV Manager."""
import logging
import sys
import os
from pathlib import Path

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QPalette, QColor, QIcon
from PyQt5.QtCore import Qt

from core.config import ConfigManager
from core.master_key import MasterKeyManager
from ui.main_window import MainWindow
from ui.login_dialog import LoginDialog
from utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


def get_base_dir() -> Path:
    """Get base directory of the application."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).parent


def get_icon_path(icon_name: str) -> str:
    """Get full path to an icon file."""
    base_dir = get_base_dir()

    # Проверяем несколько возможных расположений папки icons
    possible_paths = [
        base_dir / 'icons' / icon_name,
        base_dir.parent / 'icons' / icon_name,
        Path(__file__).parent / 'icons' / icon_name,
        Path(__file__).parent.parent / 'icons' / icon_name
    ]

    for path in possible_paths:
        if path.exists():
            logger.info(f"Icon found: {path}")
            return str(path)

    logger.warning(f"Icon not found: {icon_name}")
    return ""


def apply_dark_theme(app: QApplication):
    """Apply dark theme to application."""
    app.setStyle('Fusion')

    palette = QPalette()

    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)

    app.setPalette(palette)


def apply_light_theme(app: QApplication):
    """Apply light theme to application."""
    app.setStyle('Fusion')

    palette = QPalette()
    palette.setColor(QPalette.Window, Qt.white)
    palette.setColor(QPalette.WindowText, Qt.black)
    palette.setColor(QPalette.Base, QColor(240, 240, 240))
    palette.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.black)
    palette.setColor(QPalette.Text, Qt.black)
    palette.setColor(QPalette.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ButtonText, Qt.black)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(0, 0, 255))
    palette.setColor(QPalette.Highlight, QColor(51, 153, 255))
    palette.setColor(QPalette.HighlightedText, Qt.white)

    app.setPalette(palette)


def main():
    """Main application entry point."""
    base_dir = get_base_dir()

    # Initialize configuration
    config = ConfigManager()

    # Setup logging
    log_dir = base_dir / 'logs'
    log_dir.mkdir(exist_ok=True)

    setup_logging(
        log_dir=str(log_dir),
        log_file="webdav_manager.log",
        level=config.get_setting("log_level", "INFO"),
        console=True
    )

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("WebDAV Manager")
    app.setOrganizationName("WebDAVManager")

    # Set application icon
    icon_path = get_icon_path('app.ico')
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    # Apply theme
    theme = config.get_setting("theme", "dark")
    if theme == "dark":
        apply_dark_theme(app)
    elif theme == "light":
        apply_light_theme(app)

    # Initialize master key manager
    config_dir = os.path.join(os.path.expanduser("~"), ".webdav_manager")
    master_key_manager = MasterKeyManager(config_dir)

    # Show login dialog
    login_dialog = LoginDialog(master_key_manager)

    # Если пользователь закрыл диалог или не прошел аутентификацию
    if login_dialog.exec_() != LoginDialog.Accepted:
        logger.info("Login cancelled or failed, exiting application")
        sys.exit(0)

    # Create and show main window
    window = MainWindow(config)
    window.show()

    # Run application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()