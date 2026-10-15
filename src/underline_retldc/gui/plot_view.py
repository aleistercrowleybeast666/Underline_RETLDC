from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from underline_retldc.core.plot_view import AxisViewState


def PlotViews_Bindings(plots: Mapping[str, Any]) -> dict[str, tuple[Any, int]]:
    """Name actual ViewBox axes once, including extra axes attached to a plot."""
    bindings: dict[str, tuple[Any, int]] = {}
    seen: set[tuple[int, int]] = set()
    for plot_id, widget in plots.items():
        item = widget.plot_widget.getPlotItem()
        candidates = [("x", item.vb, 0), ("y", item.vb, 1)]
        for name, entry in sorted(item.axes.items()):
            view = entry["item"].linkedView()
            if view is not None and view is not item.vb:
                candidates.extend(((f"{name}:x", view, 0), (f"{name}:y", view, 1)))
        for axis_id, view, axis in candidates:
            identity = (id(view), axis)
            if identity not in seen:
                seen.add(identity)
                bindings[f"{plot_id}/{axis_id}"] = (view, axis)
    return bindings


def PlotViews_Capture(plots: Mapping[str, Any]) -> dict[str, dict[str, AxisViewState]]:
    bindings = PlotViews_Bindings(plots)
    identities = {(id(view), axis): key for key, (view, axis) in bindings.items()}
    states: dict[str, dict[str, AxisViewState]] = {}
    for key, (view, axis) in bindings.items():
        target = view.linkedView(axis)
        linked_to = identities.get((id(target), axis)) if target is not None else None
        plot_id, axis_id = key.split("/", 1)
        control = plots[plot_id].plot_widget.getPlotItem().ctrl
        states.setdefault(plot_id, {})[axis_id] = AxisViewState(
            None if linked_to else tuple(view.viewRange()[axis]),
            view.autoRangeEnabled()[axis], linked_to,
            axis_id == "x" and control.fftCheck.isChecked(),
            (control.logXCheck if axis == 0 else control.logYCheck).isChecked(),
            axis_id == "x" and control.subtractMeanCheck.isChecked(),
        )
    return states


def PlotViews_Restore(
    plots: Mapping[str, Any], states: Mapping[str, Mapping[str, AxisViewState]],
) -> None:
    """Restore display coordinates after curves; never apply a Source time transform."""
    bindings = PlotViews_Bindings(plots)
    # Transforms must precede range restoration: saved coordinates may be Hz/log10.
    for plot_id, axes in states.items():
        widget = plots.get(plot_id)
        if widget is None:
            continue
        control = widget.plot_widget.getPlotItem().ctrl
        x_state, y_state = axes.get("x"), axes.get("y")
        if x_state is not None:
            control.subtractMeanCheck.setChecked(x_state.subtract_mean_mode)
            control.fftCheck.setChecked(x_state.fft_mode)
            control.logXCheck.setChecked(x_state.log_mode)
        if y_state is not None:
            control.logYCheck.setChecked(y_state.log_mode)
    for plot_id, axes in states.items():
        for axis_id, state in axes.items():
            binding = bindings.get(f"{plot_id}/{axis_id}")
            if binding is None:
                continue
            view, axis = binding
            target = bindings.get(state.linked_to) if state.linked_to else None
            if target is not None:
                view.linkView(axis, target[0])
            elif state.range is not None:
                view.setRange(**{"xRange" if axis == 0 else "yRange": state.range}, padding=0)
            view.enableAutoRange(axis=axis, enable=state.auto_range)
