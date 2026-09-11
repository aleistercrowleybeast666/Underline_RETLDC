# Version

```text
Project: Underline_RETLDC
Name: Underline
Product: Underline RETLDC
Full Name: Underline Rocket Engine Test Log Decode and Compute
Current Version: 0.0.4
Plugin API: 1
```

The directory name is never versioned. Application versions, Git tags, and schema versions are
independent identifiers.

Version `0.0.4` is an early-development iteration. 0.0.x 为早期开发阶段的正式发布版本，未来达到稳定里程碑后升级至 0.1.0 Application version numbers never alter Project, Calibration, Analysis,
or Plugin API schema generations.

Version `0.0.4` uses the five-workspace Project/Thrust/Chamber Pressure/Temperature/Data
Explorer desktop workflow with stable workspace and export-analysis dependency IDs, centralized
Quantity/Data Unit/Display Unit handling, multi-Source Stream offsets, Plugin API v1, Project schema
`underline-retldc-project/2` (with `/1` migration) and backward-compatible nullable stages,
Calibration schema
`underline-retldc-calibration/1`, and Analysis JSON schema `underline-retldc-analysis/1`.

The localized Header workspace title is distinct from the stable English window product title.
Thrust polarity is stored independently from the optional correction Processor, and shared
analysis side panels cannot be collapsed to zero width.

All official concrete plugins are recursively discovered from repository-root `plugins/` through
the same manifest/Loader/Registry path as user plugins; their existing `builtin.*` IDs remain
unchanged. The desktop theme IDs are `light` and `dark` and are persisted as UI preference under
QSettings `ui/theme` without changing any science or Project schema version.

## 0.0.4 changes

- High-confidence compatible presets now apply their validated config automatically to new
  tabular imports; saved Projects keep independent effective mappings.
- New Projects default to Thrust Correction=None; existing explicit choices remain reproducible.
- User-visible product name is Underline RETLDC and the window title includes version 0.0.4.
  README now follows workspace navigation and documents the optional correction.
- All three analysis result panes use matching calculation buttons, spacing, and diagnostics;
  temperature curve toggles stay in Display and pressure has no redundant unit-only label.
- Pressure averages now weight actual sample times, consistent with the existing thrust average;
  nonuniform sampling no longer uses an arithmetic mean. Peak values are unchanged.
- Release builds stop before PyInstaller if pytest or Ruff fails. Packaged smoke checks also
  verify product name, version, and the default no-correction selection.

- Ordinary CSV, TSV, and XLSX files now use a deterministic local detector for structure, header,
  data start, time, units, and conservative measurement-category suggestions, then parse
  automatically when no blocking ambiguity remains.
- Advanced table mapping stays complete but collapsed by default and opens automatically after
  failed detection. Unknown numeric, Kn, Ab, and burned-web columns default to preserved Other
  Channels rather than being guessed as Temperature.
- Thrust plots and formal thrust PNG exports preserve a visible 0 N tick and reference line for
  positive-only and negative-only records.
- Chamber Pressure adds an editable, Project-persisted display reference stored in Pa and
  defaulting to one standard atmosphere. The enabled overlay is included in its cropped PNG but
  never changes measurement or analysis data.
- Thrust, Chamber Pressure, and Temperature controls now share the Primary Channels, Display, and
  Test Interval ordering, with corrected compact-width pressure controls.

## 0.0.3 changes

- Fixed the external-plugin security confirmation so a real Qt button click reliably enters the
  Discovery task; the confirmation uses StandardButton value equality, localized Install/Cancel
  labels, immediate global progress feedback, and logged/user-visible startup errors.
- Fixed interactive installation diagnostics so failures report source, stage, Plugin ID/type,
  calculated destination, existing-copy paths, and the underlying reason.
- Folder and ZIP packages are scanned recursively without an artificial wrapper-depth limit.
- One source may contain multiple Parser, Calibration, Processor, Analyzer, and Exporter plugins;
  each resolved plugin root is classified from `plugin.json` and installed independently.
- A manifest directory that contains a descendant manifest is treated as a nested container; only
  deepest valid plugin roots are installable by default.
- New plugins prefer the matching category in the writable Application Plugin Root and fall back
  per plugin to the matching User Plugin Root category only for access-related failures.
- Existing Plugin IDs are replaced atomically at their current location, preventing a second copy
  from being created in the other root.
- Package scanning, copying, Registry refresh, and load verification reuse the main-window global
  TaskManager and status-bar progress UI. Copy completion alone is no longer reported as success;
  the installed record must finish with `PluginLoadResult.LOADED`.
- ZIP traversal, absolute/drive paths, links, encrypted entries, duplicate paths, special entries,
  the 4096-entry limit, and the 512 MiB expanded-size limit remain enforced.

Application version `0.0.4` does not change Plugin API `1`, Project schema
`underline-retldc-project/2`, Calibration schema `underline-retldc-calibration/1`, or Analysis JSON
schema `underline-retldc-analysis/1`.

When the Windows portable release is produced, the release archive name is
`Underline_RETLDC_0_0_4_Windows_Portable.zip`; it contains the stable `Underline_RETLDC/` folder
and `Underline_RETLDC.exe`. The archive/version naming does not rename the repository directory or
the executable inside the portable folder.
