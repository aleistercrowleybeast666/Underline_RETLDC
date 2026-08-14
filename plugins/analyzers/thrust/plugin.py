from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np

from underline_retldc.core.dataset import Dataset
from underline_retldc.core.diagnostics import Diagnostic, DiagnosticSeverity
from underline_retldc.core.units import (
    G0_STANDARD_M_S2,
    Quantity_Dimension,
    Unit_ConvertValues,
    Unit_IsPhysicalForQuantity,
)
from underline_retldc.plugin_api.analyzer import AnalyzerPlugin
from underline_retldc.plugin_api.common import (
    AnalysisResult,
    PluginDescriptor,
    PluginType,
    TaskContext,
)


class ThrustAnalyzer(AnalyzerPlugin):
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="builtin.analyzer.thrust",
            plugin_type=PluginType.ANALYZER,
            version="1.0.0",
            api_version="1",
            name="Thrust Analyzer",
            description="Thrust performance metrics using actual timestamps",
            translation_key="analyzer.thrust.name",
        )

    def config_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["channel_id", "ignition", "burnout"],
            "properties": {
                "channel_id": {"type": "string", "default": "thrust_processed"},
                "ignition": {"type": "number"},
                "burnout": {"type": "number"},
                "propellant_mass_kg": {"type": ["number", "null"]},
            },
        }

    def analyze(
        self, dataset: Dataset, config: Mapping[str, Any], context: TaskContext
    ) -> AnalysisResult:
        channel_id = str(config.get("channel_id", "thrust_processed"))
        channel = dataset.channel(channel_id)
        ignition = float(config["ignition"])
        burnout = float(config["burnout"])
        if not math.isfinite(ignition) or not math.isfinite(burnout) or ignition >= burnout:
            raise ValueError("Analyzer requires finite ignition < burnout")
        project_time = dataset.project_time
        mask = (project_time >= ignition) & (project_time <= burnout)
        time = project_time[mask]
        force = channel.values[mask]
        finite = np.isfinite(time) & np.isfinite(force)
        time = time[finite]
        force = force[finite]
        if len(time) < 2:
            raise ValueError("Burn region must contain at least two finite samples")
        if np.any(np.diff(time) <= 0):
            raise ValueError("Timestamps must be strictly increasing inside the burn region")
        context.raise_if_cancelled()

        duration = burnout - ignition
        relative_integral = float(np.trapezoid(force, time))
        peak_index = int(np.argmax(force))
        peak_value = float(force[peak_index])
        average_value = relative_integral / duration
        time_to_peak = float(time[peak_index] - ignition)
        propellant_mass = config.get("propellant_mass_kg")
        specific_impulse: float | None = None
        diagnostics: list[Diagnostic] = []
        physical_force = (
            Quantity_Dimension(channel.quantity) == "force"
            and Unit_IsPhysicalForQuantity(channel.quantity, channel.data_unit)
        )
        peak_thrust: float | None = None
        average_thrust: float | None = None
        total_impulse: float | None = None
        if physical_force:
            force_newtons = Unit_ConvertValues(force, channel.data_unit, "N")
            total_impulse = float(np.trapezoid(force_newtons, time))
            peak_thrust = float(force_newtons[peak_index])
            average_thrust = total_impulse / duration
        else:
            diagnostics.append(
                Diagnostic(
                    DiagnosticSeverity.ERROR,
                    "analysis.force_unit_not_physical",
                    "Physical thrust, total impulse, and specific impulse are unavailable "
                    f"because {channel.data_unit!r} is not a physical force unit",
                    plugin_id=self.descriptor.plugin_id,
                    details={
                        "channel_id": channel_id,
                        "quantity": channel.quantity,
                        "data_unit": channel.data_unit,
                    },
                )
            )
        if propellant_mass not in (None, "") and total_impulse is not None:
            propellant_mass_value = float(propellant_mass)
            if propellant_mass_value <= 0 or not math.isfinite(propellant_mass_value):
                diagnostics.append(
                    Diagnostic(
                        DiagnosticSeverity.WARNING,
                        "analysis.invalid_propellant_mass",
                        "Specific impulse is unavailable because propellant mass is not positive",
                        plugin_id=self.descriptor.plugin_id,
                    )
                )
            else:
                specific_impulse = total_impulse / (
                    propellant_mass_value * G0_STANDARD_M_S2
                )

        metrics: dict[str, float | None] = {
            "peak_thrust_n": peak_thrust,
            "average_thrust_n": average_thrust,
            "burn_duration_s": duration,
            "total_impulse_ns": total_impulse,
            "specific_impulse_s": specific_impulse,
            "time_to_peak_s": time_to_peak,
            "peak_value": peak_value,
            "average_value": average_value,
            "relative_integral": relative_integral,
        }
        if config.get("equivalent_mass_change_kg") is not None:
            metrics["equivalent_mass_change_kg"] = float(config["equivalent_mass_change_kg"])
        context.report_progress(1.0, "Thrust analysis complete")
        return AnalysisResult(
            metrics=metrics,
            diagnostics=diagnostics,
            metadata={
                "channel_id": channel_id,
                "ignition": ignition,
                "burnout": burnout,
                "integration": "trapezoidal_actual_timestamps",
                "g0_m_s2": G0_STANDARD_M_S2,
                "input_quantity": channel.quantity,
                "input_data_unit": channel.data_unit,
                "physical_force_available": physical_force,
                "relative_metric_unit": channel.data_unit,
            },
        )
