# Data Formats

## TR_F / TR_P / TR_T v1

The TR family is a shared two-column raw-log syntax. The selected Parser declares what the second
column means; the file itself contains no calibration coefficient:

```text
TR_F: Time / Raw Force            → quantity=force, semantic_role=thrust
TR_P: Time / Raw Pressure         → quantity=pressure, semantic_role=chamber_pressure
TR_T: Time / Raw Temperature      → quantity=temperature, semantic_role=temperature
```

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

Each Parser declares `unit=raw`. The platform still assigns factory-default Identity Calibration
so values can be viewed and segmented. Physical results remain unavailable until a Calibration
produces a compatible engineering Unit. For TR_F specifically, SI thrust, impulse, Isp, and ENG
remain unavailable until the output uses a convertible force Unit.

The three formats have identical numeric syntax and therefore receive similar probe scores. Parser
recommendation selects automatically only when the best score reaches the configured threshold
and exceeds the runner-up by the configured ambiguity margin. Otherwise the Project page displays
all close candidates and requires the operator to confirm whether the source is force, pressure,
or temperature data.

## Generic Tabular files

`builtin.parser.generic_delimited` reads CSV, TSV, pipe/space-separated, and custom one-character
delimited text. `builtin.parser.generic_xlsx` reads one selected worksheet from an ordinary OOXML
`.xlsx` workbook. Both open sources read-only and pass a cell matrix to one shared Tabular Mapping
Engine. The parse contract is the explicit configuration, never a header vocabulary:

```json
{
  "header_row": 1,
  "data_start_row": 2,
  "data_end_row": null,
  "time": {"mode": "column", "column": 0, "unit": "s"},
  "columns": [
    {"column": 0, "usage": "time", "expected_header": "Time"},
    {
      "column": 1,
      "usage": "data",
      "channel_id": "pc",
      "quantity": "pressure",
      "role": "chamber_pressure",
      "unit": "MPa",
      "expected_header": "Pc"
    }
  ],
  "invalid_row_policy": "preserve"
}
```

Rows are one-based and columns are zero-based. `header_row` may be null. Time mode is `column`,
`sample_rate`, or `sample_period`; no mode is a blocking error. A real time column is converted to
seconds and retained without uniform resampling. A mapped time column is excluded from Channels.
Missing/non-numeric measurement cells become NaN in `preserve` mode so all Channels retain row
alignment, or block in `error` mode. Mapped columns missing from a new file are errors. Extra
populated unmapped columns and expected-header differences generate warnings.

Auto Mapping may propose the following mappings, but only to pre-fill the editable GUI. Parsing
uses the saved column-index mapping, so unknown headers such as `T0,CH_A,CH_B` remain importable
through manual configuration:

```text
Pc (MPa) → quantity=pressure, semantic_role=chamber_pressure, data_unit=MPa
F (N)    → quantity=force, semantic_role=thrust, data_unit=N
e (mm)   → quantity=length, semantic_role=burned_web, data_unit=mm
Ab (mm²) → quantity=area, semantic_role=burn_area, data_unit=mm²
Kn       → quantity=kn, data_unit=1 (canonical dimensionless SI fallback)
```

The ordinary Quick Import UI intentionally exposes a smaller, registry-driven vocabulary:

```text
Time | Thrust | Chamber Pressure | Temperature | Other
```

The first four choices resolve through Workspace Capability definitions. `Other` creates an
auxiliary Channel that is imported and persisted but excluded from automatic primary binding,
dedicated plots, segmentation, and scientific analysis. Advanced Mapping, collapsed by default,
retains direct Data Channel/Ignore/Metadata usage plus Channel ID, Quantity, Semantic Role, and
Data Unit controls. This is a presentation simplification only; both views produce the same Parser
configuration.

An explicit mapped Unit records `unit_source=plugin_declared`; a known Quantity without a Unit
records canonical SI and `unit_source=default_si`. Parsing never infers sensor Calibration.

Tabular Presets use schema `underline-retldc-tabular-preset/1`. They are pure JSON containing a
name, Parser ID/version, and the full mapping config. Column indexes control execution; expected
headers are safety hints only. Bundled portable presets may live in `presets/tabular/`; imported
user presets live in `%APPDATA%/Underline_RETLDC/presets/tabular/` on Windows. Projects store their
own copy of the final mapping in each Source Parser reference.

## Calibration JSON

Calibration JSON is defined in [Calibration.md](Calibration.md).

## Project JSON

Writers use schema ID `underline-retldc-project/2`; readers migrate
`underline-retldc-project/1`. Writers emit `schema`, `software_version`, legacy
primary `source`, `sources`, `streams`, `parser`, `calibration`, `channels`, `processors`,
`regions`, `processing_metadata`, `analyzer`, `motor_metadata`, `export_settings`,
`workflow_state`, top-level `thrust_polarity`, `locale`, and `diagnostics`.

`source`, `parser`, `calibration`, and `analyzer` may be `null`; `processors` and `regions` may be
empty. This represents a valid incomplete Project, not corrupt data. `workflow_state` explicitly
records the `parsed`, `calibrated`, `processed`, and `analyzed` booleans plus the workspace-specific
`chamber_pressure_analyzed` and `temperature_analyzed` booleans, so reopening does not advance past
the saved stage. Readers infer the legacy pipeline stage only when `workflow_state` is absent;
missing workspace-specific analysis flags default to `false`.

When present, each Source records stable ID, path, SHA-256, and Parser reference. Each Stream
records stable ID, owning Source, optional name, and `time_offset_s`; its Project Time is local time
plus that offset. The legacy `source` object identifies the primary analysis Source for compatible
readers. Every plugin reference records `id`, `version`, `api_version`, and `config`. Each Channel
state records Quantity, Data Unit, Unit Source, optional Project Display Unit override, semantic
role, Calibration plugin/version/parameters, and output Channel ID. In a multi-Stream Project it
also records `source_id` and `stream_id`, and the map key is the stable
`source_id/stream_id/channel_id` reference so equal local Channel IDs cannot overwrite one
another. Data Unit interpretation and Calibration are scientific state; a global Display Unit
preference is not.

`primary_channels` stores `thrust` and `chamber_pressure` as a nullable full
`{source_id, stream_id, channel_id}` reference and stores `temperature_channels` as an array of
those references. These explicit bindings are the final inputs to workspaces and processing;
semantic roles remain hints. Legacy Projects without this object are migrated by conservative
auto-binding and can then be saved in schema v2.

`thrust_polarity` is the Thrust Workflow's stable numeric `+1` or `-1` setting and defaults to
`+1`. It is independent of `processors`. A development-era v2 document with `sign` inside its
first Processor config is read by moving that value to `thrust_polarity` when the top-level field
is absent, then removing `sign` from the effective Processor config. This migration does not
change the `underline-retldc-project/2` schema ID.

Regions record PRE, ACTIVE_TEST, and POST in Project Time. PRE and POST may be null; legacy
`burn` input is normalized to ACTIVE_TEST. If a
Processor assumes a missing baseline is zero, `processing_metadata` records both numeric value and
`assumed_zero` source; equivalent mass change is null unless both endpoints are measured fits in a
physical force Unit. Source data is referenced, not embedded or modified. A missing path can be
replaced only when SHA-256 matches. Unknown extra keys are accepted where practical; unsupported
schema IDs are rejected rather than guessed.

`export_settings` stores a locale-neutral directory, `selected_exporter_ids`,
`selection_initialized_exporter_ids`, metric-annotation preference, and the stable `output_locale`
mode (`follow_ui`, `zh_CN`, or `en_US`). The initialized-ID list distinguishes formats whose
first-availability default has already been applied from formats that are still locked in an
incomplete Project. `follow_ui` is the default and resolves only when an export is executed. Older
Projects without the initialized-ID list remain readable. They may also retain
`curve_confirmed` or an
`openrocket_exporter_id` extension key; readers accept the legacy keys, but current writers omit
curve confirmation and need only the generic selected-ID list. Localized exporter names are never
persisted.

The Export dialog is visible before analysis, but a file can be selected only after its declared
Analyzer IDs and generic data capabilities are complete. Overall reports require
`project_summary_ready`; thrust CSV/PNG require `thrust_ready`; pressure CSV/PNG require an explicit
Chamber Pressure calculation and `chamber_pressure_ready`, while pressure PNG additionally requires
`segmentation_ready`; temperature CSV/PNG require an explicit
Temperature calculation and `temperature_ready`; ENG additionally requires `physical_force` and
`segmentation_ready`, but no separate final-curve confirmation. Changing the relevant Primary
binding or Project segmentation invalidates the affected workspace calculation. Disabled items
stay unchecked. Each metadata default is applied only the first time the option becomes available,
and a later availability refresh does not undo a user's manual uncheck. Every bundled format,
including ENG, defaults on once its own requirements are met. Group and
format ordering come from exporter metadata; absent metadata places a third-party option in Other
at the end. The list shows at most ten option rows and scrolls when more are registered.

Removing a parsed Source immediately removes its Source/Stream/Channel-backed state and Primary
bindings, then clears stale candidates, segmentation reference, processing, analysis, statistics,
and export readiness. Removing a pending unparsed entry does not alter the remaining parsed
Project. Removing the final Source also clears parser selection, schema, preview, diagnostics,
workspaces, plots, and result panels.

## Export artifacts

The unified dialog owns language-qualified fixed names. Output Language defaults to Follow UI;
users may instead pin Simplified Chinese or English independently of the current GUI language. The
resolved report language determines the suffix:

```text
thrust_data_ZH.csv / thrust_data_EN.csv
chamber_pressure_data_ZH.csv / chamber_pressure_data_EN.csv
temperature_data_ZH.csv / temperature_data_EN.csv
analysis_data_ZH.json / analysis_data_EN.json
analysis_summary_ZH.txt / analysis_summary_EN.txt
thrust_curve_ZH.png / thrust_curve_EN.png
chamber_pressure_curve_ZH.png / chamber_pressure_curve_EN.png
temperature_curve_ZH.png / temperature_curve_EN.png
motor.eng
```

ENG remains locale-neutral and receives no language suffix. Existing files are atomically
replaced. CSV headers, JSON display metadata, TXT labels, and all PNG text use the selected Chinese
or English output language; stable IDs and machine-readable schema keys remain unchanged. TXT is
UTF-8 and contains provenance, metrics, diagnostics, and a final test-interval time/thrust table.
Thrust PNG is 1600×1000 and displays only the selected final processed test curve. Chamber-pressure
PNG likewise clips its data and X axis to ACTIVE_TEST; it does not include PRE/POST samples around a
highlighted band. Pressure and temperature outputs query stable Quantity/Semantic Role and are
omitted when no matching Channel exists. The single TXT summary also records chamber-pressure and
per-temperature-channel metrics
when those measurements exist. TXT, thrust PNG, and ENG shift
ignition to `t = 0`; export-only endpoint interpolation may add ignition/burnout points and is
disclosed in ExportResult metadata and TXT.
