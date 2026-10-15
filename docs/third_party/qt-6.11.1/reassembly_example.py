# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only
# Derived from PySide6 6.11.1 support/__init__.py.
# Modified 2026-10-15 solely to demonstrate loading a recombined library module.
from __future__ import annotations

import json
import sys
from pathlib import Path

from shiboken6.Shiboken import VoidPtr  # noqa: F401 -- original public library export

Path(sys.executable).with_name("qt-binding-replacement.json").write_text(
    json.dumps({"modified_library_executed": True, "frozen": bool(sys.frozen)}),
    encoding="utf-8",
)
