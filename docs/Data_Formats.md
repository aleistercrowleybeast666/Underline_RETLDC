# Data Formats

## TR_F v1

TR_F means Time / Raw Force. It is syntax only and contains no calibration coefficient.

```text
column 0: timestamp
column 1: raw force-sensor value
delimiter: comma by default (configurable by the Parser)
header: none
source timestamp unit: s by default; configurable as s, ms, or us
Dataset timestamp unit: s (configured source values are normalized explicitly)
raw unit: raw (undefined engineering scale)
```

Each nonblank row must contain exactly two finite decimal numbers. UTF-8/ASCII text and ordinary
line endings are accepted. Blank rows are ignored. Malformed or extra-column rows are retained as
line-numbered diagnostics and skipped; a file with no valid records fails parsing. Original row
order and timestamps are preserved, including duplicates/backward values, which generate quality
diagnostics. The Parser never assumes a fixed sample rate or a raw-to-newton coefficient.

Probe reads only a bounded prefix and scores two-column numeric syntax, comma use, sufficient valid
records, and approximate timestamp monotonicity. The user may override its recommendation.

## Calibration JSON

Calibration JSON is defined in [Calibration.md](Calibration.md).

## Project JSON

Schema ID remains `underline-retldc-project/1`. Writers emit `schema`, `software_version`,
`source`, `parser`, `calibration`, `processors`, `regions`, `analyzer`, `motor_metadata`,
`export_settings`, `workflow_state`, `locale`, and `diagnostics`.

`source`, `parser`, `calibration`, and `analyzer` may be `null`; `processors` and `regions` may be
empty. This represents a valid incomplete Project, not corrupt data. `workflow_state` explicitly
records the `parsed`, `calibrated`, `processed`, and `analyzed` booleans so reopening does not
advance past the saved stage. Readers infer legacy stage state only when that field is absent.

When present, `source` records a path and SHA-256 hash. Every plugin reference records `id`,
`version`, `api_version`, and `config`. Regions record PRE, BURN, and POST as two-element time
arrays. Source data is referenced, not embedded or modified. A missing path can be replaced by a
user-selected path only when SHA-256 matches. Unknown extra keys are accepted where practical;
unsupported schema IDs are rejected rather than guessed.

`export_settings` stores a locale-neutral directory, `selected_exporter_ids`, curve confirmation,
metric-annotation preference, and `output_locale`. Older Projects may retain an
`openrocket_exporter_id` extension key; readers accept it, but current writers need only the
generic selected-ID list. Localized exporter names are never persisted.

The Export dialog is visible before analysis, but a file can be selected only after all analyzer
IDs declared by that export option are complete. Newly unlocked files are selected by default, and
the user can clear any unwanted format before export. The list shows up to ten formats and scrolls
when more are registered. Current CSV/JSON/TXT/PNG/ENG choices all require
`builtin.analyzer.thrust`; future analysis families may declare different dependency sets.

## Export artifacts

The unified dialog owns language-qualified fixed names. The selected report language determines
the suffix, independently of the current GUI language:

```text
processed_thrust_ZH.csv / processed_thrust_EN.csv
analysis_data_ZH.json / analysis_data_EN.json
analysis_summary_ZH.txt / analysis_summary_EN.txt
thrust_curve_ZH.png / thrust_curve_EN.png
motor.eng
```

ENG remains locale-neutral and receives no language suffix. Existing files are atomically
replaced. CSV headers, JSON display metadata, TXT labels, and all PNG text use the selected Chinese
or English output language; stable IDs and machine-readable schema keys remain unchanged. TXT is
UTF-8 and contains provenance, metrics, diagnostics, and a final test-interval time/thrust table.
PNG is 1600×1000 and displays only the selected final processed test curve. TXT, PNG, and ENG shift
ignition to `t = 0`; export-only endpoint interpolation may add ignition/burnout points and is
disclosed in ExportResult metadata and TXT.
