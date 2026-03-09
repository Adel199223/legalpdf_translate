param(
    [string[]]$TargetPath = @(),
    [switch]$ReportOnly
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$sourcePath = Join-Path $repoRoot "extensions\gmail_intake"
$edgeUserData = Join-Path $env:LOCALAPPDATA "Microsoft\Edge\User Data"

if (-not (Test-Path -LiteralPath $sourcePath)) {
    throw "Source extension directory not found at: $sourcePath"
}

if (-not (Test-Path -LiteralPath $edgeUserData)) {
    throw "Edge user data directory not found at: $edgeUserData"
}

$pythonExe = Join-Path $repoRoot ".venv311\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $pythonExe = "python"
}

$robocopyExe = Join-Path $env:SystemRoot "System32\robocopy.exe"
if (-not (Test-Path -LiteralPath $robocopyExe)) {
    $robocopyExe = "robocopy"
}

# The report is derived from Edge Secure Preferences entries for unpacked extensions/gmail_intake loads.
Push-Location $repoRoot
try {
    $reportPath = [System.IO.Path]::GetTempFileName()
    & $pythonExe -m legalpdf_translate.gmail_focus_host --edge-extension-report --edge-extension-report-file $reportPath
}
finally {
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
