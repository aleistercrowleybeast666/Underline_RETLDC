from __future__ import annotations

import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from underline_retldc.core.dataset import Dataset
from underline_retldc.core.diagnostics import Diagnostic, DiagnosticSeverity
from underline_retldc.plugin_api.common import (
    AnalysisResult,
    ExportResult,
    PluginDescriptor,
    PluginType,
    TaskContext,
)
from underline_retldc.plugin_api.export_curve import ExportCurve_Extract
from underline_retldc.plugin_api.exporter import EXPORTER_UI_SCHEMA_KEY, ExporterPlugin


class OpenRocketEngExporter(ExporterPlugin):
    REQUIRED_FIELDS = (
        "motor_designation",
        "diameter_mm",
        "length_mm",
        "delay_s",
        "propellant_mass_kg",
        "total_motor_mass_kg",
        "manufacturer",
    )

    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="builtin.exporter.openrocket_eng",
            plugin_type=PluginType.EXPORTER,
            version="1.0.0",
            api_version="1",
            name="OpenRocket ENG Exporter",
            description="Exports the confirmed processed thrust curve as a RASP ENG file",
            translation_key="exporter.openrocket_eng.name",
        )

    def config_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": [*self.REQUIRED_FIELDS, "ignition", "burnout", "curve_confirmed"],
            "properties": {
                "channel_id": {"type": "string", "default": "thrust_processed"},
                "curve_confirmed": {"type": "boolean", "default": False},
                "motor_designation": {"type": "string"},
                "diameter_mm": {"type": "number"},
                "length_mm": {"type": "number"},
                "delay_s": {"type": "number"},
                "propellant_mass_kg": {"type": "number"},
                "total_motor_mass_kg": {"type": "number"},
                "manufacturer": {"type": "string"},
                "ignition": {"type": "number"},
                "burnout": {"type": "number"},
            },
            EXPORTER_UI_SCHEMA_KEY: {
                "filename": "motor.eng",
                "translation_key": "export.eng",
                "required_analysis_ids": ["builtin.analyzer.thrust"],
                "locale_qualified": False,
                "requires_motor_metadata": True,
            },
        }

    def validate(
        self,
        dataset: Dataset,
        analysis: AnalysisResult | None,
        config: Mapping[str, Any],
    ) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        missing = [field for field in self.REQUIRED_FIELDS if config.get(field) in (None, "")]
        if missing:
            diagnostics.append(
                Diagnostic(
                    DiagnosticSeverity.ERROR,
                    "export.eng.missing_metadata",
                    f"Missing OpenRocket metadata: {', '.join(missing)}",
                    plugin_id=self.descriptor.plugin_id,
                )
            )
        channel_id = str(config.get("channel_id", "thrust_processed"))
        if channel_id not in dataset.channels:
            diagnostics.append(
                Diagnostic(
                    DiagnosticSeverity.ERROR,
                    "export.eng.missing_channel",
                    f"Dataset does not contain final channel {channel_id!r}",
                    plugin_id=self.descriptor.plugin_id,
                )
            )
        if not bool(config.get("curve_confirmed", False)):
            diagnostics.append(
                Diagnostic(
                    DiagnosticSeverity.ERROR,
                    "export.eng.unconfirmed_curve",
                    "Confirm the final processed thrust curve before ENG export",
                    plugin_id=self.descriptor.plugin_id,
                )
            )
        for field in (
            "diameter_mm",
            "length_mm",
            "propellant_mass_kg",
            "total_motor_mass_kg",
        ):
            if config.get(field) not in (None, ""):
                try:
                    if float(config[field]) <= 0 or not math.isfinite(float(config[field])):
                        raise ValueError
                except (TypeError, ValueError):
                    diagnostics.append(
                        Diagnostic(
                            DiagnosticSeverity.ERROR,
                            "export.eng.invalid_metadata",
                            f"OpenRocket field {field} must be a positive finite number",
                            plugin_id=self.descriptor.plugin_id,
                        )
                    )
        return diagnostics

    def export(
        self,
        destination: Path,
        dataset: Dataset,
        analysis: AnalysisResult | None,
        config: Mapping[str, Any],
        context: TaskContext,
    ) -> ExportResult:
        diagnostics = self.validate(dataset, analysis, config)
        errors = [item for item in diagnostics if item.severity is DiagnosticSeverity.ERROR]
        if errors:
            raise ValueError(errors[0].message)
        curve = ExportCurve_Extract(dataset, analysis, config)
        ignition = curve.ignition
        time = np.array(curve.time, copy=True)
        force = np.array(curve.thrust, copy=True)
        if np.any(force < 0):
            diagnostics.append(
                Diagnostic(
                    DiagnosticSeverity.WARNING,
                    "export.eng.negative_clipped",
                    "Negative final thrust samples were clipped to zero for ENG compatibility",
                    plugin_id=self.descriptor.plugin_id,
                )
            )
        force = np.maximum(force, 0.0)
        force[0] = 0.0
        if force[-1] != 0.0:
            median_dt = float(np.median(np.diff(time)))
            time = np.r_[time, time[-1] + max(median_dt, 1e-6)]
            force = np.r_[force, 0.0]

        header = (
            f"{config['motor_designation']} {float(config['diameter_mm']):g} "
            f"{float(config['length_mm']):g} {float(config['delay_s']):g} "
            f"{float(config['propellant_mass_kg']):g} "
            f"{float(config['total_motor_mass_kg']):g} {config['manufacturer']}"
        )
        lines = ["; Generated by Underline RETLDC", header]
        for index, (timestamp, thrust) in enumerate(zip(time, force, strict=True)):
            if index % 4096 == 0:
                context.raise_if_cancelled()
                context.report_progress(index / len(time), "Exporting OpenRocket ENG")
            lines.append(f"{timestamp:.7g} {thrust:.7g}")
        lines.append("")

        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        try:
            temporary.write_text("\n".join(lines), encoding="ascii", errors="strict")
            os.replace(temporary, destination)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        context.report_progress(1.0, "OpenRocket ENG exported")
        return ExportResult(
            destination=destination,
            diagnostics=diagnostics,
            metadata={
                "curve_points": len(time),
                "ignition_shift_s": ignition,
                "source_channel_id": curve.source_channel_id,
                "interpolated_boundaries": list(curve.interpolated_boundaries),
            },
        )
