@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "APP_NAME=Underline_RETLDC"
set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"
set "DIST_ROOT=%CD%\dist"
if defined UNDERLINE_RC_20261103 set "DIST_ROOT=%CD%\dist\rc_20261103"
set "DIST_DIR=%DIST_ROOT%\%APP_NAME%"
set "WORK_DIR=%CD%\build\%APP_NAME%"
set "BUILD_ROOT=%CD%\build"

if defined UNDERLINE_RC_20261103 set "WORK_DIR=%LOCALAPPDATA%\UnderlineBuild\rc_20261103"

echo [1/8] Checking project environment...
if not exist "%VENV_PYTHON%" (
    echo ERROR: .venv was not found.
    echo Create it and install the project first:
    echo   py -m venv .venv
    echo   .\.venv\Scripts\python.exe -m pip install -e .
    if not defined CI pause
    exit /b 1
)

if not exist "%CD%\plugins" (
    echo ERROR: The bundled plugins directory is missing: %CD%\plugins
    if not defined CI pause
    exit /b 1
)

rem A validated tag isolates a new candidate without overwriting a previous release.
if defined UNDERLINE_BUILD_TAG (
    call :configure_tagged_output
    if errorlevel 1 exit /b 1
)

echo [2/8] Running release preflight: pytest...
"%VENV_PYTHON%" -m pytest
if not errorlevel 0 goto :native_failure
if errorlevel 1 (
    echo ERROR: pytest failed. Portable build was not started.
    if not defined CI pause
    exit /b 1
)

echo [3/8] Running release preflight: Ruff...
"%VENV_PYTHON%" -m ruff check .
if not errorlevel 0 goto :native_failure
if errorlevel 1 (
    echo ERROR: Ruff failed. Portable build was not started.
    if not defined CI pause
    exit /b 1
)

echo [4/8] Checking PyInstaller...
"%VENV_PYTHON%" -c "import PyInstaller" >nul 2>nul
if not errorlevel 0 goto :native_failure
if errorlevel 1 (
    echo PyInstaller is not installed. Installing it into .venv...
    "%VENV_PYTHON%" -m pip install "pyinstaller>=6.21"
    if not errorlevel 0 goto :native_failure
    if errorlevel 1 (
        echo ERROR: PyInstaller installation failed.
        if not defined CI pause
        exit /b 1
    )
)

echo [5/8] Building the one-folder application...
rem Bind the collected folder to this exact invocation, even if an older EXE exists.
if not exist "%BUILD_ROOT%" mkdir "%BUILD_ROOT%"
set "BUILD_ID=%BUILD_ROOT%\underline-build-invocation.txt"
"%VENV_PYTHON%" -c "import sys,uuid;from pathlib import Path;Path(sys.argv[1]).write_text(uuid.uuid4().hex,encoding='ascii')" "%BUILD_ID%"
if not errorlevel 0 goto :native_failure
if errorlevel 1 exit /b 1
"%VENV_PYTHON%" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --onedir ^
    --name "%APP_NAME%" ^
    --distpath "%DIST_ROOT%" ^
    --workpath "%WORK_DIR%" ^
    --specpath "%BUILD_ROOT%" ^
    --paths "%CD%\src" ^
    --add-data "%BUILD_ID%;." ^
    --add-data "%CD%\src\underline_retldc\i18n;underline_retldc\i18n" ^
    --collect-data pyqtgraph ^
    --hidden-import csv ^
    --hidden-import datetime ^
    --hidden-import zipfile ^
    --hidden-import xml.etree.ElementTree ^
    --hidden-import underline_retldc.core.units ^
    --hidden-import underline_retldc.core.measurement_export ^
    --hidden-import underline_retldc.core.measurement_statistics ^
    --hidden-import underline_retldc.core.parser_selection ^
    --hidden-import underline_retldc.core.primary_channels ^
    --hidden-import underline_retldc.core.tabular ^
    --hidden-import underline_retldc.core.tabular_auto_detector ^
    --hidden-import underline_retldc.core.workspace_capabilities ^
    --hidden-import underline_retldc.plugin_api.export_curve ^
    --hidden-import underline_retldc.plugin_api.two_column ^
    --hidden-import underline_retldc.plugins.measurement_export ^
    "%CD%\main.py"
if not errorlevel 0 goto :native_failure
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    if not defined CI pause
    exit /b 1
)

fc /b "%BUILD_ID%" "%DIST_DIR%\_internal\underline-build-invocation.txt" >nul
if not errorlevel 0 goto :native_failure
if errorlevel 1 (
    echo ERROR: The collected application does not belong to this build invocation.
    exit /b 1
)

echo [6/8] Copying bundled plugins and user documentation...
rem Qt6Core uses the Windows system ICU.  Some development shells put an unrelated
rem Poppler ICU on PATH, which PyInstaller may collect under the same DLL name.
if exist "%DIST_DIR%\_internal\icuuc.dll" del /Q "%DIST_DIR%\_internal\icuuc.dll"
if exist "%DIST_DIR%\_internal\icudt78.dll" del /Q "%DIST_DIR%\_internal\icudt78.dll"
if exist "%DIST_DIR%\_internal\icuuc.dll" (
    echo ERROR: Failed to remove an incompatible bundled ICU runtime.
    if not defined CI pause
    exit /b 1
)

rem QtGui's hook also collects the optional GPL/commercial virtual keyboard.
rem This QWidget desktop has no VirtualKeyboard/QML input feature or Python binding.
rem Exclude only these generated package files; never change the installed Qt tree.
if exist "%DIST_DIR%\_internal\PySide6\plugins\platforminputcontexts\qtvirtualkeyboardplugin.dll" del /Q "%DIST_DIR%\_internal\PySide6\plugins\platforminputcontexts\qtvirtualkeyboardplugin.dll"
if exist "%DIST_DIR%\_internal\PySide6\Qt6VirtualKeyboard.dll" del /Q "%DIST_DIR%\_internal\PySide6\Qt6VirtualKeyboard.dll"
if exist "%DIST_DIR%\_internal\PySide6\Qt6VirtualKeyboard.dll" (
    echo ERROR: Failed to exclude the unused Virtual Keyboard runtime.
    if not defined CI pause
    exit /b 1
)
if exist "%DIST_DIR%\_internal\PySide6\plugins\platforminputcontexts\qtvirtualkeyboardplugin.dll" (
    echo ERROR: Failed to exclude the unused Virtual Keyboard plugin.
    if not defined CI pause
    exit /b 1
)

rem QtGui also collects the read-only PDF image plugin. No workflow opens PDF,
rem and QML/Quick have no binding/resource/root reference after keyboard exclusion.
if exist "%DIST_DIR%\_internal\PySide6\plugins\imageformats\qpdf.dll" del /Q "%DIST_DIR%\_internal\PySide6\plugins\imageformats\qpdf.dll"
if exist "%DIST_DIR%\_internal\PySide6\plugins\imageformats\qpdf.dll" (
    echo ERROR: Failed to exclude the unused PDF image reader plugin.
    if not defined CI pause
    exit /b 1
)
for %%F in (Qt6Pdf.dll Qt6Quick.dll Qt6Qml.dll Qt6QmlMeta.dll Qt6QmlModels.dll Qt6QmlWorkerScript.dll) do (
    if exist "%DIST_DIR%\_internal\PySide6\%%F" del /Q "%DIST_DIR%\_internal\PySide6\%%F"
    if exist "%DIST_DIR%\_internal\PySide6\%%F" (
        echo ERROR: Failed to exclude unused %%F.
        if not defined CI pause
        exit /b 1
    )
)

robocopy "%CD%\plugins" "%DIST_DIR%\plugins" /E /XD __pycache__ .pytest_cache /XF *.pyc *.pyo /NFL /NDL /NJH /NJS /NP >nul
if not errorlevel 0 goto :native_failure
if errorlevel 8 (
    echo ERROR: Failed to copy bundled plugins.
    if not defined CI pause
    exit /b 1
)

rem A candidate carries the public manuals and upstream notices, not local review notes or test logs.
robocopy "%CD%\docs" "%DIST_DIR%\docs" Architecture.md Analysis.md Calibration.md Data_Formats.md Plugin_API.md VERSION.md Theoretical_Curves.md TreeDiagram_Export_Contract.md Recorded_Data_Showcase.md Synthetic_Overlay_Example.md Qt_*.md /NFL /NDL /NJH /NJS /NP >nul
if not errorlevel 0 goto :native_failure
if errorlevel 8 exit /b 1
robocopy "%CD%\docs\assets" "%DIST_DIR%\docs\assets" /E /NFL /NDL /NJH /NJS /NP >nul
if not errorlevel 0 goto :native_failure
if errorlevel 8 exit /b 1
robocopy "%CD%\docs\third_party" "%DIST_DIR%\docs\third_party" /E /NFL /NDL /NJH /NJS /NP >nul
if not errorlevel 0 goto :native_failure
if errorlevel 8 (
    echo ERROR: Failed to copy documentation.
    if not defined CI pause
    exit /b 1
)

xcopy "%CD%\examples\*" "%DIST_DIR%\examples\" /E /I /Y /Q >nul
if not errorlevel 0 goto :native_failure
if errorlevel 1 (
    echo ERROR: Failed to copy examples.
    if not defined CI pause
    exit /b 1
)

if exist "%CD%\presets" (
    robocopy "%CD%\presets" "%DIST_DIR%\presets" /E /XD __pycache__ /XF *.pyc *.pyo /NFL /NDL /NJH /NJS /NP >nul
    if not errorlevel 0 goto :native_failure
    if errorlevel 8 (
        echo ERROR: Failed to copy bundled Tabular presets.
        if not defined CI pause
        exit /b 1
    )
)

robocopy "%CD%\contracts\motor-test-package" "%DIST_DIR%\contracts\motor-test-package" /E /NFL /NDL /NJH /NJS /NP >nul
if not errorlevel 0 goto :native_failure
if errorlevel 8 exit /b 1
copy /Y "%CD%\README.txt" "%DIST_DIR%\README.txt" >nul
copy /Y "%CD%\新增解析器_PROMPT.txt" "%DIST_DIR%\新增解析器_PROMPT.txt" >nul
copy /Y "%CD%\新增校准配置_PROMPT.txt" "%DIST_DIR%\新增校准配置_PROMPT.txt" >nul

rem Preserve upstream documents and any owner-selected root legal files.
rem This collects notices; it does not select a project license or approve release.
"%VENV_PYTHON%" "%CD%\scripts\collect_licenses.py" --output "%DIST_DIR%"
if not errorlevel 0 goto :native_failure
if errorlevel 1 (
    echo ERROR: Failed to collect third-party license documents.
    if not defined CI pause
    exit /b 1
)

if not exist "%DIST_DIR%\%APP_NAME%.exe" (
    echo ERROR: The expected executable was not created.
    if not defined CI pause
    exit /b 1
)

echo [7/8] Smoke-testing the packaged executable in light mode...
start "" /wait "%DIST_DIR%\%APP_NAME%.exe" --smoke-test --theme light
if not errorlevel 0 goto :native_failure
if errorlevel 1 (
    echo ERROR: Packaged light-mode smoke test failed.
    if not defined CI pause
    exit /b 1
)

echo [8/8] Smoke-testing the packaged executable in dark mode...
start "" /wait "%DIST_DIR%\%APP_NAME%.exe" --smoke-test --theme dark
if not errorlevel 0 goto :native_failure
if errorlevel 1 (
    echo ERROR: Packaged dark-mode smoke test failed.
    if not defined CI pause
    exit /b 1
)

echo.
echo Build completed successfully.
echo Folder: %DIST_DIR%
echo Program: %DIST_DIR%\%APP_NAME%.exe
echo Distribute the entire %APP_NAME% folder, not the EXE alone.
if not defined CI pause
exit /b 0

:native_failure
echo ERROR: A native process terminated abnormally. Candidate rejected.
if not defined CI pause
exit /b 1

:configure_tagged_output
"%VENV_PYTHON%" -c "import os,re,sys;sys.exit(0 if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',os.environ['UNDERLINE_BUILD_TAG']) else 1)"
if not errorlevel 0 goto :native_failure
if errorlevel 1 (
    echo ERROR: UNDERLINE_BUILD_TAG must be 1-64 ASCII letters, digits, underscores or hyphens, beginning with a letter or digit.
    exit /b 1
)
set "DIST_ROOT=%CD%\dist\%UNDERLINE_BUILD_TAG%"
set "DIST_DIR=%DIST_ROOT%\%APP_NAME%"
set "BUILD_ROOT=%CD%\.work\%UNDERLINE_BUILD_TAG%\package"
set "WORK_DIR=%BUILD_ROOT%\%APP_NAME%"
exit /b 0
