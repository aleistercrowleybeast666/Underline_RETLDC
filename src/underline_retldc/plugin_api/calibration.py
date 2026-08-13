from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

import numpy as np
from numpy.typing import NDArray

from underline_retldc.plugin_api.common import PluginDescriptor


class CalibrationModelPlugin(ABC):
    @property
    @abstractmethod
    def descriptor(self) -> PluginDescriptor: ...

    @abstractmethod
    def parameter_schema(self) -> dict[str, Any]: ...

    @abstractmethod
    def evaluate(
        self, raw: NDArray[np.float64], parameters: Mapping[str, Any]
    ) -> NDArray[np.float64]: ...

