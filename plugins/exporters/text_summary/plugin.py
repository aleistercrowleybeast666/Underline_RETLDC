from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from underline_retldc.app.version import FULL_NAME, __version__
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


class AnalysisTextExporter(ExporterPlugin):
    METRIC_ORDER = (
        "peak_thrust_n",
        "average_thrust_n",
        "burn_duration_s",
        "total_impulse_ns",
        "specific_impulse_s",
        "time_to_peak_s",
        "equivalent_mass_change_kg",
    )
    METRIC_LABELS = {
        "en_US": {
            "peak_thrust_n": "Peak Thrust [N]",
            "average_thrust_n": "Average Thrust [N]",
            "burn_duration_s": "Test Duration [s]",
            "total_impulse_ns": "Total Impulse [N s]",
            "specific_impulse_s": "Specific Impulse [s]",
            "time_to_peak_s": "Time to Peak [s]",
            "equivalent_mass_change_kg": (
                "Equivalent Mass Change (Manual Reference Only) [kg]"
            ),
        },
        "zh_CN": {
            "peak_thrust_n": "峰值推力 [N]",
            "average_thrust_n": "平均推力 [N]",
            "burn_duration_s": "试车时长 [s]",
            "total_impulse_ns": "总冲 [N s]",
            "specific_impulse_s": "比冲 [s]",
            "time_to_peak_s": "到达峰值时间 [s]",
            "equivalent_mass_change_kg": "等效质量变化（仅供人工参考）[kg]",
        },
    }
    LABELS = {
        "en_US": {
            "title": "Analysis Summary",
            "schema": "Schema",
            "software_version": "Software Version",
            "export_time": "Export Time",
            "project_name": "Project Name",
            "source_file": "Source File",
            "source_hash": "Source SHA-256",
            "final_channel": "Final Channel",
            "provenance": "Provenance",
            "parser": "Parser",
            "parser_version": "Parser Version",
            "parser_parameters": "Parser Parameters",
            "calibration": "Calibration",
            "calibration_version": "Calibration Version",
            "calibration_parameters": "Calibration Parameters",
            "processor": "Processor",
            "processor_version": "Processor Version",
            "compensation": "Motor Weight-Change Compensation Enabled",
            "sign": "Sign",
            "analyzer": "Analyzer",
            "analyzer_version": "Analyzer Version",
            "motor_metadata": "Motor Metadata",
            "propellant_mass": "Propellant Mass [kg]",
            "total_motor_mass": "Total Motor Mass [kg]",
            "all_fields": "All Fields",
            "test_interval": "Test Interval",
            "start": "Test Start [s]",
            "end": "Test End [s]",
            "duration": "Test Duration [s]",
            "time_origin": "Exported Time Origin [s]",
            "interpolation": "Boundary Interpolation",
            "metrics": "Metrics",
            "diagnostics": "Diagnostics",
            "final_curve": "Final Test Curve",
            "time_column": "Time(s)",
            "thrust_column": "Thrust({unit})",
            "unavailable": "N/A",
            "true": "True",
            "false": "False",
            "ignition": "ignition",
            "burnout": "burnout",
        },
        "zh_CN": {
            "title": "火箭发动机试车数据分析摘要",
            "schema": "数据格式",
            "software_version": "软件版本",
            "export_time": "导出时间",
            "project_name": "项目名称",
            "source_file": "源文件",
            "source_hash": "源文件 SHA-256",
            "final_channel": "最终推力通道",
            "provenance": "计算溯源",
            "parser": "解析器",
            "parser_version": "解析器版本",
            "parser_parameters": "解析器参数",
            "calibration": "校准模型",
            "calibration_version": "校准模型版本",
            "calibration_parameters": "校准参数",
            "processor": "处理器",
            "processor_version": "处理器版本",
            "compensation": "发动机自重变化补偿已启用",
            "sign": "推力极性",
            "analyzer": "分析器",
            "analyzer_version": "分析器版本",
            "motor_metadata": "发动机信息",
            "propellant_mass": "推进剂质量 [kg]",
            "total_motor_mass": "发动机总质量 [kg]",
            "all_fields": "全部字段",
            "test_interval": "试车区间",
            "start": "试车开始 [s]",
            "end": "试车结束 [s]",
            "duration": "试车时长 [s]",
            "time_origin": "导出时间原点 [s]",
            "interpolation": "边界插值",
            "metrics": "分析指标",
            "diagnostics": "诊断信息",
            "final_curve": "最终试车推力曲线",
            "time_column": "时间(s)",
            "thrust_column": "推力({unit})",
            "unavailable": "不适用（N/A）",
            "true": "是",
            "false": "否",
            "ignition": "试车开始",
            "burnout": "试车结束",
        },
    }

    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="builtin.exporter.analysis_txt",
            plugin_type=PluginType.EXPORTER,
            version="1.0.0",
            api_version="1",
            name="Analysis Text Summary Exporter",
            description="Exports a UTF-8 analysis summary and final burn table",
            translation_key="exporter.analysis_txt.name",
        )

    def config_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "default": "thrust_processed"},
                "ignition": {"type": "number"},
                "burnout": {"type": "number"},
            },
            EXPORTER_UI_SCHEMA_KEY: {
                "filename": "analysis_summary.txt",
                "translation_key": "export.analysis_txt",
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
        diagnostics: list[Diagnostic] = []
        if analysis is None:
            diagnostics.append(
                Diagnostic(
                    DiagnosticSeverity.ERROR,
                    "export.txt.no_analysis",
                    "Analysis text export requires an analysis result",
                    plugin_id=self.descriptor.plugin_id,
                )
            )
            return diagnostics
        try:
            ExportCurve_Extract(dataset, analysis, config)
        except (KeyError, ValueError) as exc:
            diagnostics.append(
                Diagnostic(
                    DiagnosticSeverity.ERROR,
                    "export.txt.invalid_curve",
                    str(exc),
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
        assert analysis is not None
        curve = ExportCurve_Extract(dataset, analysis, config)
        output_locale = str(config.get("output_locale", "en_US"))
        if output_locale not in self.LABELS:
            raise ValueError("TXT output_locale must be 'zh_CN' or 'en_US'")
        labels = self.LABELS[output_locale]
        metric_labels = self.METRIC_LABELS[output_locale]
        provenance = config.get("provenance", {})
        motor_metadata = config.get("motor_metadata", {})
        if not isinstance(provenance, Mapping):
            provenance = {}
        if not isinstance(motor_metadata, Mapping):
            motor_metadata = {}

        def field(value: Any) -> str:
            if value in (None, ""):
                return labels["unavailable"]
            if isinstance(value, bool):
                return labels["true"] if value else labels["false"]
            if isinstance(value, float):
                return f"{value:.12g}"
            return str(value)

        def plugin_value(kind: str, key: str) -> Any:
            plugin = provenance.get(kind)
            return plugin.get(key) if isinstance(plugin, Mapping) else None

        processor_config = plugin_value("processor", "config")
        if not isinstance(processor_config, Mapping):
            processor_config = {}
        lines = [
            f"{FULL_NAME}",
            labels["title"],
            f"{labels['schema']}: underline-retldc-analysis-text/1",
            f"{labels['software_version']}: {__version__}",
            f"{labels['export_time']}: "
            f"{datetime.now().astimezone().isoformat(timespec='seconds')}",
            f"{labels['project_name']}: {field(config.get('project_name'))}",
            f"{labels['source_file']}: {field(dataset.metadata.get('source_path'))}",
            f"{labels['source_hash']}: {field(config.get('source_hash'))}",
            f"{labels['final_channel']}: {curve.source_channel_id}",
            "",
            f"[{labels['provenance']}]",
            f"{labels['parser']}: {field(plugin_value('parser', 'id'))}",
            f"{labels['parser_version']}: {field(plugin_value('parser', 'version'))}",
            f"{labels['parser_parameters']}: "
            + json.dumps(
                plugin_value("parser", "config") or {},
                ensure_ascii=False,
                sort_keys=True,
            ),
            f"{labels['calibration']}: {field(plugin_value('calibration', 'id'))}",
            f"{labels['calibration_version']}: "
            f"{field(plugin_value('calibration', 'version'))}",
            f"{labels['calibration_parameters']}: "
            + json.dumps(
                plugin_value("calibration", "config") or {},
                ensure_ascii=False,
                sort_keys=True,
            ),
            f"{labels['processor']}: {field(plugin_value('processor', 'id'))}",
            f"{labels['processor_version']}: "
            f"{field(plugin_value('processor', 'version'))}",
            f"{labels['compensation']}: {field(processor_config.get('enabled'))}",
            f"{labels['sign']}: {field(processor_config.get('sign'))}",
            f"{labels['analyzer']}: {field(plugin_value('analyzer', 'id'))}",
            f"{labels['analyzer_version']}: "
            f"{field(plugin_value('analyzer', 'version'))}",
            "",
            f"[{labels['motor_metadata']}]",
            f"{labels['propellant_mass']}: "
            f"{field(motor_metadata.get('propellant_mass_kg'))}",
            f"{labels['total_motor_mass']}: "
            f"{field(motor_metadata.get('total_motor_mass_kg'))}",
            f"{labels['all_fields']}: "
            + json.dumps(motor_metadata, ensure_ascii=False, sort_keys=True),
            "",
            f"[{labels['test_interval']}]",
            f"{labels['start']}: {curve.ignition:.12g}",
            f"{labels['end']}: {curve.burnout:.12g}",
            f"{labels['duration']}: {curve.burnout - curve.ignition:.12g}",
            f"{labels['time_origin']}: 0",
            f"{labels['interpolation']}: "
            + (
                ", ".join(labels[item] for item in curve.interpolated_boundaries)
                if curve.interpolated_boundaries
                else labels["unavailable"]
            ),
            "",
            f"[{labels['metrics']}]",
        ]
        for metric_name in self.METRIC_ORDER:
            value = analysis.metrics.get(metric_name)
            lines.append(
                f"{metric_labels[metric_name]}: "
                f"{labels['unavailable'] if value is None else f'{float(value):.12g}'}"
            )
        lines.extend(("", f"[{labels['diagnostics']}]"))
        combined_diagnostics = (*dataset.diagnostics, *analysis.diagnostics)
        if combined_diagnostics:
            lines.extend(
                f"{item.severity.value}\t{item.code}\t{item.message}"
                for item in combined_diagnostics
            )
        else:
            lines.append(labels["unavailable"])
        lines.extend(
            (
                "",
                f"[{labels['final_curve']}]",
                f"{labels['time_column']}\t"
                f"{labels['thrust_column'].format(unit=curve.unit)}",
            )
        )
        sample_count = len(curve.time)
        for index, (timestamp, thrust) in enumerate(
            zip(curve.time, curve.thrust, strict=True)
        ):
            if index % 4096 == 0:
                context.raise_if_cancelled()
                context.report_progress(index / sample_count, "Exporting analysis text")
            lines.append(f"{timestamp:.12g}\t{thrust:.12g}")
        lines.append("")

        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        try:
            temporary.write_text("\n".join(lines), encoding="utf-8")
            os.replace(temporary, destination)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        context.report_progress(1.0, "Analysis text exported")
        return ExportResult(
            destination=destination,
            diagnostics=diagnostics,
            metadata={
                "schema": "underline-retldc-analysis-text/1",
                "source_channel_id": curve.source_channel_id,
                "sample_count": sample_count,
                "time_start": float(curve.time[0]),
                "time_end": float(curve.time[-1]),
                "interpolated_boundaries": list(curve.interpolated_boundaries),
                "output_locale": output_locale,
            },
        )
