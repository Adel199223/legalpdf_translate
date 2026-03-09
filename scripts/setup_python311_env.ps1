[CmdletBinding()]
param(
    [string]$VenvName = ".venv311",
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[setup-python311] $Message"
}

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $projectRoot

Write-Step "Project root: $projectRoot"

try {
    $pythonVersion = py -3.11 --version 2>$null
    if (-not $pythonVersion) {
        throw "Python 3.11 is not available from py launcher."
    }
    Write-Step "Detected: $pythonVersion"
}
catch {
    throw @"
Python 3.11 was not found.
Install it first (per-user recommended):
  winget install --id Python.Python.3.11 -e --scope user --accept-package-agreements --accept-source-agreements
Then re-run this script.
"@
}

$venvPath = Join-Path $projectRoot $VenvName
if (Test-Path $venvPath) {
    if ($Recreate) {
        Write-Step "Removing existing $VenvName"
        Remove-Item -Recurse -Force $venvPath
    }
    else {
        Write-Step "$VenvName already exists (use -Recreate to rebuild)"
    }
}

if (-not (Test-Path $venvPath)) {
    Write-Step "Creating virtual environment: $VenvName"
    py -3.11 -m venv $VenvName
}

$venvPython = Join-Path $venvPath "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Venv python not found: $venvPython"
}

Write-Step "Bootstrapping pip/setuptools/wheel"
& $venvPython -m ensurepip --upgrade
& $venvPython -m pip install --upgrade pip setuptools wheel

Write-Step "Installing project dependencies"
& $venvPython -m pip install -e .
& $venvPython -m pip install -e .[dev]

Write-Step "Running package health check"
& $venvPython -c "import html.entities, idna, pip; print('python health check: ok')"

Write-Step "Done. Activate with:"
Write-Host ". .\$VenvName\Scripts\Activate.ps1"
