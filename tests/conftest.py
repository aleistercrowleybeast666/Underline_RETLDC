import os
from pathlib import Path

import pytest

from underline_retldc.core.registry import PluginLoadResult, PluginRegistry
from underline_retldc.plugins.loader import PluginDiscoveryRoot, PluginLoader

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def bundled_registry() -> PluginRegistry:
    root = Path(__file__).resolve().parents[1] / "plugins"
    registry = PluginRegistry()
    records = PluginLoader(registry).discover(
        (PluginDiscoveryRoot(root, "bundled"),)
    )
    assert records
    assert all(record.result is PluginLoadResult.LOADED for record in records)
    return registry
