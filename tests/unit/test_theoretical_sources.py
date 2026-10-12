from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from underline_retldc.core.channel import Channel
from underline_retldc.core.curve_display import CurveDisplay_IsCompatible
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.primary_channels import (
    PrimaryChannels_AutoBind,
    PrimaryChannels_Candidates,
    PrimaryChannels_Validate,
)
from underline_retldc.core.project import (
    Project_Load,
    Project_Save,
    ProjectDocument,
    ProjectSourceState,
)
from underline_retldc.core.project_data import (
    ChannelReference,
    PrimaryChannelBindings,
    ProjectData,
    Source,
    SourceDisplayTransform,
    SourceKind,
    Stream,
)
from underline_retldc.core.segmentation import Segmentation_SelectReference


def _project(time: list[float], values: list[float]) -> ProjectData:
    dataset = Dataset(time, {
        "f": Channel("f", "force", "N", values, "raw", semantic_role="thrust")
    })
    sources = {
        "exp": Source("exp", Path("exp.csv")),
        "theory": Source("theory", Path("theory.csv"), source_kind=SourceKind.THEORETICAL),
    }
    streams = {key: Stream(key, key, dataset) for key in sources}
    return ProjectData(sources, streams)


def test_theory_is_excluded_from_primary_and_segmentation() -> None:
    project = _project([0, 1, 2, 3], [0, 5, 8, 0])
    exp_ref = ChannelReference("exp", "exp", "f")
    theory_ref = ChannelReference("theory", "theory", "f")
    assert PrimaryChannels_Candidates(project, dimension="force") == (exp_ref,)
    bindings = PrimaryChannels_AutoBind(project)
    assert bindings.thrust == exp_ref
    with pytest.raises(ValueError):
        PrimaryChannels_Validate(project, PrimaryChannelBindings(thrust=theory_ref))
    assert Segmentation_SelectReference(
        project.with_primary_channels(PrimaryChannelBindings(thrust=theory_ref))
    ) is None
    assert project.channel(exp_ref).role == project.channel(theory_ref).role == "raw"


@pytest.mark.parametrize("shift", [-9.5, 0, 15.25])
def test_display_alignment_preserves_original_arrays(shift: float) -> None:
    project = _project([8, 9, 10, 14], [np.nan, 5, np.nan, 7])
    ref = ChannelReference("theory", "theory", "f")
    shifted = project.with_source_display("theory", SourceDisplayTransform(shift, True))
    np.testing.assert_array_equal(
        shifted.display_time(ref), [-1 + shift, shift, 1 + shift, 5 + shift]
    )
    np.testing.assert_array_equal(project.streams["theory"].dataset.time, [8, 9, 10, 14])
    np.testing.assert_array_equal(project.channel(ref).values, [np.nan, 5, np.nan, 7])
    assert not shifted.display_time(ref).flags.writeable
    reset = shifted.with_source_display("theory", SourceDisplayTransform())
    np.testing.assert_array_equal(reset.display_time(ref), [8, 9, 10, 14])
    exp_ref = ChannelReference("exp", "exp", "f")
    np.testing.assert_array_equal(shifted.display_time(exp_ref), [8, 9, 10, 14])
    with pytest.raises(ValueError):
        project.with_source_display("exp", SourceDisplayTransform(1))


def test_zero_start_uses_source_anchor_across_streams() -> None:
    project = _project([8, 9], [np.nan, 1])
    extra = Stream(
        "extra", "theory", Dataset([12, 13], {"p": Channel("p", "pressure", "Pa", [1, 2], "raw")})
    )
    project = ProjectData(project.sources, {**project.streams, "extra": extra})
    project = project.with_source_display("theory", SourceDisplayTransform(2, True))
    np.testing.assert_array_equal(
        project.display_time(ChannelReference("theory", "extra", "p")), [5, 6]
    )


@pytest.mark.parametrize("time,values", [([], []), ([1, 2], [np.nan, np.nan])])
def test_empty_source_has_no_alignment_anchor(time: list[float], values: list[float]) -> None:
    project = _project(time, values)
    assert project.source_display_anchor("theory") is None
    ref = ChannelReference("theory", "theory", "f")
    aligned = project.with_source_display("theory", SourceDisplayTransform(0, True))
    assert len(aligned.display_time(ref)) == len(time)


@pytest.mark.parametrize("shift", [float("nan"), float("inf"), -float("inf"), "bad", None, {}])
def test_nonfinite_or_invalid_shift_is_rejected(shift: float | str) -> None:
    with pytest.raises(ValueError):
        SourceDisplayTransform(shift)
    with pytest.raises(ValueError):
        ProjectSourceState.from_dict({
            "source_id": "theory", "path": "theory.csv", "source_kind": "theoretical",
            "display_transform": {"shift_s": shift},
        })


def test_source_state_roundtrip_and_legacy_default(tmp_path: Path) -> None:
    transform = SourceDisplayTransform(-2.5, True, ("theory/stream/f",))
    document = ProjectDocument(sources=(ProjectSourceState(
        "theory", "theory.csv", source_kind=SourceKind.THEORETICAL, display_transform=transform,
    ),))
    path = tmp_path / "project.retldc.json"
    Project_Save(document, path)
    assert Project_Load(path).sources == document.sources
    legacy = ProjectSourceState.from_dict({"source_id": "old", "path": "old.csv"})
    assert legacy.source_kind == SourceKind.EXPERIMENTAL
    assert legacy.display_transform == SourceDisplayTransform()
    with pytest.raises(ValueError):
        replace(legacy, source_kind="unsupported")


@pytest.mark.parametrize("quantity,unit,compatible", [
    ("force", "kN", True), ("pressure", "Pa", False), ("force", "Pa", False),
    ("force", "raw", False), ("unknown", "N", False),
])
def test_overlay_checks_quantity_and_unit(quantity: str, unit: str, compatible: bool) -> None:
    target = Channel("exp", "force", "N", [0, 1], "raw")
    candidate = Channel("theory", quantity, unit, [0, 1], "raw")
    assert CurveDisplay_IsCompatible(candidate, target, "N") == compatible
