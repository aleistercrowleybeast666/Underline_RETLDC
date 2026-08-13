from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np

from underline_retldc.core.dataset import Dataset
from underline_retldc.core.diagnostics import Diagnostic, DiagnosticSeverity
from underline_retldc.core.units import G0_STANDARD_M_S2
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
        mask = (dataset.time >= ignition) & (dataset.time <= burnout)
        time = dataset.time[mask]
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
        total_impulse = float(np.trapezoid(force, time))
        peak_index = int(np.argmax(force))
        peak = float(force[peak_index])
        average = total_impulse / duration
        time_to_peak = float(time[peak_index] - ignition)
        propellant_mass = config.get("propellant_mass_kg")
        specific_impulse: float | None = None
        diagnostics: list[Diagnostic] = []
        if propellant_mass not in (None, ""):
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
            "peak_thrust_n": peak,
            "average_thrust_n": average,
            "burn_duration_s": duration,
            "total_impulse_ns": total_impulse,
            "specific_impulse_s": specific_impulse,
            "time_to_peak_s": time_to_peak,
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
            },
        )
