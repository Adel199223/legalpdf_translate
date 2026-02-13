$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$distPath = Join-Path $repoRoot "dist\legalpdf_translate"
$exePath = Join-Path $distPath "LegalPDFTranslate.exe"
$icoPath = Join-Path $repoRoot "resources\icons\LegalPDFTranslate.ico"
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "EXE not found at: $exePath. Run scripts/build_qt.ps1 first."
}
if (-not (Test-Path -LiteralPath $icoPath)) {
    throw "Icon not found at: $icoPath. Generate/build icon assets first."
}

$desktopPaths = @(
    [Environment]::GetFolderPath("Desktop"),
    [Environment]::GetFolderPath("CommonDesktopDirectory")
)

foreach ($desktopPath in $desktopPaths) {
    if (-not $desktopPath) {
        continue
    }
    if (-not (Test-Path -LiteralPath $desktopPath)) {
        continue
    }
    $existingShortcuts = Get-ChildItem -LiteralPath $desktopPath -Filter "*.lnk" -File |
        Where-Object { $_.Name -imatch "^LegalPDF.*\.lnk$" }
    foreach ($existing in $existingShortcuts) {
        Remove-Item -LiteralPath $existing.FullName -Force
    }
}

$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "LegalPDF Translate.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $distPath
$shortcut.IconLocation = "$icoPath,0"
$shortcut.Save()

$summaryShortcut = $shell.CreateShortcut($shortcutPath)
$summary = [PSCustomObject]@{
    ShortcutPath = $shortcutPath
    TargetPath = $summaryShortcut.TargetPath
    IconLocation = $summaryShortcut.IconLocation
}

$allShortcuts = @()
foreach ($checkDesktopPath in $desktopPaths) {
    if (-not $checkDesktopPath) {
        continue
    }
    if (-not (Test-Path -LiteralPath $checkDesktopPath)) {
        continue
    }
    $allShortcuts += Get-ChildItem -LiteralPath $checkDesktopPath -Filter "*.lnk" -File |
        Where-Object { $_.Name -imatch "^LegalPDF.*\.lnk$" }
}

if ($allShortcuts.Count -ne 1 -or $allShortcuts[0].Name -cne "LegalPDF Translate.lnk") {
    $found = if ($allShortcuts.Count -eq 0) { "<none>" } else { ($allShortcuts | ForEach-Object { $_.FullName }) -join "; " }
    throw "Expected exactly one canonical LegalPDF shortcut across user/public desktops, found: $found"
}

Write-Host "Desktop shortcut created and normalized:"
$summary | Format-Table ShortcutPath, TargetPath, IconLocation -AutoSize | Out-Host
Write-Output $summary
