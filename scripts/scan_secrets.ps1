# Scans a directory tree for API-key-like strings using ripgrep.
# Usage:
#   .\scripts\scan_secrets.ps1                               # scans dist\legalpdf_translate
#   .\scripts\scan_secrets.ps1 -Path "$env:LOCALAPPDATA\Programs\LegalPDF Translate"
param([string]$Path = "dist\legalpdf_translate")

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Path)) {
    Write-Host "ERROR: path not found: $Path"
    exit 2
}

$patterns = @(
    'sk-[A-Za-z0-9]{20,}',
    'Authorization:\s*Bearer',
    'OPENAI_API_KEY\s*=',
    'x-api-key',
    'api[_-]?key\s*[:=]'
)

$found = $false
foreach ($pat in $patterns) {
    $hits = & rg --binary -c $pat $Path 2>$null
    if ($LASTEXITCODE -eq 0 -and $hits) {
        Write-Host "MATCH [$pat]:"
        $hits | ForEach-Object { Write-Host "  $_" }
        $found = $true
    }
}

if ($found) {
    Write-Host "`nFAIL: secret-like strings detected in $Path"
    exit 1
}
Write-Host "PASS: no secret-like strings found in $Path"
exit 0
