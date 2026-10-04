@echo off
setlocal
cd /d "%~dp0"
set "PROJECT_PYTHON=%~dp0.venv\Scripts\python.exe"
set "PYINSTALLER_CONFIG_DIR=%~dp0.pyinstaller-cache"
set "TEMP=%~dp0.tmp"
set "TMP=%~dp0.tmp"
if not exist "%PYINSTALLER_CONFIG_DIR%" mkdir "%PYINSTALLER_CONFIG_DIR%"
if not exist "%TEMP%" mkdir "%TEMP%"
if not exist "%PROJECT_PYTHON%" (
    echo Project virtual environment not found.
    pause
    exit /b 1
)

"%PROJECT_PYTHON%" -m PyInstaller --noconfirm --clean --onedir --windowed ^
  --name KangarooCustomerAgent ^
  --add-data "desktop\assets;desktop\assets" ^
  --add-data "data\knowledge;data\knowledge" ^
  --collect-all langgraph ^
  --collect-all langchain_core ^
  --collect-all sentence_transformers ^
  --collect-all transformers ^
  run_app.py

if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

copy /Y ".env.example" "dist\KangarooCustomerAgent\.env.example" >nul
echo Build complete: dist\KangarooCustomerAgent\KangarooCustomerAgent.exe
endlocal
