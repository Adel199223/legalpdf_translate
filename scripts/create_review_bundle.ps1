[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[create-review-bundle] $Message"
}

function Normalize-RelativePath {
    param([string]$Path)

    $normalized = ([string]$Path).Trim().Trim('"') -replace "\\", "/"
    if ($normalized.StartsWith("./")) {
        $normalized = $normalized.Substring(2)
    }
    return $normalized.TrimStart("/")
}

function Test-DocArtifactPath {
    param([string]$RelativePath)

    $rel = Normalize-RelativePath -Path $RelativePath
    return $rel -match '\.(docx|pdf)$'
}

function Test-ArtifactScanIgnoredPath {
    param([string]$RelativePath)

    $rel = Normalize-RelativePath -Path $RelativePath
    if (-not $rel) {
        return $true
    }
    if ($rel -match '(^|/)\.git(/|$)') {
        return $true
    }
    if ($rel -match '(^|/)\.venv[^/]*(/|$)') {
        return $true
    }
    if ($rel -match '(^|/)(__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.playwright|\.playwright-cli)(/|$)') {
        return $true
    }
    if ($rel -match '(^|/)[^/]+\.egg-info(/|$)') {
        return $true
    }
    return $false
}

function Test-ExcludedPath {
    param([string]$RelativePath)

    $rel = Normalize-RelativePath -Path $RelativePath
    if (-not $rel) {
        return $true
    }

    $leaf = Split-Path -Path $rel -Leaf

    if ($rel -eq ".env") {
        return $true
    }
    if ($rel.StartsWith(".env.") -and $rel -ne ".env.example") {
        return $true
    }
    if ($rel -match '(^|/)\.git(/|$)') {
        return $true
    }
    if ($rel -match '(^|/)\.venv[^/]*(/|$)') {
        return $true
    }
    if ($rel -match '(^|/)(__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.playwright|\.playwright-cli)(/|$)') {
        return $true
    }
    if ($rel -match '(^|/)[^/]+\.egg-info(/|$)') {
        return $true
    }
    if ($rel -match '(^|/)[^/]+_run(/|$)') {
        return $true
    }
    if ($rel -match '(^|/)(tmp|output|dist)(/|$)') {
        return $true
    }
    if ($rel -match '(^|/)build(/|$)' -and $rel -ne 'build/pyinstaller_qt.spec') {
        return $true
    }
    if ($leaf -eq "requirements_freeze.txt" -or $leaf -like "rg_*") {
        return $true
    }
    if (Test-DocArtifactPath -RelativePath $rel) {
        return $true
    }
    return $false
}

function Get-GitCandidatePaths {
    $gitCommand = Get-Command git -ErrorAction SilentlyContinue
    if ($null -eq $gitCommand) {
        return $null
    }

    $paths = & git ls-files --cached --others --exclude-standard 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $null
    }

    return @($paths | ForEach-Object { Normalize-RelativePath -Path $_ })
}

function Get-FallbackCandidatePaths {
    param([string]$ProjectRoot)

    $paths = New-Object System.Collections.Generic.List[string]
    Get-ChildItem -LiteralPath $ProjectRoot -Recurse -Force -File | ForEach-Object {
        $relative = $_.FullName.Substring($ProjectRoot.Length).TrimStart('\')
        $paths.Add((Normalize-RelativePath -Path $relative))
    }
    return $paths.ToArray()
}

function Get-GeneratedDocumentArtifacts {
    param([string]$ProjectRoot)

    $gitCommand = Get-Command git -ErrorAction SilentlyContinue
    if ($null -ne $gitCommand) {
        $paths = & git ls-files --others --ignored --exclude-standard -- "*.docx" "*.pdf" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return @(
                $paths |
                ForEach-Object { Normalize-RelativePath -Path $_ } |
                Where-Object { -not (Test-ArtifactScanIgnoredPath -RelativePath $_) } |
                Sort-Object -Unique
            )
        }
    }

    $matches = New-Object System.Collections.Generic.List[string]
    Get-ChildItem -LiteralPath $ProjectRoot -Recurse -Force -File -Include *.docx, *.pdf | ForEach-Object {
        $relative = Normalize-RelativePath -Path ($_.FullName.Substring($ProjectRoot.Length).TrimStart('\'))
        if ((Test-DocArtifactPath -RelativePath $relative) -and -not (Test-ArtifactScanIgnoredPath -RelativePath $relative)) {
            $matches.Add($relative)
        }
    }
    return $matches.ToArray() | Sort-Object -Unique
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot
Write-Step "Project root: $projectRoot"

$downloads = Join-Path $env:USERPROFILE "Downloads"
if (-not (Test-Path $downloads)) {
    New-Item -ItemType Directory -Path $downloads -Force | Out-Null
}

$gitShortHash = $null
$gitCommand = Get-Command git -ErrorAction SilentlyContinue
if ($null -ne $gitCommand) {
    $gitShortHash = (& git rev-parse --short HEAD 2>$null)
    if ($LASTEXITCODE -ne 0) {
        $gitShortHash = $null
    }
}
if ([string]::IsNullOrWhiteSpace($gitShortHash)) {
    $gitShortHash = "workingtree"
}

$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$zipPath = Join-Path $downloads ("legalpdf_translate_source_{0}_{1}.zip" -f $gitShortHash.Trim(), $timestamp)

$candidatePaths = Get-GitCandidatePaths
if ($null -eq $candidatePaths) {
    Write-Step "Git file listing unavailable. Falling back to directory walk."
    $candidatePaths = Get-FallbackCandidatePaths -ProjectRoot $projectRoot
}
else {
    Write-Step "Using Git-tracked and untracked file listing for bundle contents."
}

$includedPaths = New-Object System.Collections.Generic.List[string]
foreach ($path in @($candidatePaths | Sort-Object -Unique)) {
    if (-not (Test-ExcludedPath -RelativePath $path)) {
        $fullPath = Join-Path $projectRoot ($path -replace "/", "\")
        if (Test-Path $fullPath -PathType Leaf) {
            $includedPaths.Add($path)
        }
    }
}

$excludedGeneratedDocs = Get-GeneratedDocumentArtifacts -ProjectRoot $projectRoot

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$fileStream = [System.IO.File]::Open($zipPath, [System.IO.FileMode]::CreateNew)
try {
    $archive = New-Object System.IO.Compression.ZipArchive($fileStream, [System.IO.Compression.ZipArchiveMode]::Create, $false)
    try {
        foreach ($path in $includedPaths) {
            $sourcePath = Join-Path $projectRoot ($path -replace "/", "\")
            $entryName = "legalpdf_translate/$path"
            $entry = $archive.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
            $entry.LastWriteTime = [DateTimeOffset](Get-Item -LiteralPath $sourcePath).LastWriteTime
            $entryStream = $entry.Open()
            try {
                $sourceStream = [System.IO.File]::OpenRead($sourcePath)
                try {
                    $sourceStream.CopyTo($entryStream)
                }
                finally {
                    $sourceStream.Dispose()
                }
            }
            finally {
                $entryStream.Dispose()
            }
        }
    }
    finally {
        $archive.Dispose()
    }
}
finally {
    $fileStream.Dispose()
}

Write-Step "Bundle created: $zipPath"
if (@($excludedGeneratedDocs).Count -gt 0) {
    $preview = @($excludedGeneratedDocs | Select-Object -First 5)
    Write-Step ("Generated DOCX/PDF files excluded: yes ({0})" -f @($excludedGeneratedDocs).Count)
    Write-Step ("Excluded examples: {0}" -f ($preview -join ", "))
}
else {
    Write-Step "Generated DOCX/PDF files excluded: no generated DOCX/PDF files were found."
}

Write-Host $zipPath
