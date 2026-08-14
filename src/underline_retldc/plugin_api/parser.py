from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from underline_retldc.core.dataset import Dataset
from underline_retldc.core.diagnostics import Diagnostic
from underline_retldc.core.tabular import TabularPreview
from underline_retldc.plugin_api.common import (
    ParseResult,
    PluginDescriptor,
    ProbeContext,
    ProbeResult,
    TaskContext,
)


class ParserPlugin(ABC):
    @property
    @abstractmethod
    def descriptor(self) -> PluginDescriptor: ...

    @abstractmethod
    def probe(self, source: Path, context: ProbeContext) -> ProbeResult: ...

    @abstractmethod
    def config_schema(self) -> dict[str, Any]: ...

    @abstractmethod
    def parse(
        self, source: Path, config: Mapping[str, Any], context: TaskContext
    ) -> ParseResult: ...

    @abstractmethod
    def validate(self, dataset: Dataset) -> list[Diagnostic]: ...


class TabularParserPlugin(ParserPlugin):
    """Optional Parser API v1 capability for bounded, read-only table previews."""

    @abstractmethod
    def preview(
        self,
        source: Path,
        config: Mapping[str, Any],
        *,
        maximum_rows: int = 50,
    ) -> TabularPreview: ...
