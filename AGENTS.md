# AGENTS.md — Underline_RETLDC Development Rules

## Scope and authority

This file governs all changes in the `Underline_RETLDC` repository. Read this file,
`TARGETS.md`, and the relevant `docs/*.md` specifications before changing an API,
file format, scientific algorithm, persistence schema, plugin loader, or i18n behavior.

## Architecture boundaries

- `core/` owns generic data, diagnostics, project persistence, task state, and registries.
- `plugin_api/` owns stable Plugin API v1 contracts and may depend only on `core/`.
- The application/repository `plugins/` root contains every official bundled Parser, Calibration,
  Processor, Analyzer, and Exporter implementation. Third-party plugins may be installed in that
  root when it is writable or in the platform user plugin root as a permission fallback.
- `src/underline_retldc/plugins/` owns manifest, recursive discovery, installation, and failure
  isolation infrastructure; it contains no concrete scientific plugin implementation.
- `gui/` is presentation and orchestration only; scientific formulas must not be copied there.
- `i18n/` owns translation resources and locale fallback. Business logic uses stable IDs.

Dependencies point inward: GUI and plugins may use Core; Core never imports GUI, TR_F, or
plugin implementations.

Do not add a new concrete Parser, Calibration, Processor, Analyzer, or Exporter under Core or a
source-package `builtin/` tree. Add it under repository-root `plugins/<category>/`. Official and
third-party plugins use the same Plugin API, manifest, Loader, Registry, schemas, and i18n path.
Core changes are reserved for generic data models, APIs, infrastructure, or reusable GUI
capability. Never add a MainWindow or workspace branch keyed to one concrete `plugin_id` merely
to expose a plugin; extend a general schema/role/registry capability instead.

## Data preservation

- Source files are opened read-only and are never rewritten.
- Parsed raw arrays are copied and marked read-only.
- Calibration, baseline, correction, processing, and analysis create new channels/results.
- Never overwrite a raw channel or silently clip, resample, reorder, or delete measurements.
- Recalculation must always be possible from parsed raw values and saved configuration.
- Source/Stream/Channel is the persistent measurement hierarchy. Streams retain their own local
  timestamps and use `t_project = t_local + time_offset_s`; sharing a Project segment never
  requires resampling or rewriting a source array.

## Generic tabular ingestion

- Ordinary two-dimensional CSV, TSV, delimited text, and XLSX formats use the Generic Tabular
  Parsers plus an explicit Mapping Preset. Do not create a new Parser merely because columns,
  headers, units, or leading description rows differ.
- Concrete laboratory header strings must never become a Core or Parser format contract. Header
  recognition is permitted only for an editable Auto Mapping suggestion; `parse()` executes the
  saved column-index mapping.
- Generic Delimited and Generic XLSX share the platform Tabular Mapping Engine and
  `TabularMappingEditor`. GUI orchestration must discover that capability through API/schema
  metadata, never a branch on a concrete plugin ID.
- A Tabular mapping must explicitly choose a time column, sample rate, or sample period. Never
  invent a silent 1 Hz fallback. Preserve real timestamps when present.
- Tabular Presets are pure JSON, execute no code, and are index-based. Expected-header hints may
  warn but never replace the saved index contract. A Project stores its own copy of each Source's
  final mapping.

## Unit and Calibration invariants

- Unit and Calibration are independent. Never infer Calibration state from the presence, absence,
  or spelling of a Unit.
- Every newly parsed Channel receives `builtin.calibration.identity` by factory default, including
  Channels declared as `raw`, `count`, or `ADC`. Identity means “no additional transform”; it is
  not certification that a sensor was physically calibrated.
- A Parser that knows a Channel's Unit must declare it. For a known Quantity with no declared
  Unit, Core assigns the canonical SI Data Unit and records `unit_source=default_si`; an unknown
  Quantity remains explicitly unknown and produces a Diagnostic.
- Data Unit and Display Unit are separate. A Data Unit override reinterprets unchanged source
  numbers and is scientific Project state. A Display Unit is a view preference and converts only
  the displayed values.
- Unit conversion and Calibration are separate layers. Unit conversion is between compatible
  units of one dimension; Calibration may transform `raw/count/ADC/V` into an engineering
  quantity and must define its output Quantity and Unit behavior.
- Never implement conversion by renaming a Unit string. Never mutate raw values while changing a
  display preference, and never offer direct physical conversion from `raw`, `count`, or `ADC`.
- Physical analyzers and exporters validate both Quantity and Unit. Identity does not turn `raw`
  force into newtons or make SI impulse, Isp, or ENG scientifically available.

## Plugin API stability

- Plugin API generation `1` is documented in `docs/Plugin_API.md`.
- Persistent data stores stable plugin ID, plugin version, and API version, never a localized name.
- Changes that break a v1 signature require a new API generation and migration documentation.
- A malformed, incompatible, duplicate, or failing optional plugin must not prevent startup.
- External Python plugins contain executable code, are not sandboxed, and must be installed only
  from trusted sources.
- Plugin folder categories are organizational only; `plugin_type` in the manifest is authoritative.
- Both physical roots use the same Plugin API, Loader, manifest format, Registry, schemas, and
  i18n path. Discovery is recursive, skips symlinks and environment/cache directories, and records
  Loader-determined `Bundled`/`Application`/`User` provenance without granting trust.
- Interactive installation prefers the application plugin root when it is writable and falls back
  to the user plugin root only when the application root cannot be written. It never requires
  administrator privileges for normal installation and never infers writability from a drive
  letter. A preflight write probe does not replace handling an access error from the actual copy.
- Plugin installation derives type and destination category from `plugin.json`, never from source
  folder placement, folder name, or ZIP name.
- Folder and ZIP packages may contain arbitrary wrapper depth and multiple plugins. The Installer
  recursively resolves each manifest directory, copies the deepest Plugin Roots rather than their
  wrapper package directories, and rejects duplicate IDs within one source.
- New plugins prefer the matching category under the writable Application Plugin Root. The User
  Plugin Root is a per-plugin permission fallback, not a fallback for manifest, API, conflict, ZIP,
  entry, or other ordinary errors. Existing IDs are replaced at their current physical location.
- Interactive installation uses the shared TaskManager and global status/progress UI. Installation
  success means the installed PluginRecord is discoverable with result `LOADED`, not merely copied.
- ZIP extraction rejects traversal, absolute/drive paths, links, encryption, special entries, and
  configured entry/expanded-size excess. Replacement is staged and committed as a complete
  directory so old file remnants are not mixed with the new plugin.

## Coding conventions

- Python requires type hints, explicit exceptions, UTF-8, and a 100-column soft limit.
- Compare Qt dialog and standard-button return values by value (`==` / `!=`), never by Python
  object identity (`is` / `is not`).
- Plugin contract names (`probe`, `parse`, `evaluate`, `process`, `analyze`, `export`) remain
  exactly as documented. Project-level free functions otherwise prefer a subsystem/verb-object
  form such as `Project_Save` or `Burn_DetectCandidates` when it improves clarity.
- Type names use PascalCase. An enum that reports success/failure to an upper layer ends in
  `Result`, for example `PluginLoadResult`.
- Avoid globals. Module constants are immutable; process state is held by instances. If a future
  C/C++ module genuinely needs file-local state, use `static` and expose it through an interface.
- A future C/C++ header guard is `__` plus the uppercase filename with `.` replaced by `_`, for
  example `__DEBUG_LOG_H`.
- Never use a bare `except`, suppress an unexplained exception, or infer scientific units.

## Scientific rules

- Calibration and baseline compensation are distinct stages.
- Use actual timestamps and trapezoidal integration.
- `g0` is exactly `9.80665 m/s²`.
- Specific impulse uses propellant mass only. Unknown propellant mass means unavailable Isp.
- Automatic test-interval detection is advisory. Users retain final interval control.
- Equivalent baseline-derived mass change is not claimed as exact propellant consumption.

## Desktop workflow invariants

- Primary navigation contains stable-ID `Project`, `Thrust`, `Chamber Pressure`,
  `Temperature`, and `Data Explorer` workspaces. They share Project Time and Test Segmentation.
  Export, plugin management, and settings are dialogs or menu/toolbar actions, not primary
  workflow pages.
- Ordinary tabular import exposes capability categories such as `Time`, `Thrust`,
  `Chamber Pressure`, `Temperature`, and `Other`; it must not require ordinary users to edit raw
  Quantity, Semantic Role, or Channel ID values. Those fields remain available only in the
  collapsed Advanced Mapping editor.
- Workspace input is resolved through explicit Project `PrimaryChannelBindings` containing full
  Source/Stream/Channel references. A Channel `semantic_role` is an auto-binding hint, never the
  final workflow input, and downstream code must not assume concrete names such as
  `force_calibrated`.
- Workspace categories come from the generic Workspace Capability Registry. Adding a supported
  measurement family extends the registry and generic views rather than adding localized-name or
  concrete-plugin branches to the tabular editor.
- Thrust, Chamber Pressure, and Temperature use the shared analysis shell, plot behavior, test
  markers, empty state, theme handling, and result-panel layout. Measurement-specific formulas
  remain outside GUI code.
- Project Test Segmentation is the single source of truth for PRE/ACTIVE_TEST/POST. Never keep a
  separate final interval per Workspace. Thrust and Chamber Pressure both edit the same Project
  interval; Temperature reads it. The Thrust page detects from its explicitly bound Primary Thrust,
  while the Chamber Pressure page detects from its explicitly bound Primary Chamber Pressure;
  generic orchestration may fall back from pressure to thrust. A pressure reference always uses
  positive activity polarity and never inherits the thrust installation sign.
- Compatible two-column raw-log Parsers share the Plugin API helper for bounded probing,
  timestamp normalization, malformed-row diagnostics, and immutable Dataset construction. TR_F,
  TR_P, and TR_T differ only in declared measurement semantics and localized presentation.
- Ambiguous Parser recommendations must be explicitly selectable with a visible exclusive radio
  group. The ordinary Parser ComboBox and radio group resolve the same selection, and TR_P/TR_T
  must work in an empty Project without a prior TR_F import. Registry/discovery order must never
  silently decide among TR_F, TR_P, and TR_T.
- Parser and Calibration configuration widgets are generated from Plugin API schemas. GUI logic
  must not branch on localized names or reimplement a built-in plugin's parameter model.
- A Project may be saved at any workflow stage. Project JSON records explicit parsed, calibrated,
  processed, and analyzed state; reopening must not silently advance beyond the saved stage.
- A referenced source is verified by SHA-256. A relocated source is accepted only after the same
  check; a mismatch never enters the active analysis session.
- Export is allowed without saving a Project. Unified exports use language-qualified fixed
  filenames (`_ZH`/`_EN`, except locale-neutral ENG) and replace the same files on repeat export;
  they never invent numbered or `_final` copies.
- Export Output Language defaults to stable `follow_ui`, followed by explicit `zh_CN` and `en_US`.
  Follow mode resolves the current UI locale at export time. Export content scrolls vertically when
  constrained, while the bottom Cancel/Export action row remains outside the scroll viewport.
- Plot axis labels and tick formatting must use the resolved Display Unit and must not rely on
  pyqtgraph automatic SI prefixes. Unit Display Mode is a persisted UI preference: `engineering`
  uses configured engineering Display Units and `si_scientific` converts display values to
  canonical SI with scientific notation. Neither mode changes raw values, Data Units, Calibration,
  or formal export units.
- The Export dialog is always inspectable. Each export option declares stable data capability IDs
  and optional analysis IDs that must be complete before it becomes selectable. Options are
  grouped and sorted by generic metadata, with unknown third-party groups placed last.
- Default export selection depends on the option's actual capability and `default_selected`
  metadata. A default is applied only the first time that option becomes available; a user's
  unchecked choice is not silently restored by later availability refreshes or Project reopen.
  Persist selected IDs separately from initialized-default IDs. Unavailable formats stay disabled
  and unchecked. The list displays at most ten option rows before vertical scrolling, and every
  checkbox retains a visible square indicator in every state.
- Chamber-pressure PNG requires ACTIVE_TEST and clips both its plotted samples and X-axis range to
  that interval; it must not merely shade ACTIVE_TEST over the full PRE/POST record.
- Formal curve exports use the selected final processed channel and ACTIVE_TEST interval with
  ignition as time zero. Legacy persisted `burn` remains a read-compatible alias. Any export-only
  endpoint interpolation must be disclosed in result metadata and docs.
- Removing a parsed Source immediately removes its Streams, calibrated state, Primary bindings,
  and workspace series, then invalidates candidates, segmentation references, processing,
  analysis, cached statistics, and export availability. Removing a pending
  unparsed Source must not invalidate unrelated parsed Project data.
- Theme IDs are `light` and `dark`, selected at runtime and persisted under QSettings `ui/theme`.
  Theme is a UI preference, never Project scientific state. Formal exports must not depend on it.
- Header theme selection uses a ComboBox with stable `light`/`dark` item data and the same
  SettingsService value as the Settings ComboBox; the two views must remain synchronized.
- The stable English window product title and the localized workspace/header title are separate
  presentation concepts and must not be derived from one another.
- Critical left, plot, and right panels in `AnalysisWorkspaceShell` must not be collapsible to
  zero width; constrained side-panel content scrolls instead.
- Applicable PySide6 presentation work follows `docs/CXYL_Python_GUI_STYLE_GUIDE.md`; explicit
  product/workflow rules in this file take precedence where the generic guide differs.
- The Project workspace is responsive: constrained widths stack Import and Project Setup
  vertically, ordinary-width windows place them side by side, and neither pane may collapse or
  require horizontal scrolling for its normal form controls.
- Thrust polarity is a Project Thrust Workflow setting, not a compensation Processor parameter.
  It is applied after Calibration and before optional correction, and `None` correction must still
  create a polarity-correct `thrust_processed` Channel.
- The motor-weight selector lists only Processor plugins whose `requirements()` declares
  `processor_role = motor_weight_compensation`; its remaining form fields come from schema
  metadata rather than plugin-ID branches. `None` means a real pass-through processing stage.

## Verification and documentation

- Update implementation, tests, and the matching document together.
- Put project Markdown only in the root `AGENTS.md`/`TARGETS.md` or under `docs/`.
- Run `.venv\Scripts\python.exe -m pytest` and `.venv\Scripts\python.exe -m ruff check .`.
- Smoke-start the GUI with the project venv before completing a release task.
- Review every changed file for data loss, API compatibility, unsafe plugin behavior, unit errors,
  stale persistence fields, and GUI-main-thread blocking.
