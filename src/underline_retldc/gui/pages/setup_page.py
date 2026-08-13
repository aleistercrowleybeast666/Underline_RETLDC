from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.core.calibration import CalibrationDocument
from underline_retldc.gui.schema_form import SchemaForm
from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService


class SetupPage(QWidget):
    apply_requested = Signal()
    load_requested = Signal()
    save_requested = Signal()

    MOTOR_FIELDS = (
        "motor_designation",
        "diameter_mm",
        "length_mm",
        "delay_s",
        "propellant_mass_kg",
        "total_motor_mass_kg",
        "manufacturer",
    )

    def __init__(self, translations: TranslationService) -> None:
        super().__init__()
        self._translations = translations
        self._calibrations: tuple[Any, ...] = ()
        self.calibration_group = QGroupBox()
        calibration_layout = QFormLayout(self.calibration_group)
        self.calibration_label = QLabel()
        self.calibration_combo = StandardComboBox()
        self.calibration_combo.currentIndexChanged.connect(self._schema_update)
        self.calibration_form = SchemaForm(translations)
        calibration_layout.addRow(self.calibration_label, self.calibration_combo)
        calibration_layout.addRow(self.calibration_form)

        self.apply_button = QPushButton()
        self.apply_button.setObjectName("primaryButton")
        self.apply_button.clicked.connect(self.apply_requested)
        self.load_button = QPushButton()
        self.load_button.clicked.connect(self.load_requested)
        self.save_button = QPushButton()
        self.save_button.clicked.connect(self.save_requested)
        button_row = QHBoxLayout()
        button_row.addWidget(self.apply_button)
        button_row.addWidget(self.load_button)
        button_row.addWidget(self.save_button)
        calibration_layout.addRow(button_row)

        self.motor_group = QGroupBox()
        self.motor_labels: dict[str, QLabel] = {}
        self.motor_edits: dict[str, QLineEdit] = {}
        motor_layout = QFormLayout(self.motor_group)
        for field_name in self.MOTOR_FIELDS:
            label = QLabel()
            edit = QLineEdit()
            if field_name not in {"motor_designation", "manufacturer"}:
                validator = QDoubleValidator()
                validator.setBottom(0.0)
                edit.setValidator(validator)
            self.motor_labels[field_name] = label
            self.motor_edits[field_name] = edit
            motor_layout.addRow(label, edit)

        layout = QVBoxLayout(self)
        layout.addWidget(self.calibration_group)
        layout.addWidget(self.motor_group)
        layout.addStretch(1)
        self.retranslate()

    def retranslate(self) -> None:
        t = self._translations.translate
        self.calibration_group.setTitle(t("setup.calibration"))
        self.calibration_label.setText(t("setup.calibration"))
        self.calibration_form.retranslate()
        self.apply_button.setText(t("setup.apply_calibration"))
        self.load_button.setText(t("setup.load_calibration"))
        self.save_button.setText(t("setup.save_calibration"))
        self.motor_group.setTitle(t("setup.motor_metadata"))
        motor_keys = {
            "motor_designation": "motor.designation",
            "diameter_mm": "motor.diameter_mm",
            "length_mm": "motor.length_mm",
            "delay_s": "motor.delay_s",
            "propellant_mass_kg": "motor.propellant_mass_kg",
            "total_motor_mass_kg": "motor.total_motor_mass_kg",
            "manufacturer": "motor.manufacturer",
        }
        for field_name, key in motor_keys.items():
            self.motor_labels[field_name].setText(t(key))
        self._populate_calibrations(self.calibration_id())

    def set_calibrations(
        self, calibrations: tuple[Any, ...], *, preferred_id: str | None = None
    ) -> None:
        selected = preferred_id if preferred_id is not None else self.calibration_id()
        self._calibrations = calibrations
        self._populate_calibrations(selected)

    def _populate_calibrations(self, selected: str | None) -> None:
        previous_id = self.calibration_id()
        previous_values = (
            self.calibration_form.values()
            if self.calibration_form.field_names
            else {}
        )
        self.calibration_combo.blockSignals(True)
        self.calibration_combo.clear()
        for calibration in self._calibrations:
            descriptor = calibration.descriptor
            self.calibration_combo.addItem(
                self._translations.translate(
                    descriptor.translation_key or "", descriptor.name
                ),
                descriptor.plugin_id,
            )
        index = self.calibration_combo.findData(selected)
        self.calibration_combo.setCurrentIndex(max(0, index))
        self.calibration_combo.blockSignals(False)
        self._schema_update()
        if selected == previous_id:
            self.calibration_form.set_values(previous_values)

    def _schema_update(self, _index: int | None = None) -> None:
        plugin_id = self.calibration_id()
        plugin = next(
            (
                calibration
                for calibration in self._calibrations
                if calibration.descriptor.plugin_id == plugin_id
            ),
            None,
        )
        if plugin is None:
            self.calibration_form.set_schema({"type": "object", "properties": {}})
            return
        schema = dict(plugin.parameter_schema())
        raw_properties = schema.get("properties", {})
        if not isinstance(raw_properties, dict):
            raise ValueError("Calibration parameter schema properties must be an object")
        properties = {key: dict(value) for key, value in raw_properties.items()}
        properties["quantity"] = {
            "type": "string",
            "default": "force",
            "title": "Quantity",
            "x-i18n-key": "setup.quantity",
        }
        properties["unit"] = {
            "type": "string",
            "default": "N",
            "title": "Output Unit",
            "x-i18n-key": "setup.unit",
        }
        schema["properties"] = properties
        self.calibration_form.set_schema(schema)

    def calibration_id(self) -> str | None:
        return self.calibration_combo.currentData()

    def calibration_config(self) -> dict[str, Any]:
        plugin_id = self.calibration_id()
        if plugin_id is None:
            raise ValueError("Select a calibration model")
        values = self.calibration_form.values()
        quantity = str(values.pop("quantity", "")).strip()
        unit = str(values.pop("unit", "")).strip()
        if not quantity or not unit:
            raise ValueError("Calibration quantity and unit are required")
        return {
            "input_channel_id": "thrust_raw",
            "output_channel_id": "force_calibrated",
            "quantity": quantity,
            "unit": unit,
            "parameters": values,
        }

    def set_calibration_config(self, plugin_id: str, config: dict[str, Any]) -> None:
        index = self.calibration_combo.findData(plugin_id)
        if index >= 0:
            self.calibration_combo.setCurrentIndex(index)
        parameters = config.get("parameters", {})
        self._schema_update()
        self.calibration_form.set_values(
            {
                **dict(parameters),
                "quantity": config.get("quantity", "force"),
                "unit": config.get("unit", config.get("output_unit", "N")),
            }
        )

    def set_calibration_document(self, document: CalibrationDocument) -> None:
        self.set_calibration_config(
            document.model_id,
            {
                "parameters": dict(document.parameters),
                "quantity": document.quantity,
                "unit": document.output_unit,
            },
        )

    def motor_metadata(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        for field_name, edit in self.motor_edits.items():
            value = edit.text().strip()
            if not value:
                continue
            if field_name in {"motor_designation", "manufacturer"}:
                metadata[field_name] = value
            else:
                metadata[field_name] = float(value)
        return metadata

    def set_motor_metadata(self, metadata: dict[str, Any]) -> None:
        for field_name, edit in self.motor_edits.items():
            value = metadata.get(field_name)
            edit.setText("" if value is None else str(value))
