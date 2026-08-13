from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.plugin_api.calibration import CalibrationModelPlugin
from underline_retldc.plugin_api.common import ProcessingResult


def Calibration_Apply(
    dataset: Dataset,
    model: CalibrationModelPlugin,
    *,
    input_channel_id: str,
    output_channel_id: str = "force_calibrated",
    quantity: str,
    unit: str,
    parameters: Mapping[str, Any],
) -> Dataset:
    source = dataset.channel(input_channel_id)
    calibrated = model.evaluate(source.values, parameters)
    calibrated = np.asarray(calibrated, dtype=np.float64)
    if calibrated.shape != source.values.shape:
        raise ValueError("Calibration model returned an array with the wrong shape")
    channel = Channel(
        id=output_channel_id,
        quantity=quantity,
        unit=unit,
        values=calibrated,
        role="calibrated",
        metadata={
            "source_channel_id": input_channel_id,
            "calibration_model_id": model.descriptor.plugin_id,
            "calibration_model_version": model.descriptor.version,
            "parameters": dict(parameters),
        },
    )
    return dataset.with_channel(channel)


def Processing_Passthrough(
    dataset: Dataset,
    *,
    input_channel_id: str = "force_calibrated",
    output_channel_id: str = "thrust_processed",
) -> ProcessingResult:
    """Create a reproducible processed channel without applying a Processor plugin."""
    source = dataset.channel(input_channel_id)
    channel = Channel(
        id=output_channel_id,
        quantity="thrust",
        unit=source.unit,
        values=source.values,
        role="processed",
        metadata={
            "source_channel_id": input_channel_id,
            "processor_id": None,
            "compensation": "none",
            "user_confirmed": False,
        },
    )
    return ProcessingResult(
        dataset=dataset.with_channel(channel),
        output_channel_ids=(output_channel_id,),
        metadata={"compensation": "none", "processor_id": None},
    )
