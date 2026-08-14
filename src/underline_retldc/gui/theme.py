from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QApplication, QProxyStyle, QStyle, QStyleOption, QWidget

from underline_retldc.app.settings import THEME_DARK, THEME_LIGHT, Theme_Normalize

LIGHT_STYLE_SHEET = """
QWidget {
    color: #111827;
    background: #f4f6fa;
}
QMainWindow, QWidget#centralRoot, QStackedWidget, QScrollArea,
QScrollArea > QWidget > QWidget {
    background: #f4f6fa;
}
QDialog, QMessageBox, QFileDialog {
    background: #ffffff;
    color: #111827;
}
QLabel, QCheckBox, QRadioButton, QGroupBox {
    background: transparent;
    color: #111827;
}
QLabel:disabled, QCheckBox:disabled, QRadioButton:disabled {
    color: #737d8c;
}
QWidget#headerBar {
    background: #123a78;
    border: 0;
    border-radius: 4px;
}
QLabel#headerTitle {
    background: transparent;
    color: #ffffff;
    font-size: 21px;
    font-weight: 650;
    padding: 6px;
}
QLabel#headerVersion, QLabel#headerCredit, QLabel#headerLanguageLabel {
    background: transparent;
    color: #ffffff;
}
QPushButton#themeToggleButton {
    background: #1c4f94;
    color: #ffffff;
    border: 1px solid #6f91be;
    padding: 4px 9px;
}
QPushButton#themeToggleButton:hover { background: #2f6fed; border-color: #9bbcff; }
QListWidget#navigation {
    background: #123a78;
    color: #ffffff;
    border: 0;
    font-size: 14px;
}
QListWidget#navigation::item {
    background: #123a78;
    color: #ffffff;
    padding: 13px 12px;
    border-bottom: 1px solid #315a94;
}
QListWidget#navigation::item:hover { background: #1c4f94; }
QListWidget#navigation::item:selected { background: #2f6fed; color: #ffffff; }
QGroupBox {
    font-weight: 600;
    margin-top: 10px;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: #123a78;
}
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
QTableWidget, QListWidget:not(#navigation), QTreeWidget {
    background: #ffffff;
    color: #111111;
    border: 1px solid #aeb8c8;
    selection-background-color: #2f6fed;
    selection-color: #ffffff;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    min-height: 24px;
    padding: 1px 5px;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    color: #111111;
    border: 1px solid #8f9bad;
    selection-background-color: #2f6fed;
    selection-color: #ffffff;
    outline: 0;
}
QComboBox QAbstractItemView::item {
    background: #ffffff;
    color: #111111;
    min-height: 26px;
    padding: 3px 6px;
}
QComboBox QAbstractItemView::item:selected {
    background: #2f6fed;
    color: #ffffff;
}
QComboBox:disabled, QLineEdit:disabled, QPlainTextEdit:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled {
    background: #e9edf4;
    color: #596273;
}
QHeaderView::section {
    background: #e7ecf4;
    color: #111827;
    padding: 5px;
    border: 0;
    border-right: 1px solid #c8d0dd;
    border-bottom: 1px solid #c8d0dd;
}
QTableWidget::item, QListWidget:not(#navigation)::item {
    background: #ffffff;
    color: #111111;
}
QTableWidget::item:selected, QListWidget:not(#navigation)::item:selected {
    background: #2f6fed;
    color: #ffffff;
}
QPushButton {
    background: #ffffff;
    color: #111827;
    border: 1px solid #9eabbf;
    border-radius: 4px;
    padding: 6px 12px;
}
QPushButton:hover { background: #edf3ff; border-color: #547fcf; }
QPushButton:pressed { background: #dce8ff; }
QPushButton:disabled { background: #e9edf4; color: #6f7888; border-color: #c8d0dd; }
QPushButton#primaryButton {
    background: #2f6fed;
    color: #ffffff;
    border: 0;
    border-radius: 4px;
}
QPushButton#primaryButton:hover { background: #255fcf; }
QLabel#warningLabel {
    background: #fff2cc;
    color: #513f00;
    padding: 10px;
    border-radius: 4px;
}
QMenuBar, QMenuBar#mainMenuBar, QToolBar, QToolBar#mainToolBar {
    background: #123a78;
    color: #ffffff;
    border: 0;
}
QMenuBar::item, QMenuBar#mainMenuBar::item {
    background: transparent;
    color: #ffffff;
    padding: 5px 10px;
}
QMenuBar::item:selected, QMenuBar::item:pressed,
QMenuBar#mainMenuBar::item:selected, QMenuBar#mainMenuBar::item:pressed {
    background: #2f6fed;
    color: #ffffff;
}
QToolBar, QToolBar#mainToolBar { spacing: 4px; padding: 3px; }
QToolButton, QToolBar#mainToolBar QToolButton {
    background: #123a78;
    color: #ffffff;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 5px 9px;
}
QToolButton:hover, QToolBar#mainToolBar QToolButton:hover {
    background: #2f6fed;
    color: #ffffff;
}
QMenu {
    background: #ffffff;
    color: #111111;
    border: 1px solid #8f9bad;
}
QMenu::item { background: #ffffff; color: #111111; padding: 6px 26px; }
QMenu::item:selected { background: #2f6fed; color: #ffffff; }
QMenu::item:disabled { color: #737d8c; }
QStatusBar { background: #ffffff; color: #111827; }
QProgressBar { background: #e2e7ef; color: #111827; border: 0; }
QProgressBar::chunk { background: #2f6fed; }
QToolTip {
    background: #ffffff;
    color: #111111;
    border: 1px solid #5f6b7b;
}
QScrollBar:vertical {
    background: #edf1f6;
    width: 13px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #aeb8c8;
    min-height: 28px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover { background: #8d9bb0; }
QScrollBar:horizontal {
    background: #edf1f6;
    height: 13px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #aeb8c8;
    min-width: 28px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal:hover { background: #8d9bb0; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
"""

DARK_STYLE_SHEET = """
QWidget {
    color: #e5e7eb;
    background: #0f172a;
}
QMainWindow, QWidget#centralRoot, QStackedWidget, QScrollArea,
QScrollArea > QWidget > QWidget {
    background: #0f172a;
}
QDialog, QMessageBox, QFileDialog {
    background: #111827;
    color: #e5e7eb;
}
QLabel, QCheckBox, QRadioButton, QGroupBox {
    background: transparent;
    color: #e5e7eb;
}
QLabel:disabled, QCheckBox:disabled, QRadioButton:disabled {
    color: #64748b;
}
QWidget#headerBar {
    background: #0b2447;
    border: 0;
    border-radius: 4px;
}
QLabel#headerTitle {
    background: transparent;
    color: #f8fafc;
    font-size: 21px;
    font-weight: 650;
    padding: 6px;
}
QLabel#headerVersion, QLabel#headerCredit, QLabel#headerLanguageLabel {
    background: transparent;
    color: #e5e7eb;
}
QPushButton#themeToggleButton {
    background: #163b6c;
    color: #f8fafc;
    border: 1px solid #4f6f99;
    padding: 4px 9px;
}
QPushButton#themeToggleButton:hover { background: #245ba0; border-color: #60a5fa; }
QListWidget#navigation {
    background: #0b2447;
    color: #f8fafc;
    border: 0;
    font-size: 14px;
}
QListWidget#navigation::item {
    background: #0b2447;
    color: #e5e7eb;
    padding: 13px 12px;
    border-bottom: 1px solid #234a76;
}
QListWidget#navigation::item:hover { background: #163b6c; }
QListWidget#navigation::item:selected { background: #3b82f6; color: #ffffff; }
QGroupBox {
    font-weight: 600;
    margin-top: 10px;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: #93c5fd;
}
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
QTableWidget, QListWidget:not(#navigation), QTreeWidget {
    background: #182235;
    color: #e5e7eb;
    border: 1px solid #475569;
    selection-background-color: #3b82f6;
    selection-color: #ffffff;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    min-height: 24px;
    padding: 1px 5px;
}
QComboBox QAbstractItemView {
    background: #182235;
    color: #e5e7eb;
    border: 1px solid #475569;
    selection-background-color: #3b82f6;
    selection-color: #ffffff;
    outline: 0;
}
QComboBox QAbstractItemView::item {
    background: #182235;
    color: #e5e7eb;
    min-height: 26px;
    padding: 3px 6px;
}
QComboBox QAbstractItemView::item:selected {
    background: #3b82f6;
    color: #ffffff;
}
QComboBox:disabled, QLineEdit:disabled, QPlainTextEdit:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled {
    background: #172033;
    color: #64748b;
    border-color: #334155;
}
QHeaderView::section {
    background: #1e293b;
    color: #e5e7eb;
    padding: 5px;
    border: 0;
    border-right: 1px solid #334155;
    border-bottom: 1px solid #475569;
}
QTableCornerButton::section { background: #1e293b; border: 1px solid #334155; }
QTableWidget::item, QListWidget:not(#navigation)::item {
    background: #182235;
    color: #e5e7eb;
}
QTableWidget::item:selected, QListWidget:not(#navigation)::item:selected {
    background: #3b82f6;
    color: #ffffff;
}
QPushButton {
    background: #1e293b;
    color: #e5e7eb;
    border: 1px solid #475569;
    border-radius: 4px;
    padding: 6px 12px;
}
QPushButton:hover { background: #27364d; border-color: #60a5fa; }
QPushButton:pressed { background: #334155; }
QPushButton:disabled { background: #172033; color: #64748b; border-color: #334155; }
QPushButton#primaryButton {
    background: #3b82f6;
    color: #ffffff;
    border: 0;
    border-radius: 4px;
}
QPushButton#primaryButton:hover { background: #4f8cff; }
QLabel#warningLabel {
    background: #3b3215;
    color: #fde68a;
    padding: 10px;
    border-radius: 4px;
}
QMenuBar, QMenuBar#mainMenuBar, QToolBar, QToolBar#mainToolBar {
    background: #0b2447;
    color: #f8fafc;
    border: 0;
}
QMenuBar::item, QMenuBar#mainMenuBar::item {
    background: transparent;
    color: #f8fafc;
    padding: 5px 10px;
}
QMenuBar::item:selected, QMenuBar::item:pressed,
QMenuBar#mainMenuBar::item:selected, QMenuBar#mainMenuBar::item:pressed {
    background: #3b82f6;
    color: #ffffff;
}
QToolBar, QToolBar#mainToolBar { spacing: 4px; padding: 3px; }
QToolButton, QToolBar#mainToolBar QToolButton {
    background: #0b2447;
    color: #f8fafc;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 5px 9px;
}
QToolButton:hover, QToolBar#mainToolBar QToolButton:hover {
    background: #3b82f6;
    color: #ffffff;
}
QMenu {
    background: #182235;
    color: #e5e7eb;
    border: 1px solid #475569;
}
QMenu::item { background: #182235; color: #e5e7eb; padding: 6px 26px; }
QMenu::item:selected { background: #3b82f6; color: #ffffff; }
QMenu::item:disabled { color: #64748b; }
QStatusBar { background: #111827; color: #e5e7eb; border-top: 1px solid #334155; }
QProgressBar { background: #172033; color: #e5e7eb; border: 1px solid #334155; }
QProgressBar::chunk { background: #3b82f6; }
QToolTip {
    background: #182235;
    color: #e5e7eb;
    border: 1px solid #64748b;
}
QScrollBar:vertical {
    background: #111827;
    width: 13px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #475569;
    min-height: 28px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover { background: #64748b; }
QScrollBar:horizontal {
    background: #111827;
    height: 13px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #475569;
    min-width: 28px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal:hover { background: #64748b; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
"""


class WindowThemeFilter(QObject):
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            event.type() == QEvent.Type.Show
            and isinstance(watched, QWidget)
            and watched.isWindow()
        ):
            Window_TitleBarApply(watched)
        return super().eventFilter(watched, event)


class RetldcApplicationStyle(QProxyStyle):
    """Fusion-based style with unmistakable checkbox and radio indicators."""

    def __init__(self, theme: str) -> None:
        super().__init__("Fusion")
        self._theme = Theme_Normalize(theme)

    def pixelMetric(
        self,
        metric: QStyle.PixelMetric,
        option: QStyleOption | None = None,
        widget: QWidget | None = None,
    ) -> int:
        if metric in {
            QStyle.PixelMetric.PM_IndicatorWidth,
            QStyle.PixelMetric.PM_IndicatorHeight,
            QStyle.PixelMetric.PM_ExclusiveIndicatorWidth,
            QStyle.PixelMetric.PM_ExclusiveIndicatorHeight,
        }:
            return 18
        return super().pixelMetric(metric, option, widget)

    def drawPrimitive(
        self,
        element: QStyle.PrimitiveElement,
        option: QStyleOption,
        painter: QPainter,
        widget: QWidget | None = None,
    ) -> None:
        if element == QStyle.PrimitiveElement.PE_IndicatorRadioButton:
            enabled = bool(option.state & QStyle.StateFlag.State_Enabled)
            checked = bool(option.state & QStyle.StateFlag.State_On)
            hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
            indicator = option.rect.adjusted(1, 1, -1, -1)
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            if self._theme == THEME_DARK:
                border_color = QColor(
                    "#60a5fa" if hovered and enabled else "#94a3b8"
                )
                fill_color = QColor("#182235" if enabled else "#172033")
                dot_color = QColor("#60a5fa" if enabled else "#64748b")
            else:
                border_color = QColor(
                    "#245bc5" if hovered and enabled else "#52647d"
                )
                fill_color = QColor("#ffffff" if enabled else "#eef1f5")
                dot_color = QColor("#2f6fed" if enabled else "#91a6ca")
            painter.setPen(QPen(border_color, 1.6))
            painter.setBrush(fill_color)
            painter.drawEllipse(indicator)
            if checked:
                radius = max(3.0, min(indicator.width(), indicator.height()) * 0.27)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(dot_color)
                painter.drawEllipse(indicator.center(), radius, radius)
            painter.restore()
            return
        if element != QStyle.PrimitiveElement.PE_IndicatorCheckBox:
            super().drawPrimitive(element, option, painter, widget)
            return

        enabled = bool(option.state & QStyle.StateFlag.State_Enabled)
        checked = bool(option.state & QStyle.StateFlag.State_On)
        partial = bool(option.state & QStyle.StateFlag.State_NoChange)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        indicator = option.rect.adjusted(1, 1, -1, -1)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._theme == THEME_DARK:
            border_color = QColor("#60a5fa" if hovered and enabled else "#64748b")
            fill_color = QColor("#182235" if enabled else "#172033")
            check_color = QColor("#ffffff" if enabled else "#94a3b8")
            if checked or partial:
                fill_color = QColor("#3b82f6" if enabled else "#334155")
                border_color = QColor("#60a5fa" if enabled else "#475569")
        else:
            border_color = QColor("#4774bd" if hovered and enabled else "#65738a")
            fill_color = QColor("#ffffff" if enabled else "#eef1f5")
            check_color = QColor("#ffffff")
            if checked or partial:
                fill_color = QColor("#2f6fed" if enabled else "#91a6ca")
                border_color = QColor("#245bc5" if enabled else "#7f8da5")
        painter.setPen(QPen(border_color, 1.4))
        painter.setBrush(fill_color)
        painter.drawRoundedRect(indicator, 2.0, 2.0)

        check_pen = QPen(check_color, 2.0)
        check_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        check_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(check_pen)
        if checked:
            path = QPainterPath()
            path.moveTo(indicator.left() + indicator.width() * 0.20, indicator.center().y())
            path.lineTo(
                indicator.left() + indicator.width() * 0.43,
                indicator.bottom() - indicator.height() * 0.23,
            )
            path.lineTo(
                indicator.right() - indicator.width() * 0.16,
                indicator.top() + indicator.height() * 0.23,
            )
            painter.drawPath(path)
        elif partial:
            painter.drawLine(
                indicator.left() + indicator.width() * 0.22,
                indicator.center().y(),
                indicator.right() - indicator.width() * 0.22,
                indicator.center().y(),
            )
        painter.restore()


def Theme_Current(application: QApplication | None = None) -> str:
    instance = application or QApplication.instance()
    if instance is None:
        return THEME_LIGHT
    return Theme_Normalize(instance.property("retldcTheme"))


def _palette_create(theme: str) -> QPalette:
    palette = QPalette()
    if theme == THEME_DARK:
        colors = {
            QPalette.ColorRole.Window: "#0f172a",
            QPalette.ColorRole.WindowText: "#e5e7eb",
            QPalette.ColorRole.Base: "#182235",
            QPalette.ColorRole.AlternateBase: "#172033",
            QPalette.ColorRole.Text: "#e5e7eb",
            QPalette.ColorRole.Button: "#1e293b",
            QPalette.ColorRole.ButtonText: "#e5e7eb",
            QPalette.ColorRole.Highlight: "#3b82f6",
            QPalette.ColorRole.HighlightedText: "#ffffff",
            QPalette.ColorRole.ToolTipBase: "#182235",
            QPalette.ColorRole.ToolTipText: "#e5e7eb",
            QPalette.ColorRole.PlaceholderText: "#94a3b8",
        }
        disabled_text = QColor("#64748b")
        disabled_base = QColor("#172033")
    else:
        colors = {
            QPalette.ColorRole.Window: "#f4f6fa",
            QPalette.ColorRole.WindowText: "#111827",
            QPalette.ColorRole.Base: "#ffffff",
            QPalette.ColorRole.AlternateBase: "#edf2f8",
            QPalette.ColorRole.Text: "#111111",
            QPalette.ColorRole.Button: "#ffffff",
            QPalette.ColorRole.ButtonText: "#111827",
            QPalette.ColorRole.Highlight: "#2f6fed",
            QPalette.ColorRole.HighlightedText: "#ffffff",
            QPalette.ColorRole.ToolTipBase: "#ffffff",
            QPalette.ColorRole.ToolTipText: "#111111",
            QPalette.ColorRole.PlaceholderText: "#737d8c",
        }
        disabled_text = QColor("#737d8c")
        disabled_base = QColor("#e9edf4")
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, disabled_base)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, disabled_base)
    return palette


def Theme_Apply(application: QApplication, theme: str = THEME_LIGHT) -> str:
    normalized = Theme_Normalize(theme)
    application.setProperty("retldcTheme", normalized)
    application_style = RetldcApplicationStyle(normalized)
    application.setStyle(application_style)
    # PySide does not reliably keep the Python wrapper alive after setStyle().
    # Retain it explicitly so Qt cannot silently fall back to the base style.
    application._retldc_application_style = application_style
    application.setPalette(_palette_create(normalized))
    application.setStyleSheet(
        DARK_STYLE_SHEET if normalized == THEME_DARK else LIGHT_STYLE_SHEET
    )
    if not hasattr(application, "_retldc_theme_filter"):
        theme_filter = WindowThemeFilter(application)
        application.installEventFilter(theme_filter)
        application._retldc_theme_filter = theme_filter
    for widget in application.topLevelWidgets():
        Window_TitleBarApply(widget, normalized)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
    return normalized


def Theme_DarkBarApply(widget: QWidget, theme: str | None = None) -> None:
    normalized = Theme_Normalize(theme or Theme_Current())
    background = "#0b2447" if normalized == THEME_DARK else "#123a78"
    hover = "#3b82f6" if normalized == THEME_DARK else "#2f6fed"
    widget.setStyleSheet(
        "QMenuBar, QToolBar {"
        f"background-color: {background}; color: #ffffff; border: 0;"
        "}"
        "QMenuBar::item {"
        f"background-color: {background}; color: #ffffff; padding: 5px 10px;"
        "}"
        "QMenuBar::item:selected, QMenuBar::item:pressed {"
        f"background-color: {hover}; color: #ffffff;"
        "}"
        "QToolButton {"
        f"background-color: {background}; color: #ffffff;"
        "border: 1px solid transparent; border-radius: 3px; padding: 5px 9px;"
        "}"
        "QToolButton:hover {"
        f"background-color: {hover}; color: #ffffff;"
        "}"
    )


def _dwm_color(rgb: str) -> int:
    color = QColor(rgb)
    return color.red() | (color.green() << 8) | (color.blue() << 16)


def Window_TitleBarApply(widget: QWidget, theme: str | None = None) -> None:
    if sys.platform != "win32":
        return
    normalized = Theme_Normalize(theme or Theme_Current())
    try:
        dwmapi = ctypes.windll.dwmapi
        window_handle = ctypes.c_void_p(int(widget.winId()))
        caption_rgb = "#0b2447" if normalized == THEME_DARK else "#123a78"
        caption_color = ctypes.c_int(_dwm_color(caption_rgb))
        text_color = ctypes.c_int(_dwm_color("#f8fafc"))
        border_color = ctypes.c_int(_dwm_color(caption_rgb))
        dark_mode = ctypes.c_int(1 if normalized == THEME_DARK else 0)
        dwmapi.DwmSetWindowAttribute(
            window_handle, 20, ctypes.byref(dark_mode), ctypes.sizeof(dark_mode)
        )
        dwmapi.DwmSetWindowAttribute(
            window_handle, 34, ctypes.byref(border_color), ctypes.sizeof(border_color)
        )
        dwmapi.DwmSetWindowAttribute(
            window_handle, 35, ctypes.byref(caption_color), ctypes.sizeof(caption_color)
        )
        dwmapi.DwmSetWindowAttribute(
            window_handle, 36, ctypes.byref(text_color), ctypes.sizeof(text_color)
        )
    except (AttributeError, OSError, TypeError, ValueError):
        return
