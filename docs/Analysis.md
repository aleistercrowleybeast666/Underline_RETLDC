# Analysis

## Regions and test intervals

Users select nonempty PRE and POST baseline windows plus a BURN interval with ignition `ti` and
burnout `tb`, where PRE ends no later than `ti`, `ti < tb`, and POST begins no earlier than `tb`.
`BURN` remains the stable internal/persistence identifier; the GUI presents it as the Test Interval.
Automatic test-interval detection uses robust baseline/noise estimates, returns multiple ranked
regions with peak, duration, relative strength, and score, and is advisory only.

Before detection, the Test Interval control displays `Not detected`. After detection it selects the
highest-ranked recommendation and synchronizes all three regions. PRE/BURN/POST can be dragged on
the central plot or edited numerically; both representations update each other, while invalid or
overlapping edits are rejected without changing the active selection. `Fit Interval` sets the plot
viewport from the PRE start through the POST end. The plot exposes only `Uncorrected` and
`Corrected` visibility checkboxes.

## Motor weight-change compensation

The GUI name is `Motor Weight-Change Compensation`; the stable processor ID and vertical linear
baseline algorithm remain unchanged for reproducibility and Plugin API compatibility.

The selector is populated from all registered Processor plugins whose `requirements()` mapping
contains `processor_role = motor_weight_compensation`. `None` means compensation is genuinely not
enabled; Core creates a separate pass-through `thrust_processed` channel and the Project stores no
Processor reference. Choosing a plugin stores its stable ID, version, API version, and scalar
configuration. PRE/BURN/POST and the calibrated input channel are shared workspace state injected
through generic `x-ui-source` schema metadata rather than edited as JSON or selected by a
plugin-ID branch. If a saved Project references a missing Processor, recomputation reports the
exact missing ID/version and never silently substitutes the official linear implementation.

Fit PRE and POST independently:

```text
Bpre(t)  = a1 t + b1;  B0 = Bpre(ti)
Bpost(t) = a2 t + b2;  B1 = Bpost(tb)
Bburn(t) = B0 + (B1 - B0) × (t - ti) / (tb - ti)
Fcorrected(t) = sign × (Fmeasured(t) - B(t)), sign ∈ {+1, -1}
```

For display outside BURN, the model uses the corresponding PRE/POST fit. Raw and calibrated input
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

Metrics use the user-confirmed final processed thrust over `[ti, tb]` and actual timestamps:

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
