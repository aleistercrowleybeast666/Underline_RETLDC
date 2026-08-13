from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from underline_retldc.core.dataset import Dataset
from underline_retldc.plugin_api.common import PluginDescriptor, ProcessingResult, TaskContext

PROCESSOR_ROLE_MOTOR_WEIGHT_COMPENSATION = "motor_weight_compensation"


class ProcessorPlugin(ABC):
    @property
    @abstractmethod
    def descriptor(self) -> PluginDescriptor: ...

    @abstractmethod
    def config_schema(self) -> dict[str, Any]: ...

    @abstractmethod
    def requirements(self) -> Mapping[str, Any]: ...

    @abstractmethod
    def process(
        self, dataset: Dataset, config: Mapping[str, Any], context: TaskContext
    ) -> ProcessingResult: ...
