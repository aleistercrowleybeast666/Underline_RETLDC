from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np

from underline_retldc.core.diagnostics import Diagnostic, DiagnosticSeverity
from underline_retldc.core.measurement_statistics import MeasurementStatistics_Calculate
from underline_retldc.core.pipeline import Processing_Passthrough, ThrustPolarity_Apply
from underline_retldc.core.regions import RegionSelection
from underline_retldc.core.source_analysis import (
    SourceAnalysisConfig,
    SourceAnalysisDocument,
    SourceAnalysisInput,
)
from underline_retldc.core.units import (
    Quantity_CanonicalSIUnit,
    Quantity_Dimension,
    Unit_ConvertValues,
    Unit_IsPhysicalForQuantity,
)
from underline_retldc.plugin_api.analyzer import AnalyzerPlugin
from underline_retldc.plugin_api.common import AnalysisResult, TaskContext
from underline_retldc.plugin_api.processor import ProcessorPlugin


@dataclass(slots=True)
class SourceAnalysisState:
    config: SourceAnalysisConfig
    results: dict[str, AnalysisResult] = field(default_factory=dict)
    calculator: dict[str, Any] = field(default_factory=dict)
    completed: bool = False
    error: str = ""

    def document(self) -> SourceAnalysisDocument:
        return SourceAnalysisDocument(
            self.config,
            self.completed,
            dict(self.calculator),
            {key: result.to_dict() for key, result in self.results.items()},
        )


def SourceAnalysis_Calculate(
    config: SourceAnalysisConfig,
    inputs: tuple[SourceAnalysisInput, ...],
    context: TaskContext,
    *,
    analyzer: AnalyzerPlugin | None = None,
    processor: ProcessorPlugin | None = None,
) -> SourceAnalysisState:
    """Orchestrate existing calculators on one Source's scientific clock/parameters."""
    if not inputs or tuple(item.reference for item in inputs) != config.channels:
        raise ValueError("Select the calculation Channels for this Source")
    single = config.workspace_id != "temperature"
    if single and len(inputs) != 1:
        raise ValueError("This calculation requires exactly one Channel")
    expected_dimension = {
        "thrust_analysis": "force",
        "chamber_pressure": "pressure",
        "temperature": "temperature",
    }.get(config.workspace_id)
    if config.workspace_id != "thrust_analysis" and config.input_stage != "calibrated":
        raise ValueError("Processed thrust input is only available for thrust calculations")
    if config.processor is not None and config.input_stage != "project_processed":
        if processor is None:
            raise ValueError("The selected source Processor is unavailable")
        if processor.requirements().get("processor_role") != "motor_weight_compensation":
            raise ValueError("Processor does not support motor-weight compensation")
    state = SourceAnalysisState(config)
    for index, item in enumerate(inputs):
        context.raise_if_cancelled()
        if item.reference.source_id != config.source_id:
            raise ValueError("Calculation input belongs to another Source")
        channel = item.dataset.channel(item.channel_id)
        dimension = Quantity_Dimension(channel.quantity)
        if expected_dimension is not None and dimension != expected_dimension:
            raise ValueError("Channel Quantity is incompatible with this workspace")
        if not Unit_IsPhysicalForQuantity(channel.quantity, channel.data_unit):
            raise ValueError(
                f"Quantity/Unit cannot be calculated: {channel.quantity}/{channel.data_unit}"
            )
        time = item.dataset.project_time
        finite = np.isfinite(time) & np.isfinite(channel.values)
        finite_times = time[np.isfinite(time)]
        if not finite_times.size or not np.any(finite):
            raise ValueError(f"No finite measurement data: {item.label}")
        interval = config.interval or (float(np.min(finite_times)), float(np.max(finite_times)))
        start, end = interval
        if start >= end:
            raise ValueError("Calculation interval requires finite start < end")
        active = finite & (time >= start) & (time <= end)
        active_time = time[active]
        if not active_time.size:
            raise ValueError("Calculation interval contains no finite samples")
        if np.any(np.diff(active_time) <= 0):
            raise ValueError("Calculation timestamps must be strictly increasing")
        diagnostics: list[Diagnostic] = []
        if np.count_nonzero(~finite):
            diagnostics.append(
                Diagnostic(
                    DiagnosticSeverity.WARNING,
                    "source_analysis.non_finite_samples",
                    "Existing calculators use finite samples; "
                    "original arrays and plot gaps are retained",
                )
            )
        if config.workspace_id == "thrust_analysis":
            if not isinstance(analyzer, AnalyzerPlugin):
                raise ValueError("No thrust Analyzer is available")
            dataset, channel_id = item.dataset, item.channel_id
            processing_metadata: dict[str, Any] = dict(item.processing_metadata)
            if config.input_stage != "project_processed":
                oriented = ThrustPolarity_Apply(
                    dataset,
                    input_channel_id=channel_id,
                    polarity=config.polarity,
                )
                if processor is None:
                    processed = Processing_Passthrough(oriented, input_channel_id="thrust_oriented")
                else:
                    selection = RegionSelection.from_dict(
                        {
                            "pre": config.pre,
                            "burn": interval,
                            "post": config.post,
                        }
                    )
                    processor_config = dict(config.processor["config"] if config.processor else {})
                    injections = {
                        "processor.selection": True,
                        "thrust_analysis.input_channel": "thrust_oriented",
                        "thrust_analysis.regions": selection.to_dict(),
                    }
                    for name, schema in processor.config_schema().get("properties", {}).items():
                        source = schema.get("x-ui-source") if isinstance(schema, dict) else None
                        if source in injections:
                            processor_config[name] = injections[source]
                    processed = processor.process(oriented, processor_config, context)
                dataset = processed.dataset
                outputs = tuple(
                    candidate for candidate in processed.output_channel_ids
                    if processed.dataset.channel(candidate).role == "processed"
                )
                if len(outputs) != 1:
                    raise ValueError("Source Processor must produce one final processed Channel")
                channel_id = outputs[0]
                processing_metadata = dict(processed.metadata)
                diagnostics.extend(processed.diagnostics)
            result = analyzer.analyze(
                dataset,
                {
                    "channel_id": channel_id,
                    "ignition": start,
                    "burnout": end,
                    "propellant_mass_kg": config.propellant_mass_kg,
                    "equivalent_mass_change_kg": processing_metadata.get(
                        "equivalent_mass_change_kg"
                    ),
                },
                context,
            )
            if config.propellant_mass_kg is None:
                diagnostics.append(
                    Diagnostic(
                        DiagnosticSeverity.WARNING,
                        "source_analysis.propellant_mass_missing",
                        "Specific impulse is unavailable: "
                        "no propellant mass was set for this Source",
                    )
                )
            descriptor = analyzer.descriptor
            state.calculator = {
                "id": descriptor.plugin_id,
                "version": descriptor.version,
                "api_version": descriptor.api_version,
            }
            result = replace(result, diagnostics=(*result.diagnostics, *diagnostics))
        else:
            si_unit = Quantity_CanonicalSIUnit(channel.quantity)
            if si_unit is None:
                raise ValueError("No canonical Unit exists for this Quantity")
            values = Unit_ConvertValues(channel.values, channel.data_unit, si_unit)
            statistics = MeasurementStatistics_Calculate(time, values, interval)
            metric_names = {
                "chamber_pressure": (
                    "test_start_value",
                    "active_mean",
                    "active_maximum",
                    "active_time_to_maximum_s",
                    "active_minimum",
                ),
                "temperature": (
                    "test_start_value",
                    "active_maximum",
                    "full_maximum",
                    "full_maximum_time_s",
                ),
            }.get(
                config.workspace_id,
                (
                    "active_minimum",
                    "active_mean",
                    "active_maximum",
                    "full_maximum",
                ),
            )
            metrics = {key: getattr(statistics, key) for key in metric_names}
            if config.workspace_id != "temperature" and statistics.active_mean is None:
                diagnostics.append(
                    Diagnostic(
                        DiagnosticSeverity.WARNING,
                        "source_analysis.mean_unavailable",
                        "Time-weighted mean requires two finite samples at distinct timestamps",
                    )
                )
            result = AnalysisResult(
                metrics,
                diagnostics,
                {
                    "input_quantity": channel.quantity,
                    "input_data_unit": si_unit,
                    "metric_units": {
                        key: "s" if key.endswith("_s") else si_unit for key in metrics
                    },
                },
            )
            state.calculator = {"id": "core.measurement_statistics", "version": "1"}
        for value in result.metrics.values():
            if isinstance(value, (int, float)) and not math.isfinite(float(value)):
                raise ValueError("Calculation produced a nonfinite metric")
        metadata = {
            **result.metadata,
            "source_id": config.source_id,
            "source_display_unit": channel.display_unit,
            "reference": item.reference.to_dict(),
            "label": item.label,
            "interval": list(interval),
            "clock": "dataset.project_time",
            "display_transform_applied": False,
            "input_stage": config.input_stage,
        }
        state.results[item.reference.stable_id] = replace(result, metadata=metadata)
        context.report_progress((index + 1) / len(inputs), "Source calculation complete")
    state.completed = True
    return state
