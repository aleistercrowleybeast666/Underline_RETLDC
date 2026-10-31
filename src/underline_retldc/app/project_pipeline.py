from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from underline_retldc.app.session import AnalysisSession, ChannelCalibrationState
from underline_retldc.app.source_analysis import SourceAnalysis_Calculate, SourceAnalysisState
from underline_retldc.app.source_input import Source_ParseVerified
from underline_retldc.core.calibration import CalibrationSelectionSource
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.motor_parameters import MotorPhysicalParameters
from underline_retldc.core.pipeline import (
    THRUST_ORIENTED_CHANNEL_ID,
    Calibration_Apply,
    Calibration_OutputChannelId,
    Processing_Passthrough,
    ThrustPolarity_Apply,
)
from underline_retldc.core.primary_channels import (
    PrimaryChannels_AutoBind,
    PrimaryChannels_Validate,
)
from underline_retldc.core.project import (
    ChannelProjectState,
    PluginReference,
    Project_Load,
    Project_SourceHash,
    Project_SourceResolve,
    ProjectDocument,
    ProjectSourceHashMismatchError,
    ProjectSourceResolveResult,
    ProjectSourceState,
    ProjectStreamState,
)
from underline_retldc.core.project_data import (
    ChannelReference,
    ProjectData,
    Source,
    SourceKind,
    Stream,
)
from underline_retldc.core.regions import RegionSelection
from underline_retldc.core.registry import PluginRegistry
from underline_retldc.core.source_analysis import SourceAnalysis_UseSharedMotor, SourceAnalysisInput
from underline_retldc.plugin_api.common import (
    AnalysisResult,
    ParseResult,
    ProcessingResult,
    TaskCancelledError,
    TaskContext,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_CALIBRATION_ID = "builtin.calibration.identity"


class ProjectPipeline:
    """The one project replay implementation used by GUI and headless exports.

    It executes only the stages recorded as complete. Optional source calculations
    retain their previous failure isolation and cannot advance the main workflow.
    """

    registry: PluginRegistry

    @classmethod
    def Project_LoadSession(
        cls,
        project_path: Path,
        registry: PluginRegistry,
        context: TaskContext,
        *,
        relocated_sources: Mapping[str, Path] | None = None,
    ) -> AnalysisSession:
        service = cls()
        service.registry = registry
        project_path = Path(project_path).resolve()
        document = Project_Load(project_path)
        document, raw_source, parsed, calibrated, processing, analysis = service._project_recompute(
            document,
            context,
            project_path=project_path,
            relocated_sources=relocated_sources,
        )
        project = service._recomputed_project_data
        primary = project.primary_channels.thrust
        primary_stream_id = primary.stream_id if primary else next(iter(project.streams), None)
        stream_states, states = service._project_calibration_states_restore(
            document,
            project,
            primary_stream_id,
        )
        return AnalysisSession(
            project_path=project_path,
            source_path=raw_source,
            source_hash=document.source_hash,
            parser_id=document.parser.id if document.parser else None,
            parser_config=dict(document.parser.config) if document.parser else {},
            raw_dataset=parsed.dataset if parsed else None,
            project_data=project,
            primary_stream_id=primary_stream_id,
            active_stream_id=primary_stream_id,
            calibrated_streams=dict(service._recomputed_calibrated_streams),
            channel_calibrations=states,
            stream_channel_calibrations=stream_states,
            calibrated_dataset=calibrated,
            thrust_polarity=document.thrust_polarity,
            processor_id=document.processors[0].id if document.processors else None,
            processor_config=dict(document.processors[0].config) if document.processors else {},
            processing_result=processing,
            regions=dict(document.regions),
            analyzer_id=document.analyzer.id if document.analyzer else None,
            analyzer_config=dict(document.analyzer.config) if document.analyzer else {},
            analysis_result=analysis,
            motor_metadata=dict(document.motor_metadata),
            source_analyses=dict(service._recomputed_source_analyses),
        )

    @staticmethod
    def _channel_reference_key(source_id: str, stream_id: str, channel_id: str) -> str:
        return ChannelReference(source_id, stream_id, channel_id).stable_id

    @staticmethod
    def _project_channel_states_for_stream(
        document: ProjectDocument,
        source_id: str,
        stream_id: str,
        *,
        include_legacy: bool = False,
    ) -> tuple[ChannelProjectState, ...]:
        selected: dict[str, ChannelProjectState] = {}
        for state in document.channels.values():
            is_exact = state.stream_id == stream_id and state.source_id in (None, source_id)
            is_legacy = include_legacy and state.stream_id is None and state.source_id is None
            if is_exact or (is_legacy and state.channel_id not in selected):
                selected[state.channel_id] = state
        return tuple(selected.values())

    @staticmethod
    def _regions_normalize(
        regions: Mapping[str, Any],
    ) -> dict[str, list[float] | None]:
        active = regions.get("active_test", regions.get("burn"))
        selection = RegionSelection.from_dict(
            {
                "pre": regions.get("pre"),
                "burn": active,
                "post": regions.get("post"),
            }
        )
        payload = selection.to_dict()
        return {
            "pre": payload["pre"],
            "active_test": payload["burn"],
            "post": payload["post"],
        }

    def _project_calibrations_apply(
        self,
        dataset: Any,
        channel_states: tuple[ChannelProjectState, ...],
        *,
        legacy_reference: PluginReference | None = None,
    ) -> Any:
        """Restore every raw Channel's independent calibration without using its Unit."""
        states_by_channel = {state.channel_id: state for state in channel_states}
        identity = self.registry.get(DEFAULT_CALIBRATION_ID)
        legacy_config = dict(legacy_reference.config) if legacy_reference is not None else {}
        legacy_input_channel_id = str(legacy_config.get("input_channel_id", ""))
        legacy_applied = legacy_reference is None
        calibrated = dataset
        for source in tuple(dataset.channels.values()):
            if source.role != "raw":
                continue
            state = states_by_channel.get(source.id)
            reference = state.calibration if state is not None else None
            if (
                reference is None
                and state is None
                and legacy_reference is not None
                and source.id == legacy_input_channel_id
            ):
                reference = legacy_reference
                legacy_applied = True
            if reference is None:
                model = identity
                config: dict[str, Any] = {}
            else:
                model = self._plugin_reference_resolve(reference)
                config = dict(reference.config)
            is_identity = model.descriptor.plugin_id == DEFAULT_CALIBRATION_ID
            output_channel_id = str(
                (
                    state.output_channel_id
                    if state is not None and state.output_channel_id
                    else config.get("output_channel_id")
                )
                or Calibration_OutputChannelId(source)
            )
            calibrated = Calibration_Apply(
                calibrated,
                model,
                input_channel_id=source.id,
                output_channel_id=output_channel_id,
                quantity=(
                    source.quantity if is_identity else str(config.get("quantity", source.quantity))
                ),
                unit=(
                    source.data_unit if is_identity else str(config.get("unit", source.data_unit))
                ),
                parameters=dict(config.get("parameters", {})),
            )
        if not legacy_applied:
            raise ValueError(
                "Project calibration input Channel "
                f"{legacy_input_channel_id!r} is missing from parsed source"
            )
        return calibrated

    def _project_calibration_states_restore(
        self,
        document: ProjectDocument,
        project_data: ProjectData,
        primary_stream_id: str | None,
    ) -> tuple[
        dict[str, ChannelCalibrationState],
        dict[str, ChannelCalibrationState],
    ]:
        """Restore explicit per-Channel selections, including legacy and Identity defaults."""
        stream_states: dict[str, ChannelCalibrationState] = {}
        primary_states: dict[str, ChannelCalibrationState] = {}
        legacy_config = (
            dict(document.calibration.config) if document.calibration is not None else {}
        )
        legacy_input_channel_id = str(legacy_config.get("input_channel_id", ""))
        for stream in project_data.streams.values():
            is_primary = stream.id == primary_stream_id
            channel_states = self._project_channel_states_for_stream(
                document,
                stream.source_id,
                stream.id,
                include_legacy=is_primary,
            )
            states_by_channel = {state.channel_id: state for state in channel_states}
            for source in stream.dataset.channels.values():
                if source.role != "raw":
                    continue
                project_state = states_by_channel.get(source.id)
                reference = project_state.calibration if project_state is not None else None
                if (
                    reference is None
                    and project_state is None
                    and is_primary
                    and document.calibration is not None
                    and source.id == legacy_input_channel_id
                ):
                    reference = document.calibration
                if reference is None:
                    plugin_id = DEFAULT_CALIBRATION_ID
                    config: dict[str, Any] = {}
                    selection_source = CalibrationSelectionSource.FACTORY_DEFAULT
                else:
                    plugin_id = reference.id
                    config = dict(reference.config)
                    selection_source = CalibrationSelectionSource.PROJECT
                output_channel_id = str(
                    (
                        project_state.output_channel_id
                        if project_state is not None and project_state.output_channel_id
                        else config.get("output_channel_id")
                    )
                    or Calibration_OutputChannelId(source)
                )
                config.update(
                    {
                        "input_channel_id": source.id,
                        "output_channel_id": output_channel_id,
                        "data_quantity": source.quantity,
                        "data_unit": source.data_unit,
                        "display_unit": source.effective_display_unit(),
                        "semantic_role": source.semantic_role,
                    }
                )
                if plugin_id == DEFAULT_CALIBRATION_ID:
                    config.update(
                        {
                            "quantity": source.quantity,
                            "unit": source.data_unit,
                            "parameters": {},
                        }
                    )
                else:
                    config.setdefault("quantity", source.quantity)
                    config.setdefault("unit", source.data_unit)
                    config.setdefault("parameters", {})
                calibration_state = ChannelCalibrationState(
                    source.id,
                    output_channel_id,
                    plugin_id,
                    config,
                    selection_source,
                )
                key = self._channel_reference_key(stream.source_id, stream.id, source.id)
                stream_states[key] = calibration_state
                if is_primary:
                    primary_states[source.id] = calibration_state
        return stream_states, primary_states

    def _project_recompute(
        self,
        document: ProjectDocument,
        context: TaskContext,
        *,
        raw_source: Path | None = None,
        project_path: Path | None = None,
        relocated_sources: Mapping[str, Path] | None = None,
    ) -> tuple[
        ProjectDocument,
        Path | None,
        ParseResult | None,
        Dataset | None,
        ProcessingResult | None,
        AnalysisResult | None,
    ]:
        if relocated_sources:
            known = {source.source_id for source in document.sources}
            if set(relocated_sources) - known:
                raise ValueError("Relocation refers to an unknown Source ID")
            states = []
            for source in document.sources:
                if source.source_id not in relocated_sources:
                    states.append(source)
                    continue
                if source.sha256 is None:
                    raise ValueError("Relocation requires a recorded SHA-256; reimport explicitly")
                path = Path(relocated_sources[source.source_id]).resolve()
                actual = Project_SourceHash(path)
                if actual != source.sha256:
                    raise ProjectSourceHashMismatchError(source.sha256, actual)
                states.append(replace(source, path=str(path)))
                if source.path == document.source_path:
                    document = replace(document, source_path=str(path))
            document = replace(document, sources=tuple(states))
        payload = self._project_pipeline_recompute(
            document, context, raw_source=raw_source, project_path=project_path
        )
        document = payload[0]
        parameters = MotorPhysicalParameters.from_metadata(document.motor_metadata)
        project = self._recomputed_project_data
        calibrated_streams = self._recomputed_calibrated_streams
        inputs_by_id: dict[str, SourceAnalysisInput] = {}
        for reference in project.channel_references():
            stream = project.streams[reference.stream_id]
            dataset = calibrated_streams.get(stream.id, stream.dataset)
            states = self._project_channel_states_for_stream(
                document,
                reference.source_id,
                reference.stream_id,
                include_legacy=len(project.streams) == 1,
            )
            channel_state = next(
                (state for state in states if state.channel_id == reference.channel_id), None
            )
            channel_id = reference.channel_id
            if dataset is not stream.dataset:
                if channel_state and channel_state.output_channel_id:
                    channel_id = channel_state.output_channel_id
                else:
                    matches = tuple(
                        channel.id
                        for channel in dataset.channels.values()
                        if channel.role == "calibrated"
                        and channel.metadata.get("source_channel_id") == reference.channel_id
                    )
                    if len(matches) == 1:
                        channel_id = matches[0]
            inputs_by_id[reference.stable_id] = SourceAnalysisInput(
                reference,
                dataset,
                channel_id,
                f"{project.sources[reference.source_id].path.name} — "
                f"{project.channel(reference).name}",
            )
        self._recomputed_source_analyses = {}
        for key, saved in document.source_analyses.items():
            config = saved.config
            source = project.sources.get(config.source_id)
            shared = config.mass_source == "project" or (
                source is not None and source.source_kind == SourceKind.THEORETICAL
            )
            if shared:
                config = SourceAnalysis_UseSharedMotor(config, parameters)
            state = SourceAnalysisState(config)
            if saved.completed:
                try:
                    inputs = tuple(inputs_by_id[item.stable_id] for item in config.channels)
                    if config.input_stage == "project_processed":
                        processing = payload[4]
                        binding = project.primary_channels.thrust
                        if processing is None or config.channels != (binding,):
                            raise ValueError("Source calculation has no matching processed curve")
                        inputs = (
                            SourceAnalysisInput(
                                binding,
                                processing.dataset,
                                "thrust_processed",
                                inputs[0].label,
                                processing.metadata,
                            ),
                        )
                    analyzer = None
                    if config.workspace_id == "thrust_analysis":
                        reference = PluginReference.from_dict(saved.calculator)
                        analyzer = self._plugin_reference_resolve(reference)
                    elif saved.calculator != {"id": "core.measurement_statistics", "version": "1"}:
                        raise ValueError("Unsupported saved measurement calculator version")
                    processor = (
                        self._plugin_reference_resolve(PluginReference.from_dict(config.processor))
                        if config.processor and config.input_stage != "project_processed"
                        else None
                    )
                    state = SourceAnalysis_Calculate(
                        config,
                        inputs,
                        context,
                        analyzer=analyzer,
                        processor=processor,
                        motor_parameters=parameters if shared else None,
                    )
                except TaskCancelledError:
                    raise
                except Exception as exc:
                    # An optional Source calculator failure must not discard the Project.
                    state.error = str(exc)
                    LOGGER.warning("Source calculation %s could not reopen: %s", key, exc)
            self._recomputed_source_analyses[key] = state
        document = replace(
            document,
            source_analyses={
                key: state.document() for key, state in self._recomputed_source_analyses.items()
            },
        )
        return (document, *payload[1:])

    def _project_pipeline_recompute(
        self,
        document: ProjectDocument,
        context: TaskContext,
        *,
        raw_source: Path | None = None,
        project_path: Path | None = None,
    ) -> tuple[
        ProjectDocument,
        Path | None,
        ParseResult | None,
        Dataset | None,
        ProcessingResult | None,
        AnalysisResult | None,
    ]:
        self._recompute_project_path = project_path
        self._project_references_validate(document)
        self._recomputed_project_data = ProjectData()
        self._recomputed_calibrated_streams = {}
        source_validated = False
        if raw_source is None:
            resolution = Project_SourceResolve(document, project_path=project_path)
            if resolution.result is ProjectSourceResolveResult.NOT_CONFIGURED:
                return document, None, None, None, None, None
            if resolution.result is ProjectSourceResolveResult.MISSING:
                raise FileNotFoundError(f"Project source is missing: {resolution.path}")
            if resolution.result is ProjectSourceResolveResult.HASH_MISMATCH:
                raise ProjectSourceHashMismatchError(
                    document.source_hash or "N/A", resolution.actual_hash or "N/A"
                )
            raw_source = resolution.path
            source_validated = document.source_hash is not None
        if raw_source is None:
            return document, None, None, None, None, None
        if document.source_hash and not source_validated:
            actual_hash = Project_SourceHash(raw_source)
            if actual_hash != document.source_hash:
                raise ProjectSourceHashMismatchError(document.source_hash, actual_hash)
        if document.parser is None:
            return document, raw_source, None, None, None, None
        workflow_state = dict(document.workflow_state)
        if not workflow_state:
            workflow_state = {
                "parsed": document.parser is not None,
                "calibrated": document.calibration is not None,
                "processed": bool(document.processors),
                "analyzed": document.analyzer is not None,
            }
        if not workflow_state.get("parsed", False):
            return document, raw_source, None, None, None, None
        parser = self._plugin_reference_resolve(document.parser)
        parse_result = Source_ParseVerified(
            parser,
            raw_source,
            document.parser.config,
            context,
            expected_sha256=document.source_hash,
        )
        primary_source_id = "source_1"
        primary_stream_id = "stream_1"
        if document.sources and document.streams:
            primary_reference = (
                document.primary_channels.thrust
                or document.primary_channels.chamber_pressure
                or next(iter(document.primary_channels.temperature_channels), None)
            )
            matching_sources = tuple(
                item
                for item in document.sources
                if Path(item.path) == Path(document.source_path or raw_source)
            )
            primary_source_state = next(
                (
                    item
                    for item in matching_sources
                    if primary_reference is not None
                    and item.source_id == primary_reference.source_id
                ),
                next(iter(matching_sources), document.sources[0]),
            )
            primary_stream_state = next(
                (
                    item
                    for item in document.streams
                    if item.source_id == primary_source_state.source_id
                    and (
                        primary_reference is None
                        or primary_reference.source_id != primary_source_state.source_id
                        or item.stream_id == primary_reference.stream_id
                    )
                ),
                None,
            )
            if primary_stream_state is not None:
                primary_source_id = primary_source_state.source_id
                primary_stream_id = primary_stream_state.stream_id
                primary_stream = Stream(
                    primary_stream_state.stream_id,
                    primary_source_state.source_id,
                    parse_result.dataset,
                    primary_stream_state.time_offset_s,
                    primary_stream_state.name,
                )
                parse_result = ParseResult(
                    primary_stream.dataset, primary_stream.dataset.diagnostics
                )
        primary_channel_states = self._project_channel_states_for_stream(
            document,
            primary_source_id,
            primary_stream_id,
            include_legacy=True,
        )
        if primary_channel_states:
            raw_dataset = parse_result.dataset
            for channel_state in primary_channel_states:
                channel_id = channel_state.channel_id
                if channel_id not in raw_dataset.channels:
                    raise ValueError(
                        f"Project Channel {channel_id!r} is missing from parsed source"
                    )
                raw_dataset = raw_dataset.with_channel_interpretation(
                    channel_id,
                    quantity=channel_state.quantity,
                    data_unit=channel_state.data_unit,
                    display_unit=channel_state.display_unit,
                    semantic_role=channel_state.semantic_role,
                    unit_source=channel_state.unit_source,
                )
            parse_result = ParseResult(raw_dataset, raw_dataset.diagnostics)
        self._project_streams_recompute(
            document,
            context,
            primary_source=raw_source,
            primary_dataset=parse_result.dataset,
            apply_identity=workflow_state.get("calibrated", False),
        )
        if not workflow_state.get("calibrated", False):
            return document, raw_source, parse_result, None, None, None
        thrust_reference = self._recomputed_project_data.primary_channels.thrust
        if thrust_reference is not None:
            calibrated = self._recomputed_calibrated_streams[thrust_reference.stream_id]
            input_candidates = tuple(
                channel.id
                for channel in calibrated.channels.values()
                if channel.role == "calibrated"
                and channel.metadata.get("source_channel_id") == thrust_reference.channel_id
            )
            if len(input_candidates) != 1:
                raise ValueError(
                    "Primary Thrust Calibration output could not be resolved from "
                    f"{thrust_reference.stable_id}"
                )
            thrust_input_channel_id = input_candidates[0]
        else:
            calibrated = self._project_calibrations_apply(
                parse_result.dataset,
                primary_channel_states,
                legacy_reference=(document.calibration if not primary_channel_states else None),
            )
            thrust_input_channel_id = None
        processor = None
        processor_reference = None
        if document.processors:
            processor_reference = document.processors[0]
            processor = self._plugin_reference_resolve(processor_reference)
        processing_result = None
        if workflow_state.get("processed", False):
            if thrust_input_channel_id is None:
                raise ValueError("Processed Project has no Primary Thrust Channel binding")
            oriented = ThrustPolarity_Apply(
                calibrated,
                input_channel_id=thrust_input_channel_id,
                polarity=document.thrust_polarity,
            )
            processor_input_channel_id = THRUST_ORIENTED_CHANNEL_ID
            if processor is None or processor_reference is None:
                processing_result = Processing_Passthrough(
                    oriented,
                    input_channel_id=processor_input_channel_id,
                )
            else:
                processor_config = dict(processor_reference.config)
                schema_properties = processor.config_schema().get("properties", {})
                if isinstance(schema_properties, Mapping):
                    normalized_regions = self._regions_normalize(document.regions)
                    injected = {
                        "thrust_analysis.input_channel": processor_input_channel_id,
                        "thrust_analysis.regions": {
                            "pre": normalized_regions.get("pre"),
                            "burn": normalized_regions.get("active_test"),
                            "post": normalized_regions.get("post"),
                        },
                    }
                    for field_name, field_schema in schema_properties.items():
                        if not isinstance(field_schema, Mapping):
                            continue
                        source = field_schema.get("x-ui-source")
                        if source in injected:
                            processor_config[str(field_name)] = injected[str(source)]
                processing_result = processor.process(oriented, processor_config, context)
        if (
            processing_result is None
            or document.analyzer is None
            or not workflow_state.get("analyzed", False)
        ):
            return document, raw_source, parse_result, calibrated, processing_result, None
        analyzer = self._plugin_reference_resolve(document.analyzer)
        parameters = MotorPhysicalParameters.from_metadata(document.motor_metadata)
        analyzer_config = {**document.analyzer.config, **parameters.to_dict()}
        document = replace(document, analyzer=replace(document.analyzer, config=analyzer_config))
        analysis = analyzer.analyze(processing_result.dataset, analyzer_config, context)
        analysis = replace(
            analysis,
            metadata={
                **analysis.metadata,
                "motor_parameters": parameters.to_dict(),
                "mass_source": "project",
            },
        )
        return (
            document,
            raw_source,
            parse_result,
            calibrated,
            processing_result,
            analysis,
        )

    def _project_references_validate(self, document: ProjectDocument) -> None:
        references = [
            document.parser,
            document.calibration,
            *(source.parser for source in document.sources),
            *document.processors,
            document.analyzer,
            *(
                state.calibration
                for state in document.channels.values()
                if state.calibration is not None
            ),
        ]
        for reference in references:
            if reference is not None:
                self._plugin_reference_resolve(reference)

    def _project_streams_recompute(
        self,
        document: ProjectDocument,
        context: TaskContext,
        *,
        primary_source: Path,
        primary_dataset: Any,
        apply_identity: bool,
    ) -> None:
        source_states = document.sources or (
            ProjectSourceState(
                "source_1",
                str(primary_source),
                document.source_hash,
                document.parser,
            ),
        )
        stream_states = document.streams or tuple(
            ProjectStreamState(
                f"stream_{index + 1}",
                source.source_id,
                0.0,
                Path(source.path).name,
            )
            for index, source in enumerate(source_states)
        )
        sources: dict[str, Source] = {}
        streams: dict[str, Stream] = {}
        calibrated_streams: dict[str, Any] = {}
        primary_resolved = primary_source.resolve()
        for index, source_state in enumerate(source_states):
            configured_path = Path(source_state.path)
            is_primary = (
                source_state.source_id == primary_dataset.source_id
                if primary_dataset.source_id is not None
                else index == 0
            )
            shares_primary_path = (
                document.source_path is not None and Path(document.source_path) == configured_path
            )
            actual_path = (
                primary_resolved
                if is_primary or shares_primary_path
                else (
                    configured_path
                    if configured_path.is_absolute()
                    else self._recompute_project_path.parent / configured_path
                    if self._recompute_project_path is not None
                    else configured_path
                ).resolve()
            )
            if not actual_path.is_file():
                raise FileNotFoundError(f"Project Source is missing: {actual_path}")
            if source_state.sha256 is not None:
                actual_hash = Project_SourceHash(actual_path)
                if actual_hash != source_state.sha256:
                    raise ProjectSourceHashMismatchError(source_state.sha256, actual_hash)
            parser_reference = source_state.parser or document.parser
            if parser_reference is None:
                raise ValueError(f"Project Source {source_state.source_id!r} has no Parser")
            if is_primary:
                dataset = primary_dataset
            else:
                parser = self._plugin_reference_resolve(parser_reference)
                dataset = Source_ParseVerified(
                    parser,
                    actual_path,
                    parser_reference.config,
                    context,
                    expected_sha256=source_state.sha256,
                ).dataset
            source_record = Source(
                source_state.source_id,
                actual_path,
                sha256=dataset.metadata.get("source_sha256", source_state.sha256),
                parser_id=parser_reference.id,
                parser_version=parser_reference.version,
                parser_config=parser_reference.config,
                source_kind=source_state.source_kind,
                display_transform=source_state.display_transform,
            )
            sources[source_record.id] = source_record
            related_streams = tuple(
                item for item in stream_states if item.source_id == source_record.id
            )
            if not related_streams:
                related_streams = (
                    ProjectStreamState(
                        f"stream_{index + 1}",
                        source_record.id,
                        0.0,
                        actual_path.name,
                    ),
                )
            for stream_state in related_streams:
                channel_states = self._project_channel_states_for_stream(
                    document,
                    source_record.id,
                    stream_state.stream_id,
                    include_legacy=is_primary,
                )
                interpreted_dataset = dataset
                for channel_state in channel_states:
                    if channel_state.channel_id not in interpreted_dataset.channels:
                        raise ValueError(
                            "Project Channel "
                            f"{channel_state.persistent_key!r} is missing from parsed source"
                        )
                    interpreted_dataset = interpreted_dataset.with_channel_interpretation(
                        channel_state.channel_id,
                        quantity=channel_state.quantity,
                        data_unit=channel_state.data_unit,
                        display_unit=channel_state.display_unit,
                        semantic_role=channel_state.semantic_role,
                        unit_source=channel_state.unit_source,
                    )
                stream = Stream(
                    stream_state.stream_id,
                    source_record.id,
                    interpreted_dataset,
                    stream_state.time_offset_s,
                    stream_state.name,
                )
                streams[stream.id] = stream
                stream_calibrated = (
                    stream.id in document.calibrated_stream_ids
                    if document.calibrated_stream_ids is not None
                    else apply_identity
                )
                if stream_calibrated:
                    calibrated_streams[stream.id] = self._project_calibrations_apply(
                        stream.dataset,
                        channel_states,
                        legacy_reference=(
                            document.calibration if is_primary and not channel_states else None
                        ),
                    )
        project_data = ProjectData(sources, streams)
        bindings = (
            document.primary_channels
            if document.primary_channels_explicit
            else PrimaryChannels_AutoBind(project_data)
        )
        PrimaryChannels_Validate(project_data, bindings)
        self._recomputed_project_data = project_data.with_primary_channels(bindings)
        self._recomputed_calibrated_streams = calibrated_streams

    def _plugin_reference_resolve(self, reference: PluginReference):
        try:
            plugin = self.registry.get(reference.id)
        except KeyError as exc:
            raise ValueError(
                f"Project plugin {reference.id}@{reference.version} is not installed"
            ) from exc
        descriptor = plugin.descriptor
        if descriptor.api_version != reference.api_version:
            raise ValueError(
                f"Plugin API mismatch for {reference.id}: project {reference.api_version}, "
                f"installed {descriptor.api_version}"
            )
        if descriptor.version != reference.version:
            raise ValueError(
                f"Plugin version mismatch for {reference.id}: project {reference.version}, "
                f"installed {descriptor.version}"
            )
        return plugin
