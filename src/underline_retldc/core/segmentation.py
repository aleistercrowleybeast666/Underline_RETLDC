from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from underline_retldc.core.dataset import Dataset
from underline_retldc.core.primary_channels import PrimaryChannels_AutoBind
from underline_retldc.core.project_data import ChannelReference, ProjectData
from underline_retldc.core.regions import ActivityCandidate, RegionSelection, TimeRegion
from underline_retldc.core.units import Quantity_Dimension, Unit_IsPhysicalForQuantity


@dataclass(frozen=True, slots=True)
class SegmentationReference:
    reference: ChannelReference
    priority: str
    physical_unit: bool


def _signal_is_valid(dataset: Dataset, channel_id: str) -> bool:
    channel = dataset.channel(channel_id)
    finite = np.isfinite(dataset.project_time) & np.isfinite(channel.values)
    if np.count_nonzero(finite) < 3:
        return False
    time = dataset.project_time[finite]
    values = channel.values[finite]
    if float(np.max(time) - np.min(time)) <= 0:
        return False
    scale = max(1.0, float(np.max(np.abs(values))))
    return float(np.max(values) - np.min(values)) > np.finfo(np.float64).eps * scale


def Segmentation_SelectReference(project_data: ProjectData) -> SegmentationReference | None:
    bindings = project_data.primary_channels
    for reference, priority, dimension in (
        (bindings.chamber_pressure, "chamber_pressure", "pressure"),
        (bindings.thrust, "thrust", "force"),
    ):
        if reference is None:
            continue
        try:
            stream = project_data.streams[reference.stream_id]
            channel = project_data.channel(reference)
        except KeyError:
            continue
        if (
            Quantity_Dimension(channel.quantity) != dimension
            or not _signal_is_valid(stream.dataset, channel.id)
        ):
            continue
        return SegmentationReference(
            reference,
            priority,
            Unit_IsPhysicalForQuantity(channel.quantity, channel.data_unit),
        )
    return None


def Segmentation_SelectReferenceFromDatasets(
    datasets: Iterable[Dataset],
) -> tuple[Dataset, str, str] | None:
    sources = {}
    streams = {}
    datasets_by_stream: dict[str, Dataset] = {}
    from underline_retldc.core.project_data import Source, Stream

    for index, dataset in enumerate(datasets):
        source_id = dataset.source_id or f"source_{index + 1}"
        stream_id = dataset.stream_id or f"stream_{index + 1}"
        sources[source_id] = Source(source_id, dataset.metadata.get("source_path", source_id))
        streams[stream_id] = Stream(
            stream_id,
            source_id,
            dataset,
            dataset.time_offset_s,
        )
        datasets_by_stream[stream_id] = streams[stream_id].dataset
    project_data = ProjectData(sources, streams)
    project_data = project_data.with_primary_channels(
        PrimaryChannels_AutoBind(project_data)
    )
    selected = Segmentation_SelectReference(project_data)
    if selected is None:
        return None
    return (
        datasets_by_stream[selected.reference.stream_id],
        selected.reference.channel_id,
        selected.priority,
    )


def Segmentation_RegionsAroundCandidate(
    dataset: Dataset,
    candidate: ActivityCandidate,
) -> RegionSelection:
    finite_time = dataset.project_time[np.isfinite(dataset.project_time)]
    if finite_time.size < 2:
        raise ValueError("Test segmentation requires at least two finite timestamps")
    data_start = float(np.min(finite_time))
    data_end = float(np.max(finite_time))
    data_span = data_end - data_start
    active_span = max(candidate.duration, data_span * 0.02)
    gap = max(data_span * 0.005, np.finfo(np.float64).eps)

    pre: TimeRegion | None = None
    pre_end = candidate.start - gap
    if pre_end > data_start + gap:
        pre = TimeRegion(max(data_start, pre_end - active_span), pre_end)

    post: TimeRegion | None = None
    post_start = candidate.end + gap
    if post_start < data_end - gap:
        post = TimeRegion(post_start, min(data_end, post_start + active_span))

    return RegionSelection(
        pre=pre,
        burn=TimeRegion(candidate.start, candidate.end),
        post=post,
    )
