from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.core.regions import ActivityCandidate, RegionSelection
from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService


class TestIntervalEditor(QGroupBox):
    """Reusable editor for the one Project-level test segmentation."""

    detect_requested = Signal()
    fit_requested = Signal()
    candidate_selected = Signal(int)
    regions_changed = Signal(object)

    def __init__(
        self,
        translations: TranslationService,
        *,
        detect_translation_key: str = "process.detect_candidates",
    ) -> None:
        super().__init__()
        self._translations = translations
        self._detect_translation_key = detect_translation_key
        self._candidates: tuple[ActivityCandidate, ...] = ()
        self._syncing = False
        self._has_active = False
        self._reference_name = ""
        self._manual_modified = False

        layout = QVBoxLayout(self)
        self.reference_label = QLabel()
        self.reference_label.setWordWrap(True)
        self.modification_label = QLabel()
        self.modification_label.setWordWrap(True)
        layout.addWidget(self.reference_label)
        layout.addWidget(self.modification_label)

        buttons = QVBoxLayout()
        self.detect_button = QPushButton()
        self.detect_button.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )
        self.detect_button.clicked.connect(self.detect_requested)
        self.fit_button = QPushButton()
        self.fit_button.clicked.connect(self.fit_requested)
        buttons.addWidget(self.detect_button)
        buttons.addWidget(self.fit_button)
        layout.addLayout(buttons)

        self.candidate_combo = StandardComboBox()
        self.candidate_combo.currentIndexChanged.connect(
            self._candidate_selection_emit
        )
        layout.addWidget(self.candidate_combo)

        self.region_hint = QLabel()
        self.region_hint.setWordWrap(True)
        layout.addWidget(self.region_hint)

        region_widget = QWidget()
        region_layout = QFormLayout(region_widget)
        region_layout.setContentsMargins(0, 0, 0, 0)
        region_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        region_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        self.region_labels: dict[str, QLabel] = {}
        self.region_edits: dict[str, tuple[QDoubleSpinBox, QDoubleSpinBox]] = {}
        self.region_use_checks: dict[str, QCheckBox] = {}
        for region_name in ("pre", "active_test", "post"):
            header_widget = QWidget()
            header = QHBoxLayout(header_widget)
            header.setContentsMargins(0, 0, 0, 0)
            label = QLabel()
            label.setWordWrap(True)
            row_widget = QWidget()
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(0, 0, 0, 0)
            if region_name != "active_test":
                use_check = QCheckBox()
                use_check.setChecked(False)
                use_check.toggled.connect(self._regions_emit)
                self.region_use_checks[region_name] = use_check
                header.addWidget(use_check)
            header.addWidget(label, 1)
            start_edit = self._time_edit_create()
            end_edit = self._time_edit_create()
            start_edit.valueChanged.connect(self._regions_emit)
            end_edit.valueChanged.connect(self._regions_emit)
            row.addWidget(start_edit)
            row.addWidget(QLabel("→"))
            row.addWidget(end_edit)
            row.addStretch(1)
            self.region_labels[region_name] = label
            self.region_edits[region_name] = (start_edit, end_edit)
            region_layout.addRow(header_widget, row_widget)
        layout.addWidget(region_widget)
        self.clear()
        self.retranslate()

    @staticmethod
    def _time_edit_create() -> QDoubleSpinBox:
        edit = QDoubleSpinBox()
        edit.setDecimals(8)
        edit.setRange(-1.0e12, 1.0e12)
        edit.setMinimumWidth(90)
        edit.setMaximumWidth(115)
        edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        edit.setSuffix(" s")
        edit.setKeyboardTracking(False)
        edit.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
        return edit

    def retranslate(self) -> None:
        translate = self._translations.translate
        self.setTitle(translate("process.test_interval"))
        detect_text = translate(self._detect_translation_key)
        self.detect_button.setText(detect_text)
        self.detect_button.setToolTip(detect_text)
        self.fit_button.setText(translate("process.fit_regions"))
        self.region_hint.setText(translate("process.region_hint"))
        for key, label in self.region_labels.items():
            label.setText(translate(f"process.{key}"))
        self._candidate_labels_update()
        self._status_refresh()

    def set_detection_enabled(self, enabled: bool) -> None:
        self.detect_button.setEnabled(enabled)

    def set_reference(self, name: str, *, manually_modified: bool) -> None:
        self._reference_name = str(name)
        self._manual_modified = bool(manually_modified)
        self._status_refresh()

    def _status_refresh(self) -> None:
        translate = self._translations.translate
        self.reference_label.setText(
            translate(
                "process.segmentation_reference",
                reference=(
                    self._reference_name
                    or translate("process.segmentation_reference_none")
                ),
            )
        )
        self.modification_label.setText(
            translate(
                "process.segmentation_manual"
                if self._manual_modified
                else "process.segmentation_automatic"
            )
        )

    def set_candidates(
        self,
        candidates: list[ActivityCandidate] | tuple[ActivityCandidate, ...],
        *,
        selected_index: int = 0,
    ) -> None:
        self._candidates = tuple(candidates)
        self._candidate_labels_update(selected_index)

    def _candidate_labels_update(self, selected_index: int | None = None) -> None:
        current = (
            self.candidate_combo.currentIndex()
            if selected_index is None
            else selected_index
        )
        self.candidate_combo.blockSignals(True)
        self.candidate_combo.clear()
        if not self._candidates:
            self.candidate_combo.addItem(
                self._translations.translate("process.not_detected"),
                None,
            )
        for index, candidate in enumerate(self._candidates):
            prefix = (
                self._translations.translate("process.recommended") + " · "
                if index == 0
                else ""
            )
            self.candidate_combo.addItem(
                self._translations.translate(
                    "process.candidate_line",
                    prefix=prefix,
                    start=f"{candidate.start:.5g}",
                    end=f"{candidate.end:.5g}",
                    peak=f"{candidate.peak:.5g}",
                    score=f"{candidate.score:.4g}",
                ),
                index,
            )
        if self._candidates:
            self.candidate_combo.setCurrentIndex(
                min(max(current, 0), len(self._candidates) - 1)
            )
        else:
            self.candidate_combo.setCurrentIndex(0)
        self.candidate_combo.blockSignals(False)

    def _candidate_selection_emit(self, index: int) -> None:
        data = self.candidate_combo.itemData(index)
        if data is not None:
            self.candidate_selected.emit(int(data))

    @staticmethod
    def _selection_payload(
        regions: Mapping[str, list[float] | tuple[float, float] | None],
    ) -> dict[str, list[float] | None]:
        active = regions.get("active_test", regions.get("burn"))
        selection = RegionSelection.from_dict(
            {
                "pre": regions.get("pre"),
                "burn": active,
                "post": regions.get("post"),
            }
        )
        payload = selection.to_dict()
        return {
            "pre": payload["pre"],
            "active_test": payload["burn"],
            "post": payload["post"],
        }

    def set_regions(
        self,
        regions: Mapping[str, list[float] | tuple[float, float] | None],
        *,
        emit: bool = False,
    ) -> None:
        if not regions:
            self.clear()
            return
        payload = self._selection_payload(regions)
        self._syncing = True
        for key in ("pre", "active_test", "post"):
            value = payload[key]
            available = value is not None
            if key != "active_test":
                check = self.region_use_checks[key]
                check.setChecked(available)
            if available:
                start, end = self.region_edits[key]
                start.setValue(float(value[0]))
                end.setValue(float(value[1]))
            for edit in self.region_edits[key]:
                edit.setEnabled(available or key == "active_test")
        self._has_active = True
        self._syncing = False
        if emit:
            self._manual_modified = True
            self._status_refresh()
            self.regions_changed.emit(self.regions())

    def regions(self) -> dict[str, list[float] | None]:
        if not self._has_active:
            return {}
        payload: dict[str, list[float] | None] = {}
        for key, edits in self.region_edits.items():
            if key != "active_test" and not self.region_use_checks[key].isChecked():
                payload[key] = None
            else:
                payload[key] = [float(edits[0].value()), float(edits[1].value())]
        return self._selection_payload(payload)

    def _regions_emit(self, _value: object = None) -> None:
        if self._syncing:
            return
        self._has_active = True
        for key in ("pre", "post"):
            enabled = self.region_use_checks[key].isChecked()
            for edit in self.region_edits[key]:
                edit.setEnabled(enabled)
        try:
            payload = self.regions()
        except ValueError:
            return
        self._manual_modified = True
        self._status_refresh()
        self.regions_changed.emit(payload)

    def mark_manually_modified(self) -> None:
        self._manual_modified = True
        self._status_refresh()

    def clear(self) -> None:
        self._syncing = True
        self._has_active = False
        for key, edits in self.region_edits.items():
            if key != "active_test":
                self.region_use_checks[key].setChecked(False)
            for edit in edits:
                edit.setValue(0.0)
                edit.setEnabled(key == "active_test")
        self.region_edits["active_test"][1].setValue(1.0)
        self._syncing = False
        self._candidates = ()
        self._reference_name = ""
        self._manual_modified = False
        if hasattr(self, "candidate_combo"):
            self._candidate_labels_update()
        if hasattr(self, "reference_label"):
            self._status_refresh()
