from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from underline_retldc.gui.pages.analyze_page import AnalyzePage
from underline_retldc.gui.pages.import_page import ImportPage
from underline_retldc.gui.pages.process_page import ProcessPage
from underline_retldc.gui.pages.setup_page import SetupPage
from underline_retldc.i18n.service import TranslationService


class ProjectWorkspacePage(QWidget):
    analysis_requested = Signal()

    def __init__(
        self,
        translations: TranslationService,
        import_page: ImportPage,
        setup_page: SetupPage,
    ) -> None:
        super().__init__()
        self._translations = translations
        self.import_page = import_page
        self.setup_page = setup_page

        setup_scroll = QScrollArea()
        setup_scroll.setWidgetResizable(True)
        setup_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        setup_scroll.setWidget(setup_page)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(import_page)
        splitter.addWidget(setup_scroll)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([760, 480])

        self.analysis_button = QPushButton()
        self.analysis_button.setObjectName("primaryButton")
        self.analysis_button.clicked.connect(self.analysis_requested)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self.analysis_button)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter, 1)
        layout.addLayout(button_row)
        self.retranslate()

    def retranslate(self) -> None:
        self.import_page.retranslate()
        self.setup_page.retranslate()
        self.analysis_button.setText(
            self._translations.translate("project.enter_analysis")
        )


class ThrustAnalysisWorkspacePage(QWidget):
    def __init__(
        self,
        process_page: ProcessPage,
        analyze_page: AnalyzePage,
    ) -> None:
        super().__init__()
        self.process_page = process_page
        self.analyze_page = analyze_page
        analyze_page.setMinimumWidth(320)
        analyze_page.setMaximumWidth(430)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(process_page)
        splitter.addWidget(analyze_page)
        splitter.setStretchFactor(0, 1)
        splitter.setSizes([940, 340])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    def retranslate(self) -> None:
        self.process_page.retranslate()
        self.analyze_page.retranslate()


# Retained for extensions that imported the pre-specialization name.
AnalysisWorkspacePage = ThrustAnalysisWorkspacePage
