# ui/theme.py
"""Centralized theme management for WebDAV Manager."""

import logging

logger = logging.getLogger(__name__)

# Color definitions for light theme
LIGHT_THEME = {
    # Основные цвета окна
    'window_bg': '#f5f5f5',
    'window_text': '#000000',

    # Базовые цвета
    'base_bg': '#ffffff',
    'base_text': '#000000',
    'alternate_bg': '#f0f0f0',

    # Кнопки
    'button_bg': '#ffffff',
    'button_text': '#000000',
    'button_border': '#cccccc',
    'button_hover_bg': '#e6e6e6',
    'button_pressed_bg': '#d4d4d4',
    'button_default_bg': '#3399ff',
    'button_default_text': 'white',
    'button_disabled_bg': '#f0f0f0',
    'button_disabled_text': '#999999',

    # Заголовки
    'header_bg': '#d0d0d0',
    'header_text': '#000000',
    'header_border': '#a0a0a0',

    # Выделение
    'selection_bg': '#99ccff',
    'selection_text': 'black',
    'selection_focus_bg': '#b3d9ff',
    'selection_inactive_bg': '#cce0f0',
    'hover_bg': '#e0e0e0',

    # Панели инструментов и статуса
    'toolbar_bg': '#f0f0f0',
    'statusbar_bg': '#f0f0f0',
    'statusbar_text': '#000000',

    # Меню
    'menubar_bg': '#f0f0f0',
    'menubar_text': '#000000',
    'menubar_sel_bg': '#3399ff',
    'menu_bg': '#ffffff',
    'menu_text': '#000000',
    'menu_sel_bg': '#3399ff',
    'menu_sel_text': '#ffffff',
    'menu_border': '#cccccc',

    # Поля ввода
    'input_bg': '#ffffff',
    'input_text': '#000000',
    'input_border': '#cccccc',
    'input_focus_border': '#66b3ff',
    'input_disabled_bg': '#f0f0f0',
    'input_disabled_text': '#999999',

    # Чекбоксы
    'checkbox_border': '#cccccc',
    'checkbox_bg': '#ffffff',
    'checkbox_checked_bg': '#3399ff',

    # Прогресс бар
    'progress_chunk': '#4CAF50',

    # Квота
    'quota_warning': '#FFC107',
    'quota_danger': '#F44336',

    # Ссылки и статусы
    'link': '#3399ff',
    'success': '#4CAF50',
    'error': '#ff6b6b',
    'warning': '#ff9900',

    # Таблицы
    'table_bg': '#ffffff',
    'table_alternate_bg': '#f5f5f5',
    'table_text': '#000000',
    'table_grid': '#cccccc',
    'table_header_bg': '#d0d0d0',
    'table_header_text': '#000000',
    'table_header_border': '#a0a0a0',

    # Дерево файлов
    'tree_bg': '#ffffff',
    'tree_alternate_bg': '#f5f5f5',
    'tree_text': '#000000',
    'tree_border': '#cccccc',

    # Скроллбары
    'scrollbar_bg': '#ffffff',
    'scrollbar_handle': '#d0d0d0',
    'scrollbar_handle_hover': '#a0a0a0',

    # Вкладки
    'tab_bg': '#ffffff',
    'tab_text': '#000000',
    'tab_selected_bg': '#ffffff',
    'tab_border': '#cccccc',

    # Группы
    'groupbox_border': '#cccccc',
}

# Color definitions for dark theme
DARK_THEME = {
    # Основные цвета окна
    'window_bg': '#2b2b2b',
    'window_text': '#ffffff',

    # Базовые цвета
    'base_bg': '#3c3c3c',
    'base_text': '#ffffff',
    'alternate_bg': '#353535',

    # Кнопки
    'button_bg': '#3c3c3c',
    'button_text': '#ffffff',
    'button_border': '#555555',
    'button_hover_bg': '#4a4a4a',
    'button_pressed_bg': '#2a2a2a',
    'button_default_bg': '#3399ff',
    'button_default_text': 'white',
    'button_disabled_bg': '#2a2a2a',
    'button_disabled_text': '#666666',

    # Заголовки
    'header_bg': '#404040',
    'header_text': '#ffffff',
    'header_border': '#555555',

    # Выделение
    'selection_bg': '#3399ff',
    'selection_text': 'white',
    'selection_focus_bg': '#66b3ff',
    'selection_inactive_bg': '#66a3d2',
    'hover_bg': '#4d4d4d',

    # Панели инструментов и статуса
    'toolbar_bg': '#404040',
    'statusbar_bg': '#404040',
    'statusbar_text': '#ffffff',

    # Меню
    'menubar_bg': '#404040',
    'menubar_text': '#ffffff',
    'menubar_sel_bg': '#0066cc',
    'menu_bg': '#3c3c3c',
    'menu_text': '#ffffff',
    'menu_sel_bg': '#3399ff',
    'menu_sel_text': '#ffffff',
    'menu_border': '#555555',

    # Поля ввода
    'input_bg': '#3c3c3c',
    'input_text': '#ffffff',
    'input_border': '#555555',
    'input_focus_border': '#3399ff',
    'input_disabled_bg': '#2a2a2a',
    'input_disabled_text': '#666666',

    # Чекбоксы
    'checkbox_border': '#555555',
    'checkbox_bg': '#3c3c3c',
    'checkbox_checked_bg': '#3399ff',

    # Прогресс бар
    'progress_chunk': '#4CAF50',

    # Квота
    'quota_warning': '#FFC107',
    'quota_danger': '#F44336',

    # Ссылки и статусы
    'link': '#66b3ff',
    'success': '#4CAF50',
    'error': '#ff6b6b',
    'warning': '#ffaa00',

    # Таблицы
    'table_bg': '#3c3c3c',
    'table_alternate_bg': '#353535',
    'table_text': '#ffffff',
    'table_grid': '#555555',
    'table_header_bg': '#404040',
    'table_header_text': '#ffffff',
    'table_header_border': '#555555',

    # Дерево файлов
    'tree_bg': '#3c3c3c',
    'tree_alternate_bg': '#353535',
    'tree_text': '#ffffff',
    'tree_border': '#555555',

    # Скроллбары
    'scrollbar_bg': '#3c3c3c',
    'scrollbar_handle': '#555555',
    'scrollbar_handle_hover': '#666666',

    # Вкладки
    'tab_bg': '#3c3c3c',
    'tab_text': '#ffffff',
    'tab_selected_bg': '#3c3c3c',
    'tab_border': '#555555',

    # Группы
    'groupbox_border': '#555555',
}


def get_theme(theme_name='light'):
    """Return theme dictionary."""
    if theme_name == 'dark':
        return DARK_THEME
    return LIGHT_THEME


def get_theme_stylesheet(theme_name):
    """Get complete stylesheet for the entire application."""
    colors = get_theme(theme_name)

    return f"""
        /* Глобальные стили для всего приложения */
        QWidget {{
            background-color: {colors['window_bg']};
            color: {colors['window_text']};
            font-size: 9pt;
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

        /* Стили для полей ввода */
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

        /* Стили для чекбоксов */
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

        /* Стили для кнопок */
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

        /* Стили для комбобоксов */
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

        /* Стили для статусбара */
        QStatusBar {{
            background-color: {colors['statusbar_bg']};
            color: {colors['statusbar_text']};
        }}

        /* Стили для тулбара */
        QToolBar {{
            background-color: {colors['toolbar_bg']};
            border: none;
            spacing: 3px;
        }}

        /* Стили для заголовков таблиц */
        QHeaderView::section {{
            background-color: {colors['header_bg']};
            color: {colors['header_text']};
            border: 1px solid {colors['header_border']};
            padding: 4px;
        }}

        /* Стили для прогрессбара */
        QProgressBar {{
            border: 1px solid {colors['input_border']};
            border-radius: 3px;
            text-align: center;
        }}
        QProgressBar::chunk {{
            background-color: {colors['progress_chunk']};
            border-radius: 2px;
        }}

        /* Стили для дерева файлов */
        QTreeView {{
            background-color: {colors['tree_bg']};
            alternate-background-color: {colors['tree_alternate_bg']};
            color: {colors['tree_text']};
            border: 1px solid {colors['tree_border']};
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

        /* Стили для таблиц */
        QTableWidget {{
            background-color: {colors['table_bg']};
            alternate-background-color: {colors['table_alternate_bg']};
            color: {colors['table_text']};
            gridline-color: {colors['table_grid']};
        }}
        QTableWidget::item:selected {{
            background-color: {colors['selection_bg']};
            color: {colors['selection_text']};
        }}

        /* Стили для вкладок */
        QTabWidget::pane {{
            border: 1px solid {colors['tab_border']};
            background-color: {colors['tab_bg']};
        }}
        QTabBar::tab {{
            background-color: {colors['button_bg']};
            color: {colors['button_text']};
            padding: 6px 12px;
            border: 1px solid {colors['button_border']};
            border-bottom: none;
            border-top-left-radius: 3px;
            border-top-right-radius: 3px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background-color: {colors['tab_selected_bg']};
            border-bottom-color: {colors['tab_selected_bg']};
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {colors['button_hover_bg']};
        }}

        /* Стили для групбоксов */
        QGroupBox {{
            border: 1px solid {colors['groupbox_border']};
            border-radius: 3px;
            margin-top: 10px;
            padding-top: 10px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }}

        /* Стили для скроллбаров */
        QScrollBar:vertical {{
            background-color: {colors['scrollbar_bg']};
            width: 12px;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background-color: {colors['scrollbar_handle']};
            border: 1px solid {colors['input_border']};
            border-radius: 3px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {colors['scrollbar_handle_hover']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
        }}
    """


def apply_theme_to_widget(widget, theme_name):
    """Apply theme to a specific widget."""
    stylesheet = get_theme_stylesheet(theme_name)
    widget.setStyleSheet(stylesheet)


def get_color(theme_name, color_name):
    """Get specific color from theme."""
    theme = get_theme(theme_name)
    return theme.get(color_name, '#000000')