from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from underline_retldc.app.settings import SettingsService
from underline_retldc.app.version import NAME, PRODUCT_NAME, __version__
from underline_retldc.gui.main_window import MainWindow
from underline_retldc.gui.theme import Theme_Apply
from underline_retldc.i18n.service import TranslationService


def _arguments_parse(arguments: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(prog="underline-retldc")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Initialize and briefly show the GUI, then exit successfully",
    )
    parser.add_argument("--locale", choices=("zh_CN", "en_US"))
    parser.add_argument("--theme", choices=("light", "dark"))
    return parser.parse_known_args(arguments)


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    options, qt_arguments = _arguments_parse(arguments)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = QApplication([sys.argv[0], *qt_arguments])
    app.setOrganizationName(NAME)
    app.setApplicationName(PRODUCT_NAME)
    app.setApplicationVersion(__version__)
    settings = SettingsService()
    Theme_Apply(app, options.theme or settings.theme())
    locale = options.locale or settings.locale()
    translations = TranslationService(locale)
    window = MainWindow(
        translations,
        settings,
        project_root=Path(__file__).resolve().parents[3],
        initial_theme=options.theme,
    )
    window.show()
    if options.smoke_test:
        QTimer.singleShot(350, window.close)
        QTimer.singleShot(500, app.quit)
    return app.exec()
