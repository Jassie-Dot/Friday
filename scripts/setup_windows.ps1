param(
    [switch]$InstallEmbeddings,
    [switch]$InstallVision,
    [switch]$InstallVoice,
    [switch]$InstallFrontends
)

$ErrorActionPreference = "Stop"

function Get-WorkingPython {
    $candidates = @(
        @{ Exe = "py"; Args = @("-3.11"); Display = "py -3.11" },
        @{ Exe = "py"; Args = @("-3"); Display = "py -3" },
        @{ Exe = "python"; Args = @(); Display = "python" },
        @{ Exe = "python3"; Args = @(); Display = "python3" }
    )

    foreach ($candidate in $candidates) {
        try {
            & $candidate.Exe @($candidate.Args + @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)")) *> $null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        } catch {
        }
    }

    return $null
}

$pythonCmd = Get-WorkingPython

if (-not $pythonCmd) {
    Write-Host "No working Python 3.11+ interpreter was found." -ForegroundColor Yellow
    Write-Host "If Windows is opening the Microsoft Store alias for python.exe, install Python from python.org or disable the App execution alias." -ForegroundColor Yellow
    exit 1
}

Write-Host "Using $($pythonCmd.Display)" -ForegroundColor Cyan

if (-not (Test-Path ".venv")) {
    & $pythonCmd.Exe @($pythonCmd.Args + @("-m", "venv", ".venv"))
}

$venvPython = Join-Path (Get-Location) ".venv\Scripts\python.exe"

& $venvPython -m pip install --upgrade pip

$extras = @("dev")
if ($InstallEmbeddings) { $extras += "embeddings" }
if ($InstallVision) { $extras += "vision" }
if ($InstallVoice) { $extras += "voice" }

$extraSpec = ""
if ($extras.Count -gt 0) {
    $extraSpec = "[" + ($extras -join ",") + "]"
}

& $venvPython -m pip install -e ".$extraSpec"
& $venvPython -m playwright install chromium

if ($InstallFrontends) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Write-Host "npm was not found on PATH. Install Node.js 20+ first." -ForegroundColor Yellow
        exit 1
    }

    Push-Location "frontend-particles"
    npm install
    Pop-Location

    Push-Location "frontend-antigravity"
    npm install
    Pop-Location
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

Write-Host "Setup complete. Start Ollama, pull models, then run: friday-api or launch_friday.bat" -ForegroundColor Green
