@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON=%ROOT%venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Ambiente virtual nao encontrado em %ROOT%venv\Scripts\python.exe
    exit /b 1
)

set "ENV_FILE=%ROOT%.env"
set "ADD_ENV="
if exist "%ENV_FILE%" (
    set "ADD_ENV=--add-data=%ENV_FILE%;."
)

"%PYTHON%" -m PyInstaller --noconfirm --clean --onedir --windowed --name RadioAdDetector %ADD_ENV% "%ROOT%main.py"

endlocal