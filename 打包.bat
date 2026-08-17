@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "APP_NAME=Underline_RETLDC"
set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"
set "DIST_ROOT=%CD%\dist"
set "DIST_DIR=%DIST_ROOT%\%APP_NAME%"
set "WORK_DIR=%CD%\build\%APP_NAME%"

echo [1/6] Checking project environment...
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

echo [2/6] Checking PyInstaller...
"%VENV_PYTHON%" -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo PyInstaller is not installed. Installing it into .venv...
    "%VENV_PYTHON%" -m pip install "pyinstaller>=6.21"
    if errorlevel 1 (
        echo ERROR: PyInstaller installation failed.
        if not defined CI pause
        exit /b 1
    )
)

echo [3/6] Building the one-folder application...
"%VENV_PYTHON%" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --onedir ^
    --name "%APP_NAME%" ^
    --distpath "%DIST_ROOT%" ^
    --workpath "%WORK_DIR%" ^
    --specpath "%CD%\build" ^
    --paths "%CD%\src" ^
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
    --hidden-import underline_retldc.core.workspace_capabilities ^
    --hidden-import underline_retldc.plugin_api.export_curve ^
    --hidden-import underline_retldc.plugin_api.two_column ^
    --hidden-import underline_retldc.plugins.measurement_export ^
    "%CD%\main.py"
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    if not defined CI pause
    exit /b 1
)

echo [4/6] Copying bundled plugins and user documentation...
robocopy "%CD%\plugins" "%DIST_DIR%\plugins" /E /XD __pycache__ .pytest_cache /XF *.pyc *.pyo /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
    echo ERROR: Failed to copy bundled plugins.
    if not defined CI pause
    exit /b 1
)

xcopy "%CD%\docs\*" "%DIST_DIR%\docs\" /E /I /Y /Q >nul
if errorlevel 1 (
    echo ERROR: Failed to copy documentation.
    if not defined CI pause
    exit /b 1
)

xcopy "%CD%\examples\*" "%DIST_DIR%\examples\" /E /I /Y /Q >nul
if errorlevel 1 (
    echo ERROR: Failed to copy examples.
    if not defined CI pause
    exit /b 1
)

if exist "%CD%\presets" (
    robocopy "%CD%\presets" "%DIST_DIR%\presets" /E /XD __pycache__ /XF *.pyc *.pyo /NFL /NDL /NJH /NJS /NP >nul
    if errorlevel 8 (
        echo ERROR: Failed to copy bundled Tabular presets.
        if not defined CI pause
        exit /b 1
    )
)

copy /Y "%CD%\README.txt" "%DIST_DIR%\README.txt" >nul
copy /Y "%CD%\新增解析器_PROMPT.txt" "%DIST_DIR%\新增解析器_PROMPT.txt" >nul
copy /Y "%CD%\新增校准配置_PROMPT.txt" "%DIST_DIR%\新增校准配置_PROMPT.txt" >nul

if not exist "%DIST_DIR%\%APP_NAME%.exe" (
    echo ERROR: The expected executable was not created.
    if not defined CI pause
    exit /b 1
)

echo [5/6] Smoke-testing the packaged executable in light mode...
start "" /wait "%DIST_DIR%\%APP_NAME%.exe" --smoke-test --theme light
if errorlevel 1 (
    echo ERROR: Packaged light-mode smoke test failed.
    if not defined CI pause
    exit /b 1
)

echo [6/6] Smoke-testing the packaged executable in dark mode...
start "" /wait "%DIST_DIR%\%APP_NAME%.exe" --smoke-test --theme dark
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
