from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService
from underline_retldc.plugin_api.exporter import EXPORTER_UI_SCHEMA_KEY

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ExportOption:
    plugin_id: str
    filename: str
    translation_key: str
    required_analysis_ids: tuple[str, ...]
    display_name: str = ""
    locale_qualified: bool = True
    requires_motor_metadata: bool = False
    supports_metric_annotation: bool = False


class ExportDialog(QDialog):
    export_requested = Signal()
    MAX_VISIBLE_EXPORT_OPTIONS = 10

    EXPORTERS: tuple[ExportOption, ...] = ()
    OUTPUT_SUFFIXES = {"zh_CN": "ZH", "en_US": "EN"}
    ENG_FIELDS = (
        "motor_designation",
        "diameter_mm",
        "length_mm",
        "delay_s",
        "propellant_mass_kg",
        "total_motor_mass_kg",
        "manufacturer",
    )

    def __init__(self, translations: TranslationService, parent=None) -> None:
        super().__init__(parent)
        self._translations = translations
        self._completed_analysis_ids: set[str] = set()
        self._options: tuple[ExportOption, ...] = ()
        self.setModal(True)
        self.resize(680, 620)

        self.destination_group = QGroupBox()
        destination_layout = QFormLayout(self.destination_group)
        self.directory_label = QLabel()
        self.directory_edit = QLineEdit()
        self.directory_button = QPushButton()
        self.directory_button.clicked.connect(self._directory_browse)
        directory_row = QHBoxLayout()
        directory_row.addWidget(self.directory_edit, 1)
        directory_row.addWidget(self.directory_button)
        destination_layout.addRow(self.directory_label, directory_row)
        self.output_language_label = QLabel()
        self.output_language_combo = StandardComboBox()
        self.output_language_combo.addItem("简体中文（_ZH）", "zh_CN")
        self.output_language_combo.addItem("English (_EN)", "en_US")
        initial_locale = (
            translations.locale if translations.locale in self.OUTPUT_SUFFIXES else "en_US"
        )
        self.output_language_combo.setCurrentIndex(
            self.output_language_combo.findData(initial_locale)
        )
        self.output_language_combo.currentIndexChanged.connect(
            self._format_labels_update
        )
        destination_layout.addRow(self.output_language_label, self.output_language_combo)

        self.formats_group = QGroupBox()
        formats_layout = QVBoxLayout(self.formats_group)
        self.availability_label = QLabel()
        self.availability_label.setObjectName("warningLabel")
        self.availability_label.setWordWrap(True)
        formats_layout.addWidget(self.availability_label)
        self.exporter_scroll = QScrollArea()
        self.exporter_scroll.setObjectName("exporterScroll")
        self.exporter_scroll.setWidgetResizable(True)
        self.exporter_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.exporter_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.exporter_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.exporter_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.exporter_list_widget = QWidget()
        self.exporter_list_widget.setObjectName("exporterList")
        self.exporter_list_layout = QVBoxLayout(self.exporter_list_widget)
        self.exporter_list_layout.setContentsMargins(0, 0, 0, 0)
        self.exporter_checks: dict[str, QCheckBox] = {}
        self.exporter_scroll.setWidget(self.exporter_list_widget)
        formats_layout.addWidget(self.exporter_scroll)
        self.annotate_metrics_check = QCheckBox()
        self.annotate_metrics_check.setChecked(True)
        formats_layout.addWidget(self.annotate_metrics_check)

        self.eng_group = QGroupBox()
        eng_layout = QFormLayout(self.eng_group)
        self.eng_labels: dict[str, QLabel] = {}
        self.eng_edits: dict[str, QLineEdit] = {}
        for field_name in self.ENG_FIELDS:
            label = QLabel()
            edit = QLineEdit()
            if field_name not in {"motor_designation", "manufacturer"}:
                validator = QDoubleValidator()
                validator.setBottom(0.0)
                edit.setValidator(validator)
            self.eng_labels[field_name] = label
            self.eng_edits[field_name] = edit
            eng_layout.addRow(label, edit)

        self.export_button = QPushButton()
        self.export_button.setObjectName("primaryButton")
        self.export_button.clicked.connect(self.export_requested)
        self.close_button = QPushButton()
        self.close_button.clicked.connect(self.reject)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self.close_button)
        button_row.addWidget(self.export_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.destination_group)
        layout.addWidget(self.formats_group)
        layout.addWidget(self.eng_group)
        layout.addStretch(1)
        layout.addLayout(button_row)
        self._export_options_set(self.EXPORTERS)
        self.retranslate()
        self.set_completed_analysis_ids(())
        self._exporter_list_size_update()
        self._eng_enabled_update(False)
        self._export_controls_refresh()

    def retranslate(self) -> None:
        t = self._translations.translate
        self.setWindowTitle(t("export.dialog_title"))
        self.destination_group.setTitle(t("export.destination"))
        self.directory_label.setText(t("export.directory"))
        self.directory_button.setText(t("common.browse"))
        self.output_language_label.setText(t("export.output_language"))
        self.formats_group.setTitle(t("export.formats"))
        self.eng_group.setTitle(t("export.motor_metadata"))
        self._format_labels_update()
        self.annotate_metrics_check.setText(t("export.annotate_metrics"))

        labels = {
            "motor_designation": "motor.designation",
            "diameter_mm": "motor.diameter_mm",
            "length_mm": "motor.length_mm",
            "delay_s": "motor.delay_s",
            "propellant_mass_kg": "motor.propellant_mass_kg",
            "total_motor_mass_kg": "motor.total_motor_mass_kg",
            "manufacturer": "motor.manufacturer",
        }
        for field_name, key in labels.items():
            self.eng_labels[field_name].setText(t(key))
        self.export_button.setText(t("export.run"))
        self.close_button.setText(t("common.cancel"))

    def set_exporters(self, exporters: tuple[Any, ...]) -> None:
        options: list[ExportOption] = []
        for exporter in exporters:
            descriptor = exporter.descriptor
            try:
                schema = exporter.config_schema()
                metadata = schema.get(EXPORTER_UI_SCHEMA_KEY)
                if not isinstance(metadata, Mapping):
                    raise ValueError(
                        f"config_schema lacks {EXPORTER_UI_SCHEMA_KEY!r} metadata"
                    )
                filename = str(metadata["filename"]).strip()
                if not filename or Path(filename).name != filename:
                    raise ValueError("export filename must be a plain filename")
                required = metadata.get("required_analysis_ids", [])
                if not isinstance(required, (list, tuple)):
                    raise ValueError("required_analysis_ids must be an array")
                options.append(
                    ExportOption(
                        plugin_id=descriptor.plugin_id,
                        filename=filename,
                        translation_key=str(
                            metadata.get("translation_key")
                            or descriptor.translation_key
                            or ""
                        ),
                        required_analysis_ids=tuple(str(item) for item in required),
                        display_name=descriptor.name,
                        locale_qualified=bool(
                            metadata.get("locale_qualified", True)
                        ),
                        requires_motor_metadata=bool(
                            metadata.get("requires_motor_metadata", False)
                        ),
                        supports_metric_annotation=bool(
                            metadata.get("supports_metric_annotation", False)
                        ),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                LOGGER.warning(
                    "Exporter %s is not desktop-selectable: %s",
                    descriptor.plugin_id,
                    exc,
                )
        self._export_options_set(tuple(options))

    def _export_options_set(self, options: tuple[ExportOption, ...]) -> None:
        previous_state = {
            plugin_id: (checkbox.isChecked(), checkbox.isEnabled())
            for plugin_id, checkbox in self.exporter_checks.items()
        }
        while self.exporter_list_layout.count():
            item = self.exporter_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.exporter_checks.clear()
        self._options = tuple(options)
        for option in self._options:
            checkbox = QCheckBox()
            checked, enabled = previous_state.get(option.plugin_id, (False, False))
            checkbox.setChecked(checked)
            checkbox.setEnabled(enabled)
            checkbox.toggled.connect(self._export_controls_refresh)
            self.exporter_checks[option.plugin_id] = checkbox
            self.exporter_list_layout.addWidget(checkbox)
        self._format_labels_update()

    def _format_labels_update(self, _index: int | None = None) -> None:
        t = self._translations.translate
        for option in self._options:
            localized_filename = self.export_filename(option.plugin_id)
            label = (
                t(option.translation_key, option.display_name)
                if option.translation_key
                else option.display_name
            )
            self.exporter_checks[option.plugin_id].setText(
                f"{label}  —  {localized_filename}"
            )
        self._availability_refresh()

    def set_completed_analysis_ids(self, analysis_ids: tuple[str, ...] | list[str]) -> None:
        self._completed_analysis_ids = set(analysis_ids)
        self._availability_refresh()

    def _exporter_list_size_update(self) -> None:
        checkboxes = tuple(self.exporter_checks.values())
        if not checkboxes:
            self.exporter_scroll.setFixedHeight(0)
            return
        row_heights = [max(checkbox.sizeHint().height(), 22) for checkbox in checkboxes]
        spacing = max(self.exporter_list_layout.spacing(), 0)
        full_height = sum(row_heights) + spacing * (len(row_heights) - 1)
        visible_count = min(len(row_heights), self.MAX_VISIBLE_EXPORT_OPTIONS)
        visible_height = (
            sum(row_heights[:visible_count]) + spacing * max(visible_count - 1, 0)
        )
        self.exporter_list_widget.setMinimumHeight(full_height)
        self.exporter_scroll.setFixedHeight(visible_height)

    def _availability_refresh(self) -> None:
        if not hasattr(self, "exporter_checks"):
            return
        t = self._translations.translate
        for option in self._options:
            checkbox = self.exporter_checks[option.plugin_id]
            was_enabled = checkbox.isEnabled()
            missing = tuple(
                analysis_id
                for analysis_id in option.required_analysis_ids
                if analysis_id not in self._completed_analysis_ids
            )
            checkbox.setEnabled(not missing)
            if missing:
                checkbox.setChecked(False)
                checkbox.setToolTip(t("export.requires_thrust_analysis"))
            else:
                if not was_enabled:
                    checkbox.setChecked(True)
                checkbox.setToolTip("")
        any_ready = any(checkbox.isEnabled() for checkbox in self.exporter_checks.values())
        if not self._options:
            availability_key = "export.no_exporters"
        elif any_ready:
            availability_key = "export.analysis_ready_hint"
        else:
            availability_key = "export.analysis_required_hint"
        self.availability_label.setText(t(availability_key))
        annotation_options = {
            option.plugin_id
            for option in self._options
            if option.supports_metric_annotation
        }
        self.annotate_metrics_check.setVisible(bool(annotation_options))
        self.annotate_metrics_check.setEnabled(
            any(
                self.exporter_checks[plugin_id].isEnabled()
                for plugin_id in annotation_options
            )
        )
        self._export_controls_refresh()
        self._exporter_list_size_update()

    def _export_controls_refresh(self, _checked: bool | None = None) -> None:
        if hasattr(self, "export_button"):
            self.export_button.setEnabled(bool(self.selected_exporter_ids()))
        if hasattr(self, "eng_group"):
            motor_options = {
                option.plugin_id
                for option in self._options
                if option.requires_motor_metadata
            }
            self._eng_enabled_update(
                any(
                    self.exporter_checks[plugin_id].isChecked()
                    for plugin_id in motor_options
                )
            )

    def required_analysis_ids(self, plugin_id: str) -> tuple[str, ...]:
        try:
            return next(
                option.required_analysis_ids
                for option in self._options
                if option.plugin_id == plugin_id
            )
        except StopIteration as exc:
            raise KeyError(f"Unknown export plugin ID {plugin_id!r}") from exc

    def missing_analysis_ids(self, plugin_id: str) -> tuple[str, ...]:
        return tuple(
            analysis_id
            for analysis_id in self.required_analysis_ids(plugin_id)
            if analysis_id not in self._completed_analysis_ids
        )

    def output_directory(self) -> Path:
        value = self.directory_edit.text().strip()
        if not value:
            raise ValueError("Select an export directory")
        return Path(value)

    def set_output_directory(self, directory: Path) -> None:
        self.directory_edit.setText(str(directory))

    def selected_exporter_ids(self) -> tuple[str, ...]:
        return tuple(
            plugin_id
            for plugin_id, checkbox in self.exporter_checks.items()
            if checkbox.isChecked()
        )

    def set_selected_exporter_ids(self, plugin_ids: list[str] | tuple[str, ...]) -> None:
        selected = set(plugin_ids)
        for plugin_id, checkbox in self.exporter_checks.items():
            checkbox.setChecked(plugin_id in selected and checkbox.isEnabled())

    def set_motor_metadata(self, metadata: dict[str, Any]) -> None:
        for field_name, edit in self.eng_edits.items():
            value = metadata.get(field_name)
            edit.setText("" if value is None else str(value))

    def motor_metadata(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        for field_name, edit in self.eng_edits.items():
            value = edit.text().strip()
            if not value:
                continue
            if field_name in {"motor_designation", "manufacturer"}:
                metadata[field_name] = value
            else:
                metadata[field_name] = float(value)
        return metadata

    def annotate_metrics(self) -> bool:
        return self.annotate_metrics_check.isChecked()

    def output_locale(self) -> str:
        locale = str(self.output_language_combo.currentData())
        return locale if locale in self.OUTPUT_SUFFIXES else "en_US"

    def set_output_locale(self, locale: str) -> None:
        index = self.output_language_combo.findData(locale)
        if index < 0:
            index = self.output_language_combo.findData("en_US")
        self.output_language_combo.setCurrentIndex(index)

    def export_filename(self, plugin_id: str) -> str:
        try:
            option = next(
                option
                for option in self._options
                if option.plugin_id == plugin_id
            )
        except StopIteration as exc:
            raise KeyError(f"Unknown export plugin ID {plugin_id!r}") from exc
        if not option.locale_qualified:
            return option.filename
        path = Path(option.filename)
        suffix = self.OUTPUT_SUFFIXES[self.output_locale()]
        return f"{path.stem}_{suffix}{path.suffix}"

    def _directory_browse(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            self._translations.translate("export.destination"),
            self.directory_edit.text(),
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if selected:
            self.directory_edit.setText(selected)

    def _eng_enabled_update(self, enabled: bool) -> None:
        self.eng_group.setEnabled(enabled)
        self.eng_group.setVisible(enabled)


# Retained as a source-compatible name for extensions that imported the old widget.
ExportPage = ExportDialog
