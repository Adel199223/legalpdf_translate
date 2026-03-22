param(
    [string]$HostExePath = ""
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
$pythonExe = Resolve-RepoPython -RepoRoot $repoRoot
$sourcePath = Join-Path $repoRoot "src"

if (-not [string]::IsNullOrWhiteSpace($HostExePath) -and -not (Test-Path -LiteralPath $HostExePath)) {
    throw "Native host EXE not found at: $HostExePath"
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
    $command = @("-m", "legalpdf_translate.gmail_focus_host", "--register")
    if (-not [string]::IsNullOrWhiteSpace($HostExePath)) {
        $command += @("--host-executable", $HostExePath)
    }
    & $pythonExe @command
}
finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
