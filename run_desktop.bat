@echo off
setlocal
cd /d "%~dp0"
set "PROJECT_PYTHON=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%PROJECT_PYTHON%" (
    echo Project virtual environment not found. Run dependency setup first.
    pause
    exit /b 1
)
start "" "%PROJECT_PYTHON%" -m desktop.main
endlocal
