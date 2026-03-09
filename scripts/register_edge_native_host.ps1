param(
    [string]$HostExePath = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $repoRoot ".venv311\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $pythonExe = "python"
}

if ([string]::IsNullOrWhiteSpace($HostExePath)) {
    $HostExePath = Join-Path $repoRoot "dist\legalpdf_translate\LegalPDFGmailFocusHost.exe"
}

if (-not (Test-Path -LiteralPath $HostExePath)) {
    throw "Native host EXE not found at: $HostExePath"
}

Push-Location $repoRoot
try {
    & $pythonExe -m legalpdf_translate.gmail_focus_host --register --host-executable $HostExePath
}
finally {
    Pop-Location
}
