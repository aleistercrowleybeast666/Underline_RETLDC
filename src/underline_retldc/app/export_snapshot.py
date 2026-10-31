"""GUI-independent snapshots of actual scientific inputs, never active selection."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any

from underline_retldc.app.session import AnalysisSession
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.project_data import ChannelReference, SourceKind
from underline_retldc.core.registry import PluginRegistry
from underline_retldc.plugin_api.common import AnalysisResult


@dataclass(frozen=True, slots=True)
class ExportSnapshot:
    dataset: Dataset
    analysis: AnalysisResult | None
    config_json: str

    def Config_Copy(self) -> dict[str, Any]:
        return json.loads(self.config_json)


def _reference(
    registry: PluginRegistry, plugin_id: str | None, config: Mapping[str, Any]
) -> dict[str, Any] | None:
    if plugin_id is None:
        return None
    descriptor = registry.get(plugin_id).descriptor
    return {
        "id": descriptor.plugin_id,
        "version": descriptor.version,
        "api_version": descriptor.api_version,
        "config": deepcopy(dict(config)),
    }


def ExportSnapshot_Build(
    session: AnalysisSession,
    registry: PluginRegistry,
    *,
    group_id: str = "thrust",
    motor_metadata: Mapping[str, Any] | None = None,
) -> ExportSnapshot:
    project = session.project_data
    bindings = project.primary_channels
    reference: ChannelReference | None = bindings.thrust
    analysis = session.analysis_result
    processing = session.processing_result
    if group_id == "chamber_pressure":
        reference, analysis = bindings.chamber_pressure, None
    elif group_id == "temperature":
        reference, analysis = next(iter(bindings.temperature_channels), None), None
    if reference is None:
        raise ValueError(f"Select the Primary {group_id} Channel before export")
    source = project.sources[reference.source_id]
    stream = project.streams[reference.stream_id]
    project.channel(reference)
    if source.source_kind != SourceKind.EXPERIMENTAL:
        raise ValueError("Formal export requires the experimental primary Source")
    if group_id not in {"chamber_pressure", "temperature"}:
        if processing is None or analysis is None:
            raise ValueError("Complete the primary thrust processing and analysis before export")
        dataset = processing.dataset
        channel_id = analysis.metadata.get("channel_id")
        if channel_id not in processing.output_channel_ids:
            candidates = [
                key
                for key in processing.output_channel_ids
                if dataset.channel(key).role == "processed"
            ]
            if len(candidates) != 1:
                raise ValueError("Final processed export Channel is ambiguous")
            channel_id = candidates[0]
    else:
        dataset = session.calibrated_streams.get(stream.id)
        if dataset is None:
            raise ValueError("Primary Channel has no calibrated Dataset")
        candidates = [
            c.id
            for c in dataset.channels.values()
            if c.role == "calibrated"
            and c.metadata.get("source_channel_id") == reference.channel_id
        ]
        if len(candidates) != 1:
            raise ValueError("Primary Channel calibration output is ambiguous")
        channel_id = candidates[0]
    if dataset.source_id != reference.source_id or dataset.stream_id != reference.stream_id:
        raise ValueError("Processed Dataset identity differs from its Primary binding")
    stored_hash = dataset.metadata.get("source_sha256")
    # Imported legacy sessions may have a stored Source hash but no dataset annotation.
    if stored_hash is None:
        stored_hash = source.sha256
    if stored_hash is not None and source.sha256 is not None and stored_hash != source.sha256:
        raise ValueError("Processed Dataset and Source SHA-256 identities disagree")
    # Walk the real derived-channel graph to prove the exported curve belongs to this input.
    chain_channels = []
    current = str(channel_id)
    seen: set[str] = set()
    for _ in range(32):
        if current in seen:
            raise ValueError("Derived Channel provenance contains a cycle")
        seen.add(current)
        channel = dataset.channel(current)
        chain_channels.append(channel)
        if current == reference.channel_id:
            break
        parent = channel.metadata.get("source_channel_id")
        if not isinstance(parent, str):
            raise ValueError(f"Channel {current!r} has no traceable input Channel")
        current = parent
    else:
        raise ValueError("Derived Channel provenance exceeds 32 stages")
    calibrated = next((c for c in chain_channels if c.role == "calibrated"), None)
    calibration_state = session.stream_channel_calibrations.get(reference.stable_id)
    calibration = None
    if calibrated is not None:
        calibration_config = {
            "parameters": dict(calibrated.metadata.get("parameters", {})),
            "quantity": calibrated.quantity,
            "unit": calibrated.data_unit,
        }
        if calibration_state is not None and calibration_state.output_channel_id == calibrated.id:
            calibration_config.update(deepcopy(calibration_state.config))
        calibration = {
            "id": calibrated.metadata["calibration_model_id"],
            "version": calibrated.metadata["calibration_model_version"],
            "api_version": "1",
            "config": calibration_config,
        }
    parser = {
        "id": source.parser_id,
        "version": source.parser_version,
        "api_version": "1",
        "config": deepcopy(dict(source.parser_config)),
    }
    processor = _reference(registry, session.processor_id, session.processor_config)
    analyzer = _reference(registry, session.analyzer_id, session.analyzer_config)
    active = session.regions.get("active_test", session.regions.get("burn"))
    config = {
        "channel_id": channel_id,
        "source_hash": stored_hash,
        "source_reference": {
            **reference.to_dict(),
            "final_channel_id": channel_id,
            "sha256": stored_hash,
            "file_name": source.path.name,
            "kind": source.source_kind.value,
        },
        "source_time_offset_s": stream.time_offset_s,
        "thrust_polarity": session.thrust_polarity,
        "ignition": float(active[0]) if active is not None else None,
        "burnout": float(active[1]) if active is not None else None,
        "motor_metadata": deepcopy(
            dict(motor_metadata if motor_metadata is not None else session.motor_metadata)
        ),
        "processing_metadata": deepcopy(dict(processing.metadata)) if processing else {},
        "project_name": session.project_path.name if session.project_path else None,
        "provenance": {
            "parser": parser,
            "calibration": calibration,
            "processor": processor,
            "analyzer": analyzer,
            "regions": deepcopy(session.regions),
        },
        "channel_chain": [
            {"id": c.id, "role": c.role, "metadata": deepcopy(dict(c.metadata))}
            for c in reversed(chain_channels)
        ],
        "calibration_selection": {
            "source": calibration_state.source.value if calibration_state else "unknown",
            "profile_name": calibration_state.profile_name if calibration_state else None,
        },
    }
    # JSON storage prevents later mutation of nested session dictionaries from changing a job.
    try:
        encoded = json.dumps(config, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError(f"Export provenance must be finite declarative JSON: {exc}") from exc
    frozen_dataset = replace(dataset, metadata=deepcopy(dict(dataset.metadata)))
    frozen_analysis = (
        replace(
            analysis,
            metrics=deepcopy(dict(analysis.metrics)),
            metadata=deepcopy(dict(analysis.metadata)),
        )
        if analysis
        else None
    )
    return ExportSnapshot(frozen_dataset, frozen_analysis, encoded)
