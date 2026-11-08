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
        Arguments = @("-m", "pytest", "-q", "--durations=10",
            "tests/test_openai_multi_image.py",
            "tests/test_ocr_text_transport.py", "tests/test_ocr_text_transport_workflow.py",
            "tests/test_ordinary_semantic_audit.py", "tests/test_ordinary_semantic_review.py",
            "tests/test_ordinary_semantic_unit_refs.py", "tests/test_ordinary_semantic_inventory_budget.py",
            "tests/test_ordinary_semantic_source_review_policy.py",
            "tests/test_ordinary_semantic_page_coverage.py", "tests/test_semantic_page_coverage_integration.py",
            "tests/test_source_ambiguity_policy_v2.py", "tests/test_source_commitment_visual_v3.py", "tests/test_visible_literal_serialization_v4.py",
            "tests/test_source_precision_policy_v5.py", "tests/test_ordinary_semantic_repair.py", "tests/test_semantic_repair_diagnostics.py", "tests/test_semantic_validation_repair_v2.py",
            "tests/test_target_ambiguity_repair.py",
            "tests/test_primary_literal_markup.py",
            "tests/test_source_literal_authority.py", "tests/test_source_literal_authority_workflow.py",
            "tests/test_source_enclosure_authority.py", "tests/test_source_enclosure_authority_workflow.py",
            "tests/test_bounded_enclosure_identity.py",
            "tests/test_initial_enclosure_permutation_replacement.py",
            "tests/test_generated_emphasis_adjacent_lrm_v3.py",
            "tests/test_protected_folio_bridges_v4.py",
            "tests/test_reference_footer_hint_v5.py", "tests/test_source_folio_inline_direction.py", "tests/test_completed_unreviewed_rebuild.py",
            "tests/test_semantic_review_model_policy.py",
            "tests/test_semantic_review_native_billing.py", "tests/test_semantic_cache_usage_compatibility.py", "tests/test_semantic_review_model_integration.py",
            "tests/test_semantic_source_visual_literals.py", "tests/test_semantic_source_review_integration.py",
            "tests/test_semantic_unit_reference_integration.py", "tests/test_source_inventory_capacity_integration.py",
            "tests/test_source_boolean_question_order.py",
            "tests/test_primary_page_evidence_policy.py",
            "tests/test_primary_page_evidence.py",
            "tests/test_ocr_visual_source.py",
            "tests/test_semantic_ocr_enclosure.py",
            "tests/test_ocr_source_spans.py",
            "tests/test_source_phone_punctuation.py",
            "tests/test_ocr_tracking_omission.py",
            "tests/test_ordinary_source_postal_band.py",
            "tests/test_windows_ocr_worker.py",
            "tests/test_ordinary_source_acronyms.py",
            "tests/test_contact_folio_direction_v18.py",
            "tests/test_contact_folio_overlap_v19.py",
            "tests/test_source_alignment_instructions_v20.py",
            "tests/test_workflow_semantic_audit_integration.py",
            "tests/test_workflow_semantic_review_integration.py",
            "tests/test_semantic_audit_context_preservation.py",
            "tests/test_ar_lossless_source_components.py",
            "tests/test_ar_inline_component_proof.py",
            "tests/test_ar_prefixed_postal_packaging_v2.py",
            "tests/test_ar_source_components_v3.py",
            "tests/test_plain_list_columns_v6.py",
            "tests/test_terminal_footer_closing_v7.py",
            "tests/test_in_body_terminal_closing_v8.py",
            "tests/test_source_locative_house_join.py",
            "tests/test_source_locative_house_join_v3.py",
            "tests/test_visual_source_scope_v6.py",
            "tests/test_source_inventory_scope_v7.py",
            "tests/test_visible_source_encoding_v8.py",
            "tests/test_source_payment_roles_v9.py",
            "tests/test_ordinary_layout_reproposal.py",
            "tests/test_per_page_layout_reproposal.py",
            "tests/test_in_flow_folio_bridges_v13.py",
            "tests/test_labeled_folio_direction_v14.py",
            "tests/test_terminal_punctuation_folio_v15.py",
            "tests/test_terminal_closing_group_v4.py",
            "tests/test_terminal_closing_group_v5.py",
            "tests/test_primary_prefixed_postal_packaging_v2.py",
            "tests/test_ar_adjacent_literal_preservation.py",
            "tests/test_checkpoint_resume.py",
            "tests/test_primary_literal_packaging_integration.py",
            "tests/test_source_field_row_order.py", "tests/test_ar_field_label_boundaries.py",
            "tests/test_primary_assembly_checkpoint_recipe.py",
            "tests/test_primary_source_bound_folio.py", "tests/test_primary_source_bound_folio_separator.py",
            "tests/test_ordinary_flow_order_normalization.py",
            "tests/test_ordinary_body_columns_v3.py", "tests/test_ordinary_body_columns_workflow.py",
            "tests/test_ordinary_clock_direction.py", "tests/test_ordinary_clock_policy.py", "tests/test_ordinary_clock_workflow.py",
            "tests/test_ordinary_heading_columns_v4.py", "tests/test_ordinary_heading_columns_workflow.py",
            "tests/test_ordinary_controlled_folio_direction.py", "tests/test_source_folio_span_proof.py")
    },
    @{
        Executable = $venvPython
        Arguments = @("-m", "pytest", "-q", "--durations=10", "tests/test_shadow_runtime_metadata_atomic.py")
    },
    @{
        Executable = $venvPython
        Arguments = @("-m", "pytest", "-q", "--durations=10", "tests/test_gmail_review_state.py",
            "tests/test_translation_delivery_names.py", "tests/test_translation_completion_presentation.py",
            "tests/test_gmail_browser_service.py")
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
            "tests/test_formatting_review_browser_state.py", "tests/test_formatting_review_cli.py",
            "tests/test_run_docx_formatting_bounded_reads.py")
    },
    @{
        Executable = $venvPython
        Arguments = @("-m", "pytest", "-q", "--durations=10",
            "tests/test_saved_docx_layout.py", "tests/test_saved_docx_layout_writer.py",
            "tests/test_saved_docx_layout_horizontal_flow.py",
            "tests/test_saved_docx_layout_modern_compatibility.py",
            "tests/test_word_system_note_import.py",
            "tests/test_docx_writer.py", "tests/test_primary_docx_compatibility.py",
            "tests/test_primary_resume_compatibility.py",
            "tests/test_saved_docx_layout_partitions.py",
            "tests/test_ordinary_presentation.py",
            "tests/test_saved_docx_layout_service.py", "tests/test_shadow_web_saved_docx_layout_api.py",
            "tests/test_saved_docx_layout_browser_state.py",
            "tests/test_ordinary_auto_layout_artifacts.py")
    },
    @{
        Executable = $venvPython
        Arguments = @("-m", "pytest", "-q", "--durations=10",
            "tests/test_ordinary_layout_contracts.py", "tests/test_ordinary_layout_service.py",
            "tests/test_ordinary_source_evidence.py",
            "tests/test_optional_layout_hint_recovery.py",
            "tests/test_optional_footer_hint_recovery.py",
            "tests/test_ordinary_source_layout.py",
            "tests/test_terminal_source_layout.py",
            "tests/test_terminal_closing_group.py",
            "tests/test_ordinary_section_ownership.py",
            "tests/test_word_story_projection.py",
            "tests/test_ordinary_text_correction.py", "tests/test_ordinary_text_correction_api.py",
            "tests/test_ordinary_text_correction_browser.py",
            "tests/test_ordinary_layout_columns_rows.py",
            "tests/test_ordinary_generated_emphasis.py",
            "tests/test_ordinary_edited_revision.py",
            "tests/test_ordinary_layout_partition_contracts.py",
            "tests/test_ordinary_layout_partition_browser.py",
            "tests/test_ordinary_layout_manager.py", "tests/test_ordinary_layout_delivery_integration.py",
            "tests/test_shadow_web_ordinary_layout_api.py", "tests/test_ordinary_layout_browser_state.py",
            "tests/test_ordinary_layout_parent_races.py", "tests/test_gmail_layout_confirmation_browser.py",
            "tests/test_gmail_confirmation_prevalidation.py",
            "tests/test_ordinary_auto_layout_integration.py",
            "tests/test_ordinary_auto_layout_recovery.py",
            "tests/test_ordinary_layout_retained_continuation.py",
            "tests/test_ordinary_layout_direct_continuation.py",
            "tests/test_ordinary_layout_order_emphasis.py",
            "tests/test_ordinary_layout_zero_spacing.py",
            "tests/test_ordinary_auto_layout_workflow.py",
            "tests/test_browser_pdf_text_bundle.py",
            "tests/test_ordinary_accounting_policy.py")
    },
    @{
        Executable = $venvPython
        Arguments = @("-m", "pytest", "-q", "--durations=10",
            "tests/test_pricing.py", "tests/test_translation_finance_browser_state.py",
            "tests/test_translation_finance_qt.py", "tests/test_translation_completion_metrics.py",
            "tests/test_owned_story_save_count.py",
            "tests/test_translation_honorarios_options.py", "tests/test_gmail_fee_options_browser.py",
            "tests/test_gmail_start_page_input.py", "tests/test_shadow_web_arabic_review_passive.py",
            "tests/test_docx_arabic_folio.py", "tests/test_resources_loader.py",
            "tests/test_arabic_pre_tokenize.py",
            "tests/test_ar_source_literal_fidelity.py",
            "tests/test_translation_diagnostics.py", "tests/test_quality_risk_scoring.py",
            "tests/test_visible_translation_diagnostics.py",
            "tests/test_qt_app_state.py", "tests/test_formatting_policy_isolation.py",
            "tests/test_qt_cleanup.py", "tests/test_qt_arabic_review_lifecycle.py",
            "tests/test_test_shards.py",
            "tests/test_word_startup_diagnostics.py::test_valid_process_name_preserves_exact_case_and_existing_success")
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
