from pathlib import Path

import pytest

from underline_retldc.app.export_batch import ExportBatch_Stage
from underline_retldc.plugin_api.common import TaskCancelledError, TaskContext


def test_cancel_after_first_export_preserves_existing_outputs(tmp_path):
    previous = tmp_path / "first.csv"
    previous.write_bytes(b"previous")
    context = TaskContext()
    with (
        pytest.raises(TaskCancelledError),
        ExportBatch_Stage(tmp_path, ("first.csv", "second.txt"), context) as stage,
    ):
        (stage / "first.csv").write_bytes(b"replacement")
        context.cancellation_event.set()
    assert previous.read_bytes() == b"previous"
    assert list(tmp_path.iterdir()) == [previous]


def test_failed_second_publication_restores_first(tmp_path, monkeypatch):
    from underline_retldc.app import export_batch

    first = tmp_path / "first.csv"
    first.write_bytes(b"previous")
    failing_target = tmp_path / "second.txt"
    rename = export_batch.os.replace

    def fail_second(source, destination):
        if Path(destination) == failing_target:
            raise PermissionError("locked")
        rename(source, destination)

    monkeypatch.setattr(export_batch.os, "replace", fail_second)
    with (
        pytest.raises(PermissionError, match="locked"),
        ExportBatch_Stage(tmp_path, ("first.csv", "second.txt"), TaskContext()) as stage,
    ):
        (stage / "first.csv").write_bytes(b"replacement")
        (stage / "second.txt").write_bytes(b"other")
    assert list(tmp_path.iterdir()) == [first]
    assert first.read_bytes() == b"previous"
