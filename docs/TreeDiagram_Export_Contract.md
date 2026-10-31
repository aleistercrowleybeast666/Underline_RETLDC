# TreeDiagram motor-test package v1

Underline owns `underline.motor-test-package/1`, schema version `1`. The schema is
[`contracts/motor-test-package/v1/schema.json`](../contracts/motor-test-package/v1/schema.json).
The executable semantic authority is
[`plugins/exporters/treediagram_motor/contract.py`](../plugins/exporters/treediagram_motor/contract.py).
It uses only the Python standard library. TreeDiagram may retain an exact, attributed copy with
its upstream commit, SHA-256 and the shared golden vectors. Changes to either copy must be
reconciled with this owner. A package contains data only and grants no plugin execution authority.

## Exporting

The existing Export dialog discovers `builtin.exporter.treediagram_motor` through Plugin API v1
metadata. It writes `motor.tdmotor.json` without a locale suffix, in the selected output directory.
The project must have completed primary thrust processing, analysis, a physical force unit and
ACTIVE_TEST. Source identity is captured during parsing, so saving the project is not required.
Unknown motor masses and dimensions are allowed; TreeDiagram must obtain its own explicit mass,
inertia, aerodynamic and installation models before declaring a 6DoF configuration ready.

The CLI and GUI use the same project replay, immutable export snapshot and exporter:

```powershell
.venv\Scripts\python.exe -m underline_retldc.cli export `
  tests/fixtures/motor_test_package/v1/synthetic_positive.retldc.json `
  motor.tdmotor.json
```

From any working directory, supply an absolute project/output path. `--maximum-gap-s 0.1` is the
default explicit maximum interpolation/interval gap. `--exporter` can select other discovered
exporters. `--plugin-root` selects an explicitly trusted installed plugin directory; input files
cannot choose a code path. The CLI does not import Qt. It refuses incomplete saved workflows and
does not silently complete calibration, processing or analysis.

`--relocate SOURCE_ID=PATH` accepts an explicit alternate source only when its recorded SHA-256
matches. It may be repeated for different Source IDs. GUI Open offers relocation for each missing
source. Relative paths resolve against the project directory, including secondary sources;
absolute paths remain readable. Merely finding another file with the same name is insufficient.

The existing CSV, ENG, reports and PNG formats retain their own policies. ENG is not used as an
intermediate. In particular, its clipping, initial-zero and trailing-zero compatibility behavior
does not apply to `.tdmotor.json`.

## Fields, units and identity

All top-level fields and the nested fields declared in the schema are required. Optional physical
knowledge is represented by `null`, never a plausible-looking zero. Unknown fields are rejected
except within the explicitly declarative plugin `config` objects. Unsupported versions are rejected.

| Field | Meaning |
|---|---|
| `producer` | Application, application version, exporter ID/version and Plugin API version; independent of the data schema |
| `project.name` | Original project filename or `null` for unsaved work; never a machine absolute path |
| `motor` | Optional name; propellant/total motor masses in kg, diameter/length in m |
| `source` | Full Source/Stream/input Channel and actual final Channel references, original-byte SHA-256, filename and experimental kind |
| `processing_chain` | Actual parser, calibration, polarity, optional processor/pass-through and analyzer identities/configs, input/output references and source hash |
| `calibration` | Stated qualification and retained source notes; a checksum or force unit is never a calibration certificate |
| `time` | Local→project offset, project ignition and ACTIVE_TEST boundaries; exported time is relative to ignition |
| `evidence_curve` | Every final-channel sample in original order, SI seconds/newtons, including PRE/POST and signed values |
| `simulation_curve` | ACTIVE_TEST subset with explicit boundary interpolation metadata, or `null` when coverage/gaps prevent construction |
| `diagnostics` | Stable code, JSON field path, severity and readable message |
| `metrics.total_impulse_ns` | Actual-time trapezoidal integral of `simulation_curve`, or `null` |
| `content_sha256` | Versioned digest of all other fields, as defined below |

The relationships are `t_project = t_local + local_to_project_offset_s` and
`t_project = t_export + ignition_project_s`. ACTIVE_TEST begins at ignition and includes its two
endpoints. Display alignment, language, theme and display units do not change these values.
All original timestamps are retained relative to ignition, including negative pre-ignition times.
The source hash belongs to the parsed arrays and is not recomputed during export. If the original
file changes afterwards, the old arrays retain their original identity; reloading or saving against
that changed source refuses the mismatch. The parser boundary hashes before and after parsing and
rejects an observed concurrent change.

The final Channel is resolved from actual analysis/processing output and its derived Channel graph,
then checked against the complete Primary Channel binding. The active selection and global UI
parser/calibration fields cannot replace it. A snapshot freezes nested configuration before starting
the worker. Pressure/temperature exports retain their own source resolution; this package v1 exports
only thrust and motor metadata, and makes no claim to contain auxiliary pressure/temperature streams.

Calibration provenance can carry the original calibration document, sensor information, notes and
model parameters in the calibration stage config. Editing its values retains that document but
marks `parameters_modified`; it does not grant its old qualification to the edited calibration.
`unknown`, `estimated`, and `documented` describe the supplied evidence, not independent verification.
Identity and user-entered gains default to `unknown`. Historical projects which never saved notes
cannot have those notes reconstructed. The recorded-data showcase remains an estimated display
example, not calibrated performance evidence.

## Curves and interpolation

Input arrays must be one-dimensional, finite, equal-length and strictly increasing in time, with
2–250,000 points. Duplicate/reversed time, NaN, infinity and raw/count/ADC force units are errors.
The exporter never silently sorts, deletes, deduplicates, smooths, clips or appends zeros.
Source parser diagnostics and configurations remain part of the original workflow; this format
does not claim to recover rows a user explicitly chose to skip at parsing.

`evidence_curve` is copied directly from the actual processed Channel with genuine compatible unit
conversion (`kN→N`, `mm→m` for metadata). `simulation_curve` retains every evidence sample inside
ACTIVE_TEST. A boundary between two samples may be inserted using piecewise-linear interpolation
only if its bracketing gap does not exceed `maximum_gap_s` (default 0.1 s). Any excessive internal
gap or out-of-coverage boundary makes `simulation_curve=null`, leaves evidence intact and adds a
warning. No integration is reported for that unavailable curve.

`source_sample_indices` maps each simulation sample to a zero-based evidence index; `-1` means an
inserted boundary. `inserted_boundary_indices` lists exactly those simulation indices. The validator
checks original values, completeness of the interval subset, inserted values and bounded gaps.
Impulse uses the actual irregular timestamps and both interval endpoints; it may differ from older
analysis metrics that did not include interpolated endpoints. It is never recomputed from a regular
sampling assumption. A signed curve is valid evidence, but TreeDiagram must separately gate the
selected propulsion model or record an explicit derived policy. Thrust does not identify mass flow.
No altitude correction, whole-vehicle inertia, CG, mounting or propulsion depletion is invented here.

## Digest and bounds

The entire UTF-8 file is limited to 32 MiB, JSON nesting to 24, object keys to 512, strings/keys to
4096 characters and processing stages to 32. Duplicate keys and JSON NaN/Infinity extensions are
rejected. Booleans are not numerical physical fields. Positive known dimensions/masses are required;
propellant may not exceed total motor mass. Cancellation/failure preserves the previous output:
write a unique same-directory temporary file, flush, fsync, validate it, check cancellation, then
atomically replace the destination. The final progress report means commit already occurred.

`content_sha256` hashes every field except itself. There is deliberately no export timestamp to
destabilize repeated output. It proves content consistency, not source authenticity. A normal file
SHA-256 remains a different identity. The canonical input starts with UTF-8 bytes
`underline.motor-test-package/1` plus a single zero byte, followed by this recursive encoding:

| JSON value | Encoding |
|---|---|
| null / false / true | ASCII `Z` / `F` / `T` |
| number | ASCII `N`, then finite IEEE-754 binary64 big-endian; normalize either zero sign to +0 |
| string | ASCII `S`, 4-byte unsigned big-endian UTF-8 byte count, exact UTF-8 bytes |
| array | ASCII `L`, 4-byte unsigned big-endian item count, each encoded item in order |
| object | ASCII `D`, 4-byte unsigned big-endian key count, encoded key/value pairs sorted by key UTF-8 bytes |

This avoids differences between JSON `1` and `1.0` or serializer whitespace/locale. No Unicode
normalization is performed. Read `MotorPackage_Digest` when implementing another language.

Errors expose `MotorPackageError.code` and `.path`: `STRUCTURE`, `NUMBER`, `TEXT`, `HASH`, `LIMIT`,
`VERSION`, `MASS`, `SOURCE_KIND`, `CHAIN`, `ENUM`, `TIME`, `LENGTH`, `CLOCK`, `POLICY`, `INDICES`,
`SAMPLE_IDENTITY`, `INTERPOLATION`, `COVERAGE`, `GAP`, `IMPULSE`, `DIGEST`, `DUPLICATE_KEY`, `JSON`.
Export boundary errors additionally include `UNIT` and `SOURCE_HASH`. Warnings include
`NEGATIVE_THRUST`, `MASS_UNKNOWN`, `COVERAGE`, `BOUNDARY_GAP`, `GAP`. Fix the identified input or add
an explicit consumer-side model; do not treat every warning as an unreadable package.

`SOURCE_QUALITY` is an informational diagnostic when the parsed Dataset already reported source
issues. Its message contains JSON counts for retained samples, known malformed source rows and
source diagnostic codes; it does not rename missing source rows as valid samples.

## Reproducible examples

[`tests/fixtures/motor_test_package/v1`](../tests/fixtures/motor_test_package/v1) contains original
task-authored synthetic data, two saved projects, two real CLI exports and six rejected golden
packages indexed by `vectors.json`. These fixtures share the repository Apache-2.0 license and are
not device measurements. The triangular signal has peak 200 N and total impulse 200 N·s.

`synthetic.retldc.json` executes `K=2`, polarity `-1`, measured baseline compensation and analysis.
Its ~1e-14 N negative roundoff is preserved and diagnosed. `synthetic_positive.retldc.json` uses the
explicit exact affine conversion `K=-2, B=-20`, polarity `+1`, pass-through processing, producing
exact zero endpoints. It is suitable for a nonnegative simulation input without a hidden repair.
Both use the same immutable input bytes. They prove the software chain, not real calibration.
