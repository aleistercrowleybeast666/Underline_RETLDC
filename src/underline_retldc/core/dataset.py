from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from underline_retldc.core.channel import Channel
from underline_retldc.core.diagnostics import Diagnostic, DiagnosticSeverity
from underline_retldc.core.units import UnitSource


@dataclass(frozen=True, slots=True)
class Dataset:
    time: NDArray[np.float64] | ArrayLike
    channels: Mapping[str, Channel]
    time_unit: str = "s"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    diagnostics: tuple[Diagnostic, ...] | Iterable[Diagnostic] = field(default_factory=tuple)
    source_id: str | None = None
    stream_id: str | None = None
    time_offset_s: float = 0.0

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
        diagnostics = list(self.diagnostics)
        existing_codes = {
            (item.code, item.source, item.details.get("channel_id"))
            for item in diagnostics
        }
        for channel in channels.values():
            code = channel.metadata.get("unit_diagnostic_code")
            message = channel.metadata.get("unit_diagnostic_message")
            diagnostic_key = (str(code), None, channel.id)
            if code and diagnostic_key not in existing_codes:
                diagnostics.append(
                    Diagnostic(
                        DiagnosticSeverity.WARNING,
                        str(code),
                        str(message or code),
                        details={"channel_id": channel.id},
                    )
                )
        object.__setattr__(self, "diagnostics", tuple(diagnostics))
        object.__setattr__(self, "source_id", self.source_id or None)
        object.__setattr__(self, "stream_id", self.stream_id or None)
        object.__setattr__(self, "time_offset_s", float(self.time_offset_s))

    @property
    def sample_count(self) -> int:
        return len(self.time)

    @property
    def project_time(self) -> NDArray[np.float64]:
        project_time = np.array(self.time + self.time_offset_s, dtype=np.float64, copy=True)
        project_time.setflags(write=False)
        return project_time

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

    def with_channel_interpretation(
        self,
        channel_id: str,
        *,
        quantity: str | None = None,
        data_unit: str | None = None,
        display_unit: str | None = None,
        semantic_role: str | None = None,
        unit_source: UnitSource | str = UnitSource.USER_OVERRIDE,
    ) -> Dataset:
        source = self.channel(channel_id)
        replacement = source.with_unit_interpretation(
            quantity=quantity,
            data_unit=data_unit,
            display_unit=display_unit,
            semantic_role=semantic_role,
            unit_source=unit_source,
        )
        channels = dict(self.channels)
        channels[channel_id] = replacement
        return replace(self, channels=channels)
