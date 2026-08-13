from __future__ import annotations

import csv
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
from underline_retldc.plugin_api.exporter import EXPORTER_UI_SCHEMA_KEY, ExporterPlugin


class CsvExporter(ExporterPlugin):
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="builtin.exporter.csv",
            plugin_type=PluginType.EXPORTER,
            version="1.0.0",
            api_version="1",
            name="CSV Exporter",
            description="Exports timestamps and selected Dataset channels",
            translation_key="exporter.csv.name",
        )

    def config_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "channel_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["thrust_processed"],
                },
                "delimiter": {"type": "string", "default": ","},
                "burn_only": {"type": "boolean", "default": True},
                "shift_time": {"type": "boolean", "default": True},
            },
            EXPORTER_UI_SCHEMA_KEY: {
                "filename": "processed_thrust.csv",
                "translation_key": "export.csv",
                "required_analysis_ids": ["builtin.analyzer.thrust"],
                "locale_qualified": True,
            },
        }

    def validate(
        self,
        dataset: Dataset,
        analysis: AnalysisResult | None,
        config: Mapping[str, Any],
    ) -> list[Diagnostic]:
        channel_ids = list(config.get("channel_ids") or dataset.channels.keys())
        missing = [channel_id for channel_id in channel_ids if channel_id not in dataset.channels]
        if missing:
            return [
                Diagnostic(
                    DiagnosticSeverity.ERROR,
                    "export.csv.missing_channel",
                    f"Missing CSV channel(s): {', '.join(missing)}",
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
        diagnostics = self.validate(dataset, analysis, config)
        if any(item.severity is DiagnosticSeverity.ERROR for item in diagnostics):
            raise ValueError(diagnostics[0].message)
        channel_ids = list(config.get("channel_ids") or dataset.channels.keys())
        delimiter = str(config.get("delimiter", ","))
        output_locale = str(config.get("output_locale", "en_US"))
        if output_locale not in {"zh_CN", "en_US"}:
            raise ValueError("CSV output_locale must be 'zh_CN' or 'en_US'")
        if len(delimiter) != 1:
            raise ValueError("CSV delimiter must be one character")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, delimiter=delimiter)
                time_label = "时间" if output_locale == "zh_CN" else "Time"
                writer.writerow(
                    [f"{time_label} [{dataset.time_unit}]"]
                    + [
                        self._channel_label(
                            channel_id,
                            dataset.channels[channel_id].unit,
                            output_locale,
                        )
                        for channel_id in channel_ids
                    ]
                )
                indices = np.arange(dataset.sample_count)
                ignition = 0.0
                if bool(config.get("burn_only", False)):
                    try:
                        ignition = float(config["ignition"])
                        burnout = float(config["burnout"])
                    except (KeyError, TypeError, ValueError) as exc:
                        raise ValueError(
                            "Burn-only CSV export requires ignition and burnout"
                        ) from exc
                    indices = indices[
                        (dataset.time >= ignition) & (dataset.time <= burnout)
                    ]
                    if len(indices) < 2:
                        raise ValueError("Burn-only CSV export requires at least two samples")
                shift_time = bool(config.get("shift_time", False))
                sample_count = max(len(indices), 1)
                for progress_index, index in enumerate(indices):
                    if progress_index % 4096 == 0:
                        context.raise_if_cancelled()
                        context.report_progress(
                            progress_index / sample_count, "Exporting CSV"
                        )
                    writer.writerow(
                        [
                            f"{dataset.time[index] - (ignition if shift_time else 0.0):.12g}"
                        ]
                        + [
                            f"{dataset.channels[channel_id].values[index]:.12g}"
                            for channel_id in channel_ids
                        ]
                    )
            os.replace(temporary, destination)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        context.report_progress(1.0, "CSV exported")
        return ExportResult(
            destination=destination,
            diagnostics=diagnostics,
            metadata={
                "channel_ids": channel_ids,
                "sample_count": len(indices),
                "output_locale": output_locale,
            },
        )

    @staticmethod
    def _channel_label(channel_id: str, unit: str, output_locale: str) -> str:
        known_labels = {
            "en_US": {
                "thrust_processed": "Corrected Thrust",
                "thrust_corrected": "Corrected Thrust",
                "force_calibrated": "Uncorrected Force",
            },
            "zh_CN": {
                "thrust_processed": "已修正推力",
                "thrust_corrected": "已修正推力",
                "force_calibrated": "未修正力",
            },
        }
        label = known_labels[output_locale].get(channel_id, channel_id)
        return f"{label} [{unit}]"
