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
than one theory file supplies this measurement, the folded parameters contain a Theory file
selector. Channels, including multiple Temperature Channels, still come from the original mapping.
Historical independent experimental profiles remain in saved Projects without replacing the
primary workflow.
Expand **Source calculation parameters** to select the engineering Channel (multiple Temperature
Channels are supported), full record or custom scientific Project-time interval. Calculate uses
the same thrust Analyzer or measurement-statistics implementation as the existing workflow.

For thrust, the source defaults to polarity +1 and correction None. Optional motor-weight
compensation uses registered Processor schemas and explicit source PRE/POST intervals. A source
containing the current primary processed thrust may explicitly choose that curve instead.
Changing the Project's processed input then invalidates that dependent calculation; independently
configured source calculations keep their own intervals and correction. Neither selection creates
an experimental Primary binding for a theoretical Source.

Enter propellant mass specifically for this Source to enable Isp. It starts unspecified even if
the Project's motor metadata contains mass. Unspecified, zero or negative mass yields unavailable
Isp with a Diagnostic while impulse and other computable metrics remain available. The same
`g0 = 9.80665 m/s²` and actual-timestamp trapezoidal integration apply. No total-motor mass or
baseline-derived mass estimate is substituted.

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
