from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from underline_retldc.core.dataset import Dataset
from underline_retldc.plugin_api.common import AnalysisResult


@dataclass(frozen=True, slots=True)
class ExportCurve:
    time: NDArray[np.float64]
    thrust: NDArray[np.float64]
    source_channel_id: str
    unit: str
    ignition: float
    burnout: float
    interpolated_boundaries: tuple[str, ...]


def ExportCurve_Extract(
    dataset: Dataset,
    analysis: AnalysisResult | None,
    config: Mapping[str, Any],
) -> ExportCurve:
    analysis_metadata = dict(analysis.metadata) if analysis is not None else {}
    channel_id = str(
        config.get("channel_id")
        or analysis_metadata.get("channel_id")
        or "thrust_processed"
    )
    try:
        ignition_value = config.get("ignition")
        burnout_value = config.get("burnout")
        if ignition_value is None:
            ignition_value = analysis_metadata.get("ignition")
        if burnout_value is None:
            burnout_value = analysis_metadata.get("burnout")
        ignition = float(ignition_value)
        burnout = float(burnout_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Final-curve export requires ignition and burnout") from exc
    if not math.isfinite(ignition) or not math.isfinite(burnout) or ignition >= burnout:
        raise ValueError("Final-curve export requires finite ignition < burnout")
    channel = dataset.channel(channel_id)
    all_time = np.asarray(dataset.time, dtype=np.float64)
    all_thrust = np.asarray(channel.values, dtype=np.float64)
    mask = (dataset.time >= ignition) & (dataset.time <= burnout)
    time = np.asarray(dataset.time[mask], dtype=np.float64)
    thrust = np.asarray(channel.values[mask], dtype=np.float64)
    finite = np.isfinite(time) & np.isfinite(thrust)
    time = np.array(time[finite], dtype=np.float64, copy=True)
    thrust = np.array(thrust[finite], dtype=np.float64, copy=True)
    if len(time) < 2:
        raise ValueError("Final burn curve requires at least two finite samples")
    if np.any(np.diff(time) <= 0):
        raise ValueError("Final burn curve timestamps must be strictly increasing")
    interpolated_boundaries: list[str] = []

    def boundary_value(boundary: float) -> float | None:
        finite_all = np.isfinite(all_time) & np.isfinite(all_thrust)
        before = np.flatnonzero(finite_all & (all_time < boundary))
        after = np.flatnonzero(finite_all & (all_time > boundary))
        if before.size == 0 or after.size == 0:
            return None
        left = int(before[-1])
        right_candidates = after[after > left]
        if right_candidates.size == 0:
            return None
        right = int(right_candidates[0])
        left_time = float(all_time[left])
        right_time = float(all_time[right])
        if not left_time < boundary < right_time:
            return None
        fraction = (boundary - left_time) / (right_time - left_time)
        return float(all_thrust[left] + fraction * (all_thrust[right] - all_thrust[left]))

    if time[0] > ignition:
        value = boundary_value(ignition)
        if value is None:
            raise ValueError("Ignition is not represented or bracketed by final curve samples")
        time = np.r_[ignition, time]
        thrust = np.r_[value, thrust]
        interpolated_boundaries.append("ignition")
    if time[-1] < burnout:
        value = boundary_value(burnout)
        if value is None:
            raise ValueError("Burnout is not represented or bracketed by final curve samples")
        time = np.r_[time, burnout]
        thrust = np.r_[thrust, value]
        interpolated_boundaries.append("burnout")
    time -= ignition
    time.setflags(write=False)
    thrust.setflags(write=False)
    return ExportCurve(
        time=time,
        thrust=thrust,
        source_channel_id=channel_id,
        unit=channel.unit,
        ignition=ignition,
        burnout=burnout,
        interpolated_boundaries=tuple(interpolated_boundaries),
    )
