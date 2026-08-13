from __future__ import annotations

import os
import shutil
from pathlib import Path

from underline_retldc.plugin_api.common import PluginType
from underline_retldc.plugins.manifest import Manifest_Load

PLUGIN_CATEGORY_DIRECTORIES = {
    PluginType.PARSER: "parsers",
    PluginType.CALIBRATION: "calibrations",
    PluginType.PROCESSOR: "processors",
    PluginType.ANALYZER: "analyzers",
    PluginType.EXPORTER: "exporters",
}


def Plugin_UserDirectory() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "Underline_RETLDC" / "plugins"


def PluginInstaller_InstallDirectory(source: Path, destination_root: Path) -> Path:
    source = Path(source).resolve()
    manifest = Manifest_Load(source / "plugin.json")
    destination_root = Path(destination_root).resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    safe_name = manifest.plugin_id.replace(".", "_")
    destination = (
        destination_root
        / PLUGIN_CATEGORY_DIRECTORIES[manifest.plugin_type]
        / safe_name
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Plugin destination already exists: {destination}")
    shutil.copytree(source, destination)
    return destination
