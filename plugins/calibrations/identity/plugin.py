from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
from numpy.typing import NDArray

from underline_retldc.plugin_api.calibration import CalibrationModelPlugin
from underline_retldc.plugin_api.common import PluginDescriptor, PluginType


class IdentityCalibration(CalibrationModelPlugin):
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="builtin.calibration.identity",
            plugin_type=PluginType.CALIBRATION,
            version="1.0.0",
            api_version="1",
            name="Already Calibrated",
            description="Identity calibration y = x",
            translation_key="calibration.identity.name",
        )

    def parameter_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    def requirements(self) -> Mapping[str, Any]:
        return {
            "input_quantity": "any",
            "input_unit": "any",
            "output_quantity": "same_as_input",
            "output_unit": "same_as_input",
        }

    def evaluate(
        self, raw: NDArray[np.float64], parameters: Mapping[str, Any]
    ) -> NDArray[np.float64]:
        values = np.asarray(raw, dtype=np.float64)
        if values.ndim != 1:
            raise ValueError("Calibration input must be one-dimensional")
        return np.array(values, copy=True)
