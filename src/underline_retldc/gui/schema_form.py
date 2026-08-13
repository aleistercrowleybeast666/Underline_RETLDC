from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService


class SchemaForm(QWidget):
    """Render the scalar subset of Plugin API JSON schemas used by the desktop UI."""

    value_changed = Signal(str, object)

    def __init__(self, translations: TranslationService) -> None:
        super().__init__()
        self._translations = translations
        self._schema: dict[str, Any] = {"type": "object", "properties": {}}
        self._editors: dict[str, QWidget] = {}
        self._labels: dict[str, QLabel] = {}
        self._properties: dict[str, dict[str, Any]] = {}
        self._layout = QFormLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(self._editors)

    def field_widget(self, field_name: str) -> QWidget:
        try:
            return self._editors[field_name]
        except KeyError as exc:
            raise KeyError(f"Schema form has no field {field_name!r}") from exc

    def set_schema(
        self,
        schema: Mapping[str, Any],
        values: Mapping[str, Any] | None = None,
    ) -> None:
        properties = schema.get("properties", {})
        if not isinstance(properties, Mapping):
            raise ValueError("Schema properties must be an object")
        self._clear()
        self._schema = dict(schema)
        self._properties = {}
        supplied = dict(values or {})
        for field_name, raw_property in properties.items():
            if not isinstance(raw_property, Mapping):
                raise ValueError(f"Schema field {field_name!r} must be an object")
            name = str(field_name)
            property_schema = dict(raw_property)
            if bool(property_schema.get("x-ui-hidden", False)):
                continue
            self._properties[name] = property_schema
            editor = self._editor_create(name, property_schema)
            editor.setObjectName(f"schemaField_{name}")
            label = QLabel()
            self._editors[name] = editor
            self._labels[name] = label
            self._layout.addRow(label, editor)
            value = supplied.get(name, property_schema.get("default"))
            if value is not None:
                self._editor_value_set(editor, value)
        self.retranslate()

    def values(self) -> dict[str, Any]:
        return {
            field_name: self._editor_value(editor)
            for field_name, editor in self._editors.items()
        }

    def set_values(self, values: Mapping[str, Any]) -> None:
        for field_name, value in values.items():
            editor = self._editors.get(str(field_name))
            if editor is not None and value is not None:
                self._editor_value_set(editor, value)

    def retranslate(self) -> None:
        for field_name, label in self._labels.items():
            property_schema = self._properties[field_name]
            title = str(property_schema.get("title", field_name))
            translation_key = str(property_schema.get("x-i18n-key", ""))
            label.setText(
                self._translations.translate(translation_key, title)
                if translation_key
                else title
            )
            editor = self._editors[field_name]
            enum_keys = property_schema.get("x-enum-i18n-keys")
            if isinstance(editor, QComboBox) and isinstance(enum_keys, Mapping):
                for index in range(editor.count()):
                    value = editor.itemData(index)
                    key = enum_keys.get(str(value))
                    editor.setItemText(
                        index,
                        self._translations.translate(str(key), str(value))
                        if key
                        else str(value),
                    )

    def _clear(self) -> None:
        while self._layout.rowCount():
            self._layout.removeRow(0)
        self._editors.clear()
        self._labels.clear()
        self._properties.clear()

    def _editor_create(self, field_name: str, schema: Mapping[str, Any]) -> QWidget:
        enum_values = schema.get("enum")
        if isinstance(enum_values, list):
            combo = StandardComboBox()
            enum_keys = schema.get("x-enum-i18n-keys")
            for value in enum_values:
                key = enum_keys.get(str(value)) if isinstance(enum_keys, Mapping) else None
                label = (
                    self._translations.translate(str(key), str(value))
                    if key
                    else str(value)
                )
                combo.addItem(label, value)
            combo.currentIndexChanged.connect(
                lambda _index, name=field_name, widget=combo: self.value_changed.emit(
                    name, widget.currentData()
                )
            )
            return combo

        field_type = schema.get("type", "string")
        if isinstance(field_type, list):
            field_type = next((item for item in field_type if item != "null"), "string")
        if field_type == "boolean":
            checkbox = QCheckBox()
            checkbox.toggled.connect(
                lambda checked, name=field_name: self.value_changed.emit(name, checked)
            )
            return checkbox
        if field_type == "integer":
            spin = QSpinBox()
            spin.setRange(
                int(schema.get("minimum", -2_147_483_648)),
                int(schema.get("maximum", 2_147_483_647)),
            )
            spin.valueChanged.connect(
                lambda value, name=field_name: self.value_changed.emit(name, value)
            )
            return spin
        if field_type == "number":
            spin = QDoubleSpinBox()
            spin.setDecimals(12)
            spin.setRange(
                float(schema.get("minimum", -1.0e100)),
                float(schema.get("maximum", 1.0e100)),
            )
            spin.setSingleStep(float(schema.get("multipleOf", 0.1)))
            spin.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
            spin.valueChanged.connect(
                lambda value, name=field_name: self.value_changed.emit(name, value)
            )
            return spin
        if field_type != "string":
            raise ValueError(
                f"Schema field {field_name!r} uses unsupported scalar type {field_type!r}"
            )
        edit = QLineEdit()
        edit.textChanged.connect(
            lambda value, name=field_name: self.value_changed.emit(name, value)
        )
        return edit

    @staticmethod
    def _editor_value(editor: QWidget) -> Any:
        if isinstance(editor, QComboBox):
            return editor.currentData()
        if isinstance(editor, QCheckBox):
            return editor.isChecked()
        if isinstance(editor, (QSpinBox, QDoubleSpinBox)):
            return editor.value()
        if isinstance(editor, QLineEdit):
            return editor.text()
        raise TypeError(f"Unsupported SchemaForm editor {type(editor).__name__}")

    @staticmethod
    def _editor_value_set(editor: QWidget, value: Any) -> None:
        if isinstance(editor, QComboBox):
            index = editor.findData(value)
            if index < 0:
                raise ValueError(f"Value {value!r} is not present in schema enum")
            editor.setCurrentIndex(index)
            return
        if isinstance(editor, QCheckBox):
            editor.setChecked(bool(value))
            return
        if isinstance(editor, QSpinBox):
            editor.setValue(int(value))
            return
        if isinstance(editor, QDoubleSpinBox):
            editor.setValue(float(value))
            return
        if isinstance(editor, QLineEdit):
            editor.setText(str(value))
            return
        raise TypeError(f"Unsupported SchemaForm editor {type(editor).__name__}")
