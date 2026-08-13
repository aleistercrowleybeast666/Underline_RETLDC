from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np
from numpy.typing import NDArray

from underline_retldc.plugin_api.calibration import CalibrationModelPlugin
from underline_retldc.plugin_api.common import PluginDescriptor, PluginType


class LinearCalibration(CalibrationModelPlugin):
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="builtin.calibration.linear",
            plugin_type=PluginType.CALIBRATION,
            version="1.0.0",
            api_version="1",
            name="Linear Calibration",
            description="Linear calibration y = K*x + B",
            translation_key="calibration.linear.name",
        )

    def parameter_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["K", "B"],
            "properties": {
                "K": {
                    "type": "number",
                    "default": 1.0,
                    "title": "K",
                    "x-i18n-key": "setup.k",
                },
                "B": {
                    "type": "number",
                    "default": 0.0,
                    "title": "B",
                    "x-i18n-key": "setup.b",
                },
            },
        }

    def evaluate(
        self, raw: NDArray[np.float64], parameters: Mapping[str, Any]
    ) -> NDArray[np.float64]:
        values = np.asarray(raw, dtype=np.float64)
        if values.ndim != 1:
            raise ValueError("Calibration input must be one-dimensional")
        try:
            coefficient = float(parameters["K"])
            offset = float(parameters["B"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Linear calibration requires numeric K and B") from exc
        if not math.isfinite(coefficient) or not math.isfinite(offset):
            raise ValueError("Linear calibration K and B must be finite")
        return coefficient * values + offset
