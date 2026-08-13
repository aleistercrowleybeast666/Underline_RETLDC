from pathlib import Path

import numpy as np
import pytest

from underline_retldc.core.data_quality import Dataset_QualityInspect
from underline_retldc.plugin_api.common import ProbeContext, TaskContext


def test_tr_f_valid_fixture_is_parsed_without_calibration(bundled_registry) -> None:
    parser = bundled_registry.get("builtin.parser.tr_f")
    source = Path(__file__).parents[1] / "data" / "valid_tr_f.txt"
    result = parser.parse(source, {}, TaskContext())

    assert result.dataset.sample_count == 4
    assert result.dataset.time_unit == "s"
    assert result.dataset.channel("thrust_raw").unit == "raw"
    np.testing.assert_allclose(result.dataset.time, [0.0, 0.01, 0.02, 0.03])
    np.testing.assert_allclose(result.dataset.channel("thrust_raw").values, [0, 2, 5, 0])
    assert not result.dataset.time.flags.writeable
    assert not result.dataset.channel("thrust_raw").values.flags.writeable


def test_tr_f_probe_is_bounded_and_confident(bundled_registry) -> None:
    parser = bundled_registry.get("builtin.parser.tr_f")
    source = Path(__file__).parents[1] / "data" / "valid_tr_f.txt"
    probe = parser.probe(source, ProbeContext(max_bytes=128, max_records=4))
    assert probe.confidence > 0.9
    assert "numeric two-column" in probe.reason


def test_tr_f_empty_file_fails(tmp_path: Path, bundled_registry) -> None:
    parser = bundled_registry.get("builtin.parser.tr_f")
    source = tmp_path / "empty.txt"
    source.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no valid records"):
        parser.parse(source, {}, TaskContext())


def test_tr_f_malformed_and_extra_columns_are_diagnosed(
    tmp_path: Path, bundled_registry
) -> None:
    parser = bundled_registry.get("builtin.parser.tr_f")
    source = tmp_path / "mixed.txt"
    source.write_text("0,1\nbad,row\n1,2,3\n2,4\n", encoding="utf-8")
    result = parser.parse(source, {}, TaskContext())
    assert result.dataset.sample_count == 2
    malformed = [item for item in result.diagnostics if item.code == "tr_f.malformed_row"]
    assert [item.line for item in malformed] == [2, 3]
    assert result.dataset.metadata["malformed_rows"] == 2


def test_tr_f_strict_invalid_policy_fails_at_line(
    tmp_path: Path, bundled_registry
) -> None:
    parser = bundled_registry.get("builtin.parser.tr_f")
    source = tmp_path / "strict.txt"
    source.write_text("0,1\ninvalid\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r":2:"):
        parser.parse(source, {"invalid_row_policy": "error"}, TaskContext())


def test_tr_f_explicit_millisecond_unit_is_normalized_to_seconds(
    tmp_path: Path, bundled_registry
) -> None:
    parser = bundled_registry.get("builtin.parser.tr_f")
    source = tmp_path / "milliseconds.txt"
    source.write_text("0,0\n10,1\n20,0\n", encoding="utf-8")
    dataset = parser.parse(
        source,
        {"time_unit": "ms", "delimiter": ",", "invalid_row_policy": "skip"},
        TaskContext(),
    ).dataset
    assert dataset.time_unit == "s"
    assert dataset.metadata["source_time_unit"] == "ms"
    np.testing.assert_allclose(dataset.time, [0.0, 0.01, 0.02])


def test_timestamp_anomalies_and_gap_are_reported(
    tmp_path: Path, bundled_registry
) -> None:
    parser = bundled_registry.get("builtin.parser.tr_f")
    source = tmp_path / "timing.txt"
    source.write_text("0,0\n1,1\n1,2\n0.5,3\n20,4\n", encoding="utf-8")
    dataset = parser.parse(source, {}, TaskContext()).dataset
    report = Dataset_QualityInspect(dataset)
    assert report.duplicate_timestamps == 1
    assert report.backward_timestamps == 1
    assert report.large_gaps == 1
    codes = {item.code for item in dataset.diagnostics}
    assert {"time.duplicate", "time.backward", "time.large_gap"} <= codes


def test_large_tr_f_reports_progress_without_tell_failure(
    tmp_path: Path, bundled_registry
) -> None:
    parser = bundled_registry.get("builtin.parser.tr_f")
    source = tmp_path / "large.txt"
    source.write_text(
        "".join(f"{index / 1000:.6f},{index}\n" for index in range(2500)),
        encoding="utf-8",
    )
    progress: list[float] = []
    result = parser.parse(
        source,
        {},
        TaskContext(progress_callback=lambda value, _message: progress.append(value)),
    )
    assert result.dataset.sample_count == 2500
    assert progress[-1] == 1.0
    assert any(value < 1.0 for value in progress)
