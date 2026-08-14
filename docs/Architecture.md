# Architecture

Underline RETLDC is an offline, layered data pipeline. Core has no GUI, TR_F, or built-in-plugin
dependency, so scientific behavior is testable without starting Qt.

```mermaid
flowchart LR
    S["Read-only Source(s)"] --> P["Parser"]
    P --> ST["Stream: local time + Project offset"]
    ST --> D["Channel: Quantity + Data Unit + raw values"]
    D --> C["Calibration Model (Identity by default)"]
    C --> PR["Processor"]
    PR --> A["Analyzer"]
    PR --> E["Exporter"]
    A --> E
    R["Plugin Registry / Loader"] --> P
    R --> C
    R --> PR
    R --> A
    R --> E
    GUI["PySide6 GUI"] --> TM["Task Manager"]
    TM --> P
    TM --> C
    TM --> PR
    TM --> A
    TM --> E
    I["i18n + persistent settings"] --> GUI
    PJ["Project JSON"] -. "stable IDs and parameters" .-> GUI
    U["Unit Registry"] --> D
    U --> GUI
    U --> A
```

## Core model

`ProjectData` owns read-only `Source` records and one or more `Stream` records. Each Stream owns a
`Dataset`, retains local timestamps, and exposes Project Time as
`t_project = t_local + time_offset_s`; different Streams need not be resampled. `Dataset` owns
arbitrary stable-ID `Channel` objects, metadata, and Diagnostics. A Channel declares Quantity,
scientific Data Unit, Unit Source, optional Display Unit override, semantic role, processing role,
immutable values, and metadata. Roles distinguish raw, calibrated, baseline, corrected, and
processed values.

Unit and Calibration are orthogonal. A known Quantity with no Parser-declared Unit receives its
canonical SI Data Unit; an explicit Parser or Project/User unit wins. Every newly parsed Channel
receives factory-default Identity Calibration regardless of Unit. Identity copies values and means
“no extra transform,” not scientific certification. Calibration can turn a sensor value such as
`count` into `N`; Unit conversion only changes representation within one physical dimension, such
as Pa→MPa or K→°C, and never mutates raw arrays. `raw`, `count`, and `ADC` are intentionally
non-convertible.

Diagnostics have `INFO`, `WARNING`, or `ERROR` severity plus a stable code, message, location,
and details. Warnings preserve usable data; errors describe conditions that prevent an operation.

`PrimaryChannelBindings` stores the Project's selected thrust, chamber-pressure, and temperature
inputs as complete `ChannelReference(source_id, stream_id, channel_id)` values. The binding is the
final workflow input. Quantity and semantic role constrain candidates and help auto-binding, but a
role never overrides an explicit binding. Calibration and processing resolve their actual output
Channels dynamically, so downstream orchestration does not assume names such as
`force_calibrated`.

## Generic tabular ingestion

Ordinary CSV, TSV, custom-delimited text, and XLSX use one explicit mapping layer:

```mermaid
flowchart LR
    CSV["CSV / TSV"] --> DR["Delimited Reader"]
    XLSX["XLSX"] --> XR["Workbook / Sheet Reader"]
    DR --> T["Read-only Tabular Cell Matrix"]
    XR --> T
    T --> M["Tabular Mapping Engine"]
    WC["Workspace Capability Registry"] --> QI["Quick Import categories"]
    QI --> M
    M --> TIME["Explicit Time Source"]
    M --> CH["Quantity + Semantic Role + Data Unit Channels"]
    M --> DG["Diagnostics"]
    TIME --> ST["Stream"]
    CH --> ST
```

Readers only decode external syntax into a bounded preview or sparse cell matrix. The shared
Mapping Engine applies one-based data-row bounds, an explicit time column/sample rate/sample
period, zero-based column-index mappings, missing-value policy, and header-hint diagnostics.
Header text is never the parse contract. Auto Mapping may inspect it to pre-fill an editable GUI
configuration, but `parse()` executes only the saved mapping. An absent time source blocks parsing;
there is no implicit 1 Hz fallback.

The ordinary Quick Import view obtains its categories from the Workspace Capability Registry and
currently presents `Time`, `Thrust`, `Chamber Pressure`, `Temperature`, and `Other`. It translates
those selections into the same explicit mapping consumed by the Parser. `Other` is preserved as
an auxiliary Channel but excluded from automatic binding, dedicated plots, segmentation, and
analysis. Advanced Mapping remains available in a collapsed section for direct Quantity,
Semantic Role, Channel ID, Metadata, and Ignore control.

`TabularMappingEditor` is a platform GUI capability selected through the generic
`x-underline-retldc-tabular` schema declaration and the additive `TabularParserPlugin` preview
capability. Both official Generic Delimited and Generic XLSX Parsers reuse it without a
MainWindow branch on their plugin IDs.

TR_F, TR_P, and TR_T use the shared `TwoColumnRawParserBase` Plugin API helper for bounded probing,
timestamp normalization, row diagnostics, validation, and immutable Dataset construction. Their
small concrete plugins declare only the force, chamber-pressure, or temperature semantics. Since
their syntax is intentionally identical, recommendation logic applies both an absolute threshold
and a runner-up margin and asks for confirmation when meaning is ambiguous.

Reusable Tabular Presets are pure JSON and store Parser ID/version plus reader, row, time, and
column configuration. Execution remains index-based; optional expected-header hints generate a
warning when a layout may have changed. A Project embeds a private copy of the final Source mapping,
so later edits to a reusable Preset cannot change an existing Project.

## Plugin pipeline

The five Plugin API v1 contracts are Parser, Calibration Model, Processor, Analyzer, and Exporter.
Official bundled and third-party plugins use the same contracts, manifest, recursive discovery,
Registry, schema renderer, and i18n mechanism. Every concrete implementation lives below the
repository-root `plugins/` tree rather than inside the source package:

```text
Platform Core
    ↓
Plugin API v1
    ↓
plugins/
├─ parsers/
├─ calibrations/
├─ processors/
├─ analyzers/
└─ exporters/
```

The project/portable root `Underline_RETLDC/plugins/` is discovered as `Bundled`; the writable
platform user root (on Windows, `%APPDATA%/Underline_RETLDC/plugins/`) is discovered as `User`.
Both roots have the same layout and feed one `PluginRegistry`. Source provenance is assigned by
the Loader and confers no alternate API or permission. Folder categories are organizational;
manifest `plugin_type` is authoritative.

Discovery recursively finds `plugin.json`, while pruning `.venv`, `.git`, `__pycache__`, and
symlink directories. `PluginLoader` validates a manifest, API compatibility, imports, descriptor
consistency, and duplicate stable IDs while converting each failure into an isolated diagnostic.
There is no hard-coded built-in registration path. The `builtin.*` ID prefix remains stable for
official shipped plugins and does not imply a `src/underline_retldc/builtin/` implementation.

## Tasks and GUI

`TaskManager` runs parsing, processing, analysis, and export callables outside the Qt main thread.
It tracks name, progress, cancellation, success/failure, result, and exception. Algorithms receive
a framework-neutral `TaskContext`, allowing a later worker-process implementation.

The GUI has five stable-ID primary workspaces. `Project` combines multi-Source selection and time
offsets, Parser probing/schema configuration, parsing/quality diagnostics, per-Channel Quantity,
Data Unit, Unit Source, Display Unit, Calibration configuration/JSON, and motor metadata. `Thrust
Analysis` combines shared test-interval candidates, numeric and draggable PRE/ACTIVE_TEST/POST
regions, processing controls, the central pyqtgraph plot, thrust metrics, and diagnostics. Its
visible curve choices are the uncorrected and corrected signals. `Chamber Pressure`, `Temperature`,
and `Data Explorer` show compatible Project Channels and the same ACTIVE_TEST marker. The GUI
invokes Core/plugins and never contains copies of formulas or unit conversions.

The Session owns the only final Project Test Segmentation. Thrust and Chamber Pressure expose two
views/editors of that state and synchronize numeric edits, candidate selection, and plot dragging
in both directions; Temperature is read-only. Both Auto Detect buttons call one controller. It
selects the explicit Primary Chamber Pressure before Primary Thrust, uses the selected reference
Dataset for candidate boundaries, and fixes pressure activity polarity at `+1` independently of
the thrust Processor sign.

Thrust, Chamber Pressure, and Temperature are composed from one `AnalysisWorkspaceShell` with a
shared `AnalysisPlotWidget` and `AnalysisResultsPanel`. This keeps plot sizing, legend behavior,
PRE/ACTIVE_TEST/POST markers, Fit View, theme updates, empty states, and result-table stretching
consistent. Thrust adds processing controls, chamber pressure selects one bound Channel, and
temperature supports multiple bound Channels without duplicating the common presentation code.

The desktop supports stable `light` and `dark` theme IDs. Light uses white controls with dark text;
dark uses blue-grey surfaces with high-contrast light text. Navigation, application headers,
toolbars, and supported native Windows captions use coordinated deep blue. Menus, ComboBox
popups, tables, disabled controls, warnings, dialogs, status bars, and pyqtgraph plot colors are
all themed together at runtime. The selection is persisted under QSettings `ui/theme`; it is a UI
preference and never Project science state or an input to formal exporters.

Plot axes disable pyqtgraph Auto SI Prefix. The persisted `engineering` Unit Display Mode uses the
resolved engineering Display Unit, while `si_scientific` converts display values to canonical SI
and uses scientific tick/result formatting. Display modes never reinterpret Channel Data Units or
change Calibration and exporter inputs.

Export is a menu/toolbar action opening one unified dialog. Plugin management and Settings are
modal Tools dialogs, so auxiliary operations do not fragment the main workflow. Parser and
Calibration scalar controls come from plugin schemas (`string`, `number`, `integer`, `boolean`,
and `enum`) and retain stable plugin IDs as ComboBox data.

The motor-weight compensation selector is also Registry-driven. It filters Processor plugins by
the stable `requirements()` role `motor_weight_compensation`, injects shared analysis regions via
generic schema-source metadata, and renders remaining scalar settings through `SchemaForm`.
Selecting `None` runs a Core pass-through that creates a separate processed channel without
claiming any compensation plugin provenance.

The Export dialog may be opened at every workflow stage and lists every registered Exporter whose
schema declares valid generic desktop metadata. Each choice declares stable data capability IDs
and optional Analyzer IDs. The current capabilities include `project_summary_ready`,
`thrust_ready`, `physical_force`, `chamber_pressure_ready`, `temperature_ready`, and
`segmentation_ready`. Formats are sorted by metadata into Overall, Thrust, Chamber Pressure,
Temperature, then Other; each group uses CSV, PNG, then special-format order where applicable.
An option becomes enabled only when its own requirements are met. Its metadata default is applied
once on first availability and is never silently reapplied after the user unchecks it; ENG defaults
off. Export choices are held in a scrolling list that shows at most ten option rows.

Checkbox indicators are theme-rendered as bordered squares in unchecked, checked, and disabled
states, so no selectable or confirmable action relies on an unframed checkmark. Result tables use
stable stretch sizing; populating parser recommendations or thrust metrics never calls
content-based column shrinking.

Parser ambiguity uses an explicit exclusive `QButtonGroup` with high-contrast radio indicators,
confidence text, probe-reason tooltips, selected feedback, and recommendation-table activation.
Plugin registry order never resolves a close TR_F/TR_P/TR_T tie.

ImportPage emits the stable Source path when the user removes an entry. Removing a parsed Source
synchronously removes its Streams, calibrated Channels, Primary bindings, and workspace series and
conservatively invalidates derived segmentation, processing, analysis, confirmation, statistics,
and export availability. Removing an unparsed pending entry preserves the existing parsed Project;
removing the final Source clears parser/schema/preview/results and all workspaces.

All ComboBoxes use the shared conventional dropdown widget. A popup opens below the control when
screen space permits. Up to ten items are shown without a scrollbar; longer lists show at most ten
rows and enable vertical scrolling.

## Persistence and language

Project serialization writes `underline-retldc-project/2`, reads legacy `/1`, and records Source
identities and hashes,
Stream offsets, Channel Quantity/Data Unit/Unit Source/optional Display Unit override, per-Channel
Calibration references, stable plugin IDs/versions/API generation, configurations, intervals,
motor metadata, primary Channel bindings, export settings, locale, diagnostics, and explicit
workflow-stage flags. Legacy
single-source `source` remains readable. All stages are nullable, so an incomplete Project can be
saved without inventing results. Raw files are referenced and hashed, not modified or embedded.
Opening validates SHA-256 before recomputation; a relocated source is accepted only with the same
hash.

The unified export pipeline passes the current processed Dataset and AnalysisResult to Exporter
plugins. Untitled Projects may export directly. A saved `Test_001.retldc.json` defaults to sibling
`Test_001_exports/`; repeated exports atomically replace fixed filenames. TXT and PNG exporters
extract the final selected ACTIVE_TEST curve, shift ignition to zero, and never reparse source data. Fixed
report names carry `_ZH` or `_EN` according to the separately selected output locale; `motor.eng`
remains unsuffixed and locale-neutral.

The translation service loads `zh_CN` and `en_US`, supports runtime switching, persists selection,
accepts plugin bundles, and falls back requested locale → `en_US` → caller default/key.

## Application entry points

The recommended development/user entry point is the repository-root `main.py`:

```powershell
python .\main.py
```

It detects whether the current interpreter belongs to the repository `.venv`. If necessary, it
relaunches itself with `.venv\Scripts\python.exe`, then adds the `src` directory to the import path.
This makes VS Code's ordinary “Run Python File” action safe without activating a shell environment.

Installed/package execution remains supported through:

```powershell
.\.venv\Scripts\python.exe -m underline_retldc
```

Direct execution of `src/underline_retldc/__main__.py` is retained for editor compatibility and
forwards to the root launcher. Business startup remains in `app/application.py`; launchers contain
environment/bootstrap logic only.

## Windows folder package

Root `打包_文件夹版.bat` builds a PyInstaller `onedir` distribution named
`dist/Underline_RETLDC_0_1_0/`. Its GUI executable is `Underline_RETLDC_0_1_0.exe`; frozen startup
uses the executable's parent as the project/portable root and bypasses the source launcher's
`.venv` bootstrap. Python/Qt dependencies remain in `_internal/`, while the recursively discovered
official `plugins/` tree stays beside the executable as ordinary files. Built-in translation JSON
is collected at its package-relative path. README, plugin-authoring prompts, docs, and examples are
copied into the distribution.

The entire distribution directory is the release unit: moving only the EXE is unsupported. The
build script installs PyInstaller into the project `.venv` only when missing, replaces the same
versioned build output, and smoke-starts the packaged executable once per theme before reporting
success. A smoke run also fails when no bundled plugins are found or any bundled plugin cannot be
loaded. The script never packages source test data, rewrites raw logs, or modifies the user plugin
root.
