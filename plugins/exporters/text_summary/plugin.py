from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from underline_retldc.app.version import FULL_NAME, __version__
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.diagnostics import Diagnostic, DiagnosticSeverity
from underline_retldc.core.measurement_export import Measurement_ChannelsSelect
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
        "peak_value",
        "average_value",
        "relative_integral",
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
            "peak_value": "Peak (Current Data Unit)",
            "average_value": "Average (Current Data Unit)",
            "relative_integral": "Relative Integral (Current Data Unit s)",
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
            "peak_value": "峰值（当前数据单位）",
            "average_value": "平均值（当前数据单位）",
            "relative_integral": "相对积分（当前数据单位 s）",
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
            "thrust_polarity": "Thrust Polarity",
            "polarity_positive": "Positive (+1)",
            "polarity_reversed": "Reversed (-1)",
            "thrust_correction": "Thrust Correction",
            "correction_none": "None",
            "correction_motor_weight": "Motor Weight-Change Compensation",
            "pre_baseline": "PRE Baseline",
            "pre_baseline_source": "PRE Baseline Source",
            "post_baseline": "POST Baseline",
            "post_baseline_source": "POST Baseline Source",
            "processing_metadata": "Processing Metadata",
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
            "pressure_metrics": "Chamber Pressure Metrics",
            "pressure_channel": "Chamber Pressure Channel",
            "pressure_start": "Chamber Pressure at Test Start",
            "pressure_peak_active": "Peak Chamber Pressure",
            "pressure_mean_active": "Mean Active Chamber Pressure",
            "temperature_metrics": "Temperature Metrics",
            "temperature_channel": "Temperature Channel",
            "temperature_start": "Temperature at Test Start",
            "temperature_active_max": "Active Max",
            "temperature_full_max": "Full Record Max",
            "temperature_max_time": "Time of Max",
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
            "thrust_polarity": "推力极性",
            "polarity_positive": "正向 (+1)",
            "polarity_reversed": "反向 (-1)",
            "thrust_correction": "推力修正",
            "correction_none": "不启用",
            "correction_motor_weight": "发动机自重变化补偿",
            "pre_baseline": "PRE 基线",
            "pre_baseline_source": "PRE 基线来源",
            "post_baseline": "POST 基线",
            "post_baseline_source": "POST 基线来源",
            "processing_metadata": "处理元数据",
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
            "pressure_metrics": "燃烧室压力指标",
            "pressure_channel": "燃烧室压力通道",
            "pressure_start": "试车开始时燃烧室压力",
            "pressure_peak_active": "燃烧室压力峰值",
            "pressure_mean_active": "试车区间平均燃烧室压力",
            "temperature_metrics": "温度指标",
            "temperature_channel": "温度通道",
            "temperature_start": "试车开始时温度",
            "temperature_active_max": "试车区间最大值",
            "temperature_full_max": "全记录最大值",
            "temperature_max_time": "最大值时刻",
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
                "required_analysis_ids": [],
                "required_capability_ids": ["project_summary_ready"],
                "group_id": "overall",
                "group_order": 0,
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
        processing_metadata = config.get("processing_metadata", {})
        if not isinstance(provenance, Mapping):
            provenance = {}
        if not isinstance(motor_metadata, Mapping):
            motor_metadata = {}
        if not isinstance(processing_metadata, Mapping):
            processing_metadata = {}

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

        thrust_polarity = int(config.get("thrust_polarity", 1))
        if thrust_polarity not in {-1, 1}:
            raise ValueError("TXT thrust_polarity must be +1 or -1")
        polarity_text = labels[
            "polarity_positive" if thrust_polarity == 1 else "polarity_reversed"
        ]
        processor_id = plugin_value("processor", "id")
        if processor_id in (None, ""):
            correction_text = labels["correction_none"]
        elif processor_id == "builtin.processor.vertical_linear_baseline":
            correction_text = labels["correction_motor_weight"]
        else:
            correction_text = str(processor_id)
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
            f"{labels['thrust_polarity']}: {polarity_text}",
            f"{labels['thrust_correction']}: {correction_text}",
            f"{labels['pre_baseline']}: "
            f"{field(processing_metadata.get('baseline_start'))}",
            f"{labels['pre_baseline_source']}: "
            f"{field(processing_metadata.get('baseline_pre_source'))}",
            f"{labels['post_baseline']}: "
            f"{field(processing_metadata.get('baseline_end'))}",
            f"{labels['post_baseline_source']}: "
            f"{field(processing_metadata.get('baseline_post_source'))}",
            f"{labels['processing_metadata']}: "
            + json.dumps(
                processing_metadata, ensure_ascii=False, sort_keys=True
            ),
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
        project_time = dataset.project_time
        active_mask = (
            np.isfinite(project_time)
            & (project_time >= curve.ignition)
            & (project_time <= curve.burnout)
        )

        def start_value(channel: Any) -> float | None:
            finite = np.isfinite(project_time) & np.isfinite(channel.values)
            if not np.any(finite):
                return None
            return float(
                np.interp(
                    curve.ignition,
                    project_time[finite],
                    channel.values[finite],
                )
            )

        pressure_channels = Measurement_ChannelsSelect(
            dataset,
            dimension="pressure",
            semantic_roles=("chamber_pressure",),
        )
        if pressure_channels:
            lines.extend(("", f"[{labels['pressure_metrics']}]") )
            for channel in pressure_channels:
                selected = channel.values[active_mask & np.isfinite(channel.values)]
                lines.append(f"{labels['pressure_channel']}: {channel.name}")
                lines.append(
                    f"{labels['pressure_start']} [{channel.data_unit}]: "
                    f"{field(start_value(channel))}"
                )
                lines.append(
                    f"{labels['pressure_peak_active']} [{channel.data_unit}]: "
                    f"{field(float(np.max(selected)) if selected.size else None)}"
                )
                lines.append(
                    f"{labels['pressure_mean_active']} [{channel.data_unit}]: "
                    f"{field(float(np.mean(selected)) if selected.size else None)}"
                )

        temperature_channels = Measurement_ChannelsSelect(
            dataset,
            dimension="temperature",
        )
        if temperature_channels:
            lines.extend(("", f"[{labels['temperature_metrics']}]") )
            for channel in temperature_channels:
                active_values = channel.values[
                    active_mask & np.isfinite(channel.values)
                ]
                finite = np.isfinite(project_time) & np.isfinite(channel.values)
                finite_indices = np.flatnonzero(finite)
                maximum_index = (
                    int(finite_indices[np.argmax(channel.values[finite])])
                    if finite_indices.size
                    else None
                )
                lines.append(f"{labels['temperature_channel']}: {channel.name}")
                lines.append(
                    f"{labels['temperature_start']} [{channel.data_unit}]: "
                    f"{field(start_value(channel))}"
                )
                lines.append(
                    f"{labels['temperature_active_max']} [{channel.data_unit}]: "
                    f"{field(float(np.max(active_values)) if active_values.size else None)}"
                )
                lines.append(
                    f"{labels['temperature_full_max']} [{channel.data_unit}]: "
                    f"{field(channel.values[maximum_index] if maximum_index is not None else None)}"
                )
                lines.append(
                    f"{labels['temperature_max_time']} [s]: "
                    f"{field(project_time[maximum_index] if maximum_index is not None else None)}"
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
