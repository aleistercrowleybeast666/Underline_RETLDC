from __future__ import annotations

from collections.abc import Sequence

from underline_retldc.core.project_data import ChannelReference, SourceTestDetection
from underline_retldc.core.region_detection import Activity_DetectSegments
from underline_retldc.core.segmentation import Segmentation_RegionsAroundCandidate
from underline_retldc.core.source_analysis import SourceAnalysisInput
from underline_retldc.core.units import Quantity_Dimension, Unit_IsPhysicalForQuantity


def SourceAlignment_Detect(
    inputs: Sequence[SourceAnalysisInput],
    *,
    role: str | None = None,
    polarity: int = 1,
    preferred: ChannelReference | None = None,
) -> SourceTestDetection | None:
    """Detect one source using its own clocks and polarity, without changing its data."""
    roles = (role,) if role else ("chamber_pressure", "thrust")
    for candidate_role in roles:
        dimension = {"chamber_pressure": "pressure", "thrust": "force"}[candidate_role]
        available = []
        for item in inputs:
            channel = item.dataset.channel(item.channel_id)
            if (Quantity_Dimension(channel.quantity) == dimension
                    and Unit_IsPhysicalForQuantity(channel.quantity, channel.data_unit)):
                available.append(item)
        selected = next((item for item in available if item.reference == preferred), None)
        if selected is None:
            hints = [item for item in available if item.dataset.channel(
                item.channel_id
            ).semantic_role == candidate_role]
            candidates = hints or available
            if len(candidates) != 1:
                continue  # Ambiguous Channels must not be chosen by discovery order.
            selected = candidates[0]
        sign = polarity if candidate_role == "thrust" else 1
        detected = Activity_DetectSegments(
            selected.dataset.project_time,
            selected.dataset.channel(selected.channel_id).values,
            sign=sign,
        )
        if detected:
            return SourceTestDetection(
                selected.reference,
                Segmentation_RegionsAroundCandidate(selected.dataset, detected[0]),
                candidate_role, sign,
            )
    return None


def SourceAlignment_Offset(experimental_start: float, detection: SourceTestDetection) -> float:
    """Absolute display offset; existing display transforms never enter this calculation."""
    return float(experimental_start - detection.regions.active_test.start)
