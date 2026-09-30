[CmdletBinding()]
param(
    [switch]$ConfigurationOnly,
    [string]$PythonExecutable,
    [string]$DartExecutable,
    [switch]$AsJson
)

# This entry point only reads tracked inputs and requests tool versions.
# It never applies WinGet configuration, installs packages or creates an environment.
$ErrorActionPreference = "Stop"
if (Test-Path Variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$checks = New-Object System.Collections.Generic.List[object]

function Add-Check {
    param([string]$Name, [string]$Expected, [string]$Actual, [bool]$Required, [string]$Message, [bool]$Passed)
    $checks.Add([pscustomobject]@{
        name = $Name; expected = $Expected; actual = $Actual; required = $Required
        status = $(if ($Passed) { "pass" } elseif ($Required) { "fail" } else { "advisory" })
        message = $Message
    })
}

function Assert-Contract {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Read-VersionPin {
    param([string]$Name)
    $value = (Get-Content -LiteralPath (Join-Path $projectRoot $Name) -Raw).Trim()
    Assert-Contract ($value -match '^\d+\.\d+\.\d+$') "Invalid exact version in $Name."
    return $value
}

function Invoke-VersionProbe {
    param([string]$Executable, [string[]]$Arguments)
    $previousPreference = $ErrorActionPreference
    try {
        # Some version commands use stderr even on success (notably Dart).
        $ErrorActionPreference = "Continue"
        $output = @(& $Executable @Arguments 2>&1 | ForEach-Object { $_.ToString() })
        $code = $LASTEXITCODE
        if ($null -eq $code) { $code = 0 }
        return [pscustomobject]@{ succeeded = ($code -eq 0); text = ($output -join "`n") }
    }
    catch {
        return [pscustomobject]@{ succeeded = $false; text = "" }
    }
    finally { $ErrorActionPreference = $previousPreference }
}

function Find-Tool {
    param([string]$Name)
    $command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) { return $command.Source }
    return $null
}

function Check-Version {
    param([string]$Name, [string]$Executable, [string[]]$Arguments, [string]$Pattern, [string]$Expected, [bool]$Required, [switch]$Minimum)
    if (-not $Executable -or -not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        Add-Check $Name $Expected "missing" $Required "Tool is unavailable; no installation was attempted." $false
        return
    }
    $result = Invoke-VersionProbe $Executable $Arguments
    if (-not $result.succeeded -or $result.text -notmatch $Pattern) {
        Add-Check $Name $Expected "unverified" $Required "Version command failed or returned an unrecognized version." $false
        return
    }
    $actual = $Matches.version
    $actualVersion = $null
    $passed = if ($Minimum) { [version]::TryParse($actual, [ref]$actualVersion) -and $actualVersion -ge [version]$Expected } else { $actual -eq $Expected }
    Add-Check $Name $Expected $actual $Required $(if ($passed) { "Version check passed." } else { "Version differs from the recorded baseline; no changes were made." }) $passed
}

try {
    $baseline = Get-Content -LiteralPath (Join-Path $projectRoot "config/dev-workstation.json") -Raw | ConvertFrom-Json
    $configuration = Get-Content -LiteralPath (Join-Path $projectRoot "config/dev-workstation.winget") -Raw | ConvertFrom-Json
    Assert-Contract ($baseline.schemaVersion -eq 1) "Unsupported workstation baseline schema."
    $pythonPin = Read-VersionPin ".python-version"
    $nodePin = Read-VersionPin ".node-version"
    $dartPin = Read-VersionPin ".dart-version"
    $pyproject = Get-Content -LiteralPath (Join-Path $projectRoot "pyproject.toml") -Raw
    Assert-Contract ($pyproject -match '(?m)^required-version\s*=\s*"==(?<version>\d+\.\d+\.\d+)"\s*$') "Missing exact uv pin in pyproject.toml."
    $uvPin = $Matches.version
    Assert-Contract ($pythonPin -eq "3.11.9" -and $uvPin -eq "0.12.20") "Python/uv compatibility pins were changed; review a separate upgrade before updating this baseline."
    Assert-Contract ($baseline.versions.python -eq $pythonPin -and $baseline.versions.uv -eq $uvPin -and $baseline.versions.node -eq $nodePin -and $baseline.versions.dart -eq $dartPin) "Workstation baseline and tracked tool pins disagree."
    Assert-Contract ($configuration.'$schema' -eq "https://aka.ms/configuration-dsc-schema/0.2" -and $configuration.properties.configurationVersion -eq "0.2.0") "Unsupported WinGet configuration schema."
    Assert-Contract (@($configuration.PSObject.Properties.Name).Count -eq 2 -and @($configuration.properties.PSObject.Properties.Name).Count -eq 2) "Unexpected WinGet configuration sections."
    $packages = @($baseline.packages)
    $resources = @($configuration.properties.resources)
    $expectedTools = @("git", "uv", "node", "dart", "gh", "rg")
    $approvedIds = @{ git = "Git.Git"; uv = "astral-sh.uv"; node = "OpenJS.NodeJS.LTS"; dart = "Google.DartSDK"; gh = "GitHub.cli"; rg = "BurntSushi.ripgrep.MSVC" }
    Assert-Contract ($packages.Count -eq $expectedTools.Count -and $resources.Count -eq $expectedTools.Count) "Unexpected package/resource count."
    Assert-Contract (@($packages.tool | Sort-Object -Unique).Count -eq $expectedTools.Count -and @($resources.id | Sort-Object -Unique).Count -eq $expectedTools.Count) "Duplicate package/resource identity."
    foreach ($package in $packages) {
        Assert-Contract ($expectedTools -contains $package.tool) "Unapproved workstation tool in configuration."
        Assert-Contract ($package.id -ceq $approvedIds[$package.tool]) "Unapproved WinGet package identity."
        $expectedVersion = $baseline.versions.($package.tool)
        if ($package.tool -eq "git") { $expectedVersion = $expectedVersion -replace '\.windows\.\d+$', '' }
        Assert-Contract ($package.version -is [string] -and $package.version -eq $expectedVersion) "WinGet package version differs from recorded tool baseline."
        $resource = @($resources | Where-Object { $_.id -eq $package.tool })
        Assert-Contract ($resource.Count -eq 1 -and $resource[0].resource -eq "Microsoft.WinGet.DSC/WinGetPackage") "Unsupported WinGet resource."
        $unit = $resource[0]
        Assert-Contract (@($unit.PSObject.Properties.Name).Count -eq 4 -and @($unit.directives.PSObject.Properties.Name).Count -eq 3 -and @($unit.settings.PSObject.Properties.Name).Count -eq 7) "Unexpected WinGet resource directives/settings."
        Assert-Contract ($unit.directives.description -is [string] -and $unit.directives.version -eq $baseline.wingetDscVersion -and $unit.directives.allowPrerelease -is [bool] -and $unit.directives.allowPrerelease -eq $false) "WinGet processor must use the recorded stable module version."
        $settings = $unit.settings
        Assert-Contract ($settings.Id -ceq $package.id -and $settings.Source -eq "winget" -and $settings.Version -is [string] -and $settings.Version -eq $package.version) "WinGet package identity/source/version mismatch."
        Assert-Contract ($settings.Ensure -eq "Present" -and $settings.MatchOption -eq "Equals" -and $settings.UseLatest -is [bool] -and $settings.UseLatest -eq $false -and $settings.InstallMode -eq "Silent") "WinGet package must preserve exact version matching."
    }
    Add-Check "configuration" "tracked exact pins and six approved packages" "coherent" $true "Offline structural and pin checks passed; no WinGet processor/source was contacted." $true
}
catch {
    Add-Check "configuration" "coherent tracked inputs" "invalid" $true $_.Exception.Message $false
}

if (-not $ConfigurationOnly -and -not @($checks | Where-Object { $_.status -eq "fail" }).Count) {
    $uvExe = Find-Tool "uv"
    Check-Version "uv" $uvExe @("--version") 'uv (?<version>\d+\.\d+\.\d+\S*)' $uvPin $true
    if (-not $PythonExecutable -and $uvExe) {
        $found = Invoke-VersionProbe $uvExe @("python", "find", $pythonPin, "--no-project", "--no-python-downloads")
        if ($found.succeeded) { $PythonExecutable = ($found.text -split "`n" | Select-Object -Last 1).Trim() }
    }
    Check-Version "python" $PythonExecutable @("--version") 'Python (?<version>\d+\.\d+\.\d+\S*)' $pythonPin $true
    Check-Version "git" (Find-Tool "git") @("--version") 'git version (?<version>\d+\.\d+\.\d+\S*)' $baseline.versions.git $true
    Check-Version "node" (Find-Tool "node") @("--version") '^v(?<version>\d+\.\d+\.\d+\S*)\s*$' $nodePin $true
    if (-not $DartExecutable) { $DartExecutable = Find-Tool "dart" }
    if ($DartExecutable -and [IO.Path]::GetExtension($DartExecutable) -in @(".bat", ".cmd")) {
        # Flutter's batch launcher can bootstrap/update its SDK even for
        # --version. Select an existing SDK binary without executing it.
        $dartDirectory = Split-Path $DartExecutable -Parent
        $sdkCandidates = @( (Join-Path $dartDirectory "dart.exe"), (Join-Path $dartDirectory "cache/dart-sdk/bin/dart.exe") )
        $DartExecutable = $sdkCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    }
    Check-Version "dart" $DartExecutable @("--version") 'Dart SDK version: (?<version>\d+\.\d+\.\d+\S*)' $dartPin $true
    Check-Version "gh" (Find-Tool "gh") @("--version") 'gh version (?<version>\d+\.\d+\.\d+\S*)' $baseline.versions.gh $false
    Check-Version "rg" (Find-Tool "rg") @("--version") 'ripgrep (?<version>\d+\.\d+\.\d+\S*)' $baseline.versions.rg $false
    Check-Version "pwsh" (Find-Tool "pwsh") @("-NoProfile", "-NonInteractive", "-Command", '$PSVersionTable.PSVersion.ToString()') '(?<version>\d+\.\d+\.\d+\S*)' $baseline.versions.pwsh $false
    Check-Version "winget" (Find-Tool "winget") @("--version") 'v(?<version>\d+\.\d+\.\d+\S*)' $baseline.wingetMinimumVersion $false -Minimum
    $windowsPowerShell = Join-Path $env:SystemRoot "System32/WindowsPowerShell/v1.0/powershell.exe"
    Check-Version "windows-powershell" $windowsPowerShell @("-NoProfile", "-NonInteractive", "-Command", '$PSVersionTable.PSVersion.ToString()') '(?<version>\d+\.\d+\.\d+\S*)' "5.1" $true -Minimum
}

$failed = @($checks | Where-Object { $_.status -eq "fail" }).Count -gt 0
$report = [pscustomobject]@{
    status = $(if ($failed) { "fail" } else { "pass" })
    mode = $(if ($ConfigurationOnly) { "configuration-only" } else { "read-only-readiness" })
    checks = @($checks.ToArray())
    limitations = @("No tools, environments or services were installed or changed.", "Word/Gmail/browser readiness and runtime WinGet configuration validation are separate checks.")
}
if ($AsJson) { $report | ConvertTo-Json -Depth 8 }
else {
    $checks | Select-Object name, status, expected, actual | Format-Table -AutoSize
    Write-Output "Read-only checks complete. This command does not repair version differences or install tools."
}
if ($failed) { exit 1 }
