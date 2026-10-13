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
4. Select the curve whose source should be aligned. Enter a signed **Display time shift (s)**.
   **First valid sample → t = 0** zeroes the source start and clears the manual shift. It does not
   infer ignition. All curves from that Source move together; other Sources retain their timing.
5. **Restore original timing** clears both zeroing and shift. Reset Chart fits the complete visible
   record, including theoretical samples. Fit Interval continues to use the experimental test
   interval. Save Project and Open Project retain origin, visibility, and source alignment.

With no experimental primary selected, a compatible theoretical curve can still be inspected.
Select that Source in the result area's **Metric source** to calculate independently.
Automatic Project segmentation still requires an experimental reference.
Data Explorer uses the selected experimental quantity as its overlay target; without one, its
alignment selector chooses the theoretical quantity to inspect. Auxiliary/Other Channels with
known compatible physical quantities can be inspected and calculated through Data Explorer.

## Independent calculations in the same result area

Thrust, Chamber Pressure, Temperature and Data Explorer keep their existing result table location.
The calculation-source selector defaults to **Current primary experiment results**, retaining the
original workflow. Choosing a specific Experimental or Theoretical Source shows its own results.
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
manual display shifts, source-start zeroing, visibility and restoring timing affect only plots.
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
    "zero_start": true,
    "hidden_curve_ids": ["source_2/stream_2/f"]
  }
}
```

Old `/1` and `/2` Projects missing these fields read as Experimental with zero shift and ordinary
timing. Unknown origin values, nonfinite/invalid shifts, malformed visibility lists, and invalid
zeroing flags are rejected. Plugin API v1 and parser signatures are unchanged.

The display clock is `t_display = t_project - anchor + shift_s`, where anchor is zero unless
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
