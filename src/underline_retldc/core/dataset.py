from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from underline_retldc.core.channel import Channel
from underline_retldc.core.diagnostics import Diagnostic


@dataclass(frozen=True, slots=True)
class Dataset:
    time: NDArray[np.float64] | ArrayLike
    channels: Mapping[str, Channel]
    time_unit: str = "s"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] | Iterable[Diagnostic] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.time_unit.strip():
            raise ValueError("Dataset time unit must not be empty")
        time = np.asarray(self.time, dtype=np.float64)
        if time.ndim != 1:
            raise ValueError("Dataset time must be one-dimensional")
        immutable_time = np.array(time, dtype=np.float64, copy=True)
        immutable_time.setflags(write=False)

        channels = dict(self.channels)
        for channel_id, channel in channels.items():
            if channel_id != channel.id:
                raise ValueError(f"Channel mapping key {channel_id!r} does not match id")
            if len(channel.values) != len(immutable_time):
                raise ValueError(f"Channel {channel_id!r} length does not match time length")

        object.__setattr__(self, "time", immutable_time)
        object.__setattr__(self, "channels", MappingProxyType(channels))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    @property
    def sample_count(self) -> int:
        return len(self.time)

    def channel(self, channel_id: str) -> Channel:
        try:
            return self.channels[channel_id]
        except KeyError as exc:
            raise KeyError(f"Dataset does not contain channel {channel_id!r}") from exc

    def with_channel(self, channel: Channel) -> Dataset:
        if len(channel.values) != self.sample_count:
            raise ValueError("New channel length does not match Dataset")
        channels = dict(self.channels)
        if channel.id in channels:
            raise ValueError(f"Refusing to overwrite existing channel {channel.id!r}")
        channels[channel.id] = channel
        return replace(self, channels=channels)

    def with_diagnostics(self, diagnostics: Iterable[Diagnostic]) -> Dataset:
        return replace(self, diagnostics=(*self.diagnostics, *tuple(diagnostics)))

