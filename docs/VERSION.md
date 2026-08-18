# Version

```text
Project: Underline_RETLDC
Name: Underline
Product: Underline_RETLDC
Full Name: Underline Rocket Engine Test Log Decode and Compute
Current Version: 0.0.3
Plugin API: 1
```

The directory name is never versioned. Application versions, Git tags, and schema versions are
independent identifiers.

Version `0.0.3` is an early-development iteration. The `0.0.x` line is used while the platform and
workflow are still being established; the first formal release may advance to `0.1.0` according
to the release policy. Application version numbers never alter Project, Calibration, Analysis,
or Plugin API schema generations.

Version `0.0.3` uses the five-workspace Project/Thrust/Chamber Pressure/Temperature/Data
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

Application version `0.0.3` does not change Plugin API `1`, Project schema
`underline-retldc-project/2`, Calibration schema `underline-retldc-calibration/1`, or Analysis JSON
schema `underline-retldc-analysis/1`.

When the Windows portable release is produced, the release archive name is
`Underline_RETLDC_0_0_3_Windows_Portable.zip`; it contains the stable `Underline_RETLDC/` folder
and `Underline_RETLDC.exe`. The archive/version naming does not rename the repository directory or
the executable inside the portable folder.
