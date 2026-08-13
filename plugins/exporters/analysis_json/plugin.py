from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

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


class AnalysisJsonExporter(ExporterPlugin):
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="builtin.exporter.analysis_json",
            plugin_type=PluginType.EXPORTER,
            version="1.0.0",
            api_version="1",
            name="Analysis JSON Exporter",
            description="Exports versioned analysis metrics and provenance",
            translation_key="exporter.analysis_json.name",
        )

    def config_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            EXPORTER_UI_SCHEMA_KEY: {
                "filename": "analysis_data.json",
                "translation_key": "export.analysis_json",
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
        if analysis is None:
            return [
                Diagnostic(
                    DiagnosticSeverity.ERROR,
                    "export.json.no_analysis",
                    "Analysis JSON export requires an analysis result",
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
        if diagnostics:
            raise ValueError(diagnostics[0].message)
        assert analysis is not None
        context.raise_if_cancelled()
        output_locale = str(config.get("output_locale", "en_US"))
        if output_locale not in {"zh_CN", "en_US"}:
            raise ValueError("Analysis JSON output_locale must be 'zh_CN' or 'en_US'")
        display = self._display_labels(output_locale)
        payload = {
            "schema": "underline-retldc-analysis/1",
            "output": {
                "locale": output_locale,
                "language": "简体中文" if output_locale == "zh_CN" else "English",
                **display,
            },
            "dataset": {
                "sample_count": dataset.sample_count,
                "time_unit": dataset.time_unit,
                "channels": {
                    channel_id: {
                        "quantity": channel.quantity,
                        "unit": channel.unit,
                        "role": channel.role,
                    }
                    for channel_id, channel in dataset.channels.items()
                },
                "metadata": dict(dataset.metadata),
            },
            "analysis": analysis.to_dict(),
        }
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            os.replace(temporary, destination)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        context.report_progress(1.0, "Analysis JSON exported")
        return ExportResult(
            destination=destination,
            metadata={"schema": payload["schema"], "output_locale": output_locale},
        )

    @staticmethod
    def _display_labels(output_locale: str) -> dict[str, Any]:
        if output_locale == "zh_CN":
            return {
                "title": "火箭发动机试车数据分析",
                "metric_labels": {
                    "peak_thrust_n": "峰值推力 [N]",
                    "average_thrust_n": "平均推力 [N]",
                    "burn_duration_s": "试车时长 [s]",
                    "total_impulse_ns": "总冲 [N·s]",
                    "specific_impulse_s": "比冲 [s]",
                    "time_to_peak_s": "到达峰值时间 [s]",
                    "equivalent_mass_change_kg": "等效质量变化（仅供人工参考）[kg]",
                },
            }
        return {
            "title": "Rocket Motor Test Analysis",
            "metric_labels": {
                "peak_thrust_n": "Peak thrust [N]",
                "average_thrust_n": "Average thrust [N]",
                "burn_duration_s": "Test duration [s]",
                "total_impulse_ns": "Total impulse [N·s]",
                "specific_impulse_s": "Specific impulse [s]",
                "time_to_peak_s": "Time to peak [s]",
                "equivalent_mass_change_kg": (
                    "Equivalent mass change (manual reference only) [kg]"
                ),
            },
        }
