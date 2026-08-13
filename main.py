from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from enum import IntEnum
from pathlib import Path


class LauncherResult(IntEnum):
    SUCCESS = 0
    APPLICATION_FAILED = 1
    VIRTUAL_ENVIRONMENT_MISSING = 2
    VIRTUAL_ENVIRONMENT_LAUNCH_FAILED = 3


def Launcher_FindVenvPython(project_root: Path) -> Path | None:
    candidates = (
        project_root / ".venv" / "Scripts" / "python.exe",
        project_root / ".venv" / "bin" / "python",
    )
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def Launcher_IsProjectVenv(project_root: Path) -> bool:
    try:
        return Path(sys.prefix).resolve() == (project_root / ".venv").resolve()
    except OSError:
        return False


def Launcher_Run(arguments: Sequence[str] | None = None) -> LauncherResult:
    project_root = Path(__file__).resolve().parent
    launcher_arguments = list(sys.argv[1:] if arguments is None else arguments)
    venv_python = Launcher_FindVenvPython(project_root)
    if venv_python is None:
        print(
            "未找到项目虚拟环境 .venv。请在项目根目录执行：\n"
            "    python -m venv .venv\n"
            "    .\\.venv\\Scripts\\python.exe -m pip install -e .",
            file=sys.stderr,
        )
        return LauncherResult.VIRTUAL_ENVIRONMENT_MISSING

    if not Launcher_IsProjectVenv(project_root):
        try:
            completed = subprocess.run(
                [str(venv_python), str(Path(__file__).resolve()), *launcher_arguments],
                cwd=project_root,
                check=False,
            )
        except OSError as exc:
            print(f"无法使用项目虚拟环境启动程序：{exc}", file=sys.stderr)
            return LauncherResult.VIRTUAL_ENVIRONMENT_LAUNCH_FAILED
        return (
            LauncherResult.SUCCESS
            if completed.returncode == 0
            else LauncherResult.APPLICATION_FAILED
        )

    source_root = project_root / "src"
    source_path = str(source_root)
    if source_path not in sys.path:
        sys.path.insert(0, source_path)

    try:
        from underline_retldc.app.application import main as Application_Main
    except ImportError as exc:
        print(f"无法导入 Underline RETLDC：{exc}", file=sys.stderr)
        return LauncherResult.APPLICATION_FAILED

    application_code = Application_Main(launcher_arguments)
    return (
        LauncherResult.SUCCESS
        if application_code == 0
        else LauncherResult.APPLICATION_FAILED
    )


if __name__ == "__main__":
    raise SystemExit(int(Launcher_Run()))

