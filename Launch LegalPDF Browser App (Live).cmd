@echo off
setlocal

set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

set "BUILD_CONFIG=%REPO_ROOT%\docs\assistant\runtime\CANONICAL_BUILD.json"
set "PYTHON_EXE=%REPO_ROOT%\.venv311\Scripts\python.exe"
set "LAUNCHER_SCRIPT=%REPO_ROOT%\tooling\launch_browser_app_live_detached.py"

if not exist "%LAUNCHER_SCRIPT%" (
  echo [LegalPDF] Missing browser launcher helper:
  echo %LAUNCHER_SCRIPT%
  echo.
  echo Open this repo in its expected location and try again.
  pause
  exit /b 1
)

if not exist "%PYTHON_EXE%" (
  if exist "%BUILD_CONFIG%" (
    for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$repoRoot = '%REPO_ROOT%'; $cfgPath = '%BUILD_CONFIG%'; function Convert-CodexPathToWindows([string]$PathText) { $trimmed = [string]$PathText; if ($trimmed -match '^/mnt/([A-Za-z])/(.*)$') { return ($matches[1].ToUpper() + ':\' + ($matches[2] -replace '/', '\')) }; return $trimmed.Trim() }; $roots = New-Object 'System.Collections.Generic.List[string]'; if (Test-Path -LiteralPath $repoRoot) { $roots.Add((Resolve-Path -LiteralPath $repoRoot).Path) }; if (Test-Path -LiteralPath $cfgPath) { try { $cfg = Get-Content -Raw $cfgPath | ConvertFrom-Json; $canonical = Convert-CodexPathToWindows ([string]$cfg.canonical_worktree_path); if (-not [string]::IsNullOrWhiteSpace($canonical) -and (Test-Path -LiteralPath $canonical)) { $resolved = (Resolve-Path -LiteralPath $canonical).Path; if ($roots -notcontains $resolved) { $roots.Add($resolved) } } } catch {} }; try { $gitRoots = git -C $repoRoot worktree list --porcelain 2>$null | Where-Object { $_ -like 'worktree *' } | ForEach-Object { $_.Substring(9).Trim() }; foreach ($gitRoot in $gitRoots) { if (-not [string]::IsNullOrWhiteSpace($gitRoot) -and (Test-Path -LiteralPath $gitRoot)) { $resolved = (Resolve-Path -LiteralPath $gitRoot).Path; if ($roots -notcontains $resolved) { $roots.Add($resolved) } } } } catch {}; foreach ($root in $roots) { foreach ($relative in @('.venv311\Scripts\python.exe', '.venv\Scripts\python.exe')) { $candidate = Join-Path $root $relative; if (Test-Path -LiteralPath $candidate) { Write-Output $candidate; exit 0 } } }"` ) do set "PYTHON_EXE=%%I"
  )
)

if not exist "%PYTHON_EXE%" (
  echo [LegalPDF] Missing Python environment:
  echo %PYTHON_EXE%
  echo.
  echo Recreate the local environment first, then try again.
  pause
  exit /b 1
)

"%PYTHON_EXE%" "%LAUNCHER_SCRIPT%" --mode live --workspace workspace-1
if errorlevel 1 (
  echo.
  echo [LegalPDF] Browser app launch failed.
  pause
  exit /b 1
)

exit /b 0
