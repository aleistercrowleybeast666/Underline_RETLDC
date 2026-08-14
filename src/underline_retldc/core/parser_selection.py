from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from underline_retldc.plugin_api.common import ProbeResult


class ParserSelectionResult(StrEnum):
    SELECTED = "selected"
    AMBIGUOUS = "ambiguous"
    UNRECOGNIZED = "unrecognized"


@dataclass(frozen=True, slots=True)
class ParserSelectionDecision:
    result: ParserSelectionResult
    parser: Any | None
    candidates: tuple[tuple[Any, ProbeResult], ...]


def ParserSelection_Decide(
    results: Sequence[tuple[Any, ProbeResult]],
    *,
    threshold: float,
    ambiguity_margin: float,
) -> ParserSelectionDecision:
    ordered = tuple(
        sorted(results, key=lambda item: item[1].confidence, reverse=True)
    )
    if not ordered or ordered[0][1].confidence < threshold:
        return ParserSelectionDecision(
            ParserSelectionResult.UNRECOGNIZED,
            None,
            ordered,
        )
    top_confidence = float(ordered[0][1].confidence)
    compatible = tuple(
        item
        for item in ordered
        if top_confidence - float(item[1].confidence) < ambiguity_margin
        and item[1].confidence >= threshold
    )
    if len(compatible) > 1:
        return ParserSelectionDecision(
            ParserSelectionResult.AMBIGUOUS,
            None,
            compatible,
        )
    return ParserSelectionDecision(
        ParserSelectionResult.SELECTED,
        ordered[0][0],
        (ordered[0],),
    )
