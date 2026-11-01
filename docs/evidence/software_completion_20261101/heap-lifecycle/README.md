# Qt object lifetime investigation

This file preserves the first investigation phase and its failed ordinary full run.
The subsequent native-menu/hidden-editor ownership fixes and independently recorded
full-suite results are in [owners-v2/README.md](owners-v2/README.md). Historical raw
diagnostic scripts now use `.py.txt` carriers with unchanged bytes; the original
paths and SHA-256 mapping are in `raw-snapshot-carriers.json`.

Baseline production commit: `c1f8ac76f9bbcde1076ef9e48624c920ad161960`.
This investigation follows the unchanged full pytest process exiting with
`0xc0000374` / `-1073740940`. Its stack was inside worker-side XML parsing and
garbage collection while the GUI waited for project reopening. This is the
detection site, not a proven native corruption cause.

All new scratch outputs live in
`.work/0.1.0-software-completion-20261101`; existing source files, saved projects,
and old evidence are preserved. No hardware, packaging, installation, cleanup,
or user-window operations are involved.

Initial read-only findings:

- Three actual plot-series removals followed by collection on a worker destroyed
  their item/curve/scatter objects on the GUI thread. This probe does not justify
  changing `AnalysisPlotWidget.clear_series`.
- Three ordinary export-dialog format transitions did not reproduce foreign-thread
  destruction. No production dialog change is justified by that probe alone.
- Three standalone, actual pyqtgraph ImageExporters each released their five
  Parameter child QObjects on the collecting worker thread.
- The new regression invokes the existing
  `ReleaseSmoke_BoundedPlotCheck`, retaining its real CSV/PNG/SVG checks. Its two
  temporary ImageExporters (root plus five children each) were all destroyed on
  worker 10796 instead of GUI 29452: **1 failed / 4.07 s**. The assertion explicitly
  requires correct disposal, rather than accepting a successful export as a
  lifetime proof.
- An additional diagnostic invokes the existing full portable-source-workflow
  test, records actual temporary exporters, and explicitly collects on the next
  task worker. It passed the scientific and persistence checks (24.87 s), while
  confirming GUI-created Parameter objects were destroyed on worker 10632.
  This controlled schedule exposes a specific lifetime defect; it did not
  reproduce the native heap exception and does not prove the two are identical.

Qt's [thread and QObject documentation](https://doc.qt.io/qt-6/threads-qobject.html)
requires deletion to respect object thread affinity and provides `deleteLater`
for event-loop disposal. pyqtgraph Parameter's logical parent/children are Python
references, separate from QObject parenting; dropping its exporter can leave a
reference cycle for an arbitrary Python collecting thread.

The full diagnostic run watches existing QObject wrappers and records
`destroyed` via direct connections before ordinary tasks. It is instrumented,
not an unmodified timing benchmark. An initial diagnostic collection error
(`main` launcher absent from the diagnostic script's import path) is retained;
the corrected runner matches `python -m pytest`'s repository import path.
Neither diagnostic disables global GC or changes a scientific expectation.

The complete instrumented baseline finished: **379 passed / 561.85 s**, exit 0.
It watched 152,519 wrapper identities, observed 151,486 destructions and no
destruction on a thread other than the observer's GUI thread. Scanning and signal
instrumentation affect collection timing; this run does not negate the ordinary
full-suite crash or the controlled actual-export regression.

## Scoped repair

Only `src/underline_retldc/app/release_smoke.py` changes production Python behavior.
Its three temporary ImageExporter creation sites use one context manager. The
manager requires the GUI thread, attaches the parameter root to QApplication,
mirrors the logical parameter tree with real QObject parents, and schedules root
deletion in `finally`. This also keeps resources owned until the GUI event loop
can process deferred deletion. Plot images, options, scientific calculations,
source input, persistent state, and the ordinary GUI layout are unchanged.

The existing full-source workflow remains an actual test of parsing, calculations,
CSV/PNG/SVG, source isolation, save and reopen. No assertion or input was removed,
no global GC setting changed, and no third-party module was patched. The added
second regression retains native wrappers after an injected export failure to
verify all C++ parameters become invalid after GUI retirement; a worker request
must be refused before constructing any export resource.

After the repair, the two lifecycle tests plus the original portable-source case
passed together: **3 passed / 33.69 s**. Initial Ruff on the new tests found two
nested-context style findings; they were combined without changing expectations.
Final whole-repository Ruff passed. The project-venv offscreen smoke entry point
also passed its real two-locale CSV/PNG/SVG checks and logged normal event-loop
exit and window close on one GUI thread; native-fault log is empty. This is not
a physical desktop or hardware test.

The same controlled worker-GC source-workflow probe was then repeated with the
scoped fix: **1 passed / 27.64 s**, with all 12 observed Parameter destructions
on GUI thread 15232. Its source hash is in `smoke-export-after.jsonl`; original
and repaired records remain separate. This directly closes the reproduced
temporary-exporter lifetime boundary.

The Windows Application Error journal for the failure period reports heap
corruption detected by `ntdll.dll` at offset `0x118095`; it does not identify
the earlier corrupting instruction. `gflags`, `cdb` and WinDbg were not found
on PATH or at the checked standard Windows SDK/Store locations. No debugger
was installed and no system-wide debugging/GC setting was changed.

**The subsequent uninstrumented full suite FAILED again**, with Windows
`0xc0000374`, exit `-1073740940`, and no complete pytest summary. The detecting
worker was again in XML parsing/GC during project reopen; the main-thread wait
is now at `release_smoke.py:730`. `full-after.log` and `full-after.exit` retain
the complete failure. The scoped fix did **not** close this native heap fault.

The raw original failure, intermediate collection-harness error, controlled
probes and all complete results are preserved separately. The `0xc0000374`
native fault has **no proven causal equivalence** to the repaired QObject
defect. Its root cause remains an actual software acceptance blocker, rather
than a hardware dependency or a completed fix. QObject-wide instrumentation
and explicit earlier worker collection both change the failing schedule;
their passing results are diagnostic observations, not substitutes for this
failed ordinary run.
