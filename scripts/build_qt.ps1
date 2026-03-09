param(
    [switch]$SkipIconRefresh
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$buildRoot = Join-Path $repoRoot "build"
$distRoot = Join-Path $repoRoot "dist"
$shortcutScript = Join-Path $PSScriptRoot "create_desktop_shortcut.ps1"
$registerHostScript = Join-Path $PSScriptRoot "register_edge_native_host.ps1"
$refreshScript = Join-Path $PSScriptRoot "refresh_icon_cache.ps1"
$icoPath = Join-Path $repoRoot "resources\icons\LegalPDFTranslate.ico"
$cleanTargets = @()

if (Test-Path -LiteralPath $buildRoot) {
    $buildDirs = Get-ChildItem -LiteralPath $buildRoot -Directory
    foreach ($dir in $buildDirs) {
        $cleanTargets += $dir.FullName
    }
}

if (Test-Path -LiteralPath $distRoot) {
    $cleanTargets += $distRoot
}

foreach ($target in $cleanTargets) {
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

Push-Location $repoRoot
try {
    python -m PyInstaller "build\pyinstaller_qt.spec" --clean --noconfirm
}
finally {
    Pop-Location
}

$exePath = Join-Path $repoRoot "dist\legalpdf_translate\LegalPDFTranslate.exe"
$focusHostExePath = Join-Path $repoRoot "dist\legalpdf_translate\LegalPDFGmailFocusHost.exe"
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "Build completed but EXE was not found at: $exePath"
}
if (-not (Test-Path -LiteralPath $focusHostExePath)) {
    throw "Build completed but native host EXE was not found at: $focusHostExePath"
}
if (-not (Test-Path -LiteralPath $icoPath)) {
    throw "Build completed but ICO was not found at: $icoPath"
}

& $registerHostScript -HostExePath $focusHostExePath
$shortcutSummary = & $shortcutScript

if (-not $SkipIconRefresh) {
    & $refreshScript -Mode Recommended
} else {
    Write-Host "Skipping icon cache refresh because -SkipIconRefresh was set."
}

Write-Host "Built EXE: $exePath"
Write-Host "Built native host EXE: $focusHostExePath"
Write-Host "Using ICO: $icoPath"
Write-Host "Shortcut summary:"
$shortcutSummary | Format-Table ShortcutPath, TargetPath, IconLocation -AutoSize | Out-Host
Write-Output $exePath
