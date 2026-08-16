from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QListWidget,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.core.units import (
    Unit_AreConvertible,
    Unit_ConvertValue,
    Unit_DisplayUnitResolve,
    Unit_ValueFormat,
    UnitDisplayMode,
    UnitDisplayMode_Normalize,
)
from underline_retldc.gui.analysis_widgets import AnalysisResultsPanel
from underline_retldc.i18n.service import TranslationService
from underline_retldc.plugin_api.common import AnalysisResult


class AnalyzePage(QWidget):
    calculate_requested = Signal()

    METRIC_ORDER = (
        "peak_value",
        "average_value",
        "relative_integral",
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
        self._display_preferences: dict[str, str] = {}
        self._display_mode = UnitDisplayMode.ENGINEERING
        self.calculate_button = QPushButton()
        self.calculate_button.setObjectName("primaryButton")
        self.calculate_button.clicked.connect(self.calculate_requested)

        self.metrics_group = AnalysisResultsPanel()
        self.metrics_table = self.metrics_group.table
        self.metrics_table.setMinimumWidth(0)

        self.diagnostics_group = QGroupBox()
        self.diagnostics_list = QListWidget()
        diagnostics_layout = QVBoxLayout(self.diagnostics_group)
        diagnostics_layout.addWidget(self.diagnostics_list)

        layout = QVBoxLayout(self)
        layout.addWidget(self.calculate_button)
        layout.addWidget(self.metrics_group, 2)
        layout.addWidget(self.diagnostics_group, 1)
        self.retranslate()

    def retranslate(self) -> None:
        t = self._translations.translate
        self.calculate_button.setText(t("analyze.calculate"))
        self.metrics_group.setTitle(t("page.analyze"))
        self.diagnostics_group.setTitle(t("import.diagnostics"))
        self.metrics_table.setHorizontalHeaderLabels(
            [t("workspace.metric"), t("common.value")]
        )
        if self._result is not None:
            self.set_result(self._result)

    def set_result(self, result: AnalysisResult) -> None:
        self._result = result
        available = [key for key in self.METRIC_ORDER if key in result.metrics]
        self.metrics_table.setRowCount(len(available))
        for row, key in enumerate(available):
            value = result.metrics[key]
            label = self._translations.translate(f"metric.{key}", key)
            display_value, label = self._metric_display(result, key, value, label)
            value_text = (
                self._translations.translate("common.unavailable")
                if display_value is None
                else Unit_ValueFormat(
                    display_value,
                    display_mode=self._display_mode,
                )
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
    def set_display_configuration(
        self,
        preferences: Mapping[str, str],
        display_mode: UnitDisplayMode | str,
    ) -> None:
        self._display_preferences = dict(preferences)
        self._display_mode = UnitDisplayMode_Normalize(display_mode)
        if self._result is not None:
            self.set_result(self._result)

    def _metric_display(
        self,
        result: AnalysisResult,
        key: str,
        value: float | None,
        label: str,
    ) -> tuple[float | None, str]:
        if value is None:
            return None, label
        input_quantity = str(result.metadata.get("input_quantity", "force"))
        input_unit = str(result.metadata.get("input_data_unit", "N"))
        force_unit = Unit_DisplayUnitResolve(
            "force",
            "N",
            preferences=self._display_preferences,
            display_mode=self._display_mode,
        )
        relative_unit = Unit_DisplayUnitResolve(
            input_quantity,
            input_unit,
            preferences=self._display_preferences,
            display_mode=self._display_mode,
        )
        numeric = float(value)
        if key in {"peak_thrust_n", "average_thrust_n"}:
            numeric = Unit_ConvertValue(numeric, "N", force_unit)
            return numeric, label.replace("[N]", f"[{force_unit}]")
        if key == "total_impulse_ns":
            scale = Unit_ConvertValue(1.0, "N", force_unit) - Unit_ConvertValue(
                0.0,
                "N",
                force_unit,
            )
            return numeric * scale, label.replace("[N·s]", f"[{force_unit}·s]")
        if key in {"peak_value", "average_value"} and Unit_AreConvertible(
            input_unit,
            relative_unit,
        ):
            return (
                Unit_ConvertValue(numeric, input_unit, relative_unit),
                f"{label} [{relative_unit}]",
            )
        if key == "relative_integral" and Unit_AreConvertible(
            input_unit,
            relative_unit,
        ):
            scale = Unit_ConvertValue(
                1.0,
                input_unit,
                relative_unit,
            ) - Unit_ConvertValue(0.0, input_unit, relative_unit)
            return numeric * scale, f"{label} [{relative_unit}·s]"
        return numeric, label

    def clear_result(self) -> None:
        self._result = None
        self.metrics_table.setRowCount(0)
        self.diagnostics_list.clear()
