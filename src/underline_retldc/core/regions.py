from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TimeRegion:
    start: float
    end: float

    def __post_init__(self) -> None:
        if self.start >= self.end:
            raise ValueError("Region start must be before end")

    def to_list(self) -> list[float]:
        return [self.start, self.end]


@dataclass(frozen=True, slots=True)
class RegionSelection:
    pre: TimeRegion | None
    burn: TimeRegion
    post: TimeRegion | None

    def __post_init__(self) -> None:
        if self.pre is not None and self.pre.end > self.burn.start:
            raise ValueError("PRE must end no later than ignition")
        if self.post is not None and self.post.start < self.burn.end:
            raise ValueError("POST must start no earlier than burnout")

    @property
    def active_test(self) -> TimeRegion:
        return self.burn

    def to_dict(self) -> dict[str, list[float] | None]:
        return {
            "pre": self.pre.to_list() if self.pre is not None else None,
            "burn": self.burn.to_list(),
            "post": self.post.to_list() if self.post is not None else None,
        }

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, list[float] | tuple[float, float] | None]
    ) -> RegionSelection:
        active_payload = payload.get("burn", payload.get("active_test"))
        if active_payload is None:
            raise ValueError("Region selection requires ACTIVE_TEST/BURN")
        pre_payload = payload.get("pre")
        post_payload = payload.get("post")
        return cls(
            pre=TimeRegion(*pre_payload) if pre_payload is not None else None,
            burn=TimeRegion(*active_payload),
            post=TimeRegion(*post_payload) if post_payload is not None else None,
        )


@dataclass(frozen=True, slots=True)
class ActivityCandidate:
    start: float
    end: float
    peak: float
    duration: float
    relative_strength: float
    score: float
    sample_count: int
    start_clipped: bool = False
    end_clipped: bool = False


# Plugin API v1 and persisted GUI code retain this compatibility name.
BurnCandidate = ActivityCandidate
