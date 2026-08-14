from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike

from underline_retldc.core.regions import ActivityCandidate, BurnCandidate


def Activity_DetectSegments(
    time: ArrayLike,
    signal_values: ArrayLike,
    *,
    sign: int = 1,
    noise_sigma: float = 5.0,
    relative_threshold: float = 0.08,
    maximum_gap_samples: int = 2,
    minimum_samples: int = 3,
    minimum_duration_s: float = 0.0,
) -> list[ActivityCandidate]:
    timestamps = np.asarray(time, dtype=np.float64)
    values = np.asarray(signal_values, dtype=np.float64)
    if timestamps.ndim != 1 or values.ndim != 1 or len(timestamps) != len(values):
        raise ValueError("Activity detection requires equal one-dimensional time and signal arrays")
    if sign not in {-1, 1}:
        raise ValueError("Activity polarity must be +1 or -1")
    if minimum_duration_s < 0:
        raise ValueError("Activity minimum duration must not be negative")
    if len(timestamps) < minimum_samples:
        return []

    finite = np.isfinite(timestamps) & np.isfinite(values)
    if np.count_nonzero(finite) < minimum_samples:
        return []
    signal = sign * values
    finite_signal = signal[finite]
    baseline_cutoff = float(np.percentile(finite_signal, 30.0))
    baseline_samples = finite_signal[finite_signal <= baseline_cutoff]
    baseline = float(np.median(baseline_samples))
    absolute_deviation = np.abs(baseline_samples - baseline)
    robust_noise = 1.4826 * float(np.median(absolute_deviation))
    upper = float(np.percentile(signal[finite], 99.0))
    dynamic_range = max(0.0, upper - baseline)
    epsilon = np.finfo(np.float64).eps * max(1.0, abs(baseline), dynamic_range)
    threshold_delta = max(noise_sigma * robust_noise, relative_threshold * dynamic_range, epsilon)
    active = finite & (signal > baseline + threshold_delta)

    if maximum_gap_samples > 0 and np.any(active):
        active_indices = np.flatnonzero(active)
        for left, right in zip(active_indices[:-1], active_indices[1:], strict=True):
            if 1 < right - left <= maximum_gap_samples + 1:
                active[left : right + 1] = True

    transitions = np.diff(np.r_[False, active, False].astype(np.int8))
    starts = np.flatnonzero(transitions == 1)
    ends = np.flatnonzero(transitions == -1) - 1
    candidates: list[ActivityCandidate] = []
    noise_scale = max(robust_noise, threshold_delta / max(noise_sigma, 1.0), epsilon)
    for start_index, end_index in zip(starts, ends, strict=True):
        sample_count = int(end_index - start_index + 1)
        if sample_count < minimum_samples:
            continue
        segment_time = timestamps[start_index : end_index + 1]
        segment_force = signal[start_index : end_index + 1]
        start_time = float(np.min(segment_time))
        end_time = float(np.max(segment_time))
        duration = end_time - start_time
        if (
            not math.isfinite(duration)
            or duration <= 0
            or duration < minimum_duration_s
        ):
            continue
        peak = float(np.max(segment_force))
        relative_strength = max(0.0, (peak - baseline) / noise_scale)
        positive_area = float(
            np.trapezoid(np.maximum(segment_force - baseline, 0.0), segment_time)
        )
        score = positive_area * math.log1p(relative_strength) * math.sqrt(sample_count)
        candidates.append(
            ActivityCandidate(
                start=start_time,
                end=end_time,
                peak=peak,
                duration=duration,
                relative_strength=relative_strength,
                score=score,
                sample_count=sample_count,
                start_clipped=start_index == 0,
                end_clipped=end_index == len(timestamps) - 1,
            )
        )
    return sorted(candidates, key=lambda item: item.score, reverse=True)


def detect_activity_segments(
    time: ArrayLike,
    signal: ArrayLike,
    config: dict[str, float | int] | None = None,
) -> list[ActivityCandidate]:
    """Stable generic activity entry point used by all measurement workspaces."""
    values = dict(config or {})
    return Activity_DetectSegments(
        time,
        signal,
        sign=int(values.get("sign", 1)),
        noise_sigma=float(values.get("noise_sigma", 5.0)),
        relative_threshold=float(values.get("relative_threshold", 0.08)),
        maximum_gap_samples=int(values.get("maximum_gap_samples", 2)),
        minimum_samples=int(values.get("minimum_samples", 3)),
        minimum_duration_s=float(values.get("minimum_duration_s", 0.0)),
    )


def Burn_DetectCandidates(
    time: ArrayLike,
    force: ArrayLike,
    *,
    sign: int = 1,
    noise_sigma: float = 5.0,
    relative_threshold: float = 0.08,
    maximum_gap_samples: int = 2,
    minimum_samples: int = 3,
) -> list[BurnCandidate]:
    """Plugin API v1 compatibility wrapper around generic activity detection."""
    return Activity_DetectSegments(
        time,
        force,
        sign=sign,
        noise_sigma=noise_sigma,
        relative_threshold=relative_threshold,
        maximum_gap_samples=maximum_gap_samples,
        minimum_samples=minimum_samples,
    )
