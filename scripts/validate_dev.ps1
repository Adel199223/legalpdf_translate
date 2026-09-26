[CmdletBinding()]
param(
    [switch]$Full,
    [switch]$Quick,
    [ValidateSet(1, 2, 4)]
    [int]$Workers = 2
)

$ErrorActionPreference = "Stop"
if ($Quick -and $Full) {
    throw "Choose either -Quick or -Full."
}
if (Test-Path Variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

function Write-Step {
    param([string]$Message)
    Write-Host "[validate-dev] $Message"
}

function Format-CommandDisplay {
    param(
        [string]$Executable,
        [string[]]$Arguments
    )

    $parts = @($Executable) + $Arguments
    return ($parts | ForEach-Object {
        if ($_ -match '\s|"') {
            '"' + ($_ -replace '"', '\"') + '"'
        }
        else {
            $_
        }
    }) -join " "
}

function Invoke-LoggedCommand {
    param(
        [string]$Executable,
        [string[]]$Arguments,
        [string]$DisplayCommand,
        [switch]$AllowFailure
    )

    Write-Step "RUN: $DisplayCommand"
    $outputLines = @()
    $exitCode = 0
    $previousPreference = $ErrorActionPreference
    if ($AllowFailure) {
        $ErrorActionPreference = "Continue"
    }
    try {
        $outputLines = & $Executable @Arguments 2>&1 | ForEach-Object {
            Write-Host $_.ToString()
            $_
        }
        $exitCode = $LASTEXITCODE
        if ($null -eq $exitCode) {
            $exitCode = 0
        }
    }
    catch {
        $outputLines = @($_)
        Write-Host $_.ToString()
        $exitCode = if ($LASTEXITCODE) { $LASTEXITCODE } else { 1 }
        if (-not $AllowFailure) {
            throw
        }
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($exitCode -eq 0) {
        Write-Step "PASS (exit $exitCode): $DisplayCommand"
    }
    else {
        Write-Step "FAIL (exit $exitCode): $DisplayCommand"
        if (-not $AllowFailure) {
            exit $exitCode
        }
    }
    return [pscustomobject]@{
        ExitCode = $exitCode
        OutputText = ((@($outputLines) | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine)
        DisplayCommand = $DisplayCommand
    }
}

function Get-ChangedPaths {
    $statusLines = & git status --porcelain=v1 -uall 2>$null
    if ($LASTEXITCODE -ne 0) {
        return @()
    }

    $paths = New-Object System.Collections.Generic.List[string]
    foreach ($line in @($statusLines)) {
        $text = [string]$line
        if ([string]::IsNullOrWhiteSpace($text) -or $text.Length -lt 4) {
            continue
        }
        $path = $text.Substring(3).Trim()
        if ($path -match ' -> ') {
            $path = ($path -split ' -> ', 2)[1]
        }
        $path = $path.Trim('"') -replace '\\', '/'
        if ($path) {
            $paths.Add($path)
        }
    }
    return $paths.ToArray()
}

function Test-DocsValidationTriggered {
    param([string[]]$Paths)

    foreach ($path in @($Paths)) {
        $normalized = ([string]$path).Trim().Replace('\', '/').ToLowerInvariant()
        if ($normalized.StartsWith("docs/assistant/") -or $normalized -eq "readme.md" -or $normalized -eq "app_knowledge.md") {
            return $true
        }
    }
    return $false
}

function Invoke-DartValidator {
    param(
        [string]$ScriptPath,
        [string]$DirectDartExe
    )

    $primaryDisplay = "dart run $ScriptPath"
    $primary = Invoke-LoggedCommand -Executable "dart" -Arguments @("run", $ScriptPath) -DisplayCommand $primaryDisplay -AllowFailure
    if ($primary.ExitCode -eq 0) {
        return
    }
    if ($primary.OutputText -match "Unable to find AOT snapshot for dartdev") {
        Write-Step "Detected dartdev AOT snapshot issue. Falling back to direct Dart executable."
        if (-not (Test-Path $DirectDartExe)) {
            Write-Step "Direct Dart executable not found: $DirectDartExe"
            exit 1
        }
        $fallbackDisplay = Format-CommandDisplay -Executable $DirectDartExe -Arguments @($ScriptPath)
        $null = Invoke-LoggedCommand -Executable $DirectDartExe -Arguments @($ScriptPath) -DisplayCommand $fallbackDisplay
        return
    }
    exit $primary.ExitCode
}

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $projectRoot
Write-Step "Project root: $projectRoot"

$venvPython = Join-Path $projectRoot ".venv311\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Step "Missing required project interpreter: $venvPython"
    Write-Host "Create the Python 3.11 project environment first:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts/setup_python311_env.ps1"
    exit 1
}

$changedPaths = Get-ChangedPaths
$docsValidationTriggered = Test-DocsValidationTriggered -Paths $changedPaths
$directDartExe = "C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe"

$quickCommands = @(
    @{
        Executable = $venvPython
        Arguments = @("-m", "pytest", "-q", "--durations=10",
            "tests/test_cli_flags.py", "tests/test_workflow_parallel.py", "tests/test_run_report.py",
            "tests/test_translation_browser_state.py", "tests/test_source_review_browser_state.py",
            "tests/test_formatting_review_browser_state.py", "-k",
            "not test_actual_dom_operator_actions_to_public_service_context_and_workflow and not test_actual_dom_to_owned_formatting_api_build_and_download_preserves_original_run")
    },
    @{
        Executable = $venvPython
        Arguments = @("-m", "compileall", "-q", "src", "tests", "tooling")
    }
)

$baselineCommands = @(
    @{
        Executable = $venvPython
        Arguments = @("-m", "pytest", "-q", "--durations=10", "tests/test_shadow_web_api.py", "tests/test_shadow_web_route_state.py", "tests/test_translation_browser_state.py")
    },
    @{
        Executable = $venvPython
        Arguments = @("-m", "compileall", "-q", "src", "tests", "tooling")
    }
)

$fullExtraCommands = @(
    @{
        Executable = $venvPython
        Arguments = @("-m", "pytest", "-q", "--durations=10", "tests/test_gmail_review_state.py")
    },
    @{
        Executable = $venvPython
        Arguments = @("-m", "pytest", "-q", "--durations=10", "tests/test_gmail_intake.py", "-k", "browser_pdf or runtime_guard or review")
    },
    @{
        Executable = $venvPython
        Arguments = @("-m", "pytest", "-q", "--durations=10",
            "tests/test_source_review_candidate.py", "tests/test_ordinary_reviewed_source.py",
            "tests/test_ordinary_source_review_service.py", "tests/test_ordinary_source_bounded_reads.py",
            "tests/test_browser_source_review.py", "tests/test_shadow_web_source_review_api.py",
            "tests/test_source_review_browser_state.py")
    },
    @{
        Executable = $venvPython
        Arguments = @("tooling/test_shards.py", "run", "--workers", [string]$Workers,
            "--timings", "tooling/test_timings.json", "--output",
            (Join-Path $projectRoot ("tmp/validation/formatting-" + [guid]::NewGuid().ToString("N"))), "--",
            "tests/test_ordinary_formatting_review_service.py", "tests/test_ordinary_formatting_options.py",
            "tests/test_browser_formatting_review.py", "tests/test_shadow_web_formatting_review_api.py",
            "tests/test_formatting_review_browser_state.py", "tests/test_formatting_review_cli.py")
    }
)

$initialCommands = if ($Quick) { $quickCommands } else { $baselineCommands }
Write-Step $(if ($Quick) { "Quick feedback tier; does not replace Full or complete pytest." } elseif ($Full) { "Selected Full tier; formatting group uses $Workers isolated process(es)." } else { "Standard browser tier." })
foreach ($command in $initialCommands) {
    $display = Format-CommandDisplay -Executable $command.Executable -Arguments $command.Arguments
    $null = Invoke-LoggedCommand -Executable $command.Executable -Arguments $command.Arguments -DisplayCommand $display
}

if ($Full) {
    foreach ($command in $fullExtraCommands) {
        $display = Format-CommandDisplay -Executable $command.Executable -Arguments $command.Arguments
        $null = Invoke-LoggedCommand -Executable $command.Executable -Arguments $command.Arguments -DisplayCommand $display
    }
}

if ($docsValidationTriggered) {
    Write-Step "Docs or ExecPlan changes detected in the working tree. Running agent docs validation."
    Invoke-DartValidator -ScriptPath "tooling/validate_agent_docs.dart" -DirectDartExe $directDartExe
}
else {
    Write-Step "No docs or ExecPlan changes detected. Skipping agent docs validation."
}

$workspaceHygieneScript = Join-Path $projectRoot "tooling\validate_workspace_hygiene.dart"
if (Test-Path $workspaceHygieneScript) {
    Write-Step "Workspace hygiene validator is available. Running it."
    Invoke-DartValidator -ScriptPath "tooling/validate_workspace_hygiene.dart" -DirectDartExe $directDartExe
}
else {
    Write-Step "Workspace hygiene validator not found. Skipping it."
}

Write-Step "Validation complete."
