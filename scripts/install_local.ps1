$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$buildScript = Join-Path $PSScriptRoot "build_qt.ps1"
$shortcutScript = Join-Path $PSScriptRoot "create_desktop_shortcut.ps1"
$exePath = Join-Path $repoRoot "dist\legalpdf_translate\LegalPDFTranslate.exe"

if (-not (Test-Path -LiteralPath $exePath)) {
    & $buildScript
}

& $shortcutScript
Write-Output "Installed: click Desktop shortcut"
