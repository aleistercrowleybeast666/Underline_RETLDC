from __future__ import annotations

import faulthandler
import json
import os
import threading
import time
from pathlib import Path
from typing import TextIO


class NativeDiagnostics:
    """Optional owned smoke-run phase journal and native-fault Python stack capture."""

    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.fault_stream: TextIO = (directory / "native-fault.log").open("w", encoding="utf-8")
        self.phase_stream: TextIO = (directory / "native-phases.jsonl").open("w", encoding="utf-8")
        faulthandler.enable(file=self.fault_stream, all_threads=True)
        self.phase("diagnostics.ready")

    def phase(self, name: str, **values: object) -> None:
        self.phase_stream.write(json.dumps({
            "phase": name, "monotonic_s": time.monotonic(),
            "thread_id": threading.get_ident(), **values,
        }) + "\n")
        self.phase_stream.flush()

    def close(self) -> None:
        self.phase("diagnostics.close")
        faulthandler.disable()
        self.fault_stream.close()
        self.phase_stream.close()


def NativeDiagnostics_FromEnvironment(enabled: bool) -> NativeDiagnostics | None:
    directory = os.environ.get("UNDERLINE_NATIVE_DIAGNOSTICS_DIR")
    return NativeDiagnostics(Path(directory)) if enabled and directory else None
