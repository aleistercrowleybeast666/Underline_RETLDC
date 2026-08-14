from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygonF

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


class ThrustCurvePngExporter(ExporterPlugin):
    LABELS = {
        "en_US": {
            "title": "Rocket Motor Thrust Curve",
            "time_axis": "Time from ignition [s]",
            "thrust_axis": "Thrust [{unit}]",
            "peak": "Peak thrust",
            "impulse": "Total impulse",
            "unavailable": "N/A",
            "font": "Arial",
        },
        "zh_CN": {
            "title": "发动机推力曲线",
            "time_axis": "点火后时间 [s]",
            "thrust_axis": "推力 [{unit}]",
            "peak": "峰值推力",
            "impulse": "总冲",
            "unavailable": "不可用",
            "font": "Microsoft YaHei",
        },
    }

    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="builtin.exporter.thrust_png",
            plugin_type=PluginType.EXPORTER,
            version="1.0.0",
            api_version="1",
            name="Thrust Curve PNG Exporter",
            description="Exports a report-ready final burn thrust curve",
            translation_key="exporter.thrust_png.name",
        )

    def config_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "default": "thrust_processed"},
                "ignition": {"type": "number"},
                "burnout": {"type": "number"},
                "title": {"type": "string"},
                "annotate_metrics": {"type": "boolean", "default": True},
            },
            EXPORTER_UI_SCHEMA_KEY: {
                "filename": "thrust_curve.png",
                "translation_key": "export.thrust_png",
                "required_analysis_ids": [],
                "required_capability_ids": ["thrust_ready"],
                "group_id": "thrust",
                "group_order": 10,
                "format_order": 20,
                "locale_qualified": True,
                "supports_metric_annotation": True,
            },
        }

    def validate(
        self,
        dataset: Dataset,
        analysis: AnalysisResult | None,
        config: Mapping[str, Any],
    ) -> list[Diagnostic]:
        try:
            ExportCurve_Extract(dataset, analysis, config)
        except (KeyError, ValueError) as exc:
            return [
                Diagnostic(
                    DiagnosticSeverity.ERROR,
                    "export.png.invalid_curve",
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
        diagnostics = self.validate(dataset, analysis, config)
        if diagnostics:
            raise ValueError(diagnostics[0].message)
        curve = ExportCurve_Extract(dataset, analysis, config)
        context.raise_if_cancelled()
        output_locale = str(config.get("output_locale", "en_US"))
        if output_locale not in self.LABELS:
            raise ValueError("PNG output_locale must be 'zh_CN' or 'en_US'")
        labels = self.LABELS[output_locale]
        font_name = labels["font"]

        width, height = 1600, 1000
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(QColor("#ffffff"))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        plot = QRectF(145.0, 115.0, 1375.0, 760.0)
        title = str(config.get("title") or "").strip() or labels["title"]
        painter.setPen(QColor("#172033"))
        painter.setFont(QFont(font_name, 24, QFont.Weight.Bold))
        painter.drawText(QRectF(0, 28, width, 50), Qt.AlignmentFlag.AlignCenter, title)

        x_min, x_max = 0.0, float(curve.time[-1])
        y_min = min(0.0, float(np.min(curve.thrust)))
        y_max = max(0.0, float(np.max(curve.thrust)))
        if x_max <= x_min:
            x_max = x_min + 1.0
        if y_max <= y_min:
            y_max = y_min + 1.0
        y_padding = 0.08 * (y_max - y_min)
        y_min -= y_padding
        y_max += y_padding

        painter.setFont(QFont(font_name, 12))
        for index in range(6):
            fraction = index / 5
            x = plot.left() + fraction * plot.width()
            y = plot.bottom() - fraction * plot.height()
            painter.setPen(QPen(QColor("#dfe5ee"), 1))
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(QColor("#344054"))
            painter.drawText(
                QRectF(x - 70, plot.bottom() + 10, 140, 30),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                f"{x_min + fraction * (x_max - x_min):.4g}",
            )
            painter.drawText(
                QRectF(20, y - 15, 110, 30),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{y_min + fraction * (y_max - y_min):.4g}",
            )
        painter.setPen(QPen(QColor("#172033"), 2))
        painter.drawRect(plot)

        points = QPolygonF(
            [
                QPointF(
                    plot.left() + (float(timestamp) - x_min) / (x_max - x_min) * plot.width(),
                    plot.bottom() - (float(thrust) - y_min) / (y_max - y_min) * plot.height(),
                )
                for timestamp, thrust in zip(curve.time, curve.thrust, strict=True)
            ]
        )
        painter.setPen(QPen(QColor("#2f6fed"), 3))
        painter.drawPolyline(points)

        painter.setPen(QColor("#172033"))
        painter.setFont(QFont(font_name, 14))
        painter.drawText(
            QRectF(plot.left(), 910, plot.width(), 35),
            Qt.AlignmentFlag.AlignCenter,
            labels["time_axis"],
        )
        painter.save()
        painter.translate(42, plot.center().y())
        painter.rotate(-90)
        painter.drawText(
            QRectF(-plot.height() / 2, -22, plot.height(), 35),
            Qt.AlignmentFlag.AlignCenter,
            labels["thrust_axis"].format(unit=curve.unit),
        )
        painter.restore()

        if bool(config.get("annotate_metrics", True)) and analysis is not None:
            peak = analysis.metrics.get("peak_thrust_n")
            impulse = analysis.metrics.get("total_impulse_ns")
            unavailable = labels["unavailable"]
            annotation = (
                f"{labels['peak']}: "
                f"{unavailable if peak is None else f'{float(peak):.5g} N'}    "
                f"{labels['impulse']}: "
                f"{unavailable if impulse is None else f'{float(impulse):.5g} N·s'}"
            )
            painter.setFont(QFont(font_name, 12))
            painter.drawText(
                QRectF(plot.left(), 75, plot.width(), 28),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                annotation,
            )
        painter.end()

        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        try:
            if not image.save(str(temporary), "PNG"):
                raise OSError(f"Qt could not encode PNG image {temporary}")
            os.replace(temporary, destination)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        context.report_progress(1.0, "Thrust curve PNG exported")
        return ExportResult(
            destination=destination,
            diagnostics=diagnostics,
            metadata={
                "source_channel_id": curve.source_channel_id,
                "sample_count": len(curve.time),
                "time_start": float(curve.time[0]),
                "time_end": float(curve.time[-1]),
                "interpolated_boundaries": list(curve.interpolated_boundaries),
                "width": width,
                "height": height,
                "output_locale": output_locale,
                "title": title,
            },
        )
