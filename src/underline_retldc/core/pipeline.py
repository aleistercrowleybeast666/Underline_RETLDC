from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.units import UnitSource
from underline_retldc.plugin_api.calibration import CalibrationModelPlugin
from underline_retldc.plugin_api.common import ProcessingResult


def Calibration_OutputChannelId(source: Channel) -> str:
    return f"{source.id}_calibrated"


def Calibration_Apply(
    dataset: Dataset,
    model: CalibrationModelPlugin,
    *,
    input_channel_id: str,
    output_channel_id: str,
    quantity: str | None = None,
    unit: str | None = None,
    parameters: Mapping[str, Any],
) -> Dataset:
    source = dataset.channel(input_channel_id)
    calibrated = model.evaluate(source.values, parameters)
    calibrated = np.asarray(calibrated, dtype=np.float64)
    if calibrated.shape != source.values.shape:
        raise ValueError("Calibration model returned an array with the wrong shape")
    output_quantity = str(quantity or source.quantity)
    output_unit = str(unit or source.data_unit)
    is_identity = model.descriptor.plugin_id == "builtin.calibration.identity"
    channel = Channel(
        id=output_channel_id,
        quantity=output_quantity,
        unit=output_unit,
        values=calibrated,
        role="calibrated",
        metadata={
            "source_channel_id": input_channel_id,
            "calibration_model_id": model.descriptor.plugin_id,
            "calibration_model_version": model.descriptor.version,
            "parameters": dict(parameters),
            "input_quantity": source.quantity,
            "input_unit": source.data_unit,
            "output_quantity": output_quantity,
            "output_unit": output_unit,
        },
        unit_source=(
            source.unit_source if is_identity else UnitSource.CALIBRATION_OUTPUT
        ),
        display_unit=(
            source.display_unit if output_unit == source.data_unit else None
        ),
        semantic_role=source.semantic_role,
        name=f"{source.name} (calibrated)",
    )
    return dataset.with_channel(channel)


def Calibration_ApplyIdentityDefaults(
    dataset: Dataset,
    identity_model: CalibrationModelPlugin,
) -> tuple[Dataset, dict[str, str]]:
    if identity_model.descriptor.plugin_id != "builtin.calibration.identity":
        raise ValueError("Factory default calibration requires the Identity plugin")
    result = dataset
    outputs: dict[str, str] = {}
    source_channels = tuple(dataset.channels.values())
    for source in source_channels:
        if source.role != "raw":
            continue
        output_id = Calibration_OutputChannelId(source)
        if output_id in result.channels:
            raise ValueError(f"Default calibration output {output_id!r} already exists")
        result = Calibration_Apply(
            result,
            identity_model,
            input_channel_id=source.id,
            output_channel_id=output_id,
            quantity=source.quantity,
            unit=source.data_unit,
            parameters={},
        )
        outputs[source.id] = output_id
    return result, outputs


def Processing_Passthrough(
    dataset: Dataset,
    *,
    input_channel_id: str,
    output_channel_id: str = "thrust_processed",
) -> ProcessingResult:
    """Create a reproducible processed channel without applying a Processor plugin."""
    source = dataset.channel(input_channel_id)
    channel = Channel(
        id=output_channel_id,
        quantity="thrust",
        unit=source.data_unit,
        values=source.values,
        role="processed",
        metadata={
            "source_channel_id": input_channel_id,
            "processor_id": None,
            "compensation": "none",
            "user_confirmed": False,
        },
        unit_source=source.unit_source,
        display_unit=source.display_unit,
        semantic_role="thrust",
    )
    return ProcessingResult(
        dataset=dataset.with_channel(channel),
        output_channel_ids=(output_channel_id,),
        metadata={"compensation": "none", "processor_id": None},
    )
