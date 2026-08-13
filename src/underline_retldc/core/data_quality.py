from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from underline_retldc.core.dataset import Dataset
from underline_retldc.core.diagnostics import Diagnostic, DiagnosticSeverity


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    sample_count: int
    start_time: float | None
    end_time: float | None
    duration: float | None
    median_dt: float | None
    nominal_rate_hz: float | None
    minimum_dt: float | None
    maximum_dt: float | None
    duplicate_timestamps: int
    backward_timestamps: int
    large_gaps: int
    nan_values: int
    inf_values: int
    malformed_rows: int
    diagnostics: tuple[Diagnostic, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_count": self.sample_count,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "median_dt": self.median_dt,
            "nominal_rate_hz": self.nominal_rate_hz,
            "minimum_dt": self.minimum_dt,
            "maximum_dt": self.maximum_dt,
            "duplicate_timestamps": self.duplicate_timestamps,
            "backward_timestamps": self.backward_timestamps,
            "large_gaps": self.large_gaps,
            "nan_values": self.nan_values,
            "inf_values": self.inf_values,
            "malformed_rows": self.malformed_rows,
        }


def Dataset_QualityInspect(dataset: Dataset, *, gap_factor: float = 5.0) -> DataQualityReport:
    if gap_factor <= 1.0:
        raise ValueError("gap_factor must be greater than one")

    time = dataset.time
    count = dataset.sample_count
    finite_time = time[np.isfinite(time)]
    start = float(time[0]) if count and np.isfinite(time[0]) else None
    end = float(time[-1]) if count and np.isfinite(time[-1]) else None
    duration = end - start if start is not None and end is not None else None
    differences = np.diff(time) if count > 1 else np.array([], dtype=np.float64)
    finite_differences = differences[np.isfinite(differences)]
    positive_differences = finite_differences[finite_differences > 0]
    median_dt = float(np.median(positive_differences)) if positive_differences.size else None
    nominal_rate = 1.0 / median_dt if median_dt and median_dt > 0 else None
    minimum_dt = float(np.min(finite_differences)) if finite_differences.size else None
    maximum_dt = float(np.max(finite_differences)) if finite_differences.size else None
    duplicates = int(np.count_nonzero(finite_differences == 0))
    backwards = int(np.count_nonzero(finite_differences < 0))
    if median_dt is not None:
        typical_differences = positive_differences[positive_differences <= median_dt]
        gap_reference = float(np.median(typical_differences))
        large_gaps = int(np.count_nonzero(positive_differences > gap_factor * gap_reference))
    else:
        large_gaps = 0

    all_arrays = [time, *(channel.values for channel in dataset.channels.values())]
    nan_values = sum(int(np.count_nonzero(np.isnan(values))) for values in all_arrays)
    inf_values = sum(int(np.count_nonzero(np.isinf(values))) for values in all_arrays)
    malformed_rows = int(dataset.metadata.get("malformed_rows", 0))
    diagnostics: list[Diagnostic] = []

    if count == 0 or finite_time.size == 0:
        diagnostics.append(
            Diagnostic(DiagnosticSeverity.ERROR, "data.empty", "Dataset contains no samples")
        )
    if duplicates:
        diagnostics.append(
            Diagnostic(
                DiagnosticSeverity.WARNING,
                "time.duplicate",
                f"Detected {duplicates} duplicate timestamp interval(s)",
                details={"count": duplicates},
            )
        )
    if backwards:
        diagnostics.append(
            Diagnostic(
                DiagnosticSeverity.WARNING,
                "time.backward",
                f"Detected {backwards} backward timestamp interval(s)",
                details={"count": backwards},
            )
        )
    if large_gaps:
        diagnostics.append(
            Diagnostic(
                DiagnosticSeverity.WARNING,
                "time.large_gap",
                f"Detected {large_gaps} timing gap(s) above {gap_factor:g}× median Δt",
                details={"count": large_gaps, "gap_factor": gap_factor},
            )
        )
    if nan_values or inf_values:
        diagnostics.append(
            Diagnostic(
                DiagnosticSeverity.ERROR,
                "data.non_finite",
                f"Detected {nan_values} NaN and {inf_values} infinite value(s)",
                details={"nan": nan_values, "inf": inf_values},
            )
        )
    if malformed_rows:
        diagnostics.append(
            Diagnostic(
                DiagnosticSeverity.WARNING,
                "data.malformed_rows",
                f"Skipped {malformed_rows} malformed source row(s)",
                details={"count": malformed_rows},
            )
        )

    return DataQualityReport(
        sample_count=count,
        start_time=start,
        end_time=end,
        duration=duration,
        median_dt=median_dt,
        nominal_rate_hz=nominal_rate,
        minimum_dt=minimum_dt,
        maximum_dt=maximum_dt,
        duplicate_timestamps=duplicates,
        backward_timestamps=backwards,
        large_gaps=large_gaps,
        nan_values=nan_values,
        inf_values=inf_values,
        malformed_rows=malformed_rows,
        diagnostics=tuple(diagnostics),
    )
