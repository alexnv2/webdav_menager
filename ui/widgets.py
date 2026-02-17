# ui/widgets.py
"""Common widgets for WebDAV Manager UI."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLabel,
                             QDialogButtonBox, QProgressBar, QWidget,
                             QHBoxLayout, QPushButton, QLineEdit)

from utils.helpers import format_size


class PropertiesDialog(QDialog):
    """Dialog for displaying file/folder properties."""

    def __init__(self, file_info, parent=None):
        super().__init__(parent)
        self.file_info = file_info
        self.setWindowTitle("Свойства")
        self.resize(400, 300)

        self._setup_ui()
        self._populate_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Create labels
        self.name_label = QLabel()
        self.path_label = QLabel()
        self.type_label = QLabel()
        self.size_label = QLabel()
        self.modified_label = QLabel()
        self.link_label = QLabel()

        # Make labels selectable
        for label in [self.name_label, self.path_label]:
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        # Add to form
        form_layout.addRow("Имя:", self.name_label)
        form_layout.addRow("Путь:", self.path_label)
        form_layout.addRow("Тип:", self.type_label)
        form_layout.addRow("Размер:", self.size_label)
        form_layout.addRow("Дата изменения:", self.modified_label)
        form_layout.addRow("Ссылка:", self.link_label)

        layout.addLayout(form_layout)

        # Button box
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

    def _populate_data(self):
        """Populate dialog with file info."""
        info = self.file_info

        self.name_label.setText(info.get('name', ''))
        self.path_label.setText(info.get('path', ''))

        if info.get('isdir'):
            self.type_label.setText("Папка")
        elif info.get('islink'):
            self.type_label.setText("Ссылка")
        else:
            name = info.get('name', '')
            if '.' in name:
                ext = name.split('.')[-1].upper()
                self.type_label.setText(f"Файл ({ext})")
            else:
                self.type_label.setText("Файл")

        size = info.get('size', 0)
        self.size_label.setText(
            format_size(size) if not info.get('isdir') else "—")

        self.modified_label.setText(info.get('modified', ''))
        self.link_label.setText("Да" if info.get('islink') else "Нет")


class ProgressWidget(QWidget):
    """Widget for showing operation progress."""

    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)

        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.clicked.connect(self.cancelled.emit)
        self.cancel_button.setEnabled(False)

        layout.addWidget(self.progress_bar)
        layout.addWidget(self.cancel_button)

    def set_progress(self, current: int, total: int):
        """Update progress bar."""
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)
            self.progress_bar.setFormat(f"%p% ({current}/{total})")
        else:
            self.progress_bar.setValue(0)

    def set_operation(self, operation: str):
        """Set current operation name."""
        self.progress_bar.setFormat(f"{operation}: %p%")

    def set_cancel_enabled(self, enabled: bool):
        """Enable/disable cancel button."""
        self.cancel_button.setEnabled(enabled)

    def reset(self):
        """Reset progress bar."""
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")


class PathBar(QWidget):
    """Widget for displaying and editing path."""

    pathChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Путь к файлу или папке")
        self.path_edit.returnPressed.connect(self._on_path_entered)

        self.go_button = QPushButton("Перейти")
        self.go_button.clicked.connect(self._on_path_entered)

        layout.addWidget(self.path_edit)
        layout.addWidget(self.go_button)

    def set_path(self, path: str):
        """Set path text without emitting signal."""
        self.path_edit.setText(path)

    def _on_path_entered(self):
        """Emit pathChanged signal with current text."""
        path = self.path_edit.text().strip()
        if path:
            self.pathChanged.emit(path)