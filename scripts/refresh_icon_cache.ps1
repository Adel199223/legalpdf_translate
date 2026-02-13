param(
    [ValidateSet("Recommended", "DeepClean")]
    [string]$Mode = "Recommended"
)

$ErrorActionPreference = "Stop"

Write-Host "Refreshing Windows icon cache (mode: $Mode)"
Write-Host "Stopping Explorer..."
Get-Process -Name "explorer" -ErrorAction SilentlyContinue | Stop-Process -Force

try {
    $ie4uinitPath = Join-Path $env:SystemRoot "System32\ie4uinit.exe"
    if (-not (Test-Path -LiteralPath $ie4uinitPath)) {
        throw "ie4uinit.exe not found at: $ie4uinitPath"
    }

    Write-Host "Running ie4uinit.exe -ClearIconCache"
    & $ie4uinitPath -ClearIconCache

    if ($Mode -eq "DeepClean") {
        $iconCacheDir = Join-Path $env:LOCALAPPDATA "Microsoft\Windows\Explorer"
        $iconCacheFiles = @(Get-ChildItem -LiteralPath $iconCacheDir -Filter "iconcache*" -File -ErrorAction SilentlyContinue)
        if ($iconCacheFiles.Count -eq 0) {
            Write-Host "No iconcache* files found under: $iconCacheDir"
        } else {
            Write-Host "Deleting iconcache* files under: $iconCacheDir"
            foreach ($file in $iconCacheFiles) {
                Remove-Item -LiteralPath $file.FullName -Force
            }
        }
    }
}
finally {
    Write-Host "Restarting Explorer..."
    Start-Process "explorer.exe"
}

Write-Host "Icon cache refresh completed."
if ($Mode -eq "DeepClean") {
    Write-Host "DeepClean mode was used (iconcache* files removed when present)."
} else {
    Write-Host "Recommended mode was used."
}
