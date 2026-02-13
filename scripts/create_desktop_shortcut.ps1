$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$distPath = Join-Path $repoRoot "dist\legalpdf_translate"
$exePath = Join-Path $distPath "LegalPDFTranslate.exe"
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "EXE not found at: $exePath. Run scripts/build_qt.ps1 first."
}

$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutNames = @(
    "LegalPDF Translate.lnk",
    "LegalPDFTranslate.lnk",
    "LegalPDFTranslateQt.lnk"
)
foreach ($shortcutName in $shortcutNames) {
    $existingPath = Join-Path $desktopPath $shortcutName
    if (Test-Path -LiteralPath $existingPath) {
        Remove-Item -LiteralPath $existingPath -Force
    }
}

$shortcutPath = Join-Path $desktopPath "LegalPDF Translate.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $distPath
$shortcut.IconLocation = "$exePath,0"
$shortcut.Save()

Write-Host "Desktop shortcut: $shortcutPath"
Write-Output $shortcutPath
