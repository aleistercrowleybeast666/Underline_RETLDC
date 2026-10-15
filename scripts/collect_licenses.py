"""Copy upstream license documents without choosing an application license."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from importlib.metadata import distribution
from pathlib import Path
from shutil import copyfile


def _copy(source: Path, destination: Path) -> dict[str, str | int]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    copyfile(source, destination)
    data = source.read_bytes()
    if destination.read_bytes() != data:
        raise OSError(f"License copy differs: {destination}")
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def Licenses_Collect(output: Path) -> dict[str, object]:
    repository = Path(__file__).resolve().parents[1]
    output = output.resolve()
    upstream = repository / "docs" / "third_party"
    if output in (repository, upstream) or upstream in output.parents:
        raise ValueError("License output must not overwrite the repository or legal sources")
    runtime = output / "docs" / "third_party" / "runtime"
    records: list[dict[str, object]] = []
    for name in (
        "numpy", "scipy", "pyqtgraph", "PySide6", "PySide6_Essentials",
        "PySide6_Addons", "shiboken6", "PyInstaller",
    ):
        package = distribution(name)
        documents = [
            path for path in package.files or ()
            if any(token in path.name.lower()
                   for token in ("license", "copying", "notice", "copyright"))
        ]
        if not documents:
            raise FileNotFoundError(f"No upstream license documents found for {name}")
        copied = []
        for relative in documents:
            if (relative.is_absolute() or Path(relative).drive
                    or ".." in relative.parts):
                raise ValueError(f"Unsafe license metadata path: {relative}")
            destination = runtime / name / relative
            copied.append({
                "path": destination.relative_to(output).as_posix(),
                "upstream_path": relative.as_posix(),
                **_copy(Path(package.locate_file(relative)), destination),
            })
        records.append({
            "distribution": name, "version": package.version,
            "license_expression": package.metadata.get("License-Expression"),
            "files": copied,
        })

    python_version = ".".join(str(part) for part in sys.version_info[:3])
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    destination = runtime / "Python" / "LICENSE.txt"
    records.append({
        "distribution": "Python", "version": python_version,
        "files": [{"path": destination.relative_to(output).as_posix(),
                   "upstream_path": "LICENSE.txt", **_copy(python_license, destination)}],
    })
    notices = repository / "THIRD_PARTY_NOTICES.txt"
    _copy(notices, output / notices.name)
    for source in upstream.rglob("*"):
        if source.is_file() and "runtime" not in source.relative_to(upstream).parts:
            _copy(source, output / "docs" / "third_party" / source.relative_to(upstream))
    application_license_files = []
    for name in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING", "NOTICE", "NOTICE.txt"):
        source = repository / name
        if source.is_file():
            _copy(source, output / name)
            application_license_files.append(name)
    bundled_qt = output / "_internal" / "PySide6"
    manifest: dict[str, object] = {
        "scope": "Upstream documents only; no UNDERLINE license selection or compliance approval",
        "application_legal_files": application_license_files,
        "distributions": records,
        "qt_virtual_keyboard_present": (bundled_qt / "Qt6VirtualKeyboard.dll").is_file(),
        "unresolved": [
            "Application license and copyright holder require owner decision",
            "Qt licensing route, matching sources and complete nested attributions need review",
            "Copying license texts alone does not authorize a public release",
        ],
    }
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = Licenses_Collect(args.output)
    count = sum(len(item["files"]) for item in result["distributions"])
    print(f"Copied {count} upstream license documents; see docs/third_party/runtime/manifest.json")
    print("Application/Qt release licensing decisions remain separate from document collection.")


if __name__ == "__main__":
    main()
