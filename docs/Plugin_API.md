# Plugin API v1

Plugin API generation `1` defines five trusted Python extension categories. External plugins run
with the user's application permissions; install only plugins from trusted sources.

## Descriptor

Every plugin returns a `PluginDescriptor` containing:

```text
plugin_id       stable, locale-neutral identifier
plugin_type     parser | calibration | processor | analyzer | exporter
version         plugin implementation version
api_version     "1"
name            default display name
description     default description
translation_key optional localized-name key
```

IDs and versions are persisted. Display names are never used for logic.

## Shared contexts and results

`ProbeContext` supplies a byte/record budget. `TaskContext` supplies cancellation and progress
callbacks without depending on Qt. Operations return typed result objects containing data and
diagnostics. Fatal input problems raise a specific exception; loaders and the GUI surface it.

## Parser

```python
class ParserPlugin(ABC):
    @property
    def descriptor(self) -> PluginDescriptor: ...
    def probe(self, source: Path, context: ProbeContext) -> ProbeResult: ...
    def config_schema(self) -> dict[str, Any]: ...
    def parse(
        self, source: Path, config: Mapping[str, Any], context: TaskContext
    ) -> ParseResult: ...
    def validate(self, dataset: Dataset) -> list[Diagnostic]: ...
```

`probe` is bounded and must not fully parse a large file. A Parser converts syntax to raw Dataset
channels only. It never calibrates, detects the final burn, analyzes, or exports.

The desktop schema form currently renders object properties whose type is `string`, `number`,
`integer`, or `boolean`, plus scalar `enum` values. `default`, `minimum`, `maximum`, `title`, and
optional `x-i18n-key`/`x-enum-i18n-keys` are honored. A property with `x-ui-hidden: true` is not
rendered. Orchestration may inject a value using a documented generic `x-ui-source`, such as
`thrust_analysis.input_channel` or `thrust_analysis.regions`; this metadata must describe a shared
workspace capability and must never be interpreted through a concrete plugin ID. Other valid
schema structures remain available to non-GUI clients but require a future generic GUI renderer.

## Calibration Model

```python
class CalibrationModelPlugin(ABC):
    @property
    def descriptor(self) -> PluginDescriptor: ...
    def parameter_schema(self) -> dict[str, Any]: ...
    def evaluate(self, raw: np.ndarray, parameters: Mapping[str, Any]) -> np.ndarray: ...
```

Evaluation returns a new array. It must not mutate `raw`.

The same scalar schema renderer consumes `parameter_schema()`. Quantity and output unit are
workflow fields appended around the plugin parameters; they are not inferred by the Calibration
plugin or hardcoded for Linear Calibration.

## Processor

```python
class ProcessorPlugin(ABC):
    @property
    def descriptor(self) -> PluginDescriptor: ...
    def config_schema(self) -> dict[str, Any]: ...
    def requirements(self) -> Mapping[str, Any]: ...
    def process(
        self, dataset: Dataset, config: Mapping[str, Any], context: TaskContext
    ) -> ProcessingResult: ...
```

Processors add new channels/results and leave their input channels unchanged.

`requirements()` can advertise a stable role without changing the API v1 signature. The current
role convention is:

```text
processor_role = motor_weight_compensation
```

The Motor Weight-Change Compensation selector lists only Processors declaring that exact role.
The official `builtin.processor.vertical_linear_baseline` plugin declares it. Compatible user
plugins appear after refresh without a MainWindow change. No role means the Processor is not shown
in that selector; future filter, resampler, or smoother workspaces should define their own roles.
Selecting `None` stores no Processor reference and uses a Core pass-through stage that preserves
the calibrated input in a new processed channel.

## Analyzer

```python
class AnalyzerPlugin(ABC):
    @property
    def descriptor(self) -> PluginDescriptor: ...
    def config_schema(self) -> dict[str, Any]: ...
    def analyze(
        self, dataset: Dataset, config: Mapping[str, Any], context: TaskContext
    ) -> AnalysisResult: ...
```

Analyzers return metrics and diagnostics; they do not modify Dataset channels.

## Exporter

```python
class ExporterPlugin(ABC):
    @property
    def descriptor(self) -> PluginDescriptor: ...
    def config_schema(self) -> dict[str, Any]: ...
    def validate(
        self, dataset: Dataset, analysis: AnalysisResult | None, config: Mapping[str, Any]
    ) -> list[Diagnostic]: ...
    def export(
        self,
        destination: Path,
        dataset: Dataset,
        analysis: AnalysisResult | None,
        config: Mapping[str, Any],
        context: TaskContext,
    ) -> ExportResult: ...
```

Built-in Exporter IDs are:

```text
builtin.exporter.csv
builtin.exporter.analysis_json
builtin.exporter.analysis_txt
builtin.exporter.thrust_png
builtin.exporter.openrocket_eng
```

Exporters receive the already parsed/processed Dataset and optional AnalysisResult. They never
reopen or reparse the raw source. The formal TXT/PNG/ENG curve is selected from the configured
final channel over ignition through burnout and shifted to zero. The Export Dialog uses stable IDs
and fixed filenames; overwrite policy is orchestration behavior, not a localized plugin name.

An Exporter opts into the desktop Export Dialog through generic top-level config-schema metadata:

```json
{
  "x-underline-retldc-export": {
    "filename": "example.dat",
    "translation_key": "example.export.name",
    "required_analysis_ids": ["builtin.analyzer.thrust"],
    "locale_qualified": true
  }
}
```

Optional booleans include `requires_motor_metadata` and `supports_metric_annotation`. The dialog
uses this mapping for labels, availability, default selection, and output naming; it does not
hard-code bundled Exporter IDs. A malformed desktop mapping is skipped with a diagnostic/log entry
instead of preventing other plugins from loading. Exporters without desktop metadata remain valid
API v1 plugins for non-desktop clients.

## Manifest, roots, and discovery

Every official bundled and third-party plugin is a directory with `plugin.json`:

```json
{
  "plugin_id": "example.parser.mydaq",
  "plugin_type": "parser",
  "api_version": "1",
  "version": "1.0.0",
  "entry": "plugin:MyDAQParser",
  "name": "MyDAQ Parser"
}
```

`entry` is `module_path:ClassName`, relative to the plugin directory. The standard layout is:

```text
plugins/
├─ parsers/<folder>/plugin.json + plugin.py
├─ calibrations/<folder>/plugin.json + plugin.py
├─ processors/<folder>/plugin.json + plugin.py
├─ analyzers/<folder>/plugin.json + plugin.py
└─ exporters/<folder>/plugin.json + plugin.py
```

The repository/portable `plugins/` root is `Bundled`; the writable platform user root is `User`
(`%APPDATA%/Underline_RETLDC/plugins/` on Windows). Both roots use identical APIs and feed one
Registry. Provenance comes from the configured root, never a plugin manifest claim. The category
directory is for organization only; manifest `plugin_type` determines the required abstract class.

Discovery is recursive and prunes `.venv`, `.git`, `__pycache__`, and symlink directories. A plugin
directory is loaded at most once. Failures are isolated and reported as manifest, API, import,
initialization, descriptor, discovery, or duplicate-ID diagnostics. API generations other than
`1` are disabled, and a failing optional plugin never prevents application startup.

There is no separate built-in registration path. Official IDs retain the `builtin.*` prefix for
Project compatibility, while their concrete code lives in repository-root `plugins/`. Installing
a third-party directory copies it under the appropriate category in the writable user root.

Optional translations live at `i18n/zh_CN.json` and `i18n/en_US.json`. Keys should be prefixed by
the plugin ID. Missing requested strings fall back to the English bundle and then descriptor text.

## Minimal third-party Parser

`plugin.json` can use the manifest above. Put this in `plugin.py`:

```python
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from underline_retldc.core.channel import Channel
from underline_retldc.core.dataset import Dataset
from underline_retldc.plugin_api.common import (
    ParseResult,
    PluginDescriptor,
    PluginType,
    ProbeContext,
    ProbeResult,
    TaskContext,
)
from underline_retldc.plugin_api.parser import ParserPlugin


class MyDAQParser(ParserPlugin):
    @property
    def descriptor(self) -> PluginDescriptor:
        return PluginDescriptor(
            plugin_id="example.parser.mydaq",
            plugin_type=PluginType.PARSER,
            version="1.0.0",
            api_version="1",
            name="MyDAQ Parser",
            description="Example two-column parser",
        )

    def probe(self, source: Path, context: ProbeContext) -> ProbeResult:
        first = source.open("r", encoding="utf-8").readline()
        return ProbeResult(0.8 if ";" in first else 0.0, "semicolon signature")

    def config_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    def parse(
        self, source: Path, config: Mapping[str, Any], context: TaskContext
    ) -> ParseResult:
        matrix = np.loadtxt(source, delimiter=";")
        dataset = Dataset(
            time=matrix[:, 0],
            time_unit="s",
            channels={
                "sensor_raw": Channel(
                    id="sensor_raw",
                    quantity="force",
                    unit="raw",
                    values=matrix[:, 1],
                    role="raw",
                )
            },
        )
        return ParseResult(dataset=dataset, diagnostics=[])

    def validate(self, dataset: Dataset) -> list:
        return []
```

Do not import GUI modules. Respect cancellation for long loops, keep source files read-only, and
return a fresh array/Dataset rather than modifying caller-owned values.
