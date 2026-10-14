# Source curves and calculations in 0.1.0

Theoretical and experimental data use the same registered Parsers and explicit mappings. No
software name or header vocabulary determines origin. Choose **New sources → Theoretical** before
adding a file on Project; ordinary existing and legacy sources default to Experimental. Each entry
shows its origin. The selected pending source can be reclassified before parsing. A parsed origin
is fixed; remove and import it again to change origin deliberately.

The same physical file may be imported once as Experimental and once as Theoretical. Import
deduplication uses path plus origin, not path alone. Each gets a distinct Source/Stream identity
and its own saved mapping, calibration and display state. No file copy is needed. Selecting or
removing one origin targets its stable Source ID and does not select/remove the other. Reopen
parses each Source's own mapping even when its path and SHA-256 match another Source.

## Import state and mappings

Toolbar Import and Project Add Sources both append to the current Project. New Project is an
explicit separate action. Canceling the file picker or adding the same path/origin again leaves
selection, mappings and scientific state unchanged. Appending another Experimental source keeps
existing Primary bindings and completed results; ambiguous alternatives remain explicit choices.

Each pending entry has its own parser/mapping draft. A new table starts with empty mapping columns
and is detected independently, even when it uses the same parser as the preceding file. The visible
tabular mapping imports only its selected file; other pending tables require their own selection
and mapping. Saved source mappings are never overwritten by another file's preview. Switching
back to a parsed source restores its saved mapping; switching between pending entries retains
manual drafts. Removing and re-adding a file starts a new pending entry.

Probe, preview and parse callbacks are accepted only for their original session, source entry,
origin, selection, offsets and parser configuration. Removal, input changes, New Project or closing
make old callbacks ineligible. Failed parsing leaves the committed Project unchanged. Removing
one entry restores the surviving selection only after removal completes; removing the last entry
resets both the parser selector and mapping editor. Two-column raw TXT parser ambiguity still
requires an explicit parser choice; no registry-order fallback is introduced.

## Operator workflow

1. Import experimental data normally and confirm its Primary Channels.
2. On Project, choose Theoretical for new sources, then Add Sources. Existing CSV/TSV/XLSX mappings,
   auto detection, presets, and other registered Parsers remain available. There is no restriction
   to a particular simulation application.
3. Open Thrust, Chamber Pressure, Temperature, or an appropriate Data Explorer time curve. Display
   lists theoretical curves with visibility checkboxes. Each visible curve uses a distinct color,
   dashed line, and a localized Theoretical legend prefix. Multiple theoretical sources and
   temperature curves are supported without a separate comparison page.
4. Enter a signed **Display time shift (s)** or drag its slider. Every theory Source and all
   four workspaces share the same absolute offset; the controls synchronize in both directions.
   **Align test starts** uses the current experimental ACTIVE_TEST start (including manual edits)
   minus the independently detected theory start in original scientific Project Time. Repeated
   clicks are idempotent. The slider can fine-tune the result immediately.
5. **Restore original timing** clears the shared theory shift and any legacy start-zeroing. Reset Chart fits the complete visible
   record, including theoretical samples. Fit Interval continues to use the experimental test
   interval. Save Project and Open Project retain origin, visibility, and source alignment.

With no experimental primary selected, a compatible theoretical curve can still be inspected.
Choose **Theoretical** in the result area to calculate independently.
Automatic Project segmentation still requires an experimental reference.
Data Explorer uses the selected experimental quantity as its overlay target; without one, its
alignment-reference selector chooses the theoretical quantity to inspect. Auxiliary/Other Channels with
known compatible physical quantities can be inspected and calculated through Data Explorer.

## Independent calculations in the same result area

Thrust, Chamber Pressure, Temperature and Data Explorer keep their existing result table location.
The calculation-source selector contains exactly **Experimental** and **Theoretical**. Experimental
uses the existing primary workflow, parameters and results; Theoretical uses its independently
saved source parameters and results. It does not create duplicate experimental choices. If more
than one theory file supplies this measurement, the parameters contain a Theory file
selector. Channels, including multiple Temperature Channels, still come from the original mapping.
Historical independent experimental profiles remain in saved Projects without replacing the
primary workflow.
The metric-source selector is one compact row inside the existing results group. There is no
separate theory Channel/interval panel or Calculate button in that column. Use the single toolbar
Calculate action for either origin. Theory uses the existing theory-curve selector in Display to
identify its Source/Channel. Saved source intervals and Channel sets remain intact; a new profile
uses its full scientific record, and Temperature keeps its saved multi-channel set or defaults to
all Temperature Channels in that Source. Calculation uses the same Analyzer/statistics as before.
Missing/unusable inputs show an unavailable reason and cannot fall back to experimental data.

New thrust calculations use the current engineering Channel, polarity +1 and correction None.
The result area keeps only the compact source switch and existing results. Source Channel and
interval drafts remain internal scientific configuration; all calculation goes through one toolbar
action. Input stage, polarity, Processor/PRE/POST and mass controls are not duplicated here.
Experimental correction and segmentation never become theoretical calculation inputs implicitly.
Existing Display Unit settings are shared by both origins.

Enter engine physical parameters once in Project Setup. Theory reads the experimental engine's
`MotorPhysicalParameters`: propellant mass, total motor mass, diameter and length. These are the
same resolved values passed to both origins' thrust calculators and recorded in result metadata.
Only propellant mass enters Isp; total mass and dimensions remain shared provenance for the
existing calculator, which does not define additional formulas using them. Changing a shared
physical parameter makes primary experimental and shared
source thrust results pending; press Calculate for each source to recompute. It does not change
processing, segmentation, Channel arrays or source clocks. Unspecified, zero or negative mass
yields unavailable Isp with a Diagnostic while impulse and other computable metrics remain
available. The same `g0 = 9.80665 m/s²` and actual-timestamp trapezoidal integration apply. No
total-motor mass or baseline-derived mass estimate is substituted.

Legacy theory profiles now use experimental engine parameters (`mass_source=project`), including
an unspecified experimental mass. Conflicting former values remain in
`legacy_physical_parameters`, including old total mass/dimensions if present, for traceability.
A nonblocking load notice explains this migration. Completed theory profiles recompute with the
resolved shared model; drafts remain pending. The migration preserves their Channel references,
interval, stage, polarity, correction and PRE/POST windows. Experimental independent source
profiles retain their explicit legacy mass. A saved profile dependent on primary processed thrust continues to be
invalidated when that processed input changes.

Pressure retains start/mean/maximum/time-to-maximum/minimum; Temperature retains start, interval
maximum, full-record maximum and recorded time; Data Explorer retains its existing applicable
minimum/mean/maximum statistics. Physical values are calculated in canonical units and rendered
with current Display Units. Unit/Quantity conflicts, empty/all-invalid records, invalid intervals
or unsupported inputs show a scoped unavailable reason, without clearing another Source's result.
Finite-sample integration follows existing calculator behavior (including integration across
retained finite points around NaNs), with a Diagnostic; plotted gaps and raw samples are preserved.
No endpoint interpolation, sorting or resampling is added for calculation.

Source results and configuration use full Source/Stream/Channel references, so two origins of one
file or equal local Channel names do not share caches. Calculation uses `dataset.project_time`:
manual display shifts, test-start alignment, visibility and restoring timing affect only plots.
The source calculation interval is separate from the Project's experimental Test Segmentation;
existing experimental markers remain unchanged. Saving stores independent parameters, calculator
provenance, results and completion. Reopen verifies source hashes and recomputes completed profiles
from saved scientific input; uncalculated drafts stay uncalculated. Removing a Source drops its
profiles only. Formal export readiness continues to follow the original experimental workflow.

## Plot viewport persistence

Project `/2` has an optional `plot_views` view-state object, keyed by stable workspace plot IDs
(`thrust_analysis`, `chamber_pressure`, `temperature`, `data_explorer`) and actual axis IDs (`x`,
`y`, or an attached axis such as `right:y`). Each independent axis stores its displayed finite
range and auto-range boolean/fraction. Shared ViewBox axes are recorded once; linked axes store
`linked_to` rather than another range. Additional unknown plot/axis records survive a save.
Older files without this field retain the normal default view. Invalid ranges/flags are rejected.

Reopen restores viewports after verified data, scientific state, theory shifts, curves and locale
initialization, with one deferred guarded restoration for queued layout refreshes. Stored ranges
are already display coordinates: the theory shift is never applied again. Manual ranges and
auto-range settings survive page changes. Reset Chart still deliberately fits all visible data.
View state does not change samples, scientific timestamps, calculation intervals or exports.

## Data and unit contract

Source stores `source_kind`: `experimental` or `theoretical`. This is independent of Channel
`role` (`raw`, `calibrated`, `processed`, etc.). Full Source/Stream/Channel references isolate
equal local Channel IDs. Project schema `/2` adds source `display_transform`:

```json
{
  "source_kind": "theoretical",
  "display_transform": {
    "shift_s": -0.25,
    "zero_start": false,
    "hidden_curve_ids": ["source_2/stream_2/f"]
  }
}
```

Old `/1` and `/2` Projects missing these fields read as Experimental with zero shift and ordinary
timing. Unknown origin values, nonfinite/invalid shifts, malformed visibility lists, invalid
zeroing flags and malformed detected intervals/references are rejected. Plugin API v1 and parser signatures are unchanged.

New UI operations use `t_display = t_project + shared_shift_s`; every theory Source stores the
same absolute shift. Newly imported theory inherits it. The older display clock remains readable
as `t_display = t_project - anchor + shift_s`, where anchor is zero unless
`zero_start` is enabled. For each Stream, the first row with finite time and at least one finite
measurement supplies its start; the earliest of these Stream starts is the Source anchor. Empty
or all-invalid sources have no anchor and cannot be zeroed through the UI. Stream local time,
scientific `time_offset_s`, measurement arrays, and external files are never changed by alignment.
Original sample count, ordering, irregular spacing, and NaN gaps remain intact. The plot connects
only adjacent finite samples and does not interpolate or resample overlays.

Sharing an axis requires compatible Quantity dimensions, physically valid Data Units for both
Quantities, and conversion to the target Display Unit through the existing Unit Registry.
Unknown quantities, conflicting units, and `raw`/`count`/`ADC` overlays are visibly unavailable;
Identity Calibration does not make them physical. K/°C offsets and Pa/MPa, N/kN, m/mm scales are
real display conversions. Theoretical Calibration/Data Unit edits stay within their Source.

## Experiment isolation

Theoretical sources are excluded from automatic and manual experimental Primary Channel
selection and from segmentation reference resolution. Adding, removing, hiding, aligning, or
calibrating a theoretical source preserves experimental bindings, segmentation, thrust polarity,
correction selection, processing, analysis, workspace calculation flags, and export selection.
Incremental theoretical import uses the existing parser infrastructure without reparsing the
experiment. A failed import adds nothing. Formal exports continue to use experimental analysis
inputs and do not include the display overlays or their alignment.

Residual metrics, MAE/RMSE, fitting, LLM analysis, and motor optimization are outside this version.

The four current time-curve pages are **Thrust / 推力** (`thrust_analysis`), **Chamber Pressure /
燃烧室压力** (`chamber_pressure`), **Temperature / 温度** (`temperature`), and **Data Explorer /
数据浏览器** (`data_explorer`). Project contains import/setup controls and no time-curve plot.

## Test-start alignment reference

The Thrust/Chamber Pressure detection action independently runs the existing activity detector
on the experimental primary and eligible theory Channels of the same measurement family. Only
the experimental PRE/ACTIVE_TEST/POST is drawn and remains manually editable. Theory detection
is an internal advisory reference, stored as optional `display_transform.detected_test` with a
full Channel reference, original-clock regions, detection role and own polarity. It does not
replace calculation intervals, processing parameters, mass or completed metrics. Pressure uses
positive polarity; theory thrust never borrows the experiment's installation sign.

Align Test Starts uses the selected reference curve's Source detection. If it has not been
detected, the shared TaskManager detects theory only (pressure then thrust); the current manual
experimental interval is preserved. Ambiguous Channels require an explicit existing calculation
Channel selection. Missing theory, missing experimental ACTIVE_TEST and no usable theory region
show localized notices without changing the current shift. Calibration/reparse invalidates the
affected cached reference. Changing the selected calculation Channel or its thrust polarity also
invalidates that family's reference. Detection rejects nonphysical or conflicting units.
Save/reopen preserves the reference and manual experimental regions
after source hash verification. A hidden or incompatible family still shares the global offset.

No theory intervals are drawn. Alignment is not fitting, resampling, a residual metric, a
scientific Stream offset, or a mixed-source calculation. Legacy per-Source display transforms
remain readable until a new slider/input/alignment/reset action applies the shared absolute shift.
