from __future__ import annotations

import pytest

from underline_retldc.core.plot_view import AxisViewState
from underline_retldc.core.project import ProjectDocument


def test_plot_view_roundtrip_and_legacy_defaults() -> None:
    states = {"temperature": {
        "x": AxisViewState((-3, 8), False), "y": AxisViewState((10, 50), .85),
        "right:x": AxisViewState(None, False, "temperature/x"),
    }}
    document = ProjectDocument(plot_views=states)
    assert ProjectDocument.from_dict(document.to_dict()).plot_views == states
    payload = document.to_dict()
    payload.pop("plot_views")
    assert ProjectDocument.from_dict(payload).plot_views == {}


@pytest.mark.parametrize("state", [
    {"range": [1, 1]}, {"range": [2, 1]}, {"range": [0, float("nan")]},
    {"range": [0, float("inf")]}, {"range": "0,1"}, {"range": [0]},
    {"range": [0, 1], "auto_range": 2}, {"range": [0, 1], "auto_range": "yes"},
    {"range": None}, {"range": [0, 1], "linked_to": 12},
])
def test_invalid_plot_view_rejected(state: dict) -> None:
    payload = ProjectDocument().to_dict()
    payload["plot_views"] = {"temperature": {"x": state}}
    with pytest.raises(ValueError):
        ProjectDocument.from_dict(payload)
