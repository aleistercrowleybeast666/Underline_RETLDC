# 0.1.0 development validation

Validated on the local Windows checkout for the 2026-10-15 release target. This records source
development validation, not a published release or portable package validation.

## Baseline and scope

- Initial branch: main; HEAD `3c4e436cc0072c0a3f33c068d3a9bb6df1a43fa7`; worktree clean.
- Development branch: `feature/v0.1.0-theory-overlays`.
- Reused `.venv`; no additional environment, worktree, package build, push, tag, or publication.
- No changes to SilverStar, STM32 projects, source logs, Plugin API generation, or scientific
  processing/export formulas.
- Read AGENTS.md, TARGETS.md, test setup and relevant architecture, persistence, analysis, i18n,
  Plugin API and GUI specifications. No repository `.agents/skills` directory was present.

## Passed

- Initial full `.venv\Scripts\python.exe -m pytest -q`: **209 passed**, 131.25 seconds.
- Delivery review full run (`pytest -vv`): **217 passed**, 194.40 seconds. After the last
  theory-only pressure-reference unit fix, its new test and two affected shared plot/segmentation
  tests passed separately.
- Final frozen-code verification on `282a2cbca8540f85c8cc24145d399d270f44bd29`:
  **218 passed**, 203.40 seconds; **0 failures**. The complete suite includes the last pressure
  display fix. Ruff also passed. Code remained unchanged throughout this run; the following
  commit updates validation documents only. See Delivery_Review_0_1_0.md for scope.
- `.venv\Scripts\python.exe -m ruff check .`: **All checks passed**.
- `git diff --check`: passed.
- GUI startup with the project venv: `-m underline_retldc --smoke-test`, English/Light and
  Chinese/Dark; both exit codes 0, bundled plugin loading and version/default checks passed.
- Rendered and inspected Project source markers and Thrust, Chamber Pressure, Temperature and
  Data Explorer overlays across zh_CN/en_US, Light/Dark, 980x640/1280x820. Source markers, dashed
  theory legends, distinct curve colors, gap breaks and scrollable controls were visible.
  Offscreen rendering loaded existing Windows YaHei/Segoe UI fonts for readable screenshots.

New regressions in `tests/unit/test_theoretical_sources.py` and
`tests/integration/test_theory_overlay.py` cover shared parser import for both origins, equal local
Channel IDs, theory-only import, theory-before-experiment import, preserved source alignment and
IDs, all four plot families (including auxiliary length), N/kN, Pa/MPa and K/°C display conversion,
engineering/SI display, signed shifts, source-start zeroing, reset, hidden curves, save/reopen,
parsed/unparsed legacy defaults, theory source deletion, failed-import rollback, immutable raw
values/file bytes, experiment binding/segmentation/result/export preservation, empty/NaN data,
invalid/nonfinite shifts, incompatible quantities/units, and Qt binding rebuild safety.

## Earlier failures and environment notes

The first full run had 203 passes and 4 ZIP-installer failures because the sandbox-selected system
temporary path rejected access. Repointing TEMP/TMP to the explicitly writable task scratch root
resolved these without changing plugin installation code or escalating filesystem access.
An expanded legacy fixture initially removed its explicit bindings while creating two ambiguous
experimental thrust sources; its incorrect non-null expectation was corrected. The same review
found and fixed intermediate Qt selection signals reading stale temperature references.
Final full-suite failures: **0**.

The existing venv emits a Python 3.14 base-location warning before commands, but commands execute
and verification exits successfully. Initial offscreen screenshots lacked fonts; readable visual
checks were repeated with existing Windows fonts. Neither condition remains a feature blocker.

## Reproduction and retained evidence

In PowerShell, point TEMP/TMP to one writable task directory before tests. In this session:

```powershell
$env:TEMP = 'C:\Users\chdxm\AppData\Local\Temp\retldc-v010'
$env:TMP = $env:TEMP
.venv\Scripts\python.exe -m pytest -q -o "cache_dir=$env:TEMP\cache" --basetemp="$env:TEMP\full"
.venv\Scripts\python.exe -m ruff check .
```

Checked-in regression tests and this report are the durable evidence. The small task scratch root
retains only compact test/GUI summaries, a real-pipeline GUI inspection script, and two representative
PNG screenshots (Project source markers and Chamber Pressure overlay). Generated fixture trees,
test caches and editing scripts are cleaned after validation. Existing user files and unrelated
task directories are outside cleanup scope.

## Not run

- PyInstaller build, portable ZIP extraction/executable checks, full `--release-smoke` packaging
  workflow, GitHub push/tag/Release, and external publication: deliberately deferred as requested.
- User review against their own experimental/theoretical files: pending the release acceptance
  step; automated imports use small reproducible local fixtures.

No remaining blocker for the implemented source feature. Portable packaging and its separate
verification remain necessary before an actual release.

The post-review GUI script leaves automatic table preview enabled and runs real parser,
compensation and analysis plugins. Only file-picker paths and error-dialog collection are
scripted. It covers real import through theory removal/save/reopen and is distinct from startup
smoke or the earlier generated-model layout screenshots. Detailed review and a short morning
acceptance path are in Delivery_Review_0_1_0.md.
