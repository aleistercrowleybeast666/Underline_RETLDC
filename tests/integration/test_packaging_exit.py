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
def test_abnormal_builder_exit_must_not_accept_an_old_exe(
    tmp_path: Path,
    native_status: int,
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
