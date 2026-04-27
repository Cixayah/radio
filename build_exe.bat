@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

echo ================================================
echo   Build - RadioAdDetector
echo ================================================

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "VENV_DIR=%ROOT%.venv"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"
set "PIP=%VENV_DIR%\Scripts\pip.exe"
set "DIST_DIR=%ROOT%dist"
set "BUILD_DIR=%DIST_DIR%\RadioAdDetector"
set "INTERNAL_DIR=%DIST_DIR%\_internal"
set "ENV_FILE=%ROOT%.env"
set "FFMPEG_SRC="

if defined FFMPEG_PATH if exist "%FFMPEG_PATH%" (
    set "FFMPEG_SRC=%FFMPEG_PATH%"
)

if exist "%ROOT%bin\ffmpeg.exe" (
    set "FFMPEG_SRC=%ROOT%bin\ffmpeg.exe"
)

if not defined FFMPEG_SRC (
    for /f "delims=" %%I in ('where ffmpeg 2^>nul') do (
        if not defined FFMPEG_SRC set "FFMPEG_SRC=%%~fI"
    )
)

if not defined FFMPEG_SRC (
    echo [ERRO] ffmpeg.exe nao encontrado em:
    echo        %ROOT%bin\ffmpeg.exe
    echo        no PATH do sistema
    exit /b 1
)

if not exist "%ENV_FILE%" (
    echo [ERRO] Arquivo .env nao encontrado em:
    echo        %ENV_FILE%
    echo Crie o .env com GROQ_API_KEY antes de gerar o pacote.
    exit /b 1
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [1/8] Criando venv...
    py -3 -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERRO] Falha ao criar venv.
        exit /b 1
    )
) else (
    echo [1/8] Venv ja existe.
)

echo [2/8] Atualizando pip/setuptools/wheel...
"%PYTHON%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo [ERRO] Falha ao atualizar ferramentas base.
    exit /b 1
)

echo [3/8] Instalando dependencias...
"%PIP%" install -r "%ROOT%requirements.txt"
if errorlevel 1 (
    echo [ERRO] Falha ao instalar requirements.
    exit /b 1
)

echo [4/8] Limpando build anterior...
if exist "%ROOT%build" rmdir /s /q "%ROOT%build"
if exist "%ROOT%dist" rmdir /s /q "%ROOT%dist"

echo [5/8] Gerando executavel...
"%PYTHON%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name "RadioAdDetector" ^
  --onedir ^
  --contents-directory "_internal" ^
  --optimize 2 ^
  --strip ^
  --noupx ^
  --exclude-module anthropic ^
  --exclude-module whisper ^
  --exclude-module openai ^
  --exclude-module tiktoken ^
  --exclude-module IPython ^
  --exclude-module jupyter ^
  --exclude-module jupyter_client ^
  --exclude-module jupyter_core ^
  --exclude-module pytest ^
  --exclude-module torch ^
  --exclude-module torchaudio ^
  --exclude-module torchcodec ^
  --exclude-module sympy ^
  --exclude-module networkx ^
  --exclude-module librosa ^
  --exclude-module numba ^
  --exclude-module llvmlite ^
  --exclude-module scipy ^
  --exclude-module sklearn ^
  --exclude-module pooch ^
  --exclude-module tzdata ^
  --add-data "%FFMPEG_SRC%;bin" ^
  "%ROOT%main.py"
if errorlevel 1 (
    echo [ERRO] PyInstaller falhou.
    exit /b 1
)

echo [6/8] Garantindo ffmpeg no pacote...
if not exist "%BUILD_DIR%\_internal\bin" mkdir "%BUILD_DIR%\_internal\bin"
copy /y "%FFMPEG_SRC%" "%BUILD_DIR%\_internal\bin\ffmpeg.exe" >nul

echo [7/8] Organizando estrutura final da pasta dist...
if exist "%DIST_DIR%\RadioAdDetector.exe" del /q "%DIST_DIR%\RadioAdDetector.exe"
if exist "%INTERNAL_DIR%" rmdir /s /q "%INTERNAL_DIR%"

move /y "%BUILD_DIR%\RadioAdDetector.exe" "%DIST_DIR%\RadioAdDetector.exe" >nul
if errorlevel 1 (
    echo [ERRO] Falha ao mover o executavel para dist.
    exit /b 1
)

move /y "%BUILD_DIR%\_internal" "%INTERNAL_DIR%" >nul
if errorlevel 1 (
    echo [ERRO] Falha ao mover a pasta _internal para dist.
    exit /b 1
)

if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"

echo [8/8] Incluindo .env no pacote final...
copy /y "%ENV_FILE%" "%DIST_DIR%\.env" >nul
if errorlevel 1 (
    echo [ERRO] Falha ao copiar .env para %DIST_DIR%\.env
    exit /b 1
)

echo [VALIDACAO] Conferindo layout final em dist...
if not exist "%DIST_DIR%\RadioAdDetector.exe" (
    echo [ERRO] Executavel final nao encontrado em %DIST_DIR%\RadioAdDetector.exe
    exit /b 1
)
if not exist "%DIST_DIR%\_internal" (
    echo [ERRO] Pasta de dependencias nao encontrada em %DIST_DIR%\_internal
    exit /b 1
)
if not exist "%DIST_DIR%\.env" (
    echo [ERRO] Arquivo .env nao encontrado no pacote final: %DIST_DIR%\.env
    exit /b 1
)
if not exist "%DIST_DIR%\_internal\bin\ffmpeg.exe" (
    echo [ERRO] ffmpeg.exe nao encontrado em %DIST_DIR%\_internal\bin\ffmpeg.exe
    exit /b 1
)
if exist "%DIST_DIR%\RadioAdDetector" (
    echo [ERRO] Pasta intermediaria detectada: %DIST_DIR%\RadioAdDetector
    echo        O layout correto deve conter apenas o .exe e a pasta _internal em dist.
    exit /b 1
)

echo.
echo Build concluido com sucesso.
echo Pasta final: %DIST_DIR%
echo Executavel : %DIST_DIR%\RadioAdDetector.exe
echo Dependencias: %DIST_DIR%\_internal
echo Configuracao: %DIST_DIR%\.env
echo.
echo IMPORTANTE: este pacote inclui .env com a chave da API e ffmpeg em _internal\bin.
echo.
echo Dica: compacte a pasta dist inteira para distribuir.
exit /b 0