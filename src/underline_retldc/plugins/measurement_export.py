from __future__ import annotations

import csv
import os
from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygonF

from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset


class MeasurementWriteResult(StrEnum):
    WRITTEN = "written"
    SKIPPED_NO_CHANNEL = "skipped_no_channel"


def MeasurementCsv_Write(
    destination: Path,
    dataset: Dataset,
    channels: Iterable[Channel],
    *,
    output_locale: str,
    delimiter: str = ",",
) -> MeasurementWriteResult:
    selected = tuple(channels)
    if not selected:
        return MeasurementWriteResult.SKIPPED_NO_CHANNEL
    if output_locale not in {"zh_CN", "en_US"}:
        raise ValueError("Measurement CSV locale must be 'zh_CN' or 'en_US'")
    if len(delimiter) != 1:
        raise ValueError("Measurement CSV delimiter must be one character")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    time_label = "时间" if output_locale == "zh_CN" else "Time"
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter=delimiter)
            writer.writerow(
                [f"{time_label} [{dataset.time_unit}]"]
                + [f"{channel.name} [{channel.data_unit}]" for channel in selected]
            )
            project_time = dataset.project_time
            for index in range(dataset.sample_count):
                writer.writerow(
                    [f"{project_time[index]:.12g}"]
                    + [f"{channel.values[index]:.12g}" for channel in selected]
                )
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return MeasurementWriteResult.WRITTEN


def MeasurementPng_Write(
    destination: Path,
    dataset: Dataset,
    channels: Iterable[Channel],
    *,
    output_locale: str,
    quantity_title_en: str,
    quantity_title_zh: str,
    active_interval: tuple[float, float] | None = None,
    crop_to_active_interval: bool = False,
) -> MeasurementWriteResult:
    selected = tuple(channels)
    if not selected:
        return MeasurementWriteResult.SKIPPED_NO_CHANNEL
    if output_locale not in {"zh_CN", "en_US"}:
        raise ValueError("Measurement PNG locale must be 'zh_CN' or 'en_US'")
    project_time = dataset.project_time
    finite_time_mask = np.isfinite(project_time)
    finite_time = project_time[finite_time_mask]
    if finite_time.size == 0:
        return MeasurementWriteResult.SKIPPED_NO_CHANNEL
    if crop_to_active_interval:
        if active_interval is None:
            raise ValueError("Cropped measurement PNG export requires ACTIVE_TEST")
        x_min, x_max = (float(active_interval[0]), float(active_interval[1]))
        if not np.isfinite(x_min) or not np.isfinite(x_max) or x_min >= x_max:
            raise ValueError("Measurement PNG ACTIVE_TEST must be finite and increasing")
        time_window = finite_time_mask & (project_time >= x_min) & (project_time <= x_max)
    else:
        x_min = float(np.min(finite_time))
        x_max = float(np.max(finite_time))
        time_window = finite_time_mask
    finite_values = np.concatenate(
        [
            channel.values[time_window & np.isfinite(channel.values)]
            for channel in selected
        ]
    )
    if finite_values.size == 0:
        return MeasurementWriteResult.SKIPPED_NO_CHANNEL

    width, height = 1600, 1000
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    plot = QRectF(145.0, 125.0, 1375.0, 720.0)
    font_name = "Microsoft YaHei" if output_locale == "zh_CN" else "Arial"
    title = quantity_title_zh if output_locale == "zh_CN" else quantity_title_en
    time_label = "时间 [s]" if output_locale == "zh_CN" else "Time [s]"
    value_label = "数值" if output_locale == "zh_CN" else "Value"

    painter.setPen(QColor("#172033"))
    painter.setFont(QFont(font_name, 24, QFont.Weight.Bold))
    painter.drawText(QRectF(0, 30, width, 52), Qt.AlignmentFlag.AlignCenter, title)
    y_min = min(0.0, float(np.min(finite_values)))
    y_max = max(0.0, float(np.max(finite_values)))
    if x_max <= x_min:
        x_max = x_min + 1.0
    if y_max <= y_min:
        y_max = y_min + 1.0
    y_padding = 0.08 * (y_max - y_min)
    y_min -= y_padding
    y_max += y_padding

    if active_interval is not None and not crop_to_active_interval:
        start = max(x_min, float(active_interval[0]))
        end = min(x_max, float(active_interval[1]))
        if start < end:
            left = plot.left() + (start - x_min) / (x_max - x_min) * plot.width()
            right = plot.left() + (end - x_min) / (x_max - x_min) * plot.width()
            painter.fillRect(
                QRectF(left, plot.top(), right - left, plot.height()),
                QColor(245, 158, 11, 28),
            )

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

    colors = ("#2563eb", "#dc2626", "#059669", "#7c3aed", "#ea580c", "#0891b2")
    for channel_index, channel in enumerate(selected):
        finite = time_window & np.isfinite(channel.values)
        points = QPolygonF(
            [
                QPointF(
                    plot.left()
                    + (float(timestamp) - x_min) / (x_max - x_min) * plot.width(),
                    plot.bottom()
                    - (float(value) - y_min) / (y_max - y_min) * plot.height(),
                )
                for timestamp, value in zip(
                    project_time[finite], channel.values[finite], strict=True
                )
            ]
        )
        color = QColor(colors[channel_index % len(colors)])
        painter.setPen(QPen(color, 3))
        painter.save()
        painter.setClipRect(plot)
        painter.drawPolyline(points)
        painter.restore()
        legend_y = 88 + channel_index * 24
        painter.drawLine(QPointF(160, legend_y), QPointF(205, legend_y))
        painter.setPen(QColor("#172033"))
        painter.drawText(
            QRectF(215, legend_y - 12, 800, 24),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{channel.name} [{channel.data_unit}]",
        )

    painter.setPen(QColor("#172033"))
    painter.setFont(QFont(font_name, 14))
    painter.drawText(
        QRectF(plot.left(), 885, plot.width(), 35),
        Qt.AlignmentFlag.AlignCenter,
        time_label,
    )
    painter.save()
    painter.translate(42, plot.center().y())
    painter.rotate(-90)
    painter.drawText(
        QRectF(-plot.height() / 2, -22, plot.height(), 35),
        Qt.AlignmentFlag.AlignCenter,
        value_label,
    )
    painter.restore()
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
    return MeasurementWriteResult.WRITTEN
