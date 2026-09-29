[CmdletBinding()]
param(
    [ValidatePattern('^\.venv[0-9A-Za-z_-]*$')]
    [string]$VenvName = ".venv311",
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"
if (Test-Path Variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

function Write-Step {
    param([string]$Message)
    Write-Host "[setup-python311] $Message"
}

function Invoke-CheckedCommand {
    param([string]$Executable, [string[]]$Arguments, [string]$Description)
    Write-Step $Description
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed (exit $LASTEXITCODE). Setup did not complete."
    }
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPath = [IO.Path]::GetFullPath((Join-Path $projectRoot $VenvName))
if ([IO.Path]::GetDirectoryName($venvPath) -ne $projectRoot) {
    throw "The environment must be a direct child of the project root."
}
if (Test-Path -LiteralPath $venvPath) {
    $venvItem = Get-Item -LiteralPath $venvPath -Force
    if (-not $venvItem.PSIsContainer -or ($venvItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "The environment must be a regular directory, not a file or linked directory."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $venvPath "pyvenv.cfg"))) {
        throw "Existing directory is not a Python virtual environment: $VenvName"
    }
}

$uvCommand = Get-Command uv -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $uvCommand) {
    throw "uv is required. Install it with: winget install --id astral-sh.uv --exact --scope user"
}
$uvExe = $uvCommand.Source
$pythonPinPath = Join-Path $projectRoot ".python-version"
if (-not (Test-Path -LiteralPath $pythonPinPath) -or -not (Test-Path -LiteralPath (Join-Path $projectRoot "uv.lock"))) {
    throw "The tracked .python-version and uv.lock files are required."
}
$pythonPin = (Get-Content -LiteralPath $pythonPinPath -Raw).Trim()
if ($pythonPin -notmatch '^3\.11\.\d+$') {
    throw "Expected an exact Python 3.11 patch version in .python-version."
}

Push-Location $projectRoot
$oldProjectEnvironment = [Environment]::GetEnvironmentVariable("UV_PROJECT_ENVIRONMENT", "Process")
$backupPath = $null
try {
    Write-Step "Project root: $projectRoot"
    $pythonOutput = @(Invoke-CheckedCommand -Executable $uvExe -Arguments @(
        "python", "find", $pythonPin, "--no-project", "--no-python-downloads"
    ) -Description "Locate Python $pythonPin (no automatic downloads)")
    $pythonExe = ($pythonOutput | Select-Object -Last 1).ToString().Trim()
    if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
        throw "Pinned Python was not found. Install Python $pythonPin and run setup again."
    }
    $null = Invoke-CheckedCommand -Executable $uvExe -Arguments @(
        "lock", "--check", "--python", $pythonExe, "--no-python-downloads"
    ) -Description "Verify the tracked dependency lock"

    if (-not $Recreate -and (Test-Path -LiteralPath $venvPath)) {
        $existingPython = Join-Path $venvPath "Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $existingPython -PathType Leaf)) {
            throw "Existing environment has no Python interpreter. Use -Recreate to rebuild with a backup."
        }
        $existingVersion = @(Invoke-CheckedCommand -Executable $uvExe -Arguments @(
            "run", "--no-project", "--no-env-file", "--offline", "--no-python-downloads",
            "--python", $existingPython, "python", "-c", "import sys; print(sys.version.split()[0])"
        ) -Description "Check existing environment Python")
        if (($existingVersion | Select-Object -Last 1) -ne $pythonPin) {
            throw "Existing environment does not use Python $pythonPin. Use -Recreate to preserve it before replacement."
        }
    }

    if ($Recreate -and (Test-Path -LiteralPath $venvPath)) {
        $backupPath = $venvPath + ".backup-" + [guid]::NewGuid().ToString("N")
        if ([IO.Path]::GetDirectoryName($backupPath) -ne $projectRoot) {
            throw "Invalid environment backup path."
        }
        Move-Item -LiteralPath $venvPath -Destination $backupPath
        Write-Step "Previous environment preserved at $backupPath"
    }
    [Environment]::SetEnvironmentVariable("UV_PROJECT_ENVIRONMENT", $venvPath, "Process")
    $null = Invoke-CheckedCommand -Executable $uvExe -Arguments @(
        "sync", "--locked", "--extra", "dev", "--inexact", "--python", $pythonExe, "--no-python-downloads"
    ) -Description "Install locked project and development dependencies"

    $venvPython = Join-Path $venvPath "Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw "Environment Python was not created: $venvPython"
    }
    $null = Invoke-CheckedCommand -Executable $uvExe -Arguments @(
        "pip", "check", "--python", $venvPython, "--offline", "--no-python-downloads"
    ) -Description "Check installed dependency compatibility"
    $healthCode = "import sys, html.entities, idna, pip, openai, fitz, docx, PySide6, fastapi; assert sys.version.split()[0] == '$pythonPin'; print('python and package health check: ok')"
    $null = Invoke-CheckedCommand -Executable $uvExe -Arguments @(
        "run", "--no-project", "--no-env-file", "--offline", "--no-python-downloads",
        "--python", $venvPython, "python", "-c", $healthCode
    ) -Description "Verify pinned Python and application imports"
    Write-Step "Done. Activate with:"
    Write-Host ". .\$VenvName\Scripts\Activate.ps1"
}
catch {
    if ($backupPath -and (Test-Path -LiteralPath $backupPath)) {
        if (Test-Path -LiteralPath $venvPath) {
            $failedPath = $venvPath + ".failed-" + [guid]::NewGuid().ToString("N")
            if ([IO.Path]::GetDirectoryName($failedPath) -ne $projectRoot) {
                throw "Invalid failed-environment path; original remains at $backupPath."
            }
            Move-Item -LiteralPath $venvPath -Destination $failedPath
            Write-Step "Incomplete replacement preserved at $failedPath"
        }
        Move-Item -LiteralPath $backupPath -Destination $venvPath
        Write-Step "Previous environment restored."
    }
    throw
}
finally {
    [Environment]::SetEnvironmentVariable("UV_PROJECT_ENVIRONMENT", $oldProjectEnvironment, "Process")
    Pop-Location
}
