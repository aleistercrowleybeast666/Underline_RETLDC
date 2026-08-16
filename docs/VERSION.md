# Version

```text
Project: Underline_RETLDC
Name: Underline
Product: Underline_RETLDC
Full Name: Underline Rocket Engine Test Log Decode and Compute
Current Version: 0.0.2
Plugin API: 1
```

The directory name is never versioned. Application versions, Git tags, and schema versions are
independent identifiers.

Version `0.0.2` is an early-development iteration. The `0.0.x` line is used while the platform and
workflow are still being established; the first formal release may advance to `0.1.0` according
to the release policy. Application version numbers never alter Project, Calibration, Analysis,
or Plugin API schema generations.

Version `0.0.2` uses the five-workspace Project/Thrust/Chamber Pressure/Temperature/Data
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
