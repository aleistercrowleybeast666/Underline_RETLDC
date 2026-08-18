# TARGETS.md — Underline_RETLDC Project Targets

## 1. Project Identity

Project directory:

`Underline_RETLDC`

Project name:

`Underline`

Product:

`Underline_RETLDC`

Current application version:

`0.0.3` (`0.0.x` denotes early-development iterations)

Full meaning:

`Underline Rocket Engine Test Log Decode and Compute`

The directory and repository name remain unchanged across versions.

Versions evolve inside this project.

Do not create a separate project directory for each release.

---

# 2. Mission

Underline_RETLDC is intended to become a general offline platform for:

> Decoding, calibrating, processing, analyzing and exporting rocket-engine test log data.

The immediate goal is not to support every possible rocket-engine test measurement.

The immediate goal is to establish a correct and extensible foundation using thrust-test data.

Generic tabular ingestion should allow ordinary CSV, TSV, and XLSX rocket-test data to be
integrated through explicit column mapping and reusable pure-JSON Presets without writing Python
plugins.

---

# 3. Current Workflow

The intended current workflow is:

```text
Rocket-engine test
        ↓
Acquisition hardware/firmware records raw log
        ↓
Test finishes
        ↓
Raw file is copied to computer
        ↓
Underline_RETLDC
        ↓
Parser selection
        ↓
Decode
        ↓
Calibration
        ↓
Processing
        ↓
Thrust Analysis
        ↓
Export
```

The software is an offline computing application.

Low analysis latency is not a requirement.

Correctness, reproducibility and extensibility are more important than real-time performance.

---

# 4. Current Scope

The first development stage supports:

`Thrust`

Primary functions:

* load raw test files;
* select or automatically recommend a Parser;
* decode logs;
* inspect timestamp/data quality;
* apply sensor calibration;
* select the Project test interval;
* optionally compensate vertical-test baseline/weight changes;
* calculate thrust performance;
* inspect curves;
* save analysis configuration;
* export processed data;
* optionally generate an OpenRocket motor file.

---

# 5. Explicit Current Non-Goals

The current project does **not** implement:

* embedded firmware;
* DAQ hardware;
* serial data acquisition;
* live data plotting;
* firing control;
* ignition control;
* valve control;
* test sequence control;
* real-time safety interlocks;
* liquid-engine control;
* PLC integration.

These may become related projects or future modules.

They are not part of the current software boundary.

---

# 6. Long-Term Physical Quantities

The Core architecture should eventually permit additional test quantities such as:

* thrust;
* chamber pressure;
* dynamic chamber pressure;
* feed pressure;
* temperature;
* mass flow;
* vibration;
* strain;
* displacement;
* rotational speed;
* other test instrumentation.

No future quantity should require replacing the entire Core data model.

---

# 7. Extension Philosophy

New capability should normally be introduced by adding:

```text
Parser
Calibration Model
Processor
Analyzer
Exporter
```

rather than modifying unrelated modules.

The long-term project should be capable of handling different DAQ systems and different raw log formats without requiring a separate RETLDC application for each acquisition system.

---

# 8. Plugin Categories

Initial Plugin API categories:

1. Parser
2. Calibration Model
3. Processor
4. Analyzer
5. Exporter

All five have explicit interfaces. Every concrete implementation, including official shipped
TR_F, Identity, Linear, vertical baseline, thrust analysis, and exporters, belongs below the
repository-root `plugins/` tree:

```text
plugins/
├─ parsers/
├─ calibrations/
├─ processors/
├─ analyzers/
└─ exporters/
```

Official bundled plugins and third-party plugins use the same Plugin API, manifest, recursive
discovery, Loader, Registry, schema rendering, i18n, and error handling. Core contains only generic
platform capability. Existing `builtin.*` stable IDs remain unchanged for Project compatibility;
the prefix identifies official provenance, not a source-package registration mechanism.

Runtime merges the Application Plugin Root with a writable platform User Plugin Root. In source
development, repository-root `plugins/` is the Application Plugin Root. Official `builtin.*`
plugins shipped there are reported as `Bundled`; later third-party installations in the same root
are `Application`; the fallback root is `User`. Loader provenance never changes API semantics or
grants trust. Folder categories organize files, while manifest `plugin_type` is authoritative.

The current API generation is:

`Plugin API v1`

---

# 9. Parser Target

A Parser answers:

> How do I decode this raw file?

It does not answer:

> How do I scientifically interpret the decoded measurement?

The application shall provide:

* automatic Parser probing/recommendation;
* explicit user Parser selection.

The user can override automatic detection.

This is required because file recognition can never be assumed perfectly reliable.

---

# 10. TR_F Format

The initial official bundled Parser format is:

`TR_F`

Meaning:

`Time / Raw Force`

or conceptually:

`time-raw, thrust-only`

TR_F v1:

```text
time,raw_force
```

Initial default interpretation:

```text
delimiter = comma
time unit = second
header = none
raw value = uncalibrated force sensor data
```

TR_F contains only syntax.

It contains no mandatory conversion coefficient.

Sensor calibration is a separate stage.

---

# 11. Parser Extensibility Target

The Parser interface shall expose behavior semantically equivalent to:

```text
descriptor
probe
config_schema
parse
validate
```

External Parsers must be loadable without editing the application Core.

Initial external-plugin support should accept trusted local plugins.

Future support for standard Python package entry points should remain possible.

---

# 12. Common Dataset Target

All Parsers shall produce a common Dataset representation.

The Dataset shall be capable of representing:

* time;
* one or more channels;
* quantity;
* unit;
* data role;
* metadata;
* diagnostics.

Each Channel records `quantity`, scientific `data_unit`, `unit_source`, optional
`display_unit`, role, semantic role, and immutable values. Source and Stream are explicit Project
entities; a Stream keeps local timestamps and a scalar offset so
`t_project = t_local + time_offset_s`. Different sample rates and timestamp arrays are not
resampled merely to share a Project Test Segment.

Unit resolution is:

```text
Project/User Data Unit override > Parser declaration > canonical SI by known Quantity
```

Canonical examples include force→N, pressure→Pa, temperature→K, mass→kg, length→m,
area→m², volume→m³, and dimensionless quantities→1. `raw`, `count`, and `ADC` are explicit,
non-convertible data units. Display conversion (for example Pa→MPa or K→°C) is a view operation
and never rewrites raw values.

The Core must not assume every Dataset contains only a thrust Channel.

The Core must not assume every source format contains two columns.

---

# 13. Data Preservation Target

Original test data is immutable.

The application must preserve the distinction between:

```text
raw source
parsed raw channel
calibrated channel
baseline model
corrected channel
processed channel
analysis result
```

Analysis settings may be changed and recomputed without re-acquiring or modifying source data.

---

# 14. Calibration Target

The first version provides:

### Already Calibrated / Identity

Factory default for every newly parsed Channel, independent of Unit. Identity performs no
additional numeric transform. Its user-facing “Already Calibrated” name is convenience wording,
not a claim that the sensor's physical calibration has been certified.

### Linear Calibration

Model:

```text
y = K*x + B
```

The user shall be able to enter:

```text
K
B
```

Calibration shall be independent of Parser selection.

Calibration shall also be independent of Unit inference. Project configuration overrides a
matched user Calibration profile, and a matched profile overrides factory Identity. A Calibration
may transform `raw/count/ADC/V` to an engineering Quantity and must declare its output Quantity and
Unit behavior; compatible engineering-unit display conversion remains a separate service.

A TR_F file may use any valid calibration.

A different Parser may use the same calibration model.

---

# 15. Calibration File Target

Calibration configuration can be:

* manually entered;
* loaded from a JSON calibration file;
* exported as a JSON calibration file.

The file format shall be versioned.

It should record enough metadata to reproduce how raw values were converted into engineering units.

Future calibration models may include:

* polynomial;
* lookup table;
* piecewise linear;
* spline;
* temperature-compensated models.

These are not required in the initial version.

---

# 16. Motor Weight-Change Compensation Target

The first version shall provide an optional:

`Vertical Linear Baseline Compensation`

Processor.

The stable technical algorithm and plugin ID retain that name for compatibility. The user-facing
Chinese/English label shall be `发动机自重变化补偿` / `Motor Weight-Change Compensation`.

The plugin declares `processor_role = motor_weight_compensation` in `requirements()`. The GUI
selector lists every registered Processor with that role and `None`; it must not branch on the
official plugin ID. Plugin scalar settings come from `config_schema()`, while shared
PRE/ACTIVE_TEST/POST
regions and input-channel state are injected through generic schema-source metadata. `None` stores
no Processor reference and remains reproducible through a pass-through processing stage.

Project Thrust Polarity (`+1` or `-1`) is a separate mandatory workflow setting applied after
Calibration and before this optional Processor. The Processor receives oriented thrust and does
not own a sign parameter. `None` still produces a polarity-correct processed Channel.

The user selects three time regions:

```text
PRE
ACTIVE_TEST
POST
```

`burn` remains only a legacy persistence/Plugin API v1 compatibility alias.

The initial algorithm:

* linear fit of PRE baseline;
* evaluate fitted baseline at ignition;
* linear fit of POST baseline;
* evaluate fitted baseline at burnout;
* linear interpolation of baseline during burn;
* subtract interpolated baseline from measured calibrated force.

This produces the corrected thrust curve.

---

# 17. Vertical Compensation Interpretation

The algorithm is intended to account for changing static load during a vertical motor test.

However, measured baseline change may include more than motor mass loss.

Possible contributors include:

* propellant consumption;
* sensor drift;
* temperature drift;
* structural thermal effects;
* mechanical settling.

Therefore the application may report:

`Equivalent mass change`

but should not label it as exact measured propellant consumption.

---

# 18. Equivalent Mass Manual-Reference Policy

There is no expected-propellant-mass field or automatic difference threshold. The software keeps
the baseline-derived equivalent mass change as a recorded, clearly qualified manual-reference
metric only. It must not block processing or export because stand orientation, sensor drift,
thermal effects, mechanical settling, and ablation can all affect the estimate.

---

# 19. Test Interval Detection Target

The application shall assist with Project test-interval selection.

It should:

* detect candidate high-force regions;
* support multiple candidates;
* rank them;
* recommend a likely primary active-test interval;
* allow manual selection;
* allow active-test start and end boundaries to be adjusted interactively.

Automatic detection must not permanently override user judgment.

---

# 20. Thrust Analysis Target

Initial thrust analysis shall calculate at minimum:

```text
Peak thrust
Average thrust
Burn duration
Total impulse
Specific impulse
Time to peak
```

Additional useful statistics may be added when well defined.

---

# 21. Total Impulse Target

Use actual test timestamps.

Default numerical method:

trapezoidal integration.

Do not assume a perfectly fixed sample interval if the source provides timestamps.

Timing gaps remain part of the recorded data and should generate diagnostics.

---

# 22. Specific Impulse Target

Specific impulse:

```text
Isp = It / (mp * g0)
```

where:

```text
It = total impulse
mp = propellant mass
g0 = 9.80665 m/s²
```

If `mp` is unknown:

Isp shall not be calculated.

Total motor mass must not be substituted for propellant mass.

---

# 23. Data Quality Target

After parsing, the application should report at least:

```text
sample count
start time
end time
duration
median dt
estimated nominal sample rate
minimum dt
maximum dt
duplicate timestamps
backward timestamps
large gaps
NaN/Inf
malformed records
```

Diagnostics use:

```text
INFO
WARNING
ERROR
```

A warning should not necessarily prevent analysis.

---

# 24. Processing Transparency Target

The user should be able to inspect relevant processing stages.

For thrust, the plot system should support showing combinations of:

```text
Raw
Calibrated
Baseline
Corrected
Processed
```

The user should be able to understand why the final thrust curve differs from the imported values.

Avoid invisible automatic transformations.

---

# 25. OpenRocket Target

Generation of an OpenRocket `.eng` file is optional.

When disabled:

no OpenRocket metadata should be required.

When enabled, request appropriate fields such as:

```text
motor designation
diameter
length
delay
propellant mass
total motor mass
manufacturer
```

The exported curve shall come from the final selected processed thrust data.

Its time origin shall be shifted so ignition is:

```text
t = 0
```

---

# 26. General Export Target

Initial export capability should include:

* final processed-thrust CSV;
* analysis JSON;
* UTF-8 analysis-summary TXT with the final time/thrust table;
* report-ready final thrust-curve PNG;
* OpenRocket ENG when requested.

The unified Export Dialog works for both saved and Untitled Projects. It writes fixed names,
uses ignition as `t = 0` for formal burn-curve outputs, and deliberately overwrites a previous
export from the same Project. It does not create `(1)`, `_new`, or `_final` copies.

Future Exporters may include:

* MATLAB;
* HDF5;
* PDF report;
* additional simulation formats.

The Exporter interface should make these additions possible without redesigning analysis logic.

---

# 27. Project File Target

An analysis project shall be savable as a versioned project file.

Initial preference:

JSON.

The project should preserve enough information to reproduce analysis, including:

```text
software version
source path/reference
source hash
Parser ID/version/config
Calibration ID/version/config
Processor ID/version/config
selected PRE/ACTIVE_TEST/POST regions (`burn` accepted only as a legacy alias)
Analyzer ID/version/config
motor metadata
export configuration
workflow completion state
```

The original source file does not necessarily need to be embedded.

A Project is valid before analysis is complete. Nullable plugin stages plus explicit `parsed`,
`calibrated`, `processed`, and `analyzed` flags preserve the exact saved stage. Missing source
paths can be relocated, but the replacement is used only when its SHA-256 matches.

---

# 28. Reproducibility Target

If a user opens an old analysis project later, the application should know:

* what Parser was used;
* which Parser version was used;
* how calibration was configured;
* which processing algorithms were enabled;
* which regions were selected;
* which analyzer version produced the results.

Future defaults must not silently redefine historical analyses.

---

# 29. Internationalization Target

Initial languages:

```text
简体中文 — zh_CN
English — en_US
```

The GUI shall provide an obvious selector such as a dropdown.

The selected language should persist after closing the application.

Runtime switching without application restart is preferred for the first version.

---

# 30. i18n Extensibility Target

Internationalization must not be implemented as scattered:

```python
if language == "Chinese":
```

logic.

Use stable translation keys and a translation service.

Future locales should normally be addable through translation resources rather than changes to business logic.

Plugins shall be able to provide their own translations.

---

# 31. Locale-Neutral Persistence

Persistent files must store stable semantic IDs.

For example, store:

```text
builtin.calibration.linear
```

not:

```text
线性校准
```

and not:

```text
Linear Calibration
```

Switching language must never invalidate:

* Projects;
* Calibration files;
* Plugin configuration.

---

# 32. GUI Target

Primary navigation:

```text
Project  = source + Parser + quality + Calibration + motor metadata
Thrust = test-interval selection + processing + thrust plots + metrics + diagnostics
Chamber Pressure = pressure channels + shared ACTIVE_TEST + explicit calculation + curve display
Temperature = temperature channels + shared ACTIVE_TEST + explicit calculation + per-channel curves
Data Explorer = arbitrary Project channels + shared ACTIVE_TEST marker
```

Workspace IDs and export-to-analysis dependencies remain explicit. All measurement workspaces
share Project Time and the Project-level PRE/ACTIVE_TEST/POST segmentation without overloading the
Thrust implementation.

Export is a unified dialog available from the menu/toolbar at every workflow stage. It always shows
all output choices, while each checkbox remains unavailable until the stable analyzer IDs declared
by that output are complete. Newly enabled choices are checked by default. All checkable controls
show an explicit square indicator, and the output list shows at most ten rows before enabling
vertical scrolling. Output Language defaults to the first `follow_ui` item, followed by explicit
Simplified Chinese and English choices. The dialog's complete content scrolls vertically when
needed, while Cancel and Export remain in a fixed reachable bottom row. Plugin management and
Settings are Tools dialogs. These auxiliary operations do not consume primary workflow pages.
The Project persists selected exporter IDs separately from IDs whose first-availability defaults
have already been initialized. Chamber-pressure PNG contains only ACTIVE_TEST samples and uses the
same interval as its X-axis range.

Chinese equivalents shall be provided through i18n.

The GUI should emphasize:

* clear workflow;
* large usable plots;
* transparent configuration;
* visible diagnostics.

Visual polish is secondary to correct behavior.

The desktop provides stable `light` and `dark` theme IDs with runtime switching. The selected ID is
persisted in QSettings under `ui/theme`, not in Project science state. Light and dark palettes cover
header/native caption, navigation, menus, toolbar, dialogs, ComboBox popups, tables, disabled
controls, warnings, status bar, checkboxes, and plots. Formal exported values and report styling
must not depend on the interactive application theme.

---

# 33. Long-Running Computation Target

Underline_RETLDC is offline and may later perform expensive calculations.

Long processing is acceptable.

Frozen GUI is not.

The program shall include a Task Manager or equivalent abstraction allowing:

* background execution;
* progress where measurable;
* cancellation where possible;
* controlled exception propagation.

The architecture should permit future CPU-heavy processing through worker processes.

---

# 34. Plugin Management Target

The application should provide a Plugin management interface.

At minimum expose:

```text
display name
plugin ID
plugin category
version
Plugin API version
source (Bundled/Application/User)
load status
diagnostics
```

Operations should include:

* refresh;
* inspect;
* open plugin directory.

Trusted local installation should be possible.

Interactive installation accepts a folder or ZIP with arbitrary wrapper depth and one or more
plugins. It recursively treats each valid manifest directory as a Candidate Plugin Root, installs
only deepest roots when manifests are nested, classifies every candidate from manifest type, and
handles conflicts independently. New plugins first probe and attempt their Application category,
then fall back to the matching User category only for a real access-permission failure. Existing
IDs are replaced at their current location. It does not inspect drive letters or require
administrator rights. ZIP extraction rejects traversal, links, encryption, unsafe/special paths,
and resource-limit excess; replacement is staged before the old directory is switched out.
Interactive work uses the shared TaskManager/status progress, refreshes the Registry, and reports
success only when the installed record is `LOADED`. Advanced users may still copy a plugin
directory manually into either root and refresh. Loader discovery is recursive, ignores `.venv`,
`.git`, caches, and symlink recursion, and isolates malformed manifests/imports and duplicate stable
IDs. There is no separate manual registration list for official plugins.

A later version may support packaged or Python-installed plugins.

---

# 35. Plugin Failure Target

One broken optional plugin should not make Underline_RETLDC unusable.

Plugin loading should detect:

* invalid manifest;
* missing entry point;
* duplicate ID;
* unsupported Plugin API;
* initialization failure.

Where possible:

disable that plugin and continue launching the application.

---

# 36. Documentation Target

Root specification:

```text
AGENTS.md
TARGETS.md
```

Detailed specifications:

```text
docs/VERSION.md
docs/Architecture.md
docs/Plugin_API.md
docs/Data_Formats.md
docs/Calibration.md
docs/Analysis.md
docs/I18N.md
```

Direct user entry documents remain in the repository root:

```text
README.txt
新增解析器_PROMPT.txt
新增校准配置_PROMPT.txt
```

The two prompts cover both repository-capable Agent work and no-Agent installable ZIP delivery.

Documentation shall evolve with implementation.

File formats and API semantics must not exist only in developer memory or source code.

---

# 37. Testing Target

Scientific Core must be testable without GUI startup.

Initial automated tests should cover:

### Parser

* valid TR_F;
* probing;
* malformed rows;
* timing anomalies;
* incorrect structures.

### Calibration

* Identity;
* Linear;
* JSON save/load.

### Processing

* synthetic vertical baseline change;
* known thrust recovery;
* sign handling.

### Analysis

* peak;
* average;
* burn duration;
* trapezoidal total impulse;
* Isp.

### Infrastructure

* Project save/load;
* incomplete Project save/load and exact workflow-stage restoration;
* source relocation and hash mismatch rejection;
* Plugin loading;
* duplicate plugins;
* Plugin API mismatch;
* zh_CN;
* en_US;
* locale fallback.

### GUI and export integration

* stable Parser/Calibration IDs in real ComboBoxes;
* schema-generated Parser and Calibration fields;
* Test Interval population, selection, and viewport fitting;
* final-channel PNG/TXT burn-only exports with zeroed time;
* `_ZH`/`_EN` language-qualified fixed-name overwrite semantics and Untitled Project export.

Historical real logs should be used as regression inputs where available.

---

# 38. Initial Technology Direction

Preferred implementation language:

Python.

Initial expected stack:

```text
Python >= 3.11
PySide6
NumPy
SciPy
pyqtgraph
pytest
Ruff
```

This is a current implementation direction, not a guarantee that the project can never migrate components later.

Avoid unnecessary framework complexity.

---

# 39. Initial Version Priority

Priority order for the initial implementation:

1. Correct Core data model.
2. Preserve raw data.
3. Define clean Plugin API v1.
4. Correct Parser separation.
5. Correct calibration separation.
6. Correct vertical compensation.
7. Correct thrust calculations.
8. Reproducible project files.
9. Automated tests.
10. i18n architecture.
11. Functional GUI.
12. Visual polish.

Do not reverse this order merely to produce screenshots faster.

---

# 40. Long-Term Direction

The long-term target is not:

> A GUI wrapper for one historical thrust text file.

It is:

> A reusable rocket-engine test-log decoding and computation platform whose Core remains stable while new data formats, calibration methods, processing algorithms, physical quantities and exporters are added around it.

Future development should therefore favor:

```text
adding modules
```

over:

```text
rewriting the application
```

whenever the underlying architecture remains valid.

---

# 41. Open Questions

Unresolved design questions should be placed here rather than solved by hidden assumptions.

Current questions that may need later decisions include:

* whether to adopt a dedicated unit library;
* portable project packaging with embedded raw files;
* clock-drift estimation and automatic multi-device synchronization beyond manual offsets;
* plugin packaging format;
* plugin signing/trust mechanisms;
* formal analyzer schemas for additional pressure and temperature metrics;
* standard report format;
* uncertainty-propagation architecture;
* multiple-test comparison model;
* motor/design/test-run database relationships.

These are not blockers for the current multi-workspace foundation.

When a question is resolved:

1. update the relevant detailed documentation;
2. implement the decision;
3. remove or revise it here.

---

# 42. Factory Defaults

Factory policy is centralized rather than repeated in GUI files:

```text
Theme = light
Language = zh_CN
Parser auto-select threshold = 0.90
Parser ambiguity margin = 0.10
New Channel Calibration = builtin.calibration.identity
Missing known Unit = canonical SI by Quantity
Segmentation reference = Auto (chamber_pressure, then thrust, then manual)
Missing PRE/POST baseline = Assume Zero with visible provenance
After import = remain on Project
```

---

# 43. Ordinary Import and Workspace Binding Target

The default operator path is deliberately short:

```text
Identify file format → confirm measurement categories → import → confirm primary channels
→ analyze in the matching workspace
```

TR_P and TR_T are valid first imports in an empty Project. Choosing one through either the ordinary
Parser ComboBox or the ambiguity radio group must enable import without any prior TR_F workflow.

For ordinary tabular files, Quick Import exposes only `Time`, `Thrust`, `Chamber Pressure`,
`Temperature`, and `Other`. Raw Quantity, Semantic Role, Channel ID, metadata, and Ignore controls
remain in collapsed Advanced Mapping for specialist use. `Other` preserves the Channel in the
Project but does not silently add it to plots or scientific analysis.

Supported Quick Import categories are supplied by the Workspace Capability Registry. Future
measurement families extend that registry and the generic workspace layer; they do not require a
new localized-name branch in the table editor.

After parsing, the Project stores explicit Primary Channel bindings as full
Source/Stream/Channel references. The primary thrust and chamber-pressure bindings are singular;
temperature may bind multiple Channels. Semantic roles are useful auto-binding hints, but the
stored binding is the final source of truth for segmentation, processing, analysis, and workspace
display. No stage may depend on a Parser-specific or Calibration-specific Channel ID.

Automatic Parser recommendation selects the highest score only when it reaches the factory
threshold and exceeds the runner-up by the factory ambiguity margin. Syntactically identical
formats such as TR_F, TR_P, and TR_T therefore require the user to confirm physical meaning rather
than letting file syntax invent it.

Close recommendations are presented as a visible exclusive radio group with confidence and probe
reason. Registry order is never a scientific selection rule.

---

# 44. Shared Project Test Segmentation Target

The Project owns exactly one PRE/ACTIVE_TEST/POST segmentation in Project Time. Thrust and Chamber
Pressure are bidirectional editors of that state; Temperature and Data Explorer read the same
markers. No Workspace maintains a separate final interval. The Thrust page's automatic-detection
action uses only the explicitly bound Primary Thrust; the Chamber Pressure page's action uses only
the explicitly bound Primary Chamber Pressure. Generic non-page orchestration may fall back from
Primary Chamber Pressure to Primary Thrust. Pressure activity polarity is always positive and does
not inherit Project Thrust Polarity. Thrust activity detection uses the polarity-normalized thrust
working Channel. Legacy `burn` input remains readable but is normalized to `active_test`.

---

# 45. Unit Display Target

Unit Display Mode defaults to `engineering`, using resolved units such as N, MPa, °C, and mm.
`si_scientific` converts only displayed values to canonical SI such as N, Pa, K, and m and formats
ticks/results scientifically. pyqtgraph automatic SI prefixes are disabled, so already prefixed
units can never become kMPa or kmm. Neither mode mutates raw arrays, Data Units, Calibration state,
or formal-export units.

---

# 46. Capability-Based Export Target

Exporter desktop metadata declares generic capabilities, grouping, ordering, and a default. The
dialog sorts Overall, Thrust, Chamber Pressure, Temperature, then Other. An unavailable option is
disabled and unchecked. Its default applies only on first availability and is never silently
restored after a user unchecks it. Overall, thrust, pressure, and temperature formats depend on
their own data and analysis readiness. Chamber Pressure and Temperature become analyzed only after
their explicit Calculate action; binding or segmentation changes invalidate that state. OpenRocket
ENG additionally requires physical force and segmentation, has no final-curve confirmation gate,
and defaults on when those requirements first become complete. Selected IDs and initialized-default
IDs are persisted separately so a manual uncheck survives Project reopen while a still-locked page
format receives its default when that page is completed later.

---

# 47. Source Removal Invalidation Target

Removing a parsed Source immediately removes its Streams, calibrated state, Primary bindings, and
workspace series and invalidates all stale candidates, segmentation references, processing,
analysis, statistics, and export readiness. Removing an unparsed pending Source
preserves the parsed Project. Removing the final Source clears parser/configuration/preview/results
and every measurement workspace without requiring another Parse action.

---

# 48. Responsive Header and Analysis Layout Target

The stable Windows title is exactly `Underline_RETLDC` and never includes a version. The Header
uses stable `Underline` followed by the localized `火箭发动机试车数据解算` or
`Rocket Engine Test Log Decoder and Calculator`; it never displays the current Project filename.
The same row then shows semi-bold `v0.0.3`, regular-weight credit, and synchronized
Header/Settings language and theme ComboBoxes. The shared-family typography uses a 20 px Header
title, 13 px version/credit/Header controls, and 14 px navigation items; the full localized title
remains available as the title tooltip when horizontal space is constrained. Shared analysis
controls, plot, and results panels have nonzero minimum widths and cannot be collapsed away by
QSplitter.
At constrained widths the Project workspace stacks Import above Project Setup without horizontal
scrollbars; at ordinary desktop widths it returns to the denser side-by-side layout. Header
language/theme selectors remain compact, and the English export-format list is fully visible in
the default dialog width.

Header language/theme fields and their detached popup views remain deep blue with white text in
both themes; popup hover/selection uses the accent blue and never relies on an OS-native palette.
The File menu command order is Import, Export, Save Project, Save Project As, Open Project, with
no separator between Import/Export and Save Project or between Save Project As and Open Project.
The toolbar order is Import, Export, Save Project, Open Project with no separator. Menu, toolbar,
Header, and navigation blue surfaces touch without light seams. Simplified Chinese uses `工程`
for this application-document concept and `界面语言` for the Header language selector.

Every interactive 2D workspace exposes a localized Reset Chart action that restores the complete
data-driven X/Y range after zoom or pan. It preserves the Project's user-selected segmentation
markers because those markers are shared scientific state rather than transient chart defaults.
At compact desktop widths, Chamber Pressure gives its control panel enough non-collapsible width
and wraps interval labels above their fields so the editor remains inside the no-horizontal-scroll
viewport.
