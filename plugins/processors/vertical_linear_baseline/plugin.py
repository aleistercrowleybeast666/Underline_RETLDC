from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np

from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.diagnostics import Diagnostic, DiagnosticSeverity
from underline_retldc.core.regions import RegionSelection
from underline_retldc.core.units import (
    G0_STANDARD_M_S2,
    Unit_ConvertValue,
    Unit_IsPhysicalForQuantity,
)
from underline_retldc.plugin_api.common import (
    PluginDescriptor,
    PluginType,
    ProcessingResult,
    TaskContext,
)
from underline_retldc.plugin_api.processor import (
    PROCESSOR_ROLE_MOTOR_WEIGHT_COMPENSATION,
    ProcessorPlugin,
)


class VerticalLinearBaselineProcessor(ProcessorPlugin):
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="builtin.processor.vertical_linear_baseline",
            plugin_type=PluginType.PROCESSOR,
            version="1.0.0",
            api_version="1",
            name="Vertical Linear Baseline Compensation",
            description="PRE/POST linear fits with a linearly changing burn baseline",
            translation_key="processor.vertical_linear.name",
        )

    def config_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["input_channel_id", "sign", "regions"],
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "default": True,
                    "x-ui-hidden": True,
                    "x-ui-source": "processor.selection",
                },
                "input_channel_id": {
                    "type": "string",
                    "x-ui-hidden": True,
                    "x-ui-source": "thrust_analysis.input_channel",
                },
                "sign": {
                    "type": "integer",
                    "enum": [-1, 1],
                    "default": 1,
                    "title": "Thrust Sign",
                    "x-i18n-key": "process.sign",
                    "x-enum-i18n-keys": {
                        "1": "process.sign_positive",
                        "-1": "process.sign_negative",
                    },
                },
                "regions": {
                    "type": "object",
                    "x-ui-hidden": True,
                    "x-ui-source": "thrust_analysis.regions",
                },
            },
        }

    def requirements(self) -> Mapping[str, Any]:
        return {
            "processor_role": PROCESSOR_ROLE_MOTOR_WEIGHT_COMPENSATION,
            "quantity": "force",
            "minimum_pre_samples": 2,
            "minimum_post_samples": 2,
        }

    @staticmethod
    def _fit(time: np.ndarray, values: np.ndarray, label: str) -> tuple[float, float]:
        finite = np.isfinite(time) & np.isfinite(values)
        fit_time = time[finite]
        fit_values = values[finite]
        if len(fit_time) < 2 or len(np.unique(fit_time)) < 2:
            raise ValueError(f"{label} requires at least two finite samples at distinct times")
        slope, intercept = np.polyfit(fit_time, fit_values, 1)
        if not math.isfinite(float(slope)) or not math.isfinite(float(intercept)):
            raise ValueError(f"{label} baseline fit is not finite")
        return float(slope), float(intercept)

    def _fit_or_assume_zero(
        self,
        time: np.ndarray,
        values: np.ndarray,
        region,
        boundary: float,
        label: str,
        diagnostics: list[Diagnostic],
    ) -> tuple[float, float, float, str]:
        if region is not None:
            mask = (time >= region.start) & (time <= region.end)
            try:
                slope, intercept = self._fit(time[mask], values[mask], label)
                return slope, intercept, slope * boundary + intercept, "measured_fit"
            except ValueError:
                pass
        code = f"processing.{label.lower()}_baseline_assumed_zero"
        diagnostics.append(
            Diagnostic(
                DiagnosticSeverity.WARNING,
                code,
                f"{label} baseline is unavailable and was assumed to be zero",
                plugin_id=self.descriptor.plugin_id,
            )
        )
        return 0.0, 0.0, 0.0, "assumed_zero"

    def process(
        self, dataset: Dataset, config: Mapping[str, Any], context: TaskContext
    ) -> ProcessingResult:
        input_id = str(config.get("input_channel_id", "")).strip()
        if not input_id:
            raise ValueError("Vertical baseline processing requires an input Channel")
        source = dataset.channel(input_id)
        if source.quantity.lower() not in {"force", "thrust"}:
            raise ValueError("Vertical baseline processor requires a force/thrust channel")
        sign = int(config.get("sign", 1))
        if sign not in {-1, 1}:
            raise ValueError("Thrust sign must be +1 or -1")
        enabled = bool(config.get("enabled", True))
        time = dataset.project_time
        measured = source.values
        context.raise_if_cancelled()
        diagnostics: list[Diagnostic] = []

        if enabled:
            region_payload = config.get("regions")
            if not isinstance(region_payload, dict):
                raise ValueError("Vertical baseline compensation requires PRE/BURN/POST regions")
            regions = RegionSelection.from_dict(region_payload)
            ignition = regions.burn.start
            burnout = regions.burn.end
            pre_slope, pre_intercept, baseline_start, pre_source = (
                self._fit_or_assume_zero(
                    time,
                    measured,
                    regions.pre,
                    ignition,
                    "PRE",
                    diagnostics,
                )
            )
            context.report_progress(0.3, "PRE baseline resolved")
            post_slope, post_intercept, baseline_end, post_source = (
                self._fit_or_assume_zero(
                    time,
                    measured,
                    regions.post,
                    burnout,
                    "POST",
                    diagnostics,
                )
            )
            burn_baseline = baseline_start + (baseline_end - baseline_start) * (
                (time - ignition) / (burnout - ignition)
            )
            pre_baseline = (
                pre_slope * time + pre_intercept
                if pre_source == "measured_fit"
                else np.zeros_like(measured)
            )
            post_baseline = (
                post_slope * time + post_intercept
                if post_source == "measured_fit"
                else np.zeros_like(measured)
            )
            baseline = np.where(
                time < ignition,
                pre_baseline,
                np.where(time > burnout, post_baseline, burn_baseline),
            )
        else:
            regions = None
            pre_slope = pre_intercept = post_slope = post_intercept = 0.0
            baseline_start = baseline_end = 0.0
            pre_source = post_source = "assumed_zero"
            baseline = np.zeros_like(measured)

        context.raise_if_cancelled()
        corrected = sign * (measured - baseline)
        baseline_channel = Channel(
            id="baseline_model",
            quantity=source.quantity,
            unit=source.data_unit,
            values=baseline,
            role="baseline",
            metadata={"processor_id": self.descriptor.plugin_id, "enabled": enabled},
            unit_source=source.unit_source,
            display_unit=source.display_unit,
            semantic_role=source.semantic_role,
        )
        corrected_channel = Channel(
            id="thrust_corrected",
            quantity="thrust",
            unit=source.data_unit,
            values=corrected,
            role="corrected",
            metadata={"source_channel_id": input_id, "sign": sign},
            unit_source=source.unit_source,
            display_unit=source.display_unit,
            semantic_role="thrust",
        )
        processed_channel = Channel(
            id="thrust_processed",
            quantity="thrust",
            unit=source.data_unit,
            values=corrected,
            role="processed",
            metadata={"source_channel_id": corrected_channel.id, "user_confirmed": False},
            unit_source=source.unit_source,
            display_unit=source.display_unit,
            semantic_role="thrust",
        )
        result_dataset = dataset.with_channel(baseline_channel)
        result_dataset = result_dataset.with_channel(corrected_channel)
        result_dataset = result_dataset.with_channel(processed_channel)
        equivalent_value_change = baseline_start - baseline_end
        equivalent_force_change: float | None = None
        equivalent_mass_change: float | None = None
        baselines_measured = pre_source == post_source == "measured_fit"
        physical_force = Unit_IsPhysicalForQuantity(source.quantity, source.data_unit)
        if baselines_measured and physical_force:
            baseline_start_n = Unit_ConvertValue(baseline_start, source.data_unit, "N")
            baseline_end_n = Unit_ConvertValue(baseline_end, source.data_unit, "N")
            equivalent_force_change = baseline_start_n - baseline_end_n
            equivalent_mass_change = abs(equivalent_force_change) / G0_STANDARD_M_S2
        else:
            diagnostics.append(
                Diagnostic(
                    DiagnosticSeverity.WARNING,
                    (
                        "processing.equivalent_mass_unavailable_assumed_baseline"
                        if not baselines_measured
                        else "processing.equivalent_mass_unavailable_unit"
                    ),
                    "Equivalent mass change is unavailable unless both baselines are "
                    "measured fits in a physical force unit",
                    plugin_id=self.descriptor.plugin_id,
                )
            )

        metadata = {
            "enabled": enabled,
            "pre_slope": pre_slope,
            "pre_intercept": pre_intercept,
            "post_slope": post_slope,
            "post_intercept": post_intercept,
            "baseline_start": baseline_start,
            "baseline_end": baseline_end,
            "baseline_pre_source": pre_source,
            "baseline_post_source": post_source,
            "equivalent_value_change": equivalent_value_change,
            "equivalent_value_change_unit": source.data_unit,
            "equivalent_force_change_n": equivalent_force_change,
            "equivalent_mass_change_kg": equivalent_mass_change,
            "equivalent_mass_change_usage": "manual_reference_only",
            "regions": regions.to_dict() if regions is not None else None,
        }
        context.report_progress(1.0, "Baseline compensation complete")
        return ProcessingResult(
            dataset=result_dataset,
            output_channel_ids=("baseline_model", "thrust_corrected", "thrust_processed"),
            metadata=metadata,
            diagnostics=diagnostics,
        )
