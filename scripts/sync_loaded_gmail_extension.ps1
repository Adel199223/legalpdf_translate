param(
    [string[]]$TargetPath = @(),
    [switch]$ReportOnly
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
$sourcePath = Join-Path $repoRoot "extensions\gmail_intake"
$edgeUserData = Join-Path $env:LOCALAPPDATA "Microsoft\Edge\User Data"

if (-not (Test-Path -LiteralPath $sourcePath)) {
    throw "Source extension directory not found at: $sourcePath"
}

if (-not (Test-Path -LiteralPath $edgeUserData)) {
    throw "Edge user data directory not found at: $edgeUserData"
}

$pythonExe = Resolve-RepoPython -RepoRoot $repoRoot
$repoSourcePath = Join-Path $repoRoot "src"

$robocopyExe = Join-Path $env:SystemRoot "System32\robocopy.exe"
if (-not (Test-Path -LiteralPath $robocopyExe)) {
    $robocopyExe = "robocopy"
}

# The report is derived from Edge Secure Preferences entries for unpacked extensions/gmail_intake loads.
Push-Location $repoRoot
$previousPythonPath = $env:PYTHONPATH
try {
    if (Test-Path -LiteralPath $repoSourcePath) {
        if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
            $env:PYTHONPATH = $repoSourcePath
        }
        else {
            $env:PYTHONPATH = "$repoSourcePath;$previousPythonPath"
        }
    }
    $reportPath = [System.IO.Path]::GetTempFileName()
    & $pythonExe -m legalpdf_translate.gmail_focus_host --edge-extension-report --edge-extension-report-file $reportPath
}
finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
try {
    $report = (Get-Content -LiteralPath $reportPath -Raw) | ConvertFrom-Json
}
finally {
    if (Test-Path -LiteralPath $reportPath) {
        Remove-Item -LiteralPath $reportPath -Force -ErrorAction SilentlyContinue
    }
}

if ($report.active_extension_ids.Count -gt 0) {
    Write-Output ("Active Gmail intake extension IDs: " + (($report.active_extension_ids | Sort-Object) -join ", "))
}
else {
    Write-Output "Active Gmail intake extension IDs: none"
}

if ($report.stale_extension_ids.Count -gt 0) {
    Write-Output ("Stale Gmail intake extension IDs: " + (($report.stale_extension_ids | Sort-Object) -join ", "))
}
else {
    Write-Output "Stale Gmail intake extension IDs: none"
}

if ($report.records.Count -gt 0) {
    foreach ($record in $report.records) {
        $state = if ($record.enabled) { "active" } else { "stale" }
        Write-Output ("[{0}] {1} ({2}) -> {3}" -f $state, $record.extension_id, $record.profile_name, $record.path)
    }
}

if ($ReportOnly) {
    return
}

$targets = @($TargetPath | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
if ($targets.Count -eq 0) {
    $targets = @($report.paths)
}

if ($targets.Count -eq 0) {
    throw "No loaded unpacked Gmail intake extension directories were found in Edge."
}

foreach ($targetPath in $targets) {
    if ([string]::IsNullOrWhiteSpace($targetPath)) {
        continue
    }
    if ($targetPath -eq $sourcePath) {
        continue
    }
    if (-not (Test-Path -LiteralPath $targetPath)) {
        continue
    }
    $null = & $robocopyExe $sourcePath $targetPath /MIR /NFL /NDL /NJH /NJS /NP
    $exitCode = $LASTEXITCODE
    if ($exitCode -gt 7) {
        throw "robocopy failed while syncing to: $targetPath"
    }
    Write-Output "Synced Gmail intake extension to: $targetPath"
}
