from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from underline_retldc.app.version import __version__
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.diagnostics import Diagnostic, DiagnosticSeverity
from underline_retldc.core.units import Quantity_Dimension, Unit_ConvertValues
from underline_retldc.plugin_api.common import (
    AnalysisResult,
    ExportResult,
    PluginDescriptor,
    PluginType,
    TaskContext,
)
from underline_retldc.plugin_api.exporter import EXPORTER_UI_SCHEMA_KEY, ExporterPlugin

from .contract import (
    MAX_BYTES,
    MAX_SAMPLES,
    SCHEMA_ID,
    MotorPackage_Digest,
    MotorPackage_Load,
    MotorPackage_Validate,
    MotorPackageError,
)


def _diagnostic(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "severity": "warning", "message": message}


def _simulation_curve(
    time: np.ndarray, force: np.ndarray, duration: float, maximum_gap: float, diagnostics: list
) -> dict[str, Any] | None:
    if time[0] > 0 or time[-1] < duration:
        diagnostics.append(
            _diagnostic(
                "COVERAGE", "$.simulation_curve", "ACTIVE_TEST extends outside recorded coverage"
            )
        )
        return None
    indices = np.flatnonzero((time >= 0) & (time <= duration)).tolist()
    selected_t = time[indices].tolist()
    selected_f = force[indices].tolist()
    for boundary, front in ((0.0, True), (duration, False)):
        if boundary in selected_t:
            continue
        right = int(np.searchsorted(time, boundary))
        left = right - 1
        if not 0 < right < len(time) or time[right] - time[left] > maximum_gap:
            diagnostics.append(
                _diagnostic(
                    "BOUNDARY_GAP",
                    "$.simulation_curve",
                    "Boundary interpolation exceeds maximum_gap_s",
                )
            )
            return None
        value = float(
            force[left]
            + (force[right] - force[left]) * (boundary - time[left]) / (time[right] - time[left])
        )
        position = 0 if front else len(selected_t)
        selected_t.insert(position, boundary)
        selected_f.insert(position, value)
        indices.insert(position, -1)
    if any(
        b - a > maximum_gap * (1 + 1e-12)
        for a, b in zip(selected_t[:-1], selected_t[1:], strict=True)
    ):
        diagnostics.append(
            _diagnostic(
                "GAP", "$.simulation_curve", "ACTIVE_TEST contains gaps exceeding maximum_gap_s"
            )
        )
        return None
    return {
        "time_s": selected_t,
        "thrust_n": selected_f,
        "source_sample_indices": indices,
        "inserted_boundary_indices": [i for i, original in enumerate(indices) if original == -1],
        "interpolation": "piecewise_linear",
        "maximum_gap_s": maximum_gap,
    }


class TreeDiagramMotorExporter(ExporterPlugin):
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            "builtin.exporter.treediagram_motor",
            PluginType.EXPORTER,
            "1.0.0",
            "1",
            "TreeDiagram motor test package",
            "Lossless scientific thrust evidence and explicit simulation input",
            "exporter.treediagram_motor.name",
        )

    def config_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "maximum_gap_s": {"type": "number", "exclusiveMinimum": 0, "default": 0.1},
            },
            EXPORTER_UI_SCHEMA_KEY: {
                "filename": "motor.tdmotor.json",
                "translation_key": "export.treediagram_motor",
                "required_analysis_ids": [],
                "required_capability_ids": [
                    "thrust_ready",
                    "physical_force",
                    "segmentation_ready",
                    "source_identity_ready",
                ],
                "group_id": "thrust",
                "group_order": 10,
                "format_order": 40,
                "default_selected": True,
                "locale_qualified": False,
            },
        }

    def Package_Build(self, dataset: Dataset, config: Mapping[str, Any]) -> dict[str, Any]:
        channel = dataset.channel(str(config["channel_id"]))
        if Quantity_Dimension(channel.quantity) != "force":
            raise MotorPackageError("UNIT", "$.evidence_curve", "Primary input is not force")
        force = Unit_ConvertValues(channel.values, channel.data_unit, "N")
        for key in ("ignition", "burnout"):
            if isinstance(config[key], bool) or not isinstance(config[key], (int, float)):
                raise MotorPackageError("TIME", "$.time." + key, "Numeric boundary required")
        ignition, burnout = float(config["ignition"]), float(config["burnout"])
        time = np.asarray(dataset.project_time - ignition)
        if not 2 <= len(time) <= MAX_SAMPLES:
            raise MotorPackageError("LENGTH", "$.evidence_curve", "2..250000 samples required")
        if not np.all(np.isfinite(time)) or not np.all(np.isfinite(force)):
            raise MotorPackageError(
                "NUMBER", "$.evidence_curve", "Nonfinite samples are not removed"
            )
        if np.any(np.diff(time) <= 0):
            raise MotorPackageError(
                "CLOCK", "$.evidence_curve", "Duplicate or reversed times are not repaired"
            )
        maximum_gap = config.get("maximum_gap_s", 0.1)
        if (
            isinstance(maximum_gap, bool)
            or not isinstance(maximum_gap, (float, int))
            or not np.isfinite(maximum_gap)
            or maximum_gap <= 0
        ):
            raise MotorPackageError(
                "NUMBER", "$.simulation_curve.maximum_gap_s", "Positive finite gap required"
            )
        source = dict(config["source_reference"])
        if not source.get("sha256"):
            raise MotorPackageError(
                "SOURCE_HASH", "$.source.sha256", "Reimport source to establish input identity"
            )
        diagnostics = []
        diagnostic_counts: dict[str, int] = {}
        for diagnostic in dataset.diagnostics:
            diagnostic_counts[diagnostic.code] = diagnostic_counts.get(diagnostic.code, 0) + 1
        if diagnostic_counts or dataset.metadata.get("malformed_rows", 0):
            diagnostics.append(
                {
                    "code": "SOURCE_QUALITY",
                    "path": "$.source",
                    "severity": "info",
                    "message": json.dumps(
                        {
                            "retained_sample_count": dataset.sample_count,
                            "source_malformed_rows": dataset.metadata.get("malformed_rows"),
                            "diagnostic_counts": diagnostic_counts,
                        },
                        sort_keys=True,
                        ensure_ascii=False,
                        allow_nan=False,
                    ),
                }
            )
        if np.any(force < 0):
            diagnostics.append(
                _diagnostic(
                    "NEGATIVE_THRUST",
                    "$.evidence_curve.thrust_n",
                    "Negative evidence retained; propulsion needs an explicit policy",
                )
            )
        motor_metadata = config.get("motor_metadata", {})

        def physical(key: str, scale: float = 1.0) -> float | None:
            value = motor_metadata.get(key)
            if value is None:
                return None
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise MotorPackageError("NUMBER", "$.motor." + key, "Numeric value required")
            return float(value) * scale

        motor = {
            "name": motor_metadata.get("motor_designation") or None,
            "propellant_mass_kg": physical("propellant_mass_kg"),
            "total_mass_kg": physical("total_motor_mass_kg"),
            "diameter_m": physical("diameter_mm", 0.001),
            "length_m": physical("length_mm", 0.001),
        }
        if motor["propellant_mass_kg"] is None or motor["total_mass_kg"] is None:
            diagnostics.append(
                _diagnostic(
                    "MASS_UNKNOWN",
                    "$.motor",
                    "Complete the explicit mass model in TreeDiagram before 6DoF",
                )
            )
        provenance = config["provenance"]
        chain = []
        stages = ["parser", "calibration", "polarity", "processor", "analyzer"]
        channel_chain = config.get("channel_chain", [])
        by_role = {item["role"]: item["id"] for item in channel_chain}
        prior = source["file_name"]
        for stage in stages:
            record = provenance.get(stage)
            if stage == "polarity":
                record = {
                    "id": "core.thrust_polarity",
                    "version": "1",
                    "api_version": "1",
                    "config": {"polarity": config["thrust_polarity"]},
                }
            if stage == "processor" and record is None:
                record = {
                    "id": "core.passthrough",
                    "version": "1",
                    "api_version": "1",
                    "config": {},
                }
            if record is None:
                continue
            output = {
                "parser": source["channel_id"],
                "calibration": by_role.get("calibrated"),
                "polarity": by_role.get("oriented"),
                "processor": source["final_channel_id"],
                "analyzer": "analysis",
            }[stage] or source["final_channel_id"]
            chain.append(
                {
                    "stage": stage,
                    **record,
                    "input": prior,
                    "output": output,
                    "source_sha256": source["sha256"],
                }
            )
            prior = output
        simulation = _simulation_curve(
            time, force, burnout - ignition, float(maximum_gap), diagnostics
        )
        impulse = None
        if simulation is not None:
            impulse = float(np.trapezoid(simulation["thrust_n"], simulation["time_s"]))
        # No device certificate exists in the current runtime selection model. A unit,
        # Identity transform or user-entered gain never upgrades this to verified.
        selection = config.get("calibration_selection", {})
        notes = "Device calibration qualification is unknown. " + json.dumps(
            selection, ensure_ascii=False
        )
        calibration_origin = (
            (provenance.get("calibration") or {})
            .get("config", {})
            .get("calibration_provenance", {})
        )
        origin_document = calibration_origin.get("origin_document", {})
        qualification = origin_document.get("qualification", "unknown")
        if qualification not in {"unknown", "estimated", "documented"}:
            qualification = "unknown"
        if calibration_origin.get("parameters_modified", False):
            qualification = "unknown"
        if origin_document:
            notes += " Original calibration notes: " + str(origin_document.get("notes", ""))
        package = {
            "schema_id": SCHEMA_ID,
            "schema_version": 1,
            "producer": {
                "application": "Underline RETLDC",
                "application_version": __version__,
                "exporter_id": self.descriptor.plugin_id,
                "exporter_version": self.descriptor.version,
                "plugin_api_version": "1",
            },
            "project": {"name": config.get("project_name")},
            "motor": motor,
            "source": source,
            "processing_chain": chain,
            "calibration": {"status": qualification, "notes": notes},
            "time": {
                "local_to_project_offset_s": float(config["source_time_offset_s"]),
                "ignition_project_s": ignition,
                "active_test_project_s": [ignition, burnout],
                "export_time_reference": "ignition",
            },
            "evidence_curve": {"time_s": time.tolist(), "thrust_n": force.tolist()},
            "simulation_curve": simulation,
            "diagnostics": diagnostics,
            "metrics": {"total_impulse_ns": impulse},
        }
        package["content_sha256"] = MotorPackage_Digest(package)
        return MotorPackage_Validate(package)

    def validate(
        self, dataset: Dataset, analysis: AnalysisResult | None, config: Mapping[str, Any]
    ) -> list[Diagnostic]:
        try:
            self.Package_Build(dataset, config)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            return [
                Diagnostic(
                    DiagnosticSeverity.ERROR,
                    "export.motor.invalid",
                    str(exc),
                    plugin_id=self.descriptor.plugin_id,
                )
            ]
        return []

    def export(
        self,
        destination: Path,
        dataset: Dataset,
        analysis: AnalysisResult | None,
        config: Mapping[str, Any],
        context: TaskContext,
    ) -> ExportResult:
        context.raise_if_cancelled()
        package = self.Package_Build(dataset, config)
        encoded = (
            json.dumps(package, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
        ).encode("utf-8")
        if len(encoded) > MAX_BYTES:
            raise MotorPackageError("LIMIT", "$", "Export exceeds 32 MiB")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix=".tdmotor-", suffix=".tmp", dir=destination.parent
        )
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                for start in range(0, len(encoded), 65536):
                    context.raise_if_cancelled()
                    handle.write(encoded[start : start + 65536])
                    context.report_progress(start / len(encoded), "Writing motor test package")
                handle.flush()
                os.fsync(handle.fileno())
            MotorPackage_Load(temporary)
            context.raise_if_cancelled()
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        context.report_progress(1.0, "Motor test package exported")
        return ExportResult(
            destination,
            metadata={"content_sha256": package["content_sha256"], "schema_id": SCHEMA_ID},
        )
