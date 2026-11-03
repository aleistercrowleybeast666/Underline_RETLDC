"""Headless project export using the same replay, snapshot and plugin as the GUI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from underline_retldc.app.export_snapshot import ExportSnapshot_Build
from underline_retldc.app.project_pipeline import DEFAULT_CALIBRATION_ID, ProjectPipeline
from underline_retldc.core.project import Project_Load
from underline_retldc.core.registry import PluginLoadResult, PluginRegistry
from underline_retldc.plugin_api.common import TaskContext
from underline_retldc.plugins.loader import PluginDiscoveryRoot, PluginLoader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    export = subcommands.add_parser("export", help="Export a completed saved project")
    export.add_argument("project", type=Path)
    export.add_argument("output", type=Path)
    export.add_argument("--exporter", default="builtin.exporter.treediagram_motor")
    export.add_argument("--maximum-gap-s", type=float, default=0.1)
    export.add_argument(
        "--relocate",
        action="append",
        default=[],
        metavar="SOURCE_ID=PATH",
        help="Explicit source relocation; the recorded SHA-256 must match",
    )
    application_root = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
                        else Path(__file__).resolve().parents[2])
    export.add_argument("--plugin-root", type=Path, default=application_root / "plugins")
    options = parser.parse_args(argv)
    try:
        registry = PluginRegistry()
        document = Project_Load(options.project)
        required = {options.exporter, DEFAULT_CALIBRATION_ID}
        for reference in (document.parser, document.calibration, document.analyzer,
                          *document.processors, *(source.parser for source in document.sources),
                          *(channel.calibration for channel in document.channels.values())):
            if reference is not None:
                required.add(reference.id)
        for saved in document.source_analyses.values():
            if saved.completed:
                if saved.config.workspace_id == "thrust_analysis":
                    required.add(str(saved.calculator["id"]))
                if saved.config.processor:
                    required.add(str(saved.config.processor["id"]))
        records = PluginLoader(registry).discover(
            (PluginDiscoveryRoot(options.plugin_root, "bundled"),), selected_ids=required,
        )
        failures = [record for record in records if record.plugin_id in required
                    and record.result != PluginLoadResult.LOADED]
        if failures:
            raise ValueError(
                "Plugin loading failed: "
                + "; ".join(str(record.diagnostics) for record in failures)
            )
        missing = required.difference(record.plugin_id for record in records)
        if missing:
            raise ValueError("Required plugins are not installed: " + ", ".join(sorted(missing)))
        exporter = registry.get(options.exporter)
        context = TaskContext()
        relocated = {}
        for item in options.relocate:
            source_id, separator, path = item.partition("=")
            if not separator or not source_id or not path or source_id in relocated:
                raise ValueError("Each --relocate requires a unique SOURCE_ID=PATH")
            relocated[source_id] = Path(path)
        session = ProjectPipeline.Project_LoadSession(
            options.project,
            registry,
            context,
            relocated_sources=relocated,
        )
        metadata = exporter.config_schema().get("x-underline-retldc-export", {})
        snapshot = ExportSnapshot_Build(
            session, registry, group_id=metadata.get("group_id", "thrust")
        )
        config = {
            **session.motor_metadata,
            **snapshot.Config_Copy(),
            "maximum_gap_s": options.maximum_gap_s,
            "output_locale": "en_US",
        }
        result = exporter.export(
            options.output, snapshot.dataset, snapshot.analysis, config, context
        )
        print(
            json.dumps(
                {"output": str(result.destination.resolve()), **result.metadata}, ensure_ascii=False
            )
        )
        return 0
    except (OSError, KeyError, TypeError, ValueError) as exc:
        parser.exit(2, f"Export failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
