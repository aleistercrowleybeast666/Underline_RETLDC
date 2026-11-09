"""Windows batch gate must reject an abnormal child exit even when an older EXE exists."""

import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows portable build batch file")
@pytest.mark.parametrize("native_status", [0xFFFFFFFF, 0])
@pytest.mark.parametrize("build_tag", [None, "candidate-isolated"])
def test_abnormal_builder_exit_must_not_accept_an_old_exe(
    tmp_path: Path,
    native_status: int,
    build_tag: str | None,
) -> None:
    source = Path(__file__).resolve().parents[2] / "打包.bat"
    shutil.copyfile(source, tmp_path / "candidate.bat")
    venv.EnvBuilder(with_pip=False).create(tmp_path / ".venv")
    (tmp_path / "plugins").mkdir()
    for stage in ("pytest", "ruff"):
        (tmp_path / f"{stage}.py").write_text(
            "# Fault harness only; allow this prior stage to finish.\n", encoding="utf8"
        )
    (tmp_path / "PyInstaller.py").write_text(
        "if __name__ == '__main__':\n"
        " import ctypes\n"
        f" print('FAULT_INJECTION: exit {native_status} without producing output', flush=True)\n"
        f" ctypes.windll.kernel32.ExitProcess({native_status})\n",
        encoding="utf8",
    )
    older = tmp_path / "dist/Underline_RETLDC/Underline_RETLDC.exe"
    older.parent.mkdir(parents=True)
    older.write_bytes(b"previous candidate sentinel")
    env = dict(os.environ, CI="1")
    env.pop("UNDERLINE_RC_20261103", None)
    env.pop("UNDERLINE_BUILD_TAG", None)
    if build_tag is not None:
        env["UNDERLINE_BUILD_TAG"] = build_tag
    result = subprocess.run(
        [os.environ["COMSPEC"], "/d", "/c", "candidate.bat"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        timeout=60,
        check=False,
    )
    output = result.stdout.decode("utf8", errors="replace")
    assert "FAULT_INJECTION" in output, output
    assert "[6/8]" not in output, output
    assert result.returncode != 0
    assert older.read_bytes() == b"previous candidate sentinel"
    if build_tag is not None:
        assert (tmp_path / ".work" / build_tag / "package/underline-build-invocation.txt").is_file()
        assert not (tmp_path / "build").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows portable build batch file")
def test_invalid_build_tag_stops_before_preflight_or_output(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / "打包.bat"
    shutil.copyfile(source, tmp_path / "candidate.bat")
    venv.EnvBuilder(with_pip=False).create(tmp_path / ".venv")
    (tmp_path / "plugins").mkdir()
    result = subprocess.run(
        [os.environ["COMSPEC"], "/d", "/c", "candidate.bat"], cwd=tmp_path,
        env={**os.environ, "CI": "1", "UNDERLINE_BUILD_TAG": "../must-not-exist"},
        capture_output=True, timeout=30, check=False,
    )
    assert result.returncode != 0
    assert b"UNDERLINE_BUILD_TAG must be" in result.stdout
    assert b"[2/8]" not in result.stdout
    assert not (tmp_path / "dist").exists()
    assert not (tmp_path / ".work").exists()
