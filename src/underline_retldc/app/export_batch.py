"""Publish a set of export files only after all selected exporters have completed."""
from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from underline_retldc.plugin_api.common import TaskContext


@contextmanager
def ExportBatch_Stage(
    directory: Path, filenames: Iterable[str], context: TaskContext,
) -> Iterator[Path]:
    names = tuple(filenames)
    if (not names or any(not name or Path(name).name != name or name in {".", ".."}
                         for name in names)
            or len({name.casefold() for name in names}) != len(names)):
        raise ValueError("Each exporter needs a distinct file name inside the destination")
    directory.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix=".underline-export-", dir=directory))
    outputs, backups = root / "pending", root / "previous"
    committed: list[str] = []
    retain_backups = False
    try:
        outputs.mkdir()
        backups.mkdir()
        yield outputs
        context.raise_if_cancelled()
        for name in names:
            staged = outputs / name
            target = directory / name
            if staged.is_symlink() or not staged.is_file():
                raise ValueError(f"Exporter did not produce the requested file: {name}")
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise ValueError(f"Export target is not an ordinary file: {target}")
            if target.is_file():
                shutil.copy2(target, backups / name)
        try:
            for name in names:
                context.raise_if_cancelled()
                os.replace(outputs / name, directory / name)
                committed.append(name)
        except BaseException:
            # An OS error during publication can follow an earlier successful rename.
            for name in reversed(committed):
                try:
                    if (backups / name).exists():
                        os.replace(backups / name, directory / name)
                    else:
                        (directory / name).unlink()
                except OSError as error:
                    retain_backups = True
                    raise OSError(f"Export rollback failed. Previous files: {backups}") from error
            raise
    finally:
        if not retain_backups:
            shutil.rmtree(root)
