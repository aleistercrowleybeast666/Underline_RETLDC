"""Shared immutable input identity at the real parser boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from underline_retldc.core.project import Project_SourceHash, ProjectSourceHashMismatchError
from underline_retldc.plugin_api.common import ParseResult, TaskContext
from underline_retldc.plugin_api.parser import ParserPlugin


def Source_ParseVerified(
    parser: ParserPlugin,
    path: Path,
    config: Mapping[str, Any],
    context: TaskContext,
    *,
    expected_sha256: str | None = None,
) -> ParseResult:
    """Reject changed inputs; bind the hash observed at parse to the resulting arrays."""
    context.raise_if_cancelled()
    before = Project_SourceHash(path)
    if expected_sha256 is not None and expected_sha256 != before:
        raise ProjectSourceHashMismatchError(expected_sha256, before)
    parsed = parser.parse(path, config, context)
    context.raise_if_cancelled()
    after = Project_SourceHash(path)
    if before != after:
        raise ProjectSourceHashMismatchError(before, after)
    return replace(
        parsed,
        dataset=replace(
            parsed.dataset,
            metadata={
                **parsed.dataset.metadata,
                "source_sha256": before,
            },
        ),
    )
