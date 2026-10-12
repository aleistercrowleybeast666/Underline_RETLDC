from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import NDArray

from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset


class SourceKind(StrEnum):
    EXPERIMENTAL = "experimental"
    THEORETICAL = "theoretical"


@dataclass(frozen=True, slots=True)
class SourceDisplayTransform:
    """View-only source alignment; never enters Project Time or a scientific pipeline."""

    shift_s: float = 0.0
    zero_start: bool = False
    hidden_curve_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        try:
            shift = float(self.shift_s)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Source display shift must be a finite number") from exc
        if not math.isfinite(shift):
            raise ValueError("Source display shift must be finite")
        if not isinstance(self.zero_start, bool):
            raise ValueError("Source display zero_start must be a boolean")
        object.__setattr__(self, "shift_s", shift)
        object.__setattr__(self, "hidden_curve_ids", tuple(self.hidden_curve_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "shift_s": self.shift_s,
            "zero_start": self.zero_start,
            "hidden_curve_ids": list(self.hidden_curve_ids),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SourceDisplayTransform:
        hidden = payload.get("hidden_curve_ids", [])
        if not isinstance(hidden, (list, tuple)) or any(
            not isinstance(item, str) for item in hidden
        ):
            raise ValueError("Source hidden_curve_ids must be an array of strings")
        return cls(
            shift_s=payload.get("shift_s", 0.0),
            zero_start=payload.get("zero_start", False),
            hidden_curve_ids=tuple(hidden),
        )


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    path: Path
    sha256: str | None = None
    parser_id: str | None = None
    parser_version: str | None = None
    parser_config: Mapping[str, Any] = field(default_factory=dict)
    source_kind: SourceKind = SourceKind.EXPERIMENTAL
    display_transform: SourceDisplayTransform = field(default_factory=SourceDisplayTransform)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Source id must not be empty")
        object.__setattr__(self, "path", Path(self.path))
        object.__setattr__(self, "parser_config", MappingProxyType(dict(self.parser_config)))
        object.__setattr__(self, "source_kind", SourceKind(self.source_kind))


@dataclass(frozen=True, slots=True)
class Stream:
    id: str
    source_id: str
    dataset: Dataset
    time_offset_s: float = 0.0
    name: str | None = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.source_id.strip():
            raise ValueError("Stream id and source_id must not be empty")
        offset = float(self.time_offset_s)
        object.__setattr__(self, "time_offset_s", offset)
        object.__setattr__(self, "name", self.name or self.id)
        if (
            self.dataset.source_id != self.source_id
            or self.dataset.stream_id != self.id
            or self.dataset.time_offset_s != offset
        ):
            object.__setattr__(
                self,
                "dataset",
                replace(
                    self.dataset,
                    source_id=self.source_id,
                    stream_id=self.id,
                    time_offset_s=offset,
                ),
            )


@dataclass(frozen=True, slots=True)
class ChannelReference:
    source_id: str
    stream_id: str
    channel_id: str

    @property
    def stable_id(self) -> str:
        return f"{self.source_id}/{self.stream_id}/{self.channel_id}"

    def to_dict(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "stream_id": self.stream_id,
            "channel_id": self.channel_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ChannelReference:
        return cls(
            source_id=str(payload["source_id"]),
            stream_id=str(payload["stream_id"]),
            channel_id=str(payload["channel_id"]),
        )


@dataclass(frozen=True, slots=True)
class PrimaryChannelBindings:
    thrust: ChannelReference | None = None
    chamber_pressure: ChannelReference | None = None
    temperature_channels: tuple[ChannelReference, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        temperatures = tuple(self.temperature_channels)
        if len({item.stable_id for item in temperatures}) != len(temperatures):
            raise ValueError("Temperature Channel bindings must be unique")
        object.__setattr__(self, "temperature_channels", temperatures)

    def to_dict(self) -> dict[str, Any]:
        return {
            "thrust": self.thrust.to_dict() if self.thrust is not None else None,
            "chamber_pressure": (
                self.chamber_pressure.to_dict()
                if self.chamber_pressure is not None
                else None
            ),
            "temperature_channels": [
                item.to_dict() for item in self.temperature_channels
            ],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> PrimaryChannelBindings:
        def optional_reference(key: str) -> ChannelReference | None:
            value = payload.get(key)
            if value is None:
                return None
            if not isinstance(value, Mapping):
                raise ValueError(f"Primary Channel {key!r} must be an object or null")
            return ChannelReference.from_dict(value)

        temperatures = payload.get("temperature_channels", [])
        if not isinstance(temperatures, (list, tuple)) or any(
            not isinstance(item, Mapping) for item in temperatures
        ):
            raise ValueError("Primary temperature_channels must be an array of objects")
        return cls(
            thrust=optional_reference("thrust"),
            chamber_pressure=optional_reference("chamber_pressure"),
            temperature_channels=tuple(
                ChannelReference.from_dict(item) for item in temperatures
            ),
        )


@dataclass(frozen=True, slots=True)
class ProjectData:
    sources: Mapping[str, Source] = field(default_factory=dict)
    streams: Mapping[str, Stream] = field(default_factory=dict)
    primary_channels: PrimaryChannelBindings = field(
        default_factory=PrimaryChannelBindings
    )

    def __post_init__(self) -> None:
        sources = dict(self.sources)
        streams = dict(self.streams)
        for source_id, source in sources.items():
            if source_id != source.id:
                raise ValueError("Source mapping key does not match Source.id")
        for stream_id, stream in streams.items():
            if stream_id != stream.id:
                raise ValueError("Stream mapping key does not match Stream.id")
            if stream.source_id not in sources:
                raise ValueError(f"Stream {stream_id!r} refers to an unknown Source")
        object.__setattr__(self, "sources", MappingProxyType(sources))
        object.__setattr__(self, "streams", MappingProxyType(streams))

    def channel(self, reference: ChannelReference) -> Channel:
        stream = self.streams[reference.stream_id]
        if stream.source_id != reference.source_id:
            raise KeyError(f"Channel reference {reference.stable_id!r} has the wrong Source")
        return stream.dataset.channel(reference.channel_id)

    def channel_references(self) -> tuple[ChannelReference, ...]:
        return tuple(
            ChannelReference(stream.source_id, stream.id, channel_id)
            for stream in self.streams.values()
            for channel_id in stream.dataset.channels
        )

    def with_source_stream(self, source: Source, stream: Stream) -> ProjectData:
        if stream.source_id != source.id:
            raise ValueError("Stream source_id does not match Source.id")
        sources = dict(self.sources)
        streams = dict(self.streams)
        if source.id in sources or stream.id in streams:
            raise ValueError("Refusing to overwrite an existing Source or Stream")
        sources[source.id] = source
        streams[stream.id] = stream
        return ProjectData(sources, streams, self.primary_channels)

    def with_primary_channels(
        self, primary_channels: PrimaryChannelBindings
    ) -> ProjectData:
        return ProjectData(self.sources, self.streams, primary_channels)

    def with_source_display(
        self, source_id: str, transform: SourceDisplayTransform
    ) -> ProjectData:
        source = self.sources[source_id]
        if source.source_kind != SourceKind.THEORETICAL:
            raise ValueError("Display alignment is available for theoretical Sources only")
        sources = dict(self.sources)
        sources[source_id] = replace(source, display_transform=transform)
        return ProjectData(sources, self.streams, self.primary_channels)

    def source_display_anchor(self, source_id: str) -> float | None:
        """Earliest first finite measurement in each source Stream, in Project Time."""
        starts: list[float] = []
        for stream in self.streams.values():
            if stream.source_id != source_id:
                continue
            time = stream.dataset.project_time
            valid = np.zeros(time.shape, dtype=bool)
            for channel in stream.dataset.channels.values():
                valid |= np.isfinite(channel.values)
            indices = np.flatnonzero(valid & np.isfinite(time))
            if indices.size:
                starts.append(float(time[indices[0]]))
        return min(starts) if starts else None

    def display_time(self, reference: ChannelReference) -> NDArray[np.float64]:
        self.channel(reference)  # Validate the full Source/Stream/Channel identity.
        time = self.streams[reference.stream_id].dataset.project_time
        source = self.sources[reference.source_id]
        if source.source_kind == SourceKind.THEORETICAL:
            transform = source.display_transform
            anchor = self.source_display_anchor(source.id) if transform.zero_start else 0.0
            time = time - (anchor or 0.0) + transform.shift_s
        result = np.array(time, dtype=np.float64, copy=True)
        result.setflags(write=False)
        return result
