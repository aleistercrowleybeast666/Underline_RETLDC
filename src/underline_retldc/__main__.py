from __future__ import annotations

import importlib
import sys
from pathlib import Path

if __package__:
    application = importlib.import_module("underline_retldc.app.application")
    raise SystemExit(application.main())

project_root = Path(__file__).resolve().parents[2]
project_path = str(project_root)
if project_path not in sys.path:
    sys.path.insert(0, project_path)
launcher = importlib.import_module("main")
raise SystemExit(int(launcher.Launcher_Run(sys.argv[1:])))
