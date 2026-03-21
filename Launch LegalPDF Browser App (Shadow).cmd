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
    for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$cfg = Get-Content -Raw '%BUILD_CONFIG%' | ConvertFrom-Json; $path = [string]$cfg.canonical_worktree_path; if ($path -match '^/mnt/([A-Za-z])/(.*)$') { $path = ($matches[1].ToUpper() + ':\' + ($matches[2] -replace '/', '\')) }; Write-Output (Join-Path $path '.venv311\Scripts\python.exe')"` ) do set "PYTHON_EXE=%%I"
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

"%PYTHON_EXE%" "%LAUNCHER_SCRIPT%" --mode shadow --workspace workspace-1
if errorlevel 1 (
  echo.
  echo [LegalPDF] Browser app launch failed.
  pause
  exit /b 1
)

exit /b 0
