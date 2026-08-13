from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from underline_retldc.core.data_quality import DataQualityReport
from underline_retldc.core.dataset import Dataset
from underline_retldc.core.regions import BurnCandidate
from underline_retldc.plugin_api.common import AnalysisResult, ProcessingResult


@dataclass(slots=True)
class AnalysisSession:
    project_path: Path | None = None
    source_path: Path | None = None
    source_hash: str | None = None
    parser_id: str | None = None
    parser_config: dict[str, Any] = field(default_factory=dict)
    raw_dataset: Dataset | None = None
    quality_report: DataQualityReport | None = None
    calibration_id: str | None = None
    calibration_config: dict[str, Any] = field(default_factory=dict)
    calibrated_dataset: Dataset | None = None
    processor_id: str | None = None
    processor_config: dict[str, Any] = field(default_factory=dict)
    processing_result: ProcessingResult | None = None
    candidates: list[BurnCandidate] = field(default_factory=list)
    regions: dict[str, list[float]] = field(default_factory=dict)
    analyzer_id: str | None = None
    analyzer_config: dict[str, Any] = field(default_factory=dict)
    analysis_result: AnalysisResult | None = None
    motor_metadata: dict[str, Any] = field(default_factory=dict)
    export_settings: dict[str, Any] = field(default_factory=dict)
    curve_confirmed: bool = False

    @property
    def processed_dataset(self) -> Dataset | None:
        return self.processing_result.dataset if self.processing_result is not None else None

    def reset_after_parse(self) -> None:
        self.calibration_id = None
        self.calibration_config.clear()
        self.calibrated_dataset = None
        self.processor_id = None
        self.processor_config.clear()
        self.processing_result = None
        self.candidates.clear()
        self.regions.clear()
        self.analyzer_id = None
        self.analyzer_config.clear()
        self.analysis_result = None
        self.curve_confirmed = False

    def reset_after_calibration(self) -> None:
        self.processor_id = None
        self.processor_config.clear()
        self.processing_result = None
        self.candidates.clear()
        self.regions.clear()
        self.analyzer_id = None
        self.analyzer_config.clear()
        self.analysis_result = None
        self.curve_confirmed = False

    def reset_after_processing(self) -> None:
        self.analyzer_id = None
        self.analyzer_config.clear()
        self.analysis_result = None
        self.curve_confirmed = False
