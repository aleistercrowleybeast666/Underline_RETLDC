from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AxisViewState:
    range: tuple[float, float] | None
    auto_range: bool | float = False
    linked_to: str | None = None
    fft_mode: bool = False
    log_mode: bool = False
    subtract_mean_mode: bool = False

    def __post_init__(self) -> None:
        if not all(isinstance(value, bool) for value in (
            self.fft_mode, self.log_mode, self.subtract_mean_mode,
        )):
            raise ValueError("Plot transform flags must be boolean")
        if self.range is not None:
            if len(self.range) != 2:
                raise ValueError("Plot axis range must contain two numbers")
            try:
                bounds = tuple(float(value) for value in self.range)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("Plot axis range must be numeric") from exc
            if not all(math.isfinite(value) for value in bounds) or bounds[0] >= bounds[1]:
                raise ValueError("Plot axis range must be finite and increasing")
            object.__setattr__(self, "range", bounds)
        elif not self.linked_to:
            raise ValueError("Unlinked plot axis requires a range")
        if not isinstance(self.auto_range, bool):
            if not isinstance(self.auto_range, (int, float)):
                raise ValueError("Plot auto-range must be boolean or a fraction")
            fraction = float(self.auto_range)
            if not math.isfinite(fraction) or not 0 <= fraction <= 1:
                raise ValueError("Plot auto-range fraction must be between zero and one")
            object.__setattr__(self, "auto_range", fraction)
        if self.linked_to is not None and (
            not isinstance(self.linked_to, str) or not self.linked_to.strip()
        ):
            raise ValueError("Plot linked axis ID must be a nonempty string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "range": list(self.range) if self.range is not None else None,
            "auto_range": self.auto_range, "linked_to": self.linked_to,
            "fft_mode": self.fft_mode, "log_mode": self.log_mode,
            "subtract_mean_mode": self.subtract_mean_mode,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> AxisViewState:
        bounds = payload.get("range")
        if bounds is not None and not isinstance(bounds, (list, tuple)):
            raise ValueError("Plot axis range must be an array")
        return cls(
            bounds, payload.get("auto_range", False), payload.get("linked_to"),
            payload.get("fft_mode", False), payload.get("log_mode", False),
            payload.get("subtract_mean_mode", False),
        )


def PlotViews_FromDict(payload: Any) -> dict[str, dict[str, AxisViewState]]:
    if not isinstance(payload, Mapping):
        raise ValueError("Project plot views must be an object")
    views: dict[str, dict[str, AxisViewState]] = {}
    for plot_id, axes in payload.items():
        if not isinstance(plot_id, str) or not plot_id or not isinstance(axes, Mapping):
            raise ValueError("Plot IDs and axes must be valid objects")
        views[plot_id] = {}
        for axis_id, state in axes.items():
            if not isinstance(axis_id, str) or not axis_id or not isinstance(state, Mapping):
                raise ValueError("Plot axis IDs and states must be valid objects")
            views[plot_id][axis_id] = AxisViewState.from_dict(state)
    return views
