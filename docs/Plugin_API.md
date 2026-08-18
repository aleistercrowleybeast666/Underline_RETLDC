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

Each produced Channel should provide stable `id`, human `name`, `quantity`, `unit`, `role`,
immutable `values`, semantic metadata, and optional `semantic_role`. If the format states a Unit,
the Parser must preserve it (`Pc (MPa)`→`MPa`, `F (N)`→`N`). If the format omits a Unit for a
known Quantity, the Parser may pass `None`; Core assigns the canonical SI Data Unit and records
`unit_source=default_si`. A Parser must explicitly write `raw`, `count`, or `ADC` only when the
format has that sensor-value meaning. It must not guess Calibration or label every missing unit as
raw. Unknown custom quantities should declare a Unit; otherwise Core records `unknown_si` and a
Diagnostic for user confirmation.

Parser output and Calibration state are independent. Orchestration assigns factory-default
`builtin.calibration.identity` to every newly parsed Channel, including engineering and raw
Units. The Parser does not select or execute that Calibration.

The desktop schema form currently renders object properties whose type is `string`, `number`,
`integer`, or `boolean`, plus scalar `enum` values. `default`, `minimum`, `maximum`, `title`, and
optional `x-i18n-key`/`x-enum-i18n-keys` are honored. A property with `x-ui-hidden: true` is not
rendered. Orchestration may inject a value using a documented generic `x-ui-source`, such as
`thrust_analysis.input_channel` or `thrust_analysis.regions`; this metadata must describe a shared
workspace capability and must never be interpreted through a concrete plugin ID. Other valid
schema structures remain available to non-GUI clients but require a future generic GUI renderer.

Parsers for ordinary two-dimensional tables may additionally implement the additive preview
capability without changing existing Parser API v1 implementations:

```python
class TabularParserPlugin(ParserPlugin):
    def preview(
        self,
        source: Path,
        config: Mapping[str, Any],
        *,
        maximum_rows: int = 50,
    ) -> TabularPreview: ...
```

Such a Parser declares top-level schema metadata such as:

```json
{
  "x-underline-retldc-tabular": {
    "reader": "xlsx",
    "preview_rows": 50,
    "preset_supported": true
  }
}
```

`reader` is currently `xlsx` or `delimited`. The common Tabular Mapping Editor consumes this
capability; orchestration does not compare a concrete plugin ID. Preview must be bounded and
read-only. Auto Mapping is a user-editable suggestion operation outside `parse()`. The actual
Parser contract is the explicit config: header/data rows, time mode, zero-based column mappings,
Quantity, Semantic Role, Data Unit, and invalid-value policy. A Parser must reject a missing time
source instead of inventing a 1 Hz timeline.

For a normal CSV/TSV/XLSX layout difference, prefer `builtin.parser.generic_delimited` or
`builtin.parser.generic_xlsx` plus a pure-JSON Tabular Preset. A new executable Parser plugin is
appropriate only when a format cannot be represented as an ordinary table (for example binary,
compressed, checksummed, multi-block, or proprietary-protocol data).

The platform's ordinary Quick Import categories are provided by its Workspace Capability Registry
and translated into this existing explicit tabular config. They do not add a new Parser API v1
method. Direct Quantity, Semantic Role, Channel ID, Metadata, and Ignore controls remain available
through Advanced Mapping for specialist use.

Two-column raw-log Parsers may subclass the additive `TwoColumnRawParserBase` helper in
`underline_retldc.plugin_api.two_column`. It supplies bounded syntax probing, timestamp-unit
normalization, malformed-row diagnostics, immutable raw Channel construction, and common
validation. TR_F, TR_P, and TR_T use this helper while declaring different Quantity and Semantic
Role values. The helper changes no Plugin API v1 signatures; third-party Parsers may continue to
implement `ParserPlugin` directly.

## Calibration Model

```python
class CalibrationModelPlugin(ABC):
    @property
    def descriptor(self) -> PluginDescriptor: ...
    def parameter_schema(self) -> dict[str, Any]: ...
    def requirements(self) -> Mapping[str, Any]: ...
    def evaluate(self, raw: np.ndarray, parameters: Mapping[str, Any]) -> np.ndarray: ...
```

Evaluation returns a new array. It must not mutate `raw`. `requirements()` declares input
Quantity/Unit constraints (if any) and output Quantity/Unit behavior. Stable conventions include:

```text
input_quantity = any | <quantity>
input_unit = any | <unit/dimension constraint>
output_quantity = same_as_input | parameter:<schema_property> | <quantity>
output_unit = same_as_input | parameter:<schema_property> | <unit>
```

The same scalar schema renderer consumes `parameter_schema()`. If output Quantity or Unit is
user-configurable, the plugin exposes those values through that schema. Calibration performs the
numeric mapping (for example count→N or V→Pa); it must never merely rename a Unit. Identity uses
same-as-input behavior and means no additional transform, not certification of sensor accuracy.
Unit conversion (Pa↔MPa, K↔°C) remains a separate Core service.

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

Thrust polarity is not a motor-weight compensation parameter and is not part of a Processor
schema. The Thrust Workflow applies the Project's `+1`/`-1` polarity first and supplies a fresh,
polarity-normalized input Channel to compatible correction Processors. A Processor fits and
subtracts its baseline in that orientation and must not apply another sign transform.

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
builtin.exporter.chamber_pressure_csv
builtin.exporter.chamber_pressure_png
builtin.exporter.temperature_csv
builtin.exporter.temperature_png
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
    "required_analysis_ids": [],
    "required_capability_ids": ["thrust_ready"],
    "group_id": "thrust",
    "group_translation_key": "export.group.thrust",
    "group_order": 10,
    "format_order": 10,
    "default_selected": true,
    "locale_qualified": true
  }
}
```

Optional booleans include `requires_motor_metadata` and `supports_metric_annotation`. The dialog
uses this mapping for labels, availability, default selection, and output naming; it does not
hard-code bundled Exporter IDs. A malformed desktop mapping is skipped with a diagnostic/log entry
instead of preventing other plugins from loading. Exporters without desktop metadata remain valid
API v1 plugins for non-desktop clients.

`required_capability_ids` is optional and generic. Current stable desktop capabilities are
`project_summary_ready`, `thrust_ready`, `physical_force`, `chamber_pressure_ready`,
`temperature_ready`, and `segmentation_ready`. OpenRocket ENG declares the thrust, physical-force,
and segmentation capabilities and sets `default_selected=true`; a relative analysis in
raw/count/ADC can unlock compatible reports without making ENG selectable because `physical_force`
remains incomplete. Overall, thrust,
pressure, and temperature groups use `group_order` 0/10/20/30; missing group metadata falls back to
Other at 1000. `format_order` provides CSV 10, PNG 20, and special format 30 ordering. A metadata
default is applied once when its requirements first become available; selected IDs and initialized
default IDs are persisted separately so user choices survive later refreshes and Project reopen.
Each Exporter still validates its declared requirements at execution, including
Quantity, Unit, ACTIVE_TEST segmentation, and motor metadata where applicable. ENG does not expose
or require a separate final-curve confirmation setting.

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

Three runtime concepts are distinct:

- **Application Plugin Root**: `Application_ProjectRoot()/plugins`. In source development this is
  repository-root `plugins/`; in the folder package it is the `plugins/` directory beside the EXE.
- **User Plugin Root**: the platform-writable per-user directory, on Windows
  `%APPDATA%/Underline_RETLDC/plugins/`.
- **Plugin Registry**: the single in-memory Registry fed by recursive discovery of both roots.

Both physical roots use identical APIs and manifests. Official shipped `builtin.*` plugins in the
Application Root are displayed as `Bundled`; third-party IDs in that root are `Application`; the
per-user root is `User`. This Loader-assigned display provenance is informational and grants no
trust. The category directory is organizational only; manifest `plugin_type` determines the
required abstract class.

Discovery is recursive and prunes `.venv`, `.git`, `__pycache__`, and symlink directories. A plugin
directory is loaded at most once. Failures are isolated and reported as manifest, API, import,
initialization, descriptor, discovery, or duplicate-ID diagnostics. API generations other than
`1` are disabled, and a failing optional plugin never prevents application startup.

There is no separate built-in registration path. Official IDs retain the `builtin.*` prefix for
Project compatibility, while their concrete code lives in the Application/Repository Plugin Root.

Interactive installation accepts a folder or ZIP containing one or more plugins at arbitrary
wrapper-directory depth. Folder and ZIP input share one recursive package-discovery rule: every
directory containing a valid `plugin.json` is a Candidate Plugin Root. A candidate containing a
descendant candidate is marked as a nested container, and only the deepest roots are installable by
default so copying an ancestor cannot introduce duplicate nested manifests. Multiple deepest roots
with the same Plugin ID are source conflicts; that ID is not installed, while unrelated candidates
remain available.

For every selected candidate, `plugin_type` in `plugin.json` is the sole category authority:

```text
parser      → parsers/
calibration → calibrations/
processor   → processors/
analyzer    → analyzers/
exporter    → exporters/
```

The Installer copies only the resolved Plugin Root, never its outer ZIP/folder wrappers, and then
uses this destination policy independently for each plugin:

```text
Application Plugin Root, if an actual write probe and copy succeed
    ↓ access-permission failure only
User Plugin Root
    ↓
refresh the shared Plugin Registry
    ↓
verify the installed path has a PluginRecord with result LOADED
```

The decision never depends on `C:`/`D:` or another drive letter and normal installation never
requires administrator rights. Even after a successful write probe, an access-related error from
the real staged copy triggers the User Root fallback. Both roots retain the same category layout.
Invalid manifests, unsupported APIs, corrupt ZIPs, duplicate IDs, missing entry modules, and other
non-permission errors remain explicit errors and do not trigger fallback. ZIP extraction rejects
absolute/traversal/drive paths, links, encrypted
entries, duplicate paths, special entries, more than 4096 entries, and more than 512 MiB expanded
content. Replacing an existing ID occurs at its current root (it does not migrate to the other root),
first copies and validates a complete sibling staging directory, and then swaps directories so an
interrupted copy neither destroys the old plugin nor retains obsolete files.

The interactive workflow runs package discovery, copy, Registry refresh, and load verification
through the shared `TaskManager` and main-window status/progress area. Its stable diagnostic stages
are `DISCOVERY`, `MANIFEST_VALIDATION`, `CONFLICT_CHECK`, `DESTINATION_RESOLUTION`, `EXTRACTION`,
`COPY`, `REGISTRY_REFRESH`, and `LOAD_VERIFY`. A copied plugin whose Registry record is not `LOADED`
is reported as installed-but-failed, not as a successful installation. Advanced users may still
copy a folder manually into either root and refresh; Loader discovery remains recursive.

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
                    name="Load cell ADC",
                    quantity="force",
                    unit="raw",
                    values=matrix[:, 1],
                    role="raw",
                    semantic_role="thrust",
                )
            },
        )
        return ParseResult(dataset=dataset, diagnostics=[])

    def validate(self, dataset: Dataset) -> list:
        return []
```

Do not import GUI modules. Respect cancellation for long loops, keep source files read-only, and
return a fresh array/Dataset rather than modifying caller-owned values.
