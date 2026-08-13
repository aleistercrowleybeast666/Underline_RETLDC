from pathlib import Path

import numpy as np

from underline_retldc.core.calibration import (
    Calibration_Load,
    Calibration_Save,
    CalibrationDocument,
)


def test_identity_returns_an_independent_array(bundled_registry) -> None:
    raw = np.array([1.0, 2.0, 3.0])
    calibrated = bundled_registry.get("builtin.calibration.identity").evaluate(raw, {})
    calibrated[0] = 99.0
    assert raw[0] == 1.0


def test_linear_applies_user_k_and_b(bundled_registry) -> None:
    raw = np.array([0.0, 1.0, 2.0])
    calibrated = bundled_registry.get("builtin.calibration.linear").evaluate(
        raw, {"K": 2.5, "B": -1.0}
    )
    np.testing.assert_allclose(calibrated, [-1.0, 1.5, 4.0])


def test_calibration_json_round_trip(tmp_path: Path) -> None:
    document = CalibrationDocument(
        name="LC-01",
        quantity="force",
        input_unit="raw",
        output_unit="N",
        model_id="builtin.calibration.linear",
        model_version="1.0.0",
        parameters={"K": 2.5, "B": -1.0},
        sensor={"id": "LC-01"},
        notes="test",
    )
    destination = tmp_path / "calibration.json"
    Calibration_Save(document, destination)
    restored = Calibration_Load(destination)
    assert restored == document
