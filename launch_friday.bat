@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
set "ROOT=%cd%"
set "ENV_FILE=%ROOT%\.env"
set "VENV_DIR=%ROOT%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

set "FRIDAY_HOST=127.0.0.1"
set "FRIDAY_PORT=8000"
set "FRIDAY_FRONTEND_MODE=particles"
set "FRIDAY_PARTICLES_HOST=127.0.0.1"
set "FRIDAY_PARTICLES_PORT=5173"
set "FRIDAY_ANTIGRAVITY_HOST=127.0.0.1"
set "FRIDAY_ANTIGRAVITY_PORT=5174"
set "FRIDAY_PRIMARY_MODEL=deepseek-r1:8b"
set "FRIDAY_FAST_MODEL=mistral:7b"

echo.
echo ==========================================================
echo   FRIDAY Local OS Bootstrap and Launcher
echo ==========================================================
echo.

if not exist "%ENV_FILE%" (
    echo [1/9] Creating .env from .env.example
    copy /y ".env.example" ".env" >nul || goto :fail
) else (
    echo [1/9] Using existing .env
)

for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
    if /I "%%A"=="FRIDAY_HOST" set "FRIDAY_HOST=%%B"
    if /I "%%A"=="FRIDAY_PORT" set "FRIDAY_PORT=%%B"
    if /I "%%A"=="FRIDAY_FRONTEND_MODE" set "FRIDAY_FRONTEND_MODE=%%B"
    if /I "%%A"=="FRIDAY_PARTICLES_HOST" set "FRIDAY_PARTICLES_HOST=%%B"
    if /I "%%A"=="FRIDAY_PARTICLES_PORT" set "FRIDAY_PARTICLES_PORT=%%B"
    if /I "%%A"=="FRIDAY_ANTIGRAVITY_HOST" set "FRIDAY_ANTIGRAVITY_HOST=%%B"
    if /I "%%A"=="FRIDAY_ANTIGRAVITY_PORT" set "FRIDAY_ANTIGRAVITY_PORT=%%B"
    if /I "%%A"=="FRIDAY_PRIMARY_MODEL" set "FRIDAY_PRIMARY_MODEL=%%B"
    if /I "%%A"=="FRIDAY_FAST_MODEL" set "FRIDAY_FAST_MODEL=%%B"
)

echo [2/9] Detecting Python
call :detect_python
if errorlevel 1 (
    echo No working Python 3.11+ interpreter was found.
    echo Install Python from python.org or disable the Windows App execution alias.
    goto :fail
)
echo     Using !PYTHON_DISPLAY!

if not exist "%VENV_PY%" (
    echo [3/9] Creating virtual environment
    "%PYTHON_EXE%" %PYTHON_ARGS% -m venv "%VENV_DIR%" || goto :fail
) else (
    echo [3/9] Reusing existing virtual environment
)

if not exist "%VENV_PY%" (
    echo Virtual environment creation failed.
    goto :fail
)

echo [4/9] Installing backend Python dependencies
"%VENV_PY%" -m pip install --upgrade pip || goto :fail
"%VENV_PY%" -m pip install -e ".[dev,embeddings,vision,voice]" || goto :fail
"%VENV_PY%" -m playwright install chromium || goto :fail

echo [5/9] Checking Node and installing frontend dependencies
where npm >nul 2>&1
if errorlevel 1 (
    echo npm was not found on PATH.
    echo Install Node.js 20+ and run the launcher again.
    goto :fail
)
call :npm_install "frontend-particles" || goto :fail
call :npm_install "frontend-antigravity" || goto :fail

echo [6/9] Checking Ollama
where ollama >nul 2>&1
if errorlevel 1 (
    echo Ollama was not found on PATH.
    echo Install Ollama first, then run the launcher again.
    goto :fail
)

curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo Starting Ollama server in the background
    start "FRIDAY Ollama" /min cmd /c "ollama serve"
    call :wait_for_ollama || goto :fail
) else (
    echo Ollama server is already running
)

echo [7/9] Pulling local models
echo     Primary: %FRIDAY_PRIMARY_MODEL%
ollama pull "%FRIDAY_PRIMARY_MODEL%" || goto :fail
if /I not "%FRIDAY_FAST_MODEL%"=="%FRIDAY_PRIMARY_MODEL%" (
    echo     Fast: %FRIDAY_FAST_MODEL%
    ollama pull "%FRIDAY_FAST_MODEL%" || goto :fail
)

if /I "%FRIDAY_FRONTEND_MODE%"=="antigravity" (
    set "FRONTEND_DIR=%ROOT%\frontend-antigravity"
    set "FRONTEND_HOST=%FRIDAY_ANTIGRAVITY_HOST%"
    set "FRONTEND_PORT=%FRIDAY_ANTIGRAVITY_PORT%"
) else (
    set "FRONTEND_DIR=%ROOT%\frontend-particles"
    set "FRONTEND_HOST=%FRIDAY_PARTICLES_HOST%"
    set "FRONTEND_PORT=%FRIDAY_PARTICLES_PORT%"
)
set "FRONTEND_URL=http://%FRONTEND_HOST%:%FRONTEND_PORT%"

echo [8/9] Launching backend API
set "BACKEND_CMD=cd /d ""%ROOT%"" && ""%VENV_PY%"" -m uvicorn api.main:app --host %FRIDAY_HOST% --port %FRIDAY_PORT%"
start "FRIDAY Backend" cmd /k "!BACKEND_CMD!"
call :wait_for_backend

echo [9/9] Launching %FRIDAY_FRONTEND_MODE% frontend
set "FRONTEND_CMD=cd /d ""%FRONTEND_DIR%"" && set ""VITE_FRIDAY_API_URL=http://%FRIDAY_HOST%:%FRIDAY_PORT%"" && call npm.cmd run dev -- --host %FRONTEND_HOST% --port %FRONTEND_PORT%"
start "FRIDAY Frontend" cmd /k "!FRONTEND_CMD!"
call :wait_for_frontend
start "" "%FRONTEND_URL%"

echo.
echo FRIDAY is live.
echo API: http://%FRIDAY_HOST%:%FRIDAY_PORT%
echo Frontend: %FRONTEND_URL%
echo Mode: %FRIDAY_FRONTEND_MODE%
echo.
echo Notes:
echo - The particle frontend is the default immersive presence surface.
echo - Set FRIDAY_FRONTEND_MODE=antigravity in .env to switch frontends.
echo - Stable Diffusion still needs FRIDAY_STABLE_DIFFUSION_MODEL_PATH pointed to local weights.
echo - Faster-Whisper models download locally on first transcription if missing from cache.
echo.
exit /b 0

:detect_python
set "PYTHON_EXE="
set "PYTHON_ARGS="
set "PYTHON_DISPLAY="

py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3.11"
    set "PYTHON_DISPLAY=py -3.11"
    exit /b 0
)
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3"
    set "PYTHON_DISPLAY=py -3"
    exit /b 0
)
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && (
    set "PYTHON_EXE=python"
    set "PYTHON_ARGS="
    set "PYTHON_DISPLAY=python"
    exit /b 0
)
python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1 && (
    set "PYTHON_EXE=python3"
    set "PYTHON_ARGS="
    set "PYTHON_DISPLAY=python3"
    exit /b 0
)
exit /b 1

:npm_install
echo     Installing npm dependencies in %~1
pushd "%ROOT%\%~1"
call npm.cmd install || (
    popd
    exit /b 1
)
popd
exit /b 0

:wait_for_ollama
echo Waiting for Ollama to become ready...
for /L %%I in (1,1,30) do (
    timeout /t 1 /nobreak >nul
    curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
    if not errorlevel 1 exit /b 0
)
echo Ollama did not become ready in time.
exit /b 1

:wait_for_backend
echo Waiting for the backend API to respond...
for /L %%I in (1,1,30) do (
    timeout /t 1 /nobreak >nul
    curl -s "http://%FRIDAY_HOST%:%FRIDAY_PORT%/api/health" >nul 2>&1
    if not errorlevel 1 exit /b 0
)
echo Backend is still starting. Continuing anyway.
exit /b 0

:wait_for_frontend
echo Waiting for the frontend server to respond...
for /L %%I in (1,1,30) do (
    timeout /t 1 /nobreak >nul
    curl -s "%FRONTEND_URL%" >nul 2>&1
    if not errorlevel 1 exit /b 0
)
echo Frontend is still starting. Continuing anyway.
exit /b 0

:fail
echo.
echo FRIDAY launcher failed.
echo Review the messages above, fix the missing dependency, and run it again.
echo.
pause
exit /b 1
