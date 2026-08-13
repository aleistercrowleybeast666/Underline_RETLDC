from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from underline_retldc.core.dataset import Dataset
from underline_retldc.plugin_api.common import AnalysisResult, PluginDescriptor, TaskContext


class AnalyzerPlugin(ABC):
    @property
    @abstractmethod
    def descriptor(self) -> PluginDescriptor: ...

    @abstractmethod
    def config_schema(self) -> dict[str, Any]: ...

    @abstractmethod
    def analyze(
        self, dataset: Dataset, config: Mapping[str, Any], context: TaskContext
    ) -> AnalysisResult: ...

