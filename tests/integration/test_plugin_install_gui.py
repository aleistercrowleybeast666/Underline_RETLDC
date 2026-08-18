import ast
import json
import logging
from pathlib import Path

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QProgressBar,
)

from underline_retldc.app.settings import SettingsService
from underline_retldc.gui.main_window import MainWindow
from underline_retldc.gui.plugin_install_dialog import PluginInstallPreviewDialog
from underline_retldc.i18n.service import TranslationService
from underline_retldc.plugins.installer import (
    PluginInstallDecision,
    PluginPackage_Discover,
)


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def _window(tmp_path: Path, locale: str = "en_US") -> MainWindow:
    return MainWindow(
        TranslationService(locale),
        SettingsService(tmp_path / "settings.ini"),
        project_root=tmp_path,
        application_plugin_directory=tmp_path / "application_plugins",
        user_plugin_directory=tmp_path / "user_plugins",
    )


def _message_box_click(
    monkeypatch: pytest.MonkeyPatch,
    standard_button: QMessageBox.StandardButton,
    *,
    install_text: str | None = None,
    cancel_text: str | None = None,
) -> None:
    original_exec = QMessageBox.exec

    def exec_with_click(box: QMessageBox) -> int:
        install_button = box.button(QMessageBox.StandardButton.Yes)
        cancel_button = box.button(QMessageBox.StandardButton.Cancel)
        assert install_button is not None
        assert cancel_button is not None
        if install_text is not None:
            assert install_button.text() == install_text
        if cancel_text is not None:
            assert cancel_button.text() == cancel_text
        selected_button = box.button(standard_button)
        assert selected_button is not None
        QTimer.singleShot(0, selected_button.click)
        return original_exec(box)

    monkeypatch.setattr(QMessageBox, "exec", exec_with_click)


def _plugin_source_select(
    window: MainWindow,
    source: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        lambda *_args, **_kwargs: (
            window.translations.translate("plugins.install_source_directory"),
            True,
        ),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(source),
    )


def _task_wait(window: MainWindow, timeout_ms: int = 5000) -> None:
    elapsed = 0
    while window._active_task is not None and elapsed < timeout_ms:
        _application().processEvents()
        QTest.qWait(10)
        elapsed += 10
    assert window._active_task is None


def _plugin_write(directory: Path, plugin_id: str, version: str = "1.0.0") -> Path:
    directory.mkdir(parents=True)
    manifest = {
        "plugin_id": plugin_id,
        "plugin_type": "parser",
        "api_version": "1",
        "version": version,
        "entry": "plugin:ExampleParser",
        "name": plugin_id,
    }
    code = f'''
from underline_retldc.plugin_api.common import PluginDescriptor, PluginType, ProbeResult
from underline_retldc.plugin_api.parser import ParserPlugin

class ExampleParser(ParserPlugin):
    @property
    def descriptor(self):
        return PluginDescriptor(
            "{plugin_id}", PluginType.PARSER, "{version}", "1", "{plugin_id}", ""
        )
    def probe(self, source, context):
        return ProbeResult(0.0, "test")
    def config_schema(self):
        return {{"type": "object"}}
    def parse(self, source, config, context):
        raise NotImplementedError
    def validate(self, dataset):
        return []
'''
    (directory / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    (directory / "plugin.py").write_text(code, encoding="utf-8")
    return directory


def test_qt_dialog_results_never_use_python_identity() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src"
    violations: list[str] = []
    for path in source_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            if not any(isinstance(operator, (ast.Is, ast.IsNot)) for operator in node.ops):
                continue
            expression = ast.get_source_segment(source, node) or ""
            if "QMessageBox" in expression or "QDialog" in expression:
                violations.append(f"{path}:{node.lineno}: {expression}")
    assert violations == []


def test_plugin_security_confirmation_uses_clicked_standard_button(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _application()
    window = _window(tmp_path, "zh_CN")
    _message_box_click(
        monkeypatch,
        QMessageBox.StandardButton.Yes,
        install_text="安装",
        cancel_text="取消",
    )

    assert window._plugin_install_confirm()
    window.close()


def test_security_accept_starts_discovery_and_global_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _application()
    source = _plugin_write(tmp_path / "tr_t", "example.parser.confirmed")
    window = _window(tmp_path)
    window.show()
    app.processEvents()
    _plugin_source_select(window, source, monkeypatch)
    _message_box_click(
        monkeypatch,
        QMessageBox.StandardButton.Yes,
        install_text="Install",
        cancel_text="Cancel",
    )
    monkeypatch.setattr(
        PluginInstallPreviewDialog,
        "exec",
        lambda _dialog: QDialog.DialogCode.Rejected,
    )
    task_starts: list[str] = []
    original_task_start = window._task_start

    def task_start_spy(*args, **kwargs):
        task_starts.append(str(args[0]))
        return original_task_start(*args, **kwargs)

    monkeypatch.setattr(window, "_task_start", task_start_spy)

    window._plugin_install_dialog()

    assert task_starts == [window.translations.translate("plugins.task.discovery")]
    assert window._active_task is not None
    assert window.progress_bar.isVisible()
    assert window.progress_bar.maximum() == 0
    assert window.statusBar().currentMessage() == "Scanning plugins..."
    _task_wait(window)
    window.close()
    app.processEvents()


def test_security_cancel_does_not_start_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _application()
    source = _plugin_write(tmp_path / "tr_t", "example.parser.cancelled")
    window = _window(tmp_path)
    _plugin_source_select(window, source, monkeypatch)
    _message_box_click(monkeypatch, QMessageBox.StandardButton.Cancel)
    task_starts: list[str] = []
    monkeypatch.setattr(
        window,
        "_task_start",
        lambda *args, **_kwargs: task_starts.append(str(args[0])),
    )

    window._plugin_install_dialog()

    assert task_starts == []
    assert window._active_task is None
    assert not window.progress_bar.isVisible()
    window.close()


def test_confirmed_discovery_start_exception_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _application()
    source = _plugin_write(tmp_path / "tr_t", "example.parser.start_failure")
    window = _window(tmp_path)
    _plugin_source_select(window, source, monkeypatch)
    monkeypatch.setattr(window, "_plugin_install_confirm", lambda: True)
    errors: list[BaseException] = []
    monkeypatch.setattr(window, "_error_show", errors.append)

    def task_start_fail(*_args, **_kwargs):
        raise RuntimeError("simulated discovery start failure")

    monkeypatch.setattr(window, "_task_start", task_start_fail)

    with caplog.at_level(logging.ERROR, logger="underline_retldc.gui.main_window"):
        window._plugin_install_dialog()

    assert len(errors) == 1
    assert str(errors[0]) == "simulated discovery start failure"
    assert "Unable to start plugin installation discovery" in caplog.text
    window.close()


def test_plugin_preview_uses_checkboxes_and_no_private_progress_bar(
    tmp_path: Path,
) -> None:
    _application()
    plugin_id = "example.parser.preview"
    existing = _plugin_write(
        tmp_path / "user" / "parsers" / "existing",
        plugin_id,
    )
    incoming = _plugin_write(tmp_path / "incoming", plugin_id, "2.0.0")
    package = PluginPackage_Discover(
        incoming,
        tmp_path / "application",
        tmp_path / "user",
    )
    try:
        dialog = PluginInstallPreviewDialog(
            TranslationService("zh_CN"),
            package,
        )
        candidate = package.candidates[0]
        assert candidate.existing_plugins[0].path == existing.resolve()
        assert not dialog.findChildren(QProgressBar)
        assert dialog.decisions()[candidate.relative_path] is PluginInstallDecision.SKIP
        action = dialog._actions[candidate.relative_path]
        action.setCurrentIndex(action.findData(PluginInstallDecision.REPLACE.value))
        assert dialog.decisions()[candidate.relative_path] is PluginInstallDecision.REPLACE
        dialog._selection_set(False)
        assert dialog.decisions()[candidate.relative_path] is PluginInstallDecision.SKIP
        dialog.close()
    finally:
        package.close()


def test_plugin_install_reuses_main_window_global_task_progress(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _application()
    application_root = tmp_path / "application_plugins"
    user_root = tmp_path / "user_plugins"
    source = _plugin_write(
        tmp_path / "background_plugin",
        "example.parser.background",
    )
    window = MainWindow(
        TranslationService("en_US"),
        SettingsService(tmp_path / "settings.ini"),
        project_root=tmp_path,
        application_plugin_directory=application_root,
        user_plugin_directory=user_root,
    )
    monkeypatch.setattr(window, "_plugin_install_result_show", lambda _outcome: None)
    package = PluginPackage_Discover(source, application_root, user_root)
    candidate = package.candidates[0]
    window._plugin_install_start(
        package,
        {candidate.relative_path: PluginInstallDecision.INSTALL},
    )
    assert window._active_task is not None
    assert window.progress_bar.isVisibleTo(window)
    elapsed = 0
    while window._active_task is not None and elapsed < 5000:
        app.processEvents()
        QTest.qWait(10)
        elapsed += 10
    assert window._active_task is None
    assert window.registry.get("example.parser.background")
    assert not window.progress_bar.isVisible()
    window.close()
