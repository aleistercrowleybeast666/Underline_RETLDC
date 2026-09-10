from __future__ import annotations

import argparse
import logging
import sys
import traceback
from contextlib import suppress
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from underline_retldc.app.settings import SettingsService
from underline_retldc.app.version import NAME, PRODUCT_NAME, __version__
from underline_retldc.core.registry import PluginLoadResult
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


def Application_ProjectRoot() -> Path:
    if bool(getattr(sys, "frozen", False)):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def _smoke_failure_write(details: str) -> None:
    if not bool(getattr(sys, "frozen", False)):
        return
    destination = Application_ProjectRoot() / "smoke-test-error.txt"
    try:
        destination.write_text(str(details).rstrip() + "\n", encoding="utf-8")
    except OSError:
        logging.getLogger(__name__).exception(
            "Unable to write smoke-test failure report to %s",
            destination,
        )


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
    if options.smoke_test and bool(getattr(sys, "frozen", False)):
        with suppress(OSError):
            (Application_ProjectRoot() / "smoke-test-error.txt").unlink(
                missing_ok=True
            )
    try:
        window = MainWindow(
            translations,
            settings,
            project_root=Application_ProjectRoot(),
            initial_theme=options.theme,
        )
    except BaseException:
        if options.smoke_test:
            _smoke_failure_write(traceback.format_exc())
            return 1
        raise
    window.show()
    if options.smoke_test:
        bundled_records = tuple(
            record
            for record in window.registry.records
            if record.source_kind == "bundled"
        )
        failed_records = tuple(
            record
            for record in bundled_records
            if record.result is not PluginLoadResult.LOADED
        )
        smoke_exit_code = 0
        if not bundled_records:
            logging.getLogger(__name__).error(
                "Smoke test found no bundled plugins below %s",
                window.application_plugin_directory,
            )
            smoke_exit_code = 1
        elif failed_records:
            logging.getLogger(__name__).error(
                "Smoke test found failed bundled plugins: %s",
                ", ".join(
                    f"{record.plugin_id} ({record.result.value})"
                    for record in failed_records
                ),
            )
            smoke_exit_code = 1
        if smoke_exit_code:
            lines = [
                "Underline_RETLDC packaged smoke test failed.",
                f"Plugin root: {window.application_plugin_directory}",
                f"Bundled records: {len(bundled_records)}",
            ]
            for record in failed_records:
                lines.append(
                    f"{record.plugin_id}: {record.result.value} ({record.source})"
                )
                lines.extend(
                    f"  {diagnostic.code}: {diagnostic.message}"
                    for diagnostic in record.diagnostics
                )
            _smoke_failure_write("\n".join(lines))
        QTimer.singleShot(500, lambda: app.exit(smoke_exit_code))
    return app.exec()
