from __future__ import annotations

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
    pre: TimeRegion
    burn: TimeRegion
    post: TimeRegion

    def __post_init__(self) -> None:
        if self.pre.end > self.burn.start:
            raise ValueError("PRE must end no later than ignition")
        if self.post.start < self.burn.end:
            raise ValueError("POST must start no earlier than burnout")

    def to_dict(self) -> dict[str, list[float]]:
        return {
            "pre": self.pre.to_list(),
            "burn": self.burn.to_list(),
            "post": self.post.to_list(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, list[float]]) -> RegionSelection:
        return cls(
            pre=TimeRegion(*payload["pre"]),
            burn=TimeRegion(*payload["burn"]),
            post=TimeRegion(*payload["post"]),
        )


@dataclass(frozen=True, slots=True)
class BurnCandidate:
    start: float
    end: float
    peak: float
    duration: float
    relative_strength: float
    score: float
    sample_count: int

