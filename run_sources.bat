@echo off
setlocal
cd /d "%~dp0"

set "PROJECT_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PROJECT_PYTHON%" (
    echo Project virtual environment not found. Run dependency setup first.
    pause
    exit /b 1
)
"%PROJECT_PYTHON%" -m scripts.serve_sources

if errorlevel 1 pause
endlocal
