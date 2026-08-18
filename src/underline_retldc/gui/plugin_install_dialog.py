from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.gui.widgets import StandardComboBox
from underline_retldc.i18n.service import TranslationService
from underline_retldc.plugins.installer import (
    PluginCandidateStatus,
    PluginInstallDecision,
    PluginInstallPackage,
)


class PluginInstallPreviewDialog(QDialog):
    def __init__(
        self,
        translations: TranslationService,
        package: PluginInstallPackage,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._translations = translations
        self._package = package
        self._checks: dict[str, QCheckBox] = {}
        self._actions: dict[str, StandardComboBox] = {}
        self.setModal(True)
        self.resize(980, 540)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.source_label = QLabel(str(package.source))
        self.source_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.source_label.setObjectName("secondaryLabel")
        self.table = QTableWidget(0, 8)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        for column in range(5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)

        self.issues_label = QLabel()
        self.issues_label.setWordWrap(True)
        self.issues_label.setObjectName("warningLabel")

        self.select_all_button = QPushButton()
        self.select_all_button.clicked.connect(lambda: self._selection_set(True))
        self.select_none_button = QPushButton()
        self.select_none_button.clicked.connect(lambda: self._selection_set(False))
        selection_row = QHBoxLayout()
        selection_row.addWidget(self.select_all_button)
        selection_row.addWidget(self.select_none_button)
        selection_row.addStretch(1)

        self.cancel_button = QPushButton()
        self.cancel_button.clicked.connect(self.reject)
        self.install_button = QPushButton()
        self.install_button.setObjectName("primaryButton")
        self.install_button.clicked.connect(self.accept)
        action_row = QHBoxLayout()
        action_row.addStretch(1)
        action_row.addWidget(self.cancel_button)
        action_row.addWidget(self.install_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.source_label)
        layout.addLayout(selection_row)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.issues_label)
        layout.addLayout(action_row)

        self._rows_populate()
        self.retranslate()
        self._selection_update()

    def retranslate(self) -> None:
        t = self._translations.translate
        self.setWindowTitle(t("plugins.preview_title"))
        installable_count = sum(
            candidate.installable for candidate in self._package.candidates
        )
        self.summary_label.setText(
            t("plugins.detected_count", count=installable_count)
        )
        self.select_all_button.setText(t("plugins.select_all"))
        self.select_none_button.setText(t("plugins.select_none"))
        self.cancel_button.setText(t("common.cancel"))
        self.install_button.setText(t("plugins.install_selected"))
        self.table.setHorizontalHeaderLabels(
            [
                t("plugins.preview.select"),
                t("plugins.column.name"),
                t("plugins.column.type"),
                t("plugins.column.id"),
                t("plugins.column.version"),
                t("plugins.preview.path"),
                t("plugins.preview.existing_path"),
                t("plugins.preview.action"),
            ]
        )
        for candidate in self._package.candidates:
            action = self._actions.get(candidate.relative_path)
            if action is None:
                continue
            current = action.currentData()
            action.setItemText(0, t("plugins.replace"))
            action.setItemText(1, t("plugins.skip"))
            index = action.findData(current)
            if index >= 0:
                action.setCurrentIndex(index)
        self._status_cells_update()
        issue_lines = [
            t(
                "plugins.preview.issue",
                stage=issue.stage.value.upper(),
                path=str(issue.manifest_path or issue.source),
                reason=issue.reason,
            )
            for issue in self._package.issues
        ]
        self.issues_label.setText("\n".join(issue_lines))
        self.issues_label.setVisible(bool(issue_lines))

    def decisions(self) -> dict[str, PluginInstallDecision]:
        decisions: dict[str, PluginInstallDecision] = {}
        for candidate in self._package.candidates:
            check = self._checks[candidate.relative_path]
            if not check.isEnabled() or not check.isChecked():
                decisions[candidate.relative_path] = PluginInstallDecision.SKIP
                continue
            action = self._actions.get(candidate.relative_path)
            if action is not None:
                decisions[candidate.relative_path] = PluginInstallDecision(
                    str(action.currentData())
                )
            else:
                decisions[candidate.relative_path] = PluginInstallDecision.INSTALL
        return decisions

    def _rows_populate(self) -> None:
        self.table.setRowCount(len(self._package.candidates))
        for row, candidate in enumerate(self._package.candidates):
            check = QCheckBox()
            check.setChecked(candidate.installable)
            check.setEnabled(candidate.installable)
            check.stateChanged.connect(self._selection_update)
            check_container = QWidget()
            check_layout = QHBoxLayout(check_container)
            check_layout.setContentsMargins(0, 0, 0, 0)
            check_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            check_layout.addWidget(check)
            self.table.setCellWidget(row, 0, check_container)
            self._checks[candidate.relative_path] = check
            values = (
                candidate.name,
                self._translations.translate(
                    f"plugin.type.{candidate.plugin_type.value}",
                    candidate.plugin_type.value,
                ),
                candidate.plugin_id,
                candidate.version,
                candidate.relative_path,
            )
            for column, value in enumerate(values, start=1):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
            existing_paths = "\n".join(
                str(existing.path) for existing in candidate.existing_plugins
            )
            self.table.setItem(row, 6, QTableWidgetItem(existing_paths or "—"))
            if candidate.conflict_status is PluginCandidateStatus.EXISTING:
                action = StandardComboBox()
                action.addItem("", PluginInstallDecision.REPLACE.value)
                action.addItem("", PluginInstallDecision.SKIP.value)
                action.setCurrentIndex(1)
                action.currentIndexChanged.connect(self._selection_update)
                self.table.setCellWidget(row, 7, action)
                self._actions[candidate.relative_path] = action
            else:
                self.table.setItem(row, 7, QTableWidgetItem(""))

    def _status_cells_update(self) -> None:
        t = self._translations.translate
        for row, candidate in enumerate(self._package.candidates):
            action = self._actions.get(candidate.relative_path)
            if action is not None:
                existing = candidate.existing_plugins[0]
                action.setToolTip(
                    t(
                        "plugins.conflict_tooltip",
                        current=existing.manifest.version,
                        incoming=candidate.version,
                        path=str(existing.path),
                    )
                )
                continue
            status_key = f"plugins.candidate_status.{candidate.conflict_status.value}"
            item = self.table.item(row, 7)
            if item is not None:
                item.setText(t(status_key, candidate.conflict_status.value))
                if candidate.nested_descendants:
                    item.setToolTip("\n".join(candidate.nested_descendants))

    def _selection_set(self, checked: bool) -> None:
        for check in self._checks.values():
            if check.isEnabled():
                check.setChecked(checked)
        self._selection_update()

    def _selection_update(self) -> None:
        self.install_button.setEnabled(
            any(
                decision is not PluginInstallDecision.SKIP
                for decision in self.decisions().values()
            )
        )
