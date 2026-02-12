$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$exePath = Join-Path $repoRoot "dist\legalpdf_translate\LegalPDFTranslate.exe"
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "EXE not found at: $exePath. Run scripts/build_qt.ps1 first."
}

$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "LegalPDF Translate.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = Split-Path -Path $exePath -Parent
$shortcut.IconLocation = $exePath
$shortcut.Save()

Write-Host "Desktop shortcut: $shortcutPath"
Write-Output $shortcutPath
