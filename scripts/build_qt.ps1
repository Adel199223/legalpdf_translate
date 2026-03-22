param(
    [switch]$SkipIconRefresh
)

$ErrorActionPreference = "Stop"

function Convert-CodexPathToWindows {
    param(
        [string]$PathText
    )

    $trimmed = [string]$PathText
    if ($null -eq $PathText) {
        $trimmed = ""
    }
    $trimmed = $trimmed.Trim()
    if ($trimmed -match '^/mnt/([A-Za-z])/(.*)$') {
        return ($Matches[1].ToUpper() + ':\' + ($Matches[2] -replace '/', '\'))
    }
    return $trimmed
}

function Get-CanonicalRepoRoot {
    param(
        [string]$RepoRoot
    )

    $buildConfig = Join-Path $RepoRoot "docs\assistant\runtime\CANONICAL_BUILD.json"
    if (-not (Test-Path -LiteralPath $buildConfig)) {
        return $null
    }
    try {
        $config = (Get-Content -LiteralPath $buildConfig -Raw | ConvertFrom-Json)
    }
    catch {
        return $null
    }
    $candidate = Convert-CodexPathToWindows -PathText ([string]$config.canonical_worktree_path)
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        return $null
    }
    if (-not (Test-Path -LiteralPath $candidate)) {
        return $null
    }
    return (Resolve-Path -LiteralPath $candidate).Path
}

function Resolve-RepoPython {
    param(
        [string]$RepoRoot
    )

    $candidateRoots = @($RepoRoot)
    $canonicalRoot = Get-CanonicalRepoRoot -RepoRoot $RepoRoot
    if ($canonicalRoot -and ($canonicalRoot -notin $candidateRoots)) {
        $candidateRoots += $canonicalRoot
    }
    foreach ($root in $candidateRoots) {
        foreach ($relativePath in @(".venv311\Scripts\python.exe", ".venv\Scripts\python.exe")) {
            $candidate = Join-Path $root $relativePath
            if (Test-Path -LiteralPath $candidate) {
                return $candidate
            }
        }
    }
    return "python"
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$buildRoot = Join-Path $repoRoot "build"
$distRoot = Join-Path $repoRoot "dist"
$shortcutScript = Join-Path $PSScriptRoot "create_desktop_shortcut.ps1"
$registerHostScript = Join-Path $PSScriptRoot "register_edge_native_host.ps1"
$refreshScript = Join-Path $PSScriptRoot "refresh_icon_cache.ps1"
$icoPath = Join-Path $repoRoot "resources\icons\LegalPDFTranslate.ico"
$cleanTargets = @()
$pythonExe = Resolve-RepoPython -RepoRoot $repoRoot
$sourcePath = Join-Path $repoRoot "src"

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
$previousPythonPath = $env:PYTHONPATH
try {
    if (Test-Path -LiteralPath $sourcePath) {
        if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
            $env:PYTHONPATH = $sourcePath
        }
        else {
            $env:PYTHONPATH = "$sourcePath;$previousPythonPath"
        }
    }
    & $pythonExe -m PyInstaller "build\pyinstaller_qt.spec" --clean --noconfirm
}
finally {
    $env:PYTHONPATH = $previousPythonPath
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

& $registerHostScript
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
