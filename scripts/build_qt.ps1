$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$buildRoot = Join-Path $repoRoot "build"
$distRoot = Join-Path $repoRoot "dist"
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
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "Build completed but EXE was not found at: $exePath"
}

Write-Host "Built EXE: $exePath"
Write-Output $exePath
