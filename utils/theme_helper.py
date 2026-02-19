# utils/theme_helper.py
"""Helper functions for theme management."""

from PyQt5.QtWidgets import QApplication
from ui.theme import get_theme


def apply_global_theme(app, theme_name):
    """Apply theme globally to the entire application."""
    colors = get_theme(theme_name)

    # Глобальная таблица стилей для всего приложения
    app.setStyleSheet(f"""
        /* Глобальные стили для всего приложения */
        QWidget {{
            background-color: {colors['window_bg']};
            color: {colors['window_text']};
        }}

        /* Стили для меню */
        QMenuBar {{
            background-color: {colors['menubar_bg']};
            color: {colors['menubar_text']};
            border: none;
        }}
        QMenuBar::item {{
            background-color: transparent;
            color: {colors['menubar_text']};
            padding: 4px 8px;
        }}
        QMenuBar::item:selected {{
            background-color: {colors['menubar_sel_bg']};
        }}
        QMenuBar::item:pressed {{
            background-color: {colors['menubar_sel_bg']};
        }}

        QMenu {{
            background-color: {colors['menu_bg']};
            color: {colors['menu_text']};
            border: 1px solid {colors['menu_border']};
            border-radius: 3px;
        }}
        QMenu::item {{
            background-color: transparent;
            color: {colors['menu_text']};
            padding: 6px 20px;
        }}
        QMenu::item:selected {{
            background-color: {colors['menu_sel_bg']};
            color: {colors['menu_sel_text']};
        }}
        QMenu::item:disabled {{
            color: {colors['button_disabled_text']};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {colors['menu_border']};
            margin: 4px 0px;
        }}

        /* Остальные стили */
        QLineEdit {{
            background-color: {colors['input_bg']};
            border: 1px solid {colors['input_border']};
            color: {colors['input_text']};
            padding: 4px;
            border-radius: 3px;
        }}
        QLineEdit:focus {{
            border: 2px solid {colors['input_focus_border']};
        }}
        QLineEdit:disabled {{
            background-color: {colors['input_disabled_bg']};
            color: {colors['input_disabled_text']};
        }}

        QCheckBox {{
            color: {colors['window_text']};
            spacing: 5px;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 1px solid {colors['checkbox_border']};
            background-color: {colors['checkbox_bg']};
        }}
        QCheckBox::indicator:checked {{
            background-color: {colors['checkbox_checked_bg']};
            border: 1px solid {colors['checkbox_checked_bg']};
        }}

        QPushButton {{
            background-color: {colors['button_bg']};
            border: 1px solid {colors['button_border']};
            color: {colors['button_text']};
            padding: 6px 12px;
            border-radius: 3px;
            min-width: 80px;
        }}
        QPushButton:hover {{
            background-color: {colors['button_hover_bg']};
        }}
        QPushButton:pressed {{
            background-color: {colors['button_pressed_bg']};
        }}
        QPushButton:default {{
            background-color: {colors['button_default_bg']};
            border: 1px solid {colors['button_default_bg']};
            color: {colors['button_default_text']};
            font-weight: bold;
        }}
        QPushButton:disabled {{
            background-color: {colors['button_disabled_bg']};
            color: {colors['button_disabled_text']};
        }}

        QComboBox {{
            background-color: {colors['input_bg']};
            border: 1px solid {colors['input_border']};
            color: {colors['input_text']};
            padding: 4px;
            border-radius: 3px;
        }}
        QComboBox:focus {{
            border: 2px solid {colors['input_focus_border']};
        }}
        QComboBox::drop-down {{
            border: none;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 4px solid {colors['window_text']};
            width: 0;
            height: 0;
        }}
        QComboBox QAbstractItemView {{
            background-color: {colors['menu_bg']};
            color: {colors['menu_text']};
            selection-background-color: {colors['menu_sel_bg']};
            selection-color: {colors['menu_sel_text']};
            border: 1px solid {colors['menu_border']};
        }}

        QStatusBar {{
            background-color: {colors['statusbar_bg']};
            color: {colors['statusbar_text']};
        }}

        QToolBar {{
            background-color: {colors['toolbar_bg']};
            border: none;
        }}

        QHeaderView::section {{
            background-color: {colors['header_bg']};
            color: {colors['header_text']};
            border: 1px solid {colors['header_border']};
            padding: 4px;
        }}

        QProgressBar {{
            border: 1px solid {colors['input_border']};
            border-radius: 3px;
            text-align: center;
        }}
        QProgressBar::chunk {{
            background-color: {colors['progress_chunk']};
            border-radius: 2px;
        }}

        QTreeView {{
            background-color: {colors['base_bg']};
            alternate-background-color: {colors['alternate_bg']};
            color: {colors['base_text']};
            border: 1px solid {colors['input_border']};
        }}
        QTreeView::item {{
            padding: 2px;
        }}
        QTreeView::item:selected {{
            background-color: {colors['selection_bg']};
            color: {colors['selection_text']};
        }}
        QTreeView::item:selected:focus {{
            background-color: {colors['selection_focus_bg']};
        }}
        QTreeView::item:selected:!active {{
            background-color: {colors['selection_inactive_bg']};
        }}
        QTreeView::item:hover {{
            background-color: {colors['hover_bg']};
        }}

        QTableWidget {{
            background-color: {colors['base_bg']};
            alternate-background-color: {colors['alternate_bg']};
            color: {colors['base_text']};
            gridline-color: {colors['input_border']};
        }}
        QTableWidget::item:selected {{
            background-color: {colors['selection_bg']};
            color: {colors['selection_text']};
        }}

        QTabWidget::pane {{
            border: 1px solid {colors['input_border']};
            background-color: {colors['base_bg']};
        }}
        QTabBar::tab {{
            background-color: {colors['button_bg']};
            color: {colors['button_text']};
            padding: 6px 12px;
            border: 1px solid {colors['button_border']};
            border-bottom: none;
            border-top-left-radius: 3px;
            border-top-right-radius: 3px;
        }}
        QTabBar::tab:selected {{
            background-color: {colors['base_bg']};
            border-bottom-color: {colors['base_bg']};
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {colors['button_hover_bg']};
        }}

        QGroupBox {{
            border: 1px solid {colors['input_border']};
            border-radius: 3px;
            margin-top: 10px;
            padding-top: 10px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }}

        QScrollBar:vertical {{
            background-color: {colors['base_bg']};
            width: 12px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {colors['button_bg']};
            border: 1px solid {colors['button_border']};
            border-radius: 3px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {colors['button_hover_bg']};
        }}
    """)


def change_theme(app, new_theme):
    """Change theme dynamically."""
    apply_global_theme(app, new_theme)