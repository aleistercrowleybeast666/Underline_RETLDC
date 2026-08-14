from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from underline_retldc.core.dataset import Dataset
from underline_retldc.core.measurement_export import (
    Measurement_ChannelsSelect,
)
from underline_retldc.plugin_api.common import (
    AnalysisResult,
    Diagnostic,
    ExportResult,
    PluginDescriptor,
    PluginType,
    TaskContext,
)
from underline_retldc.plugin_api.exporter import EXPORTER_UI_SCHEMA_KEY, ExporterPlugin
from underline_retldc.plugins.measurement_export import (
    MeasurementCsv_Write,
    MeasurementWriteResult,
)


class ChamberPressureCsvExporter(ExporterPlugin):
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="builtin.exporter.chamber_pressure_csv",
            plugin_type=PluginType.EXPORTER,
            version="1.0.0",
            api_version="1",
            name="Chamber Pressure CSV Exporter",
            description="Exports chamber-pressure Channels selected by Quantity and Role",
            translation_key="exporter.chamber_pressure_csv.name",
        )

    def config_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"delimiter": {"type": "string", "default": ","}},
            EXPORTER_UI_SCHEMA_KEY: {
                "filename": "chamber_pressure_data.csv",
                "translation_key": "export.chamber_pressure_csv",
                "required_analysis_ids": [],
                "required_capability_ids": ["chamber_pressure_ready"],
                "group_id": "chamber_pressure",
                "group_order": 20,
                "format_order": 10,
                "locale_qualified": True,
            },
        }

    def validate(
        self,
        dataset: Dataset,
        analysis: AnalysisResult | None,
        config: Mapping[str, Any],
    ) -> list[Diagnostic]:
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
        channels = Measurement_ChannelsSelect(
            dataset,
            dimension="pressure",
            semantic_roles=("chamber_pressure",),
        )
        result = MeasurementCsv_Write(
            destination,
            dataset,
            channels,
            output_locale=str(config.get("output_locale", "en_US")),
            delimiter=str(config.get("delimiter", ",")),
        )
        if result is MeasurementWriteResult.SKIPPED_NO_CHANNEL:
            Path(destination).unlink(missing_ok=True)
        context.report_progress(1.0, "Chamber-pressure CSV export complete")
        return ExportResult(
            destination=Path(destination),
            metadata={
                "write_result": result.value,
                "channel_ids": [channel.id for channel in channels],
            },
        )
