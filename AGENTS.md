# AGENTS.md — Underline_RETLDC Development Rules

## Scope and authority

This file governs all changes in the `Underline_RETLDC` repository. Read this file,
`TARGETS.md`, and the relevant `docs/*.md` specifications before changing an API,
file format, scientific algorithm, persistence schema, plugin loader, or i18n behavior.

## Architecture boundaries

- `core/` owns generic data, diagnostics, project persistence, task state, and registries.
- `plugin_api/` owns stable Plugin API v1 contracts and may depend only on `core/`.
- Repository-root `plugins/` contains every concrete Parser, Calibration, Processor, Analyzer,
  and Exporter implementation, including the official plugins shipped with the application.
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

## Plugin API stability

- Plugin API generation `1` is documented in `docs/Plugin_API.md`.
- Persistent data stores stable plugin ID, plugin version, and API version, never a localized name.
- Changes that break a v1 signature require a new API generation and migration documentation.
- A malformed, incompatible, duplicate, or failing optional plugin must not prevent startup.
- External plugins are trusted executable Python code, not sandboxed code.
- Plugin folder categories are organizational only; `plugin_type` in the manifest is authoritative.
- Discovery is recursive across the bundled/project root and writable user root, skips symlinks
  and environment/cache directories, and records Loader-determined `Bundled`/`User` provenance.

## Coding conventions

- Python requires type hints, explicit exceptions, UTF-8, and a 100-column soft limit.
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
- Automatic burn detection is advisory. Users retain final interval control.
- Equivalent baseline-derived mass change is not claimed as exact propellant consumption.

## Desktop workflow invariants

- The primary navigation currently contains `Project` and the explicitly typed `Thrust Analysis`
  workspace. Future measurement analyses are added as separate stable-ID workspaces. Export,
  plugin management, and settings are dialogs or menu/toolbar actions, not primary workflow pages.
- Parser and Calibration configuration widgets are generated from Plugin API schemas. GUI logic
  must not branch on localized names or reimplement a built-in plugin's parameter model.
- A Project may be saved at any workflow stage. Project JSON records explicit parsed, calibrated,
  processed, and analyzed state; reopening must not silently advance beyond the saved stage.
- A referenced source is verified by SHA-256. A relocated source is accepted only after the same
  check; a mismatch never enters the active analysis session.
- Export is allowed without saving a Project. Unified exports use language-qualified fixed
  filenames (`_ZH`/`_EN`, except locale-neutral ENG) and replace the same files on repeat export;
  they never invent numbered or `_final` copies.
- The Export dialog is always inspectable. Each export option declares stable analysis IDs that
  must be complete before the option becomes selectable; adding a new analysis/export pair must
  extend this dependency mapping rather than hard-code a localized page name.
- Newly available export options are selected by default. The export-format list displays at most
  ten rows before vertical scrolling, and every checkbox must retain a visible square indicator in
  unchecked, checked, and disabled states.
- Formal curve exports use the selected final processed channel and BURN interval with ignition as
  time zero. Any export-only endpoint interpolation must be disclosed in result metadata and docs.
- Theme IDs are `light` and `dark`, selected at runtime and persisted under QSettings `ui/theme`.
  Theme is a UI preference, never Project scientific state. Formal exports must not depend on it.
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
