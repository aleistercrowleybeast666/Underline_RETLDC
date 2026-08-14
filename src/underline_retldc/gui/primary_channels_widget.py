from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.core.primary_channels import PrimaryChannels_Candidates
from underline_retldc.core.project_data import (
    ChannelReference,
    PrimaryChannelBindings,
    ProjectData,
)
from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService


class PrimaryChannelsWidget(QWidget):
    bindings_changed = Signal(object)

    def __init__(self, translations: TranslationService) -> None:
        super().__init__()
        self._translations = translations
        self._project_data = ProjectData()
        self._references: dict[str, ChannelReference] = {}
        self._syncing = False

        self.group = QGroupBox()
        form = QFormLayout(self.group)
        self.thrust_label = QLabel()
        self.thrust_combo = StandardComboBox()
        self.thrust_combo.currentIndexChanged.connect(self._selection_changed)
        self.pressure_label = QLabel()
        self.pressure_combo = StandardComboBox()
        self.pressure_combo.currentIndexChanged.connect(self._selection_changed)
        self.temperature_label = QLabel()
        self.temperature_summary = QLabel()
        self.temperature_list = QListWidget()
        self.temperature_list.setMaximumHeight(108)
        self.temperature_list.itemChanged.connect(self._selection_changed)
        temperature_box = QWidget()
        temperature_layout = QVBoxLayout(temperature_box)
        temperature_layout.setContentsMargins(0, 0, 0, 0)
        temperature_layout.addWidget(self.temperature_summary)
        temperature_layout.addWidget(self.temperature_list)
        form.addRow(self.thrust_label, self.thrust_combo)
        form.addRow(self.pressure_label, self.pressure_combo)
        form.addRow(self.temperature_label, temperature_box)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.group)
        self.retranslate()

    def retranslate(self) -> None:
        t = self._translations.translate
        self.group.setTitle(t("primary_channels.title"))
        self.thrust_label.setText(t("primary_channels.thrust"))
        self.pressure_label.setText(t("primary_channels.pressure"))
        self.temperature_label.setText(t("primary_channels.temperature"))
        self.set_project_data(self._project_data, self.bindings())

    def _reference_label(self, reference: ChannelReference) -> str:
        source = self._project_data.sources[reference.source_id]
        channel = self._project_data.channel(reference)
        return f"{source.path.name} · {channel.name} [{channel.data_unit}]"

    def _combo_populate(
        self,
        combo: StandardComboBox,
        candidates: tuple[ChannelReference, ...],
        selected: ChannelReference | None,
    ) -> None:
        combo.clear()
        combo.addItem(self._translations.translate("primary_channels.none"), None)
        for reference in candidates:
            combo.addItem(self._reference_label(reference), reference.stable_id)
        index = combo.findData(selected.stable_id if selected is not None else None)
        combo.setCurrentIndex(max(0, index))

    def set_project_data(
        self,
        project_data: ProjectData,
        bindings: PrimaryChannelBindings | None = None,
    ) -> None:
        selected = bindings or project_data.primary_channels
        self._project_data = project_data
        self._references = {
            reference.stable_id: reference
            for reference in project_data.channel_references()
        }
        self._syncing = True
        self._combo_populate(
            self.thrust_combo,
            PrimaryChannels_Candidates(project_data, dimension="force"),
            selected.thrust,
        )
        self._combo_populate(
            self.pressure_combo,
            PrimaryChannels_Candidates(project_data, dimension="pressure"),
            selected.chamber_pressure,
        )
        self.temperature_list.clear()
        selected_temperature_ids = {
            item.stable_id for item in selected.temperature_channels
        }
        for reference in PrimaryChannels_Candidates(
            project_data,
            dimension="temperature",
        ):
            item = QListWidgetItem(self._reference_label(reference))
            item.setData(Qt.ItemDataRole.UserRole, reference.stable_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if reference.stable_id in selected_temperature_ids
                else Qt.CheckState.Unchecked
            )
            self.temperature_list.addItem(item)
        self._syncing = False
        self._temperature_summary_update()

    def bindings(self) -> PrimaryChannelBindings:
        temperatures = tuple(
            self._references[
                str(self.temperature_list.item(index).data(Qt.ItemDataRole.UserRole))
            ]
            for index in range(self.temperature_list.count())
            if self.temperature_list.item(index).checkState()
            == Qt.CheckState.Checked
        )
        thrust_id = self.thrust_combo.currentData()
        pressure_id = self.pressure_combo.currentData()
        return PrimaryChannelBindings(
            thrust=self._references.get(str(thrust_id)) if thrust_id else None,
            chamber_pressure=(
                self._references.get(str(pressure_id)) if pressure_id else None
            ),
            temperature_channels=temperatures,
        )

    def _temperature_summary_update(self) -> None:
        count = len(self.bindings().temperature_channels)
        self.temperature_summary.setText(
            self._translations.translate(
                "primary_channels.temperature_count",
                count=count,
            )
        )

    def _selection_changed(self, _value: object = None) -> None:
        self._temperature_summary_update()
        if not self._syncing:
            self.bindings_changed.emit(self.bindings())
