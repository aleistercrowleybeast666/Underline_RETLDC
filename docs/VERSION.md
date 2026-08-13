# Version

```text
Project: Underline_RETLDC
Name: Underline
Product: Underline RETLDC
Full Name: Underline Rocket Engine Test Log Decode and Compute
Current Version: 0.1.0
Plugin API: 1
```

The directory name is never versioned. Application versions, Git tags, and schema versions are
independent identifiers.

Version `0.1.0` currently uses the two-workspace Project/Thrust Analysis desktop workflow with
stable workspace and export-analysis dependency IDs, Plugin API v1, Project schema
`underline-retldc-project/1` with backward-compatible nullable stages, Calibration schema
`underline-retldc-calibration/1`, and Analysis JSON schema `underline-retldc-analysis/1`.

All official concrete plugins are recursively discovered from repository-root `plugins/` through
the same manifest/Loader/Registry path as user plugins; their existing `builtin.*` IDs remain
unchanged. The desktop theme IDs are `light` and `dark` and are persisted as UI preference under
QSettings `ui/theme` without changing any science or Project schema version.
