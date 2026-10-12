# Theoretical curve overlays in 0.1.0

Theoretical and experimental data use the same registered Parsers and explicit mappings. No
software name or header vocabulary determines origin. Choose **New sources → Theoretical** before
adding a file on Project; ordinary existing and legacy sources default to Experimental. Each entry
shows its origin. The selected pending source can be reclassified before parsing. A parsed origin
is fixed; remove and import it again to change origin deliberately.

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
Calculation and automatic segmentation remain unavailable until experimental inputs are selected.
Data Explorer uses the selected experimental quantity as its overlay target; without one, its
alignment selector chooses the theoretical quantity to inspect. Auxiliary/Other Channels with
known compatible physical quantities can be inspected through Data Explorer.

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
