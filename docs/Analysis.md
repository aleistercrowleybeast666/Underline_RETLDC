# Analysis

## Regions and test intervals

The Project owns one Test Segmentation in Project Time: optional PRE, required ACTIVE_TEST, and
optional POST. `BURN` remains a compatibility persistence alias for ACTIVE_TEST. When present, PRE
ends no later than ignition `ti`, `ti < tb`, and POST begins no earlier than `tb`. Thrust, Chamber
Pressure, Temperature, Data Explorer, analysis, and export share these markers without resampling
individual Streams.

Each editable workspace has an explicit detection source. The Thrust button uses only the bound
Primary Thrust Channel; the Chamber Pressure button uses only the bound Primary Chamber Pressure
Channel. Neither silently switches to the other measurement family. The generic Core selector
retains chamber-pressure-then-thrust priority for legacy/programmatic callers. Validation checks
finite time, sufficient samples, and signal variation. Activity detection uses relative
baseline/noise/amplitude and duration, so Pa, MPa, N, and raw signals can all provide segmentation;
it never treats Identity Calibration as evidence of physical units. Pressure detection always uses
positive activity polarity. Thrust detection uses the Project's polarity-normalized thrust working
Channel and then calls the detector with positive activity polarity. It returns multiple ranked
regions with clipped-boundary flags and remains advisory.

Before detection, the Test Interval control displays `Not detected`. The Thrust action explicitly
identifies thrust data and the Chamber Pressure action identifies chamber-pressure data. After
detection it selects the highest-ranked recommendation and synchronizes available regions.
PRE/ACTIVE_TEST/POST can be
dragged on either the Thrust or Chamber Pressure plot or edited numerically. Both workspaces write
the same Project segmentation and update each other immediately; Temperature reads the same state.
Invalid or overlapping edits are rejected without changing the active selection. `Fit Interval`
sets the plot
viewport from the available PRE start (or ACTIVE_TEST start) through the available POST end (or
ACTIVE_TEST end). The plot exposes only `Uncorrected` and
`Corrected` visibility checkboxes.

## Primary bindings and shared workspaces

Segmentation and each dedicated workspace resolve data through the Project's explicit primary
Channel bindings. Each binding contains Source, Stream, and Channel IDs, so equal local Channel IDs
from different files remain unambiguous. Semantic role is only an auto-binding hint. Ambiguous
candidates stay unbound until the user chooses; auxiliary/Other Channels are never auto-bound.

Calibration creates a new output Channel from the selected input and declares its resulting
Quantity and Unit. Processing takes that resolved output rather than assuming a Parser-specific
name such as `force_calibrated`. The same rule applies when the user changes the primary thrust
Channel or reopens a multi-Source Project.

Thrust, Chamber Pressure, and Temperature share PRE/ACTIVE_TEST/POST markers, plot behavior,
legend, theme handling, empty state, and a non-shrinking results panel. Chamber Pressure and
Temperature do not duplicate a separate View Controls group. Each instead has Curve Display plus
Reset Chart; pressure exposes one `Chamber Pressure` visibility checkbox and temperature mirrors
the selected imported temperature Channels with one checkbox per curve. The pressure workspace
reports value at test start plus active-test mean, maximum, time to maximum, and minimum. The
temperature workspace reports the test-start value, active-test maximum, full-record maximum, and
full-record time to maximum for each selected Channel. These two result tables remain empty until
the user presses their localized Calculate Analysis Results button. A binding or segmentation
change invalidates the saved completion state and requires recalculation. Reset Chart restores the
complete data-driven automatic X/Y range after zoom or pan and preserves PRE/ACTIVE_TEST/POST
because those markers are shared Project state, not disposable viewport annotations.

The chamber-pressure PNG export is stricter than the interactive full-record view: it requires a
valid ACTIVE_TEST and clips both plotted samples and the X-axis to that interval. PRE and POST remain
available in the Project and interactive workspace but are not rendered into the formal pressure
curve image.

Plot axes disable pyqtgraph automatic SI prefixes. In `engineering` Unit Display Mode, the GUI
uses resolved engineering Display Units such as N, MPa, °C, and mm. In `si_scientific` mode it
converts display values to canonical SI such as N, Pa, K, and m and formats ticks and result values
in scientific notation. These modes never change raw arrays, Data Units, Calibration, or formal
export units.

## Thrust polarity

Project `thrust_polarity` is `+1` by factory default or `-1` when the sensor installation is
reversed. It is a required Thrust Workflow setting, independent of optional correction:

```text
F_oriented(t) = thrust_polarity × F_calibrated(t)
```

Core creates a fresh read-only `thrust_oriented` Channel; parsed raw and calibrated Channels are
never overwritten. The workspace's `Uncorrected` curve is calibrated and polarity-normalized but
does not yet contain optional baseline/weight correction. With no correction Processor,
`thrust_processed` is a pass-through copy of `thrust_oriented`.

## Motor weight-change compensation

The GUI name is `Motor Weight-Change Compensation`; the stable processor ID and vertical linear
baseline algorithm remain unchanged for reproducibility and Plugin API compatibility.

The selector is populated from all registered Processor plugins whose `requirements()` mapping
contains `processor_role = motor_weight_compensation`. `None` means compensation is genuinely not
enabled; Core creates a separate pass-through `thrust_processed` channel and the Project stores no
Processor reference. Choosing a plugin stores its stable ID, version, API version, and scalar
configuration. PRE/ACTIVE_TEST/POST and the calibrated input channel are shared workspace state injected
through generic `x-ui-source` schema metadata rather than edited as JSON or selected by a
plugin-ID branch. If a saved Project references a missing Processor, recomputation reports the
exact missing ID/version and never silently substitutes the official linear implementation.

Fit PRE and POST independently:

```text
Bpre(t)  = a1 t + b1;  B0 = Bpre(ti)
Bpost(t) = a2 t + b2;  B1 = Bpost(tb)
Bburn(t) = B0 + (B1 - B0) × (t - ti) / (tb - ti)
Fcorrected(t) = Foriented(t) - Boriented(t)
```

The Processor receives `thrust_oriented`, so it fits both endpoint baselines in the same
orientation and owns no sign parameter. This is mathematically equivalent to the former
`sign × (measured - baseline)` formulation while keeping polarity available when correction is
disabled.

If PRE or POST is absent or cannot provide a measured fit, that endpoint baseline is exactly zero
and its source is `assumed_zero`. With both absent the complete baseline is zero; processing
continues. GUI, Project JSON, TXT, and result metadata expose `0 (Assumed)` rather than an
unqualified zero. Equivalent mass change is unavailable unless both endpoint sources are
`measured_fit` and the Channel uses a physical force Unit.

For display outside ACTIVE_TEST, the model uses the corresponding PRE/POST fit. Raw and calibrated input
channels remain unchanged. Equivalent force and mass changes are:

```text
ΔFeq = B0 - B1
Δmeq = |ΔFeq| / g0
g0 = 9.80665 m/s²
```

`Δmeq` may include drift, thermal/structural effects, or settling. It is not exact measured
propellant consumption. The UI and reports retain it as a manual-reference metric only. There is no
expected-propellant-mass input, comparison diagnostic, threshold, or export gate associated with
this estimate; non-vertical stands and ablation can make direct mass interpretation inappropriate.

## Thrust metrics

Metrics use the analyzed final processed thrust over `[ti, tb]` and actual Project
timestamps:

```text
peak thrust      = max(F)
burn duration    = tb - ti
total impulse It = trapezoidal integral of F with respect to t
average thrust   = It / burn duration
time to peak     = t(argmax(F)) - ti
specific impulse = It / (mp × g0)
```

`mp` is propellant mass in kilograms. If it is missing or nonpositive, Isp is unavailable. Total
motor mass is never substituted. Negative samples are not silently clipped by analysis.

The Analyzer validates both Quantity and Data Unit. Convertible force Units (N, kN) are converted
centrally to newtons before physical metrics. A force Channel in raw/count/ADC may still be plotted,
segmented, and produce unit-relative peak/average/integral, but `peak_thrust_n`, SI total impulse,
Isp, and ENG are N/A with an explicit Diagnostic. Identity Calibration never makes raw equal N.

## Formal curve export

TXT, PNG, and ENG formal curves use `thrust_processed` (or an explicitly configured final channel)
from the already processed Dataset. Only samples in `[ti, tb]` are selected and their time is
shifted by `ti`; raw and calibrated channels are never substituted. When a movable boundary falls
between recorded timestamps, TXT/PNG may add only that exact endpoint using linear interpolation
between its two recorded neighbors. The original Dataset is unchanged and ExportResult/TXT records
which boundaries were interpolated.

PNG is a 1600×1000 report image with a locale-selected default title, time/thrust axes, units,
grid, and optional peak/total impulse annotation; an explicit caller-supplied title remains
available as an override. TXT is UTF-8 and includes software/source identity, stable plugin provenance,
calibration and processing configuration, motor metadata, test limits, metrics, diagnostics, and
the complete zero-origin final time/thrust table. CSV/TXT/JSON display labels and all PNG text follow
the selected Chinese or English output locale. Missing values are written with the locale's
unavailable marker.

OpenRocket ENG becomes selectable immediately after successful thrust processing/analysis when
its physical-force, segmentation, and motor-metadata requirements are satisfied. There is no
separate curve-confirmation checkbox or confirmation field in current Project output.
