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
from underline_retldc.core.channel import Channel
from underline_retldc.core.pipeline import Calibration_OutputChannelId
from underline_retldc.core.units import (
    Quantity_KnownIds,
    Unit_ChoicesForQuantity,
    Unit_DisplayUnitResolve,
)
from underline_retldc.gui.schema_form import SchemaForm
from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService


class SetupPage(QWidget):
    apply_requested = Signal()
    load_requested = Signal()
    save_requested = Signal()
    channel_changed = Signal(str)

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
        self._channels: dict[str, Channel] = {}
        self._display_preferences: dict[str, str] = {}

        self.channel_group = QGroupBox()
        channel_layout = QFormLayout(self.channel_group)
        self.channel_label = QLabel()
        self.channel_combo = StandardComboBox()
        self.channel_combo.currentIndexChanged.connect(self._channel_update)
        self.quantity_label = QLabel()
        self.quantity_combo = StandardComboBox()
        self.quantity_combo.setEditable(True)
        self.data_unit_label = QLabel()
        self.data_unit_combo = StandardComboBox()
        self.data_unit_combo.setEditable(True)
        self.unit_source_label = QLabel()
        self.unit_source_value = QLabel("—")
        self.display_unit_label = QLabel()
        self.display_unit_combo = StandardComboBox()
        self.display_unit_combo.setEditable(True)
        for quantity in Quantity_KnownIds():
            self.quantity_combo.addItem(quantity, quantity)
        self.quantity_combo.currentTextChanged.connect(self._unit_choices_update)
        self.semantic_role_label = QLabel()
        self.semantic_role_edit = QLineEdit()
        channel_layout.addRow(self.channel_label, self.channel_combo)
        channel_layout.addRow(self.quantity_label, self.quantity_combo)
        channel_layout.addRow(self.data_unit_label, self.data_unit_combo)
        channel_layout.addRow(self.unit_source_label, self.unit_source_value)
        channel_layout.addRow(self.display_unit_label, self.display_unit_combo)
        channel_layout.addRow(self.semantic_role_label, self.semantic_role_edit)

        self.calibration_group = QGroupBox()
        calibration_layout = QFormLayout(self.calibration_group)
        self.calibration_label = QLabel()
        self.calibration_combo = StandardComboBox()
        self.calibration_combo.currentIndexChanged.connect(self._schema_update)
        self.identity_notice = QLabel()
        self.identity_notice.setObjectName("warningLabel")
        self.identity_notice.setWordWrap(True)
        self.calibration_form = SchemaForm(translations)
        calibration_layout.addRow(self.calibration_label, self.calibration_combo)
        calibration_layout.addRow(self.identity_notice)
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

        self.advanced_button = QPushButton()
        self.advanced_button.setCheckable(True)
        self.advanced_button.setChecked(False)
        self.advanced_container = QWidget()
        advanced_layout = QVBoxLayout(self.advanced_container)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.addWidget(self.channel_group)
        advanced_layout.addWidget(self.calibration_group)
        self.advanced_container.hide()
        self.advanced_button.toggled.connect(self._advanced_visibility_update)

        layout = QVBoxLayout(self)
        layout.addWidget(self.motor_group)
        layout.addWidget(self.advanced_button)
        layout.addWidget(self.advanced_container)
        layout.addStretch(1)
        self.retranslate()

    def _advanced_visibility_update(self, visible: bool) -> None:
        self.advanced_container.setVisible(bool(visible))
        self._advanced_button_text_update()

    def _advanced_button_text_update(self) -> None:
        key = (
            "setup.advanced_hide"
            if self.advanced_button.isChecked()
            else "setup.advanced_show"
        )
        self.advanced_button.setText(self._translations.translate(key))

    def retranslate(self) -> None:
        t = self._translations.translate
        self.channel_group.setTitle(t("setup.channel_interpretation"))
        self.channel_label.setText(t("setup.channel"))
        self.quantity_label.setText(t("setup.quantity"))
        self.data_unit_label.setText(t("setup.data_unit"))
        self.unit_source_label.setText(t("setup.unit_source"))
        self.display_unit_label.setText(t("setup.display_unit"))
        self.semantic_role_label.setText(t("setup.semantic_role"))
        self.calibration_group.setTitle(t("setup.calibration"))
        self.calibration_label.setText(t("setup.calibration"))
        self.identity_notice.setText(t("setup.identity_notice"))
        self.calibration_form.retranslate()
        self.apply_button.setText(t("setup.apply_calibration"))
        self.load_button.setText(t("setup.load_calibration"))
        self.save_button.setText(t("setup.save_calibration"))
        self.motor_group.setTitle(t("setup.motor_metadata"))
        self._advanced_button_text_update()
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

    def set_channels(
        self,
        channels: tuple[Channel, ...] | list[Channel],
        *,
        preferred_id: str | None = None,
    ) -> None:
        selected = preferred_id or self.selected_channel_id()
        self._channels = {channel.id: channel for channel in channels}
        self.channel_combo.blockSignals(True)
        self.channel_combo.clear()
        for channel in channels:
            self.channel_combo.addItem(str(channel.name), channel.id)
        index = self.channel_combo.findData(selected)
        self.channel_combo.setCurrentIndex(max(0, index))
        self.channel_combo.blockSignals(False)
        self._channel_update()

    def selected_channel_id(self) -> str | None:
        value = self.channel_combo.currentData()
        return str(value) if value else None

    def selected_channel(self) -> Channel | None:
        channel_id = self.selected_channel_id()
        return self._channels.get(channel_id) if channel_id is not None else None

    @staticmethod
    def _combo_text_set(combo: StandardComboBox, value: str) -> None:
        index = combo.findText(value)
        if index < 0:
            combo.addItem(value, value)
            index = combo.findText(value)
        combo.setCurrentIndex(index)

    def _channel_update(self, _index: int | None = None) -> None:
        channel = self.selected_channel()
        if channel is None:
            self.unit_source_value.setText("—")
            return
        for combo in (self.quantity_combo, self.data_unit_combo, self.display_unit_combo):
            combo.blockSignals(True)
        self._combo_text_set(self.quantity_combo, channel.quantity)
        self._unit_choices_update(channel.quantity)
        self._combo_text_set(self.data_unit_combo, channel.data_unit)
        self._combo_text_set(
            self.display_unit_combo,
            channel.display_unit
            or Unit_DisplayUnitResolve(
                channel.quantity,
                channel.data_unit,
                preferences=self._display_preferences,
            ),
        )
        for combo in (self.quantity_combo, self.data_unit_combo, self.display_unit_combo):
            combo.blockSignals(False)
        self.unit_source_value.setText(
            self._translations.translate(
                f"unit_source.{channel.unit_source.value}",
                channel.unit_source.value,
            )
        )
        self.semantic_role_edit.setText(channel.semantic_role or "")
        self._calibration_output_defaults_update()
        self.channel_changed.emit(channel.id)

    def _unit_choices_update(self, quantity: str) -> None:
        data_value = self.data_unit_combo.currentText().strip()
        display_value = self.display_unit_combo.currentText().strip()
        choices = Unit_ChoicesForQuantity(quantity)
        for combo, current in (
            (self.data_unit_combo, data_value),
            (self.display_unit_combo, display_value),
        ):
            combo.blockSignals(True)
            combo.clear()
            for unit in choices:
                combo.addItem(unit, unit)
            if current:
                self._combo_text_set(combo, current)
            combo.blockSignals(False)

    def _calibration_output_defaults_update(self) -> None:
        channel = self.selected_channel()
        if channel is None or not self.calibration_form.field_names:
            return
        if self.calibration_id() == "builtin.calibration.identity":
            self.calibration_form.set_values(
                {
                    "quantity": self.quantity_combo.currentText().strip(),
                    "unit": self.data_unit_combo.currentText().strip(),
                }
            )

    def channel_interpretation(self) -> dict[str, Any]:
        channel = self.selected_channel()
        if channel is None:
            raise ValueError("Select a Channel before editing its advanced settings")
        quantity = self.quantity_combo.currentText().strip()
        data_unit = self.data_unit_combo.currentText().strip()
        display_unit = self.display_unit_combo.currentText().strip()
        if not quantity or not data_unit or not display_unit:
            raise ValueError("Channel Quantity, Data Unit, and Display Unit are required")
        return {
            "channel_id": channel.id,
            "quantity": quantity,
            "data_unit": data_unit,
            "display_unit": display_unit,
            "semantic_role": self.semantic_role_edit.text().strip() or None,
        }

    def set_calibrations(
        self, calibrations: tuple[Any, ...], *, preferred_id: str | None = None
    ) -> None:
        selected = preferred_id if preferred_id is not None else self.calibration_id()
        self._calibrations = calibrations
        self._populate_calibrations(selected)

    def set_display_preferences(self, preferences: dict[str, str]) -> None:
        self._display_preferences = dict(preferences)
        self._channel_update()

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
            self.identity_notice.setVisible(False)
            return
        self.identity_notice.setVisible(
            plugin.descriptor.plugin_id == "builtin.calibration.identity"
        )
        schema = dict(plugin.parameter_schema())
        raw_properties = schema.get("properties", {})
        if not isinstance(raw_properties, dict):
            raise ValueError("Calibration parameter schema properties must be an object")
        properties = {
            ("quantity" if key == "output_quantity" else "unit" if key == "output_unit" else key):
            dict(value)
            for key, value in raw_properties.items()
        }
        properties.setdefault(
            "quantity",
            {
                "type": "string",
                "default": "force",
                "title": "Quantity",
                "x-i18n-key": "setup.quantity",
            },
        )
        properties.setdefault(
            "unit",
            {
                "type": "string",
                "default": "N",
                "title": "Output Unit",
                "x-i18n-key": "setup.unit",
            },
        )
        schema["properties"] = properties
        self.calibration_form.set_schema(schema)
        self._calibration_output_defaults_update()

    def calibration_id(self) -> str | None:
        return self.calibration_combo.currentData()

    def calibration_config(self) -> dict[str, Any]:
        plugin_id = self.calibration_id()
        if plugin_id is None:
            raise ValueError("Select a calibration model")
        values = self.calibration_form.values()
        quantity = str(values.pop("quantity", "")).strip()
        unit = str(values.pop("unit", "")).strip()
        values.pop("output_quantity", None)
        values.pop("output_unit", None)
        interpretation = self.channel_interpretation()
        if plugin_id == "builtin.calibration.identity":
            quantity = str(interpretation["quantity"])
            unit = str(interpretation["data_unit"])
        if not quantity or not unit:
            raise ValueError("Calibration quantity and unit are required")
        channel = self.selected_channel()
        input_channel_id = str(interpretation["channel_id"])
        if channel is None:
            raise ValueError("Select a Channel before configuring Calibration")
        output_channel_id = Calibration_OutputChannelId(channel)
        return {
            "input_channel_id": input_channel_id,
            "output_channel_id": output_channel_id,
            "quantity": quantity,
            "unit": unit,
            "parameters": values,
            "data_quantity": interpretation["quantity"],
            "data_unit": interpretation["data_unit"],
            "display_unit": interpretation["display_unit"],
            "semantic_role": interpretation["semantic_role"],
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
        channel = self.selected_channel()
        if channel is not None and config.get("input_channel_id") in (None, channel.id):
            quantity = str(config.get("data_quantity", channel.quantity))
            data_unit = str(config.get("data_unit", channel.data_unit))
            display_unit = str(
                config.get(
                    "display_unit",
                    channel.display_unit
                    or Unit_DisplayUnitResolve(
                        quantity,
                        data_unit,
                        preferences=self._display_preferences,
                    ),
                )
            )
            self._combo_text_set(self.quantity_combo, quantity)
            self._unit_choices_update(quantity)
            self._combo_text_set(self.data_unit_combo, data_unit)
            self._combo_text_set(self.display_unit_combo, display_unit)
            self.semantic_role_edit.setText(
                str(config.get("semantic_role", channel.semantic_role or ""))
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
