"""Recombine a PyInstaller 6.21 onedir EXE with one modified Qt Python module.

Run with the build's Python version and PyInstaller. Native DLL/PYD files remain
external. This developer tool never edits the input EXE or an installed package.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import marshal
import struct
import zlib
from pathlib import Path

import pefile
from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.archive.writers import CArchiveWriter
from PyInstaller.utils.win32.winutils import update_exe_pe_checksum


def QtBindings_Reassemble(
    executable: Path, module: str, replacement: Path, output: Path,
) -> dict[str, object]:
    """Replace one pure-module blob; preserve every other compressed entry exactly."""
    executable, replacement, output = (
        path.resolve() for path in (executable, replacement, output)
    )
    if output == executable or output.exists():
        raise ValueError("Output must be a new EXE, separate from the original")
    if not module.startswith(("PySide6.", "shiboken6.")):
        raise ValueError("Only a Qt/PySide/Shiboken Python submodule may be replaced")
    image = executable.read_bytes()
    pe = pefile.PE(data=image, fast_load=True)
    security = pe.OPTIONAL_HEADER.DATA_DIRECTORY[pefile.DIRECTORY_ENTRY[
        "IMAGE_DIRECTORY_ENTRY_SECURITY"
    ]]
    if security.Size:
        raise ValueError("Signed EXEs require a separate rebuild/signing workflow")
    archive = CArchiveReader(str(executable))
    pyz = archive.extract("PYZ.pyz")
    if pyz[:4] != b"PYZ\x00" or pyz[4:8] != importlib.util.MAGIC_NUMBER:
        raise ValueError("Use the same Python bytecode version as this frozen build")
    old_toc = dict(marshal.loads(pyz[struct.unpack("!i", pyz[8:12])[0]:]))
    if module not in old_toc or old_toc[module][0] not in (0, 1):
        raise ValueError("Requested module is not a pure Python module in this EXE")
    original_code = archive.open_embedded_archive("PYZ.pyz").extract(module)
    replacement_bytes = replacement.read_bytes()
    new_code = compile(replacement_bytes, original_code.co_filename, "exec")
    target_blob = zlib.compress(marshal.dumps(new_code), 6)
    stream = io.BytesIO()
    stream.write(pyz[:17])
    new_toc = []
    unchanged = 0
    for name, (kind, offset, length) in old_toc.items():
        blob = target_blob if name == module else pyz[offset:offset + length]
        new_toc.append((name, (kind, stream.tell(), len(blob))))
        stream.write(blob)
        unchanged += name != module
    toc_offset = stream.tell()
    stream.write(marshal.dumps(new_toc))
    stream.seek(8)
    stream.write(struct.pack("!i", toc_offset))
    replacement_pyz = stream.getvalue()

    payload = io.BytesIO()
    entries = []
    for name, (offset, length, raw_length, compressed, kind) in archive.toc.items():
        blob = image[archive._start_offset + offset:archive._start_offset + offset + length]
        if name == "PYZ.pyz":
            raw_length = len(replacement_pyz)
            blob = zlib.compress(replacement_pyz) if compressed else replacement_pyz
        entries.append((payload.tell(), len(blob), raw_length, compressed, kind, name))
        payload.write(blob)
    for option in archive.options:
        entries.append((0, 0, 0, 0, "o", option))
    toc_offset = payload.tell()
    toc_blob = CArchiveWriter._serialize_toc(entries)
    payload.write(toc_blob)
    cookie = list(struct.unpack(
        CArchiveWriter._COOKIE_FORMAT,
        image[archive._end_offset - CArchiveWriter._COOKIE_LENGTH:archive._end_offset],
    ))
    cookie[1:4] = (payload.tell() + CArchiveWriter._COOKIE_LENGTH, toc_offset, len(toc_blob))
    payload.write(struct.pack(CArchiveWriter._COOKIE_FORMAT, *cookie))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        handle.write(image[:archive._start_offset])
        handle.write(payload.getvalue())
    update_exe_pe_checksum(str(output))
    rebuilt = CArchiveReader(str(output)).open_embedded_archive("PYZ.pyz")
    expected_code = marshal.loads(zlib.decompress(target_blob))
    if rebuilt.extract(module).co_code != expected_code.co_code:
        raise RuntimeError("Reassembled replacement verification failed")
    report = {
        "input_sha256": hashlib.sha256(image).hexdigest(),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "module": module,
        "replacement_source_sha256": hashlib.sha256(replacement_bytes).hexdigest(),
        "other_pyz_entries_preserved": unchanged,
        "native_libraries_rebuilt": False,
        "native_libraries_external": True,
    }
    output.with_suffix(".reassembly.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--module", required=True)
    parser.add_argument("--replacement", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(QtBindings_Reassemble(
        args.exe, args.module, args.replacement, args.output,
    )))


if __name__ == "__main__":
    main()
