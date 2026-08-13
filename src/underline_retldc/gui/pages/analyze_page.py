from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QGroupBox,
    QHeaderView,
    QListWidget,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.i18n.service import TranslationService
from underline_retldc.plugin_api.common import AnalysisResult


class AnalyzePage(QWidget):
    calculate_requested = Signal()
    confirmation_changed = Signal(bool)

    METRIC_ORDER = (
        "peak_thrust_n",
        "average_thrust_n",
        "burn_duration_s",
        "total_impulse_ns",
        "specific_impulse_s",
        "time_to_peak_s",
        "equivalent_mass_change_kg",
    )

    def __init__(self, translations: TranslationService) -> None:
        super().__init__()
        self._translations = translations
        self._result: AnalysisResult | None = None
        self.calculate_button = QPushButton()
        self.calculate_button.setObjectName("primaryButton")
        self.calculate_button.clicked.connect(self.calculate_requested)
        self.confirm_check = QCheckBox()
        self.confirm_check.setEnabled(False)
        self.confirm_check.toggled.connect(self.confirmation_changed)

        self.metrics_group = QGroupBox()
        self.metrics_table = QTableWidget(0, 2)
        self.metrics_table.verticalHeader().setVisible(False)
        self.metrics_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.metrics_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.metrics_table.setMinimumWidth(300)
        self.metrics_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.metrics_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        metrics_layout = QVBoxLayout(self.metrics_group)
        metrics_layout.addWidget(self.metrics_table)

        self.diagnostics_group = QGroupBox()
        self.diagnostics_list = QListWidget()
        diagnostics_layout = QVBoxLayout(self.diagnostics_group)
        diagnostics_layout.addWidget(self.diagnostics_list)

        layout = QVBoxLayout(self)
        layout.addWidget(self.calculate_button)
        layout.addWidget(self.confirm_check)
        layout.addWidget(self.metrics_group, 2)
        layout.addWidget(self.diagnostics_group, 1)
        self.retranslate()

    def retranslate(self) -> None:
        t = self._translations.translate
        self.calculate_button.setText(t("analyze.calculate"))
        self.confirm_check.setText(t("analyze.confirmed"))
        self.metrics_group.setTitle(t("page.analyze"))
        self.diagnostics_group.setTitle(t("import.diagnostics"))
        self.metrics_table.setHorizontalHeaderLabels(
            [t("page.analyze"), t("common.value")]
        )
        if self._result is not None:
            self.set_result(self._result, confirmed=self.confirm_check.isChecked())

    def set_result(self, result: AnalysisResult, *, confirmed: bool = False) -> None:
        self._result = result
        available = [key for key in self.METRIC_ORDER if key in result.metrics]
        self.metrics_table.setRowCount(len(available))
        for row, key in enumerate(available):
            value = result.metrics[key]
            label = self._translations.translate(f"metric.{key}", key)
            value_text = (
                self._translations.translate("common.unavailable")
                if value is None
                else f"{float(value):.8g}"
            )
            self.metrics_table.setItem(row, 0, QTableWidgetItem(label))
            self.metrics_table.setItem(row, 1, QTableWidgetItem(value_text))
        self.diagnostics_list.clear()
        for diagnostic in result.diagnostics:
            message = self._translations.translate(
                f"diagnostic.{diagnostic.code}",
                diagnostic.message,
                message=diagnostic.message,
            )
            self.diagnostics_list.addItem(
                f"[{diagnostic.severity.value}] {diagnostic.code}: {message}"
            )
        self.confirm_check.setEnabled(True)
        self.confirm_check.blockSignals(True)
        self.confirm_check.setChecked(confirmed)
        self.confirm_check.blockSignals(False)

    def clear_result(self) -> None:
        self._result = None
        self.metrics_table.setRowCount(0)
        self.diagnostics_list.clear()
        self.confirm_check.blockSignals(True)
        self.confirm_check.setChecked(False)
        self.confirm_check.blockSignals(False)
        self.confirm_check.setEnabled(False)
