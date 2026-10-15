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

On first import, the local deterministic `TabularAutoDetector` examines a bounded preview. It
scores stable numeric regions, nearby header candidates, monotonic/continuous time candidates,
units, conservative measurement tokens, and matching pure-JSON Presets. A high-confidence result
becomes an explicit mapping and parses automatically. A missing or ambiguous time source blocks
automatic parsing and expands Advanced. Saved Source mappings are never guessed again.

Unknown numeric columns default to `Other` and remain in the Project. In particular Kn, Ab,
burned-web, geometry, design, and coefficient columns are not inferred as Temperature from their
numeric shape. Automatic mapping may propose the following scientific mappings, but parsing uses
the final saved column-index mapping:

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

Schema v2 also stores `reference_pressure_pa` and `pressure_reference_visible`. Older v2 files
default to 101325 Pa and a visible line. These are Project view/reference fields and never modify
Channel values or analysis formulas.

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
and a later availability refresh does not undo a user's manual uncheck. Opening the Export dialog
is an explicit UI reset to all available options; Select All repeats it. Re-showing an already
visible dialog does not reset manual choices. This changes no Project schema or scientific state. Every bundled format,
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

## v0.0.4 confident preset application

Automatic preset application is limited to new Generic Tabular imports with an empty mapping.
The detector first requires an unambiguous real time column and a detected header/data region.
Candidates must match Parser ID/version, selected sheet, header/data-start rows, all column
indices, and normalized unit hints. A fixed data-end crop is not auto-applied because a bounded
preview cannot verify the new record's end. Every normalized header name must have similarity
at least 0.95; the weakest header is the score and must lead the runner-up by at least 0.08.
Sub-threshold candidates still participate in this margin check.
These defaults live in TabularAutoDetector alongside the time thresholds. Preview mapping is
validated through the shared Tabular engine, including finite strictly increasing timestamps.
Invalid, conflicting, weak, or tied candidates fall back to ordinary conservative classification.

A successful match copies the preset's config into the effective source mapping, retaining the
current file's detected reader settings. The GUI displays the applied preset name and final
mapping. Manual edits take precedence. Project reopen uses only its saved effective mapping,
never auto-detection or a live link to a global preset.

## v0.1.0 Source origin and display state

Each `sources` entry adds `source_kind` (`experimental` / `theoretical`) and `display_transform`
with finite `shift_s`, boolean `zero_start`, and full-reference `hidden_curve_ids`. Missing fields
default to Experimental, zero shift, ordinary timing, and visible curves. These additive fields
keep Project schema `/2` and Plugin API v1 unchanged. Alignment never rewrites source files,
Channel arrays, or Stream time offsets. Both origins use the same Parser references/mappings.
Theoretical Source removal preserves experiment segmentation, derived state and export choices;
ordinary parsed experimental Source removal retains its conservative invalidation rules.
See Theoretical_Curves.md for the anchor algorithm, validation and operator workflow.
Two Sources may reference the same physical file with different origins and saved mappings.
Source ID, not path, determines selection/removal and Dataset reuse during reopen. Their hashes
can match without making their interpretations, channels, or display state interchangeable.

Project `/2` also adds `source_analyses`, keyed by `<source_id>/<workspace_id>`. Each value stores
`config` (full Channel references, scientific `interval` or null for full record, effective
`propellant_mass_kg`, `mass_source`, input stage, polarity, Processor reference/config, PRE/POST),
`completed`,
`calculator` (stable ID/version/API for plugins or the generic statistics version) and `results`.
Result metadata records source/reference, scientific interval/clock and no applied display
transform. `mass_source` is `project` for shared engine parameters, or `source` for an experimental
profile's explicitly independent saved mass. Missing provenance is initially read as `source`;
theory profiles then migrate to `project` using experimental `motor_metadata`, even if a value is
missing. Unknown provenance is rejected. Conflicting former theory mass and saved total mass or
dimensions are retained in `config.legacy_physical_parameters`. `propellant_mass_kg` remains the
effective snapshot; completed theory reopen resolves the current shared model before calculation.
Result metadata `motor_parameters` records propellant/total mass in kg and diameter/length in mm,
including nulls. Public physical-parameter edits invalidate shared thrust profiles. Source
intervals, calibrations and processing remain independent. Missing
source profiles mean none. Missing/nonpositive mass preserves other metrics while Isp stays
unavailable; nonfinite stored mass is rejected.

`calibrated_stream_ids` records independently completed stream calibrations; absence retains
legacy global workflow-stage interpretation. This permits a calibrated theoretical Source with
an unfinished experimental workflow without advancing the latter on reopen. Completed source
profiles are recomputed from hash-verified files/configuration; drafts remain pending. Profiles
with unavailable saved calculators remain pending with their own error. Source removal prunes its
profiles; scientific changes invalidate affected profiles. View transforms never invalidate them.


`plot_views` is an optional Project `/2` view-state map: stable plot IDs contain axis IDs with
`range` (two finite increasing display-coordinate bounds), `auto_range` (boolean or fraction in
[0, 1]) and optional `linked_to` (`<plot_id>/<axis_id>`). A linked axis uses null `range` to avoid
persisting another copy of its target's range. Main axes are `x`/`y`; attached ViewBoxes use axis
names such as `right:x`/`right:y`. Shared actual axes are recorded once. Missing view state uses
normal defaults; unknown UI axes remain stored. Restoration runs after curves, display transforms
and initialization. No range is added to scientific timestamps or Source alignment.

Axis entries also accept boolean `log_mode` (per axis), `fft_mode` and
`subtract_mean_mode` (main `x` entry). All default to false for legacy projects.
FFT/mean/log controls restore before ranges so saved Hz/log10 coordinates are not
misinterpreted as time/linear coordinates. These flags are view state only.
Project-level `plot_analysis_active_only` is a strict boolean, defaults to false,
and synchronizes the existing derived-plot input scope across workspaces. It does
not change scientific workflow results or original-data export semantics.
