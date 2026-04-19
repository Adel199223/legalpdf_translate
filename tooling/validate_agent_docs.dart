import 'dart:collection';
import 'dart:convert';
import 'dart:io';

class ValidationIssue {
  ValidationIssue(this.ruleId, this.message);

  final String ruleId;
  final String message;

  @override
  String toString() => '$ruleId: $message';
}

class _HarnessResolution {
  const _HarnessResolution({
    required this.hasProfile,
    required this.usedState,
    required this.resolvedModules,
    required this.resolvedOutputs,
  });

  final bool hasProfile;
  final bool usedState;
  final Set<String> resolvedModules;
  final Set<String> resolvedOutputs;
}

const List<String> _legacyRequiredFiles = <String>[
  'AGENTS.md',
  'agent.md',
  'APP_KNOWLEDGE.md',
  'docs/assistant/APP_KNOWLEDGE.md',
  'docs/assistant/INDEX.md',
  'docs/assistant/manifest.json',
  'docs/assistant/DB_DRIFT_KNOWLEDGE.md',
  'docs/assistant/ISSUE_MEMORY.md',
  'docs/assistant/ISSUE_MEMORY.json',
  'docs/assistant/LOCAL_ENV_PROFILE.local.md',
  'docs/assistant/LOCAL_CAPABILITIES.md',
  'docs/assistant/GOLDEN_PRINCIPLES.md',
  'docs/assistant/EXTERNAL_SOURCE_REGISTRY.md',
  'docs/assistant/exec_plans/PLANS.md',
  'docs/assistant/exec_plans/active/.gitkeep',
  'docs/assistant/exec_plans/completed/.gitkeep',
  'docs/assistant/LOCALIZATION_GLOSSARY.md',
  'docs/assistant/PERFORMANCE_BASELINES.md',
  'docs/assistant/features/APP_USER_GUIDE.md',
  'docs/assistant/features/PRIMARY_FEATURE_USER_GUIDE.md',
  'docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md',
  'docs/assistant/workflows/FEATURE_WORKFLOW.md',
  'docs/assistant/workflows/DATA_WORKFLOW.md',
  'docs/assistant/workflows/TRANSLATION_WORKFLOW.md',
  'docs/assistant/workflows/PERSISTENCE_DATA_WORKFLOW.md',
  'docs/assistant/workflows/LOCALIZATION_WORKFLOW.md',
  'docs/assistant/workflows/PERFORMANCE_WORKFLOW.md',
  'docs/assistant/workflows/REFERENCE_DISCOVERY_WORKFLOW.md',
  'docs/assistant/workflows/STAGED_EXECUTION_WORKFLOW.md',
  'docs/assistant/workflows/BROWSER_AUTOMATION_ENV_PROVENANCE_WORKFLOW.md',
  'docs/assistant/workflows/CLOUD_MACHINE_EVALUATION_WORKFLOW.md',
  'docs/assistant/workflows/OPENAI_DOCS_CITATION_WORKFLOW.md',
  'docs/assistant/workflows/CI_REPO_WORKFLOW.md',
  'docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md',
  'docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md',
  'docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md',
  'docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md',
  'docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md',
  'docs/assistant/runtime/CANONICAL_BUILD.json',
  'docs/assistant/templates/CODEX_PROJECT_BOOTSTRAP_PROMPT.md',
  'docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json',
  'docs/assistant/templates/BOOTSTRAP_CORE_CONTRACT.md',
  'docs/assistant/templates/BOOTSTRAP_ISSUE_MEMORY_SYSTEM.md',
  'docs/assistant/templates/BOOTSTRAP_PROJECT_HARNESS_SYNC_POLICY.md',
  'docs/assistant/templates/BOOTSTRAP_MODULES_AND_TRIGGERS.md',
  'docs/assistant/templates/BOOTSTRAP_LOCAL_ENV_OVERLAY.md',
  'docs/assistant/templates/BOOTSTRAP_CAPABILITY_DISCOVERY.md',
  'docs/assistant/templates/BOOTSTRAP_WORKTREE_BUILD_IDENTITY.md',
  'docs/assistant/templates/BOOTSTRAP_ROADMAP_GOVERNANCE.md',
  'docs/assistant/templates/BOOTSTRAP_HOST_INTEGRATION_PREFLIGHT.md',
  'docs/assistant/templates/BOOTSTRAP_HARNESS_ISOLATION_AND_DIAGNOSTICS.md',
  'docs/assistant/templates/BOOTSTRAP_UPDATE_POLICY.md',
  'tooling/launch_qt_build.py',
  'tooling/validate_agent_docs.dart',
  'test/tooling/validate_agent_docs_test.dart',
  'tooling/validate_workspace_hygiene.dart',
  'test/tooling/validate_workspace_hygiene_test.dart',
  'tooling/automation_preflight.dart',
  'test/tooling/automation_preflight_test.dart',
  'tooling/cloud_eval_preflight.dart',
  'test/tooling/cloud_eval_preflight_test.dart',
];

const List<String> _profileDrivenCoreFiles = <String>[
  'docs/assistant/HARNESS_PROFILE.json',
  'docs/assistant/schemas/HARNESS_PROFILE.schema.json',
  'docs/assistant/templates/README.md',
  'docs/assistant/templates/CHANGELOG.md',
  'docs/assistant/templates/BOOTSTRAP_VERSION.json',
  'docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json',
  'docs/assistant/templates/BOOTSTRAP_PROFILE_RESOLUTION.md',
  'docs/assistant/templates/NEW_PROJECT_BOOTSTRAP_WORKFLOW.md',
  'docs/assistant/templates/examples/BOOTSTRAP_STATE.template.json',
  'docs/assistant/templates/examples/DESKTOP_PYTHON_QT.profile.json',
  'docs/assistant/templates/examples/FLUTTER_APP.profile.json',
  'docs/assistant/templates/examples/HARNESS_PROFILE.template.json',
  'docs/assistant/templates/archetypes/api_service.md',
  'docs/assistant/templates/archetypes/browser_extension.md',
  'docs/assistant/templates/archetypes/cli_tool.md',
  'docs/assistant/templates/archetypes/desktop_python_qt.md',
  'docs/assistant/templates/archetypes/flutter_app.md',
  'docs/assistant/templates/archetypes/web_app.md',
  'tooling/bootstrap_profile_wizard.py',
  'tooling/check_harness_profile.py',
  'tooling/harness_profile_lib.py',
  'tooling/preview_harness_sync.py',
  'tests/tooling/test_harness_tools.py',
];

const Map<String, List<String>> _profileDrivenFilesByModule =
    <String, List<String>>{
      'openai_docs_mcp': <String>[
        'docs/assistant/CODEX_ENVIRONMENT.md',
        '.vscode/mcp.json.example',
      ],
    };

const Map<String, String> _compatibilityModuleAliases = <String, String>{
  'core_docs': 'base_docs',
  'worktree_build_identity': 'build_identity',
  'host_integration_preflight': 'host_integration',
  'roadmap': 'roadmap_governance',
  'local_env': 'local_env_overlay',
  'openai_docs': 'openai_docs_mcp',
  'browser_integration': 'browser_bridge',
};

const List<String> _requiredWorkflowIds = <String>[
  'feature_workflow',
  'data_workflow',
  'localization_workflow',
  'workspace_performance_workflow',
  'reference_discovery',
  'ci_repo_ops',
  'commit_publish_ops',
  'docs_maintenance_workflow',
  'project_harness_sync_workflow',
  'harness_isolation_and_diagnostics_workflow',
];

const List<String> _requiredModuleFlags = <String>[
  'core_contract',
  'beginner_layer',
  'issue_memory_system',
  'project_harness_sync',
  'localization_performance',
  'local_env_overlay',
  'capability_discovery',
  'worktree_build_identity',
  'roadmap_governance',
  'reference_discovery',
  'host_integration_preflight',
  'harness_isolation_diagnostics',
  'browser_automation_environment_provenance',
  'cloud_machine_evaluation_local_acceptance',
  'staged_execution',
  'openai_docs_citation',
];

const Map<String, List<String>> _requiredWorkflowIdsByModule =
    <String, List<String>>{
      'project_harness_sync': <String>['project_harness_sync_workflow'],
      'roadmap_governance': <String>['roadmap_workflow'],
      'host_integration_preflight': <String>[
        'host_integration_preflight_workflow',
      ],
      'harness_isolation_diagnostics': <String>[
        'harness_isolation_and_diagnostics_workflow',
      ],
      'staged_execution': <String>['staged_execution_workflow'],
      'browser_automation_environment_provenance': <String>[
        'browser_automation_env_provenance',
      ],
      'cloud_machine_evaluation_local_acceptance': <String>[
        'cloud_machine_evaluation',
      ],
      'openai_docs_citation': <String>['openai_docs_citation'],
    };

const List<String> _requiredWorkflowHeadings = <String>[
  '## What This Workflow Is For',
  '## Expected Outputs',
  '## When To Use',
  '## What Not To Do',
  '## Primary Files',
  '## Minimal Commands',
  '## Targeted Tests',
  '## Failure Modes and Fallback Steps',
  '## Handoff Checklist',
];

const List<String> _requiredUserGuideHeadings = <String>[
  '## Use This Guide When',
  '## Do Not Use This Guide For',
  '## For Agents: Support Interaction Contract',
  '## Canonical Deference Rule',
  '## Quick Start (No Technical Background)',
  '## Terms in Plain English',
];

const List<String> _requiredContractKeys = <String>[
  'template_read_policy',
  'localization_glossary_source_of_truth',
  'workspace_performance_source_of_truth',
  'environment_outside_workspace_default_policy',
  'post_change_docs_sync_prompt_policy',
  'inspiration_reference_discovery_policy',
  'golden_principles_source_of_truth',
  'execplan_policy',
  'approval_gates_policy',
  'worktree_isolation_policy',
  'doc_gardening_policy',
  'project_harness_sync_policy',
  'vendored_template_protection_policy',
  'user_guides_support_usage_policy',
  'user_guides_canonical_deference_policy',
  'user_guides_update_sync_policy',
  'template_path_routing_regression_protection',
  'issue_memory_policy',
  'test_live_state_isolation_policy',
  'multi_surface_diagnostics_packet_policy',
];

const List<String> _requiredIssueMemoryTopLevelKeys = <String>[
  'version',
  'last_updated',
  'issues',
];

const List<String> _requiredIssueMemoryIssueKeys = <String>[
  'id',
  'title',
  'first_seen_timestamp',
  'last_seen_timestamp',
  'repeat_count',
  'status',
  'trigger_source',
  'symptoms',
  'likely_root_cause',
  'attempted_fix_history',
  'accepted_fix',
  'regressed_after_accepted_fix',
  'affected_workflows',
  'affected_docs',
  'bootstrap_relevance',
  'docs_sync_relevance',
  'evidence_refs',
];

const Map<String, List<String>> _requiredContractKeysByModule =
    <String, List<String>>{
      'project_harness_sync': <String>[
        'project_harness_sync_policy',
        'vendored_template_protection_policy',
        'cleanup_complete_push_policy',
        'post_merge_repair_default_policy',
        'scratch_root_default_policy',
      ],
      'roadmap_governance': <String>[
        'roadmap_dormant_main_policy',
        'roadmap_resume_anchor_policy',
        'roadmap_active_worktree_authority_policy',
        'roadmap_update_order_policy',
      ],
      'staged_execution': <String>['stage_gate_policy'],
      'reference_discovery': <String>['reference_discovery_policy'],
      'openai_docs_citation': <String>['openai_docs_citation_freshness_policy'],
      'browser_automation_environment_provenance': <String>[
        'browser_automation_reliability_policy',
        'workspace_provenance_lock_policy',
        'automation_host_fallback_policy',
        'machine_operator_split_validation_policy',
        'restricted_browser_page_policy',
        'browser_binary_strategy_policy',
        'chromium_for_testing_conditional_install_policy',
        'automation_binary_provenance_packet_policy',
      ],
      'cloud_machine_evaluation_local_acceptance': <String>[
        'cloud_heavy_scoring_default_policy',
        'cloud_scoring_preflight_gate_policy',
        'cloud_scoring_failure_recovery_policy',
        'cloud_local_apply_separation_policy',
      ],
    };

const String _docsSyncPrompt =
    'Would you like me to run Assistant Docs Sync for this change now?';
const String _docsSyncPromptCondition =
    'relevant touched-scope docs still remain unsynced';
const String _docsSyncPromptImmediateNeed =
    'immediate same-task synchronization is necessary';
const String _docsSyncPromptDeferredPass = 'later docs-maintenance pass';
const String _docsSyncPromptNoRepeat = 'already ran during the same task/pass';

const Map<String, List<String>>
_requiredBootstrapMarkers = <String, List<String>>{
  'docs/assistant/templates/CODEX_PROJECT_BOOTSTRAP_PROMPT.md': <String>[
    'bootstrap execution order',
    'bootstrap_template_map.json',
    'bootstrap_core_contract.md',
    'bootstrap_issue_memory_system.md',
    'bootstrap_project_harness_sync_policy.md',
    'bootstrap_modules_and_triggers.md',
    'bootstrap_roadmap_governance.md',
    'implement the template files',
    'session_resume.md',
    'both active and dormant `session_resume.md` states',
    'continuity-closeout plus cleanup',
    'ignored `tmp/`',
    'follow-up branch/pr',
    'bootstrap_harness_isolation_and_diagnostics.md',
    'host-bound workflows span browser/app/local bridge or fragile listeners',
    'read-on-demand',
    'profile-first bootstrap resolution',
    'docs/assistant/harness_profile.json',
    'docs/assistant/runtime/bootstrap_state.json',
    'bootstrap_version.json',
    'bootstrap_archetype_registry.json',
    'bootstrap_profile_resolution.md',
    'enabled_modules',
    'disabled_modules',
    'openai_docs_mcp',
    'desktop_launcher',
  ],
  'docs/assistant/templates/BOOTSTRAP_CORE_CONTRACT.md': <String>[
    'docs/assistant/issue_memory.md',
    'docs/assistant/issue_memory.json',
    'session_resume.md',
    'when roadmap governance is active',
    'implement the template files',
    'sync project harness',
    'must not edit `docs/assistant/templates/*`',
    'bare `commit`',
    'push+pr+merge+cleanup',
    'branch-scoped execplan closeout before merge',
    'roadmap closeout and `session_resume.md` update before merge',
    'cleanup of known scratch outputs',
    'follow-up branch/pr',
    'ignored `tmp/`',
    'scratch artifact source control noise',
    'openai-specific behavior is temporally unstable',
    'docs-sync prompt',
    'immediate same-task synchronization is necessary',
    'later docs-maintenance pass',
  ],
  'docs/assistant/templates/BOOTSTRAP_ISSUE_MEMORY_SYSTEM.md': <String>[
    'required output',
    'docs/assistant/issue_memory.md',
    'docs/assistant/issue_memory.json',
    'prefer operational triggers first and wording triggers second',
    'do not use issue memory as a substitute for normal roadmap history',
    'assistant docs sync should consult issue memory',
    'assistant docs sync',
    'repeat_count >= 2',
    'do not seed fake incidents',
    'stale post-merge continuity',
    'stale active-plan inventory',
    'scratch artifact source control noise',
    'bootstrap relevance `possible`',
  ],
  'docs/assistant/templates/BOOTSTRAP_MODULES_AND_TRIGGERS.md': <String>[
    'issue memory system',
    'always on',
    'project harness sync',
    'implement the template files',
    'sync project harness',
    'worktree / build identity',
    'auto-conditional',
    'runnable app',
    'local desktop workflow',
    'roadmap governance',
    'docs/assistant/session_resume.md',
    'dormant roadmap state on `main`',
    'stale post-merge continuity',
    'cleanup-complete bare `push` semantics',
    'harness isolation + diagnostics',
    'tests could collide with live machine state',
    'merge-immediately-after-acceptance discipline',
    'trigger matrix',
    'stage-gate rules',
    'reference discovery rules',
    'browser automation rules',
    'harness isolation + diagnostics rules',
    'immediate same-task synchronization is necessary',
    'later docs-maintenance pass',
  ],
  'docs/assistant/templates/BOOTSTRAP_PROJECT_HARNESS_SYNC_POLICY.md': <String>[
    'implement the template files',
    'sync project harness',
    'audit project harness',
    'check project harness',
    'local apply order',
    'update codex bootstrap',
    'continuity or merge cleanup behavior',
    'commit_publish_workflow.md',
  ],
  'docs/assistant/templates/BOOTSTRAP_LOCAL_ENV_OVERLAY.md': <String>[
    'windows vs wsl routing',
    'local_env_profile.example.md',
    'local_env_profile.local.md',
    'personal-machine facts must not be written into the core bootstrap contract',
  ],
  'docs/assistant/templates/BOOTSTRAP_CAPABILITY_DISCOVERY.md': <String>[
    'local tool discovery',
    'agents skill discovery',
    'mcp availability checks',
    'local_capabilities.md',
    'do not hardcode stale tool assumptions',
  ],
  'docs/assistant/templates/BOOTSTRAP_WORKTREE_BUILD_IDENTITY.md': <String>[
    'runnable app',
    'latest-approved-baseline discipline',
    'canonical runnable-build rule',
    'build-under-test identity packet',
    'worktree path, branch, head sha, workspace file, and launch command',
  ],
  'docs/assistant/templates/BOOTSTRAP_ROADMAP_GOVERNANCE.md': <String>[
    'fresh-session resume continuity is required',
    'docs/assistant/session_resume.md',
    'resume master plan',
    'dormant roadmap state on `main`',
    'no active roadmap currently open on this worktree',
    'normal execplan flow',
    'the active roadmap tracker is the sequence source',
    'the active wave execplan is the implementation-detail source',
    '1. active wave execplan',
    'either archive roadmap artifacts or leave a dormant anchor on `main`',
    'post_merge_continuity_cleanup_drift',
  ],
  'docs/assistant/templates/BOOTSTRAP_HOST_INTEGRATION_PREFLIGHT.md': <String>[
    'verify required installs before feature work',
    'verify auth state before relying on a host-bound tool',
    'validate the target app and dependent tool on the same host',
    'run one live smoke check before claiming the integration works',
    'unavailable',
    'failed',
  ],
  'docs/assistant/templates/BOOTSTRAP_HARNESS_ISOLATION_AND_DIAGNOSTICS.md':
      <String>[
        'isolate tests from live user state',
        'non-live or ephemeral test ports',
        'listener ownership problems clearly',
        'one durable session artifact',
        'support-packet order',
      ],
  'docs/assistant/templates/BOOTSTRAP_UPDATE_POLICY.md': <String>[
    'update codex bootstrap',
    'ucbs',
    'audit codex bootstrap',
    'check codex bootstrap',
    'sync codex bootstrap docs',
    'update bootstrap is **not canonical**',
    'must not edit `docs/assistant/templates/*`',
    'allowed change surface',
    'docs/assistant/issue_memory.md',
    'docs/assistant/issue_memory.json',
    'repeat_count >= 2',
    'bootstrap relevance is:',
    'stale post-merge continuity',
    'stale active-plan inventory',
    'scratch artifact source control noise',
    'follow-up branch/pr as the default',
    'dart tooling/validate_agent_docs.dart',
    'docs sync prompt rule',
    'relevant touched-scope docs still remain unsynced',
    'immediate same-task synchronization is necessary',
    'later docs-maintenance pass',
    'already ran during the same task/pass',
  ],
};

const Map<String, Map<String, String>> _requiredBootstrapTargets =
    <String, Map<String, String>>{
      'docs/assistant/HARNESS_PROFILE.json': <String, String>{
        'template':
            'docs/assistant/templates/examples/HARNESS_PROFILE.template.json',
        'policy': 'copy_if_missing',
      },
      'docs/assistant/schemas/HARNESS_PROFILE.schema.json': <String, String>{
        'template': 'docs/assistant/schemas/HARNESS_PROFILE.schema.json',
        'policy': 'copy',
      },
      'docs/assistant/CODEX_ENVIRONMENT.md': <String, String>{
        'template': 'docs/assistant/CODEX_ENVIRONMENT.md',
        'policy': 'copy_if_missing',
      },
      '.vscode/mcp.json.example': <String, String>{
        'template': '.vscode/mcp.json.example',
        'policy': 'copy_if_missing',
      },
      'docs/assistant/runtime/BOOTSTRAP_STATE.json': <String, String>{
        'template': 'docs/assistant/templates/examples/BOOTSTRAP_STATE.template.json',
        'policy': 'generated',
      },
      'docs/assistant/templates/BOOTSTRAP_VERSION.json': <String, String>{
        'template': 'docs/assistant/templates/BOOTSTRAP_VERSION.json',
        'policy': 'copy',
      },
      'docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json':
          <String, String>{
            'template':
                'docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json',
            'policy': 'copy',
          },
    };

const List<int> _sha256K = <int>[
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
  0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
  0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
  0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
  0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
  0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
  0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
  0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
];

const Map<String, List<String>> _requiredBootstrapTopicsByModule =
    <String, List<String>>{
      'core_contract': <String>[
        'cleanup-complete push semantics',
        'ignored tmp scratch root guidance',
      ],
      'issue_memory_system': <String>['cleanup continuity issue classes'],
      'project_harness_sync': <String>[
        'continuity and cleanup governance resync',
      ],
      'roadmap_governance': <String>['dormant roadmap state on main'],
      'bootstrap_update_policy': <String>['cleanup continuity promotion rule'],
    };

const List<String> _requiredBootstrapModuleIds = <String>[
  'core_contract',
  'issue_memory_system',
  'project_harness_sync',
  'modules_and_triggers',
  'local_env_overlay',
  'capability_discovery',
  'worktree_build_identity',
  'roadmap_governance',
  'host_integration_preflight',
  'harness_isolation_diagnostics',
  'bootstrap_update_policy',
];

List<ValidationIssue> validateAgentDocs({
  required String rootPath,
  bool localizationScope = false,
}) {
  final List<ValidationIssue> issues = <ValidationIssue>[];

  bool exists(String relPath) {
    final String fullPath = _resolvePath(rootPath, relPath);
    return FileSystemEntity.typeSync(fullPath) != FileSystemEntityType.notFound;
  }

  String readText(String relPath) {
    final String fullPath = _resolvePath(rootPath, relPath);
    final File file = File(fullPath);
    if (!file.existsSync()) {
      return '';
    }
    return file.readAsStringSync();
  }

  final _HarnessResolution harnessResolution = _loadHarnessResolution(
    issues,
    exists,
    readText,
  );

  if (!localizationScope) {
    final List<String> missing = _resolveRequiredFiles(harnessResolution)
        .where((String path) => !exists(path))
        .toList();
    if (missing.isNotEmpty) {
      issues.add(
        ValidationIssue(
          'AD001',
          'Required files are missing: ${missing.join(', ')}',
        ),
      );
    }
  }

  final Map<String, dynamic>? manifest = _loadManifest(
    rootPath,
    issues,
    exists,
  );
  if (manifest == null) {
    return issues;
  }

  if (!localizationScope) {
    _validateManifestPaths(manifest, issues, exists);
    _validateModuleFlags(manifest, issues);
    _validateWorkflowIds(manifest, issues);
    _validateWorkflowDocs(manifest, issues, readText, exists);
    _validateCanonicalBridgePolicies(issues, readText);
    _validateCommands(manifest, issues);
    _validateCoreContracts(manifest, issues);
    _validateRunbookPolicies(issues, readText);
    _validateQtLaunchIdentityDiscipline(issues, readText);
    _validateApprovedBasePromotionDiscipline(issues, readText, rootPath);
    _validateCommitPushShorthandDiscipline(issues, readText);
    _validateUserGuides(manifest, issues, readText, exists);
    _validateDocsMaintenance(issues, readText);
    _validateIssueMemory(issues, readText, exists, rootPath);
    _validateQtRenderScratchPathGuidance(issues, readText);
    _validateProjectLocalOperationalLayer(manifest, issues, readText, exists);
    _validateProjectHarnessAndRoadmapGovernance(
      manifest,
      issues,
      readText,
      exists,
      rootPath,
    );
    _validateHarnessIsolationAndDiagnostics(manifest, issues, readText, exists);
    _validateTemplatePolicy(manifest, issues, readText);
    _validateBootstrapTemplateIntegrity(issues, readText, exists);
    _validateProfileDrivenBootstrapFiles(
      issues,
      readText,
      exists,
      harnessResolution,
    );
    _validateExternalSourceRegistry(issues, readText, exists);
  } else {
    _validateLocalizationScope(manifest, issues, readText, exists);
  }

  return issues;
}

Set<String> _resolveRequiredFiles(_HarnessResolution harnessResolution) {
  final Set<String> required = <String>{..._legacyRequiredFiles};
  if (!harnessResolution.hasProfile) {
    return required;
  }

  required.addAll(_profileDrivenCoreFiles);
  for (final String module in harnessResolution.resolvedModules) {
    required.addAll(_profileDrivenFilesByModule[module] ?? const <String>[]);
  }
  return required;
}

_HarnessResolution _loadHarnessResolution(
  List<ValidationIssue> issues,
  bool Function(String relPath) exists,
  String Function(String relPath) readText,
) {
  const String profilePath = 'docs/assistant/HARNESS_PROFILE.json';
  const String registryPath =
      'docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json';
  const String statePath = 'docs/assistant/runtime/BOOTSTRAP_STATE.json';

  if (!exists(profilePath)) {
    return const _HarnessResolution(
      hasProfile: false,
      usedState: false,
      resolvedModules: <String>{},
      resolvedOutputs: <String>{},
    );
  }

  final Map<String, dynamic>? profile = _loadJsonObject(
    profilePath,
    issues,
    readText,
    'AD048',
    'Harness profile',
  );
  final Map<String, dynamic>? registry = _loadJsonObject(
    registryPath,
    issues,
    readText,
    'AD048',
    'Bootstrap archetype registry',
  );
  final Map<String, dynamic>? state = exists(statePath)
      ? _loadJsonObject(
          statePath,
          issues,
          readText,
          'AD048',
          'Bootstrap state',
        )
      : null;

  if (profile == null || registry == null) {
    return const _HarnessResolution(
      hasProfile: true,
      usedState: false,
      resolvedModules: <String>{},
      resolvedOutputs: <String>{},
    );
  }

  final String fingerprint = _profileFingerprint(profile);
  if (state != null &&
      (state['profile_fingerprint'] ?? '').toString() == fingerprint) {
    final Set<String> stateModules = _resolveModulesFromState(state, registry);
    if (stateModules.isNotEmpty) {
      return _HarnessResolution(
        hasProfile: true,
        usedState: true,
        resolvedModules: stateModules,
        resolvedOutputs: _resolveOutputsForModules(stateModules, registry),
      );
    }
  }

  final Set<String> modules = _resolveModulesFromProfile(profile, registry);
  return _HarnessResolution(
    hasProfile: true,
    usedState: false,
    resolvedModules: modules,
    resolvedOutputs: _resolveOutputsForModules(modules, registry),
  );
}

Map<String, dynamic>? _loadJsonObject(
  String relPath,
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
  String ruleId,
  String label,
) {
  final String text = readText(relPath);
  if (text.trim().isEmpty) {
    return null;
  }
  try {
    final dynamic decoded = jsonDecode(text);
    if (decoded is Map<String, dynamic>) {
      return decoded;
    }
    if (decoded is Map) {
      return decoded.map(
        (dynamic key, dynamic value) => MapEntry(key.toString(), value),
      );
    }
    issues.add(
      ValidationIssue(
        ruleId,
        '$label at $relPath must decode to a JSON object.',
      ),
    );
  } catch (error) {
    issues.add(
      ValidationIssue(
        ruleId,
        '$label JSON parse failed at $relPath: $error',
      ),
    );
  }
  return null;
}

Map<String, dynamic> _asObject(dynamic value) {
  if (value is Map<String, dynamic>) {
    return value;
  }
  if (value is Map) {
    return value.map(
      (dynamic key, dynamic item) => MapEntry(key.toString(), item),
    );
  }
  return <String, dynamic>{};
}

List<dynamic> _asList(dynamic value) {
  if (value is List<dynamic>) {
    return value;
  }
  if (value is List) {
    return List<dynamic>.from(value);
  }
  return <dynamic>[];
}

Map<String, String> _collectModuleAliases(Map<String, dynamic> registry) {
  final Map<String, String> aliases = <String, String>{
    ..._compatibilityModuleAliases,
  };
  final Map<String, dynamic> modules = _asObject(registry['modules']);
  for (final MapEntry<String, dynamic> entry in modules.entries) {
    aliases.putIfAbsent(entry.key, () => entry.key);
    final Map<String, dynamic> meta = _asObject(entry.value);
    for (final dynamic alias in _asList(meta['aliases'])) {
      final String aliasText = alias.toString();
      if (aliasText.isNotEmpty) {
        aliases[aliasText] = entry.key;
      }
    }
  }
  return aliases;
}

String _canonicalizeModuleName(String module, Map<String, String> aliases) {
  final String trimmed = module.trim();
  if (trimmed.isEmpty) {
    return '';
  }
  return aliases[trimmed] ?? trimmed;
}

void _addNormalizedModules(
  Set<String> target,
  dynamic rawModules,
  Map<String, String> aliases,
) {
  for (final dynamic entry in _asList(rawModules)) {
    final String canonical = _canonicalizeModuleName(
      entry.toString(),
      aliases,
    );
    if (canonical.isNotEmpty) {
      target.add(canonical);
    }
  }
}

Set<String> _resolveModulesFromProfile(
  Map<String, dynamic> profile,
  Map<String, dynamic> registry,
) {
  final Map<String, String> aliases = _collectModuleAliases(registry);
  final Map<String, dynamic> bootstrap = _asObject(profile['bootstrap']);
  final Map<String, dynamic> operator = _asObject(profile['operator']);
  final Map<String, dynamic> stack = _asObject(profile['stack']);
  final Map<String, dynamic> archetypes = _asObject(registry['archetypes']);
  final Map<String, dynamic> modes = _asObject(registry['modes']);
  final Map<String, dynamic> featureFlags =
      _asObject(registry['feature_flag_modules']);

  final String archetypeName = (bootstrap['archetype'] ?? '').toString();
  final String modeName = (bootstrap['mode'] ?? '').toString();
  final Map<String, dynamic> archetype = _asObject(archetypes[archetypeName]);
  final Map<String, dynamic> mode = _asObject(modes[modeName]);

  final Set<String> modules = <String>{};
  _addNormalizedModules(modules, archetype['include'], aliases);
  _addNormalizedModules(modules, mode['include'], aliases);

  if (bootstrap['uses_openai'] == true) {
    _addNormalizedModules(modules, featureFlags['uses_openai'], aliases);
  }
  if (bootstrap['needs_codespaces'] == true) {
    _addNormalizedModules(modules, featureFlags['needs_codespaces'], aliases);
  }
  if (bootstrap['has_browser_bridge'] == true) {
    _addNormalizedModules(modules, featureFlags['has_browser_bridge'], aliases);
  }

  if ((operator['experience_level'] ?? '').toString() == 'beginner' ||
      operator['needs_safe_commands'] == true) {
    modules.add('beginner_support');
  }
  final bool hasDesktopSurface = _asList(
    stack['surfaces'],
  ).map((dynamic item) => item.toString()).contains('desktop');
  if (hasDesktopSurface) {
    modules.add('desktop_launcher');
  }

  _addNormalizedModules(modules, bootstrap['enabled_modules'], aliases);

  final Set<String> excluded = <String>{};
  _addNormalizedModules(excluded, archetype['exclude'], aliases);
  _addNormalizedModules(excluded, mode['exclude'], aliases);
  _addNormalizedModules(excluded, bootstrap['disabled_modules'], aliases);
  modules.removeAll(excluded);
  return modules;
}

Set<String> _resolveModulesFromState(
  Map<String, dynamic> state,
  Map<String, dynamic> registry,
) {
  final Map<String, String> aliases = _collectModuleAliases(registry);
  final Map<String, dynamic> resolved = _asObject(state['resolved']);
  final Set<String> modules = <String>{};
  _addNormalizedModules(modules, resolved['modules'], aliases);
  return modules;
}

Set<String> _resolveOutputsForModules(
  Set<String> modules,
  Map<String, dynamic> registry,
) {
  final Set<String> outputs = <String>{};
  final Map<String, dynamic> moduleDefs = _asObject(registry['modules']);
  for (final String module in modules) {
    final Map<String, dynamic> meta = _asObject(moduleDefs[module]);
    for (final dynamic output in _asList(meta['outputs'])) {
      final String path = output.toString();
      if (path.isNotEmpty) {
        outputs.add(path);
      }
    }
  }
  return outputs;
}

dynamic _canonicalizeJson(dynamic value) {
  if (value is Map) {
    final SplayTreeMap<String, dynamic> sorted = SplayTreeMap<String, dynamic>();
    final Map<String, dynamic> mapped = _asObject(value);
    for (final String key in mapped.keys) {
      sorted[key] = _canonicalizeJson(mapped[key]);
    }
    return sorted;
  }
  if (value is List) {
    return _asList(value)
        .map<dynamic>((dynamic item) => _canonicalizeJson(item))
        .toList(growable: false);
  }
  return value;
}

String _profileFingerprint(Map<String, dynamic> profile) {
  final String canonical = jsonEncode(_canonicalizeJson(profile));
  return _sha256Hex(utf8.encode(canonical)).substring(0, 12);
}

int _rotateRight(int value, int shift) {
  final int normalized = value & 0xffffffff;
  return (((normalized >> shift) |
              ((normalized << (32 - shift)) & 0xffffffff)) &
          0xffffffff)
      .toUnsigned(32);
}

String _sha256Hex(List<int> bytes) {
  final List<int> message = List<int>.from(bytes);
  final int bitLength = bytes.length * 8;
  message.add(0x80);
  while (message.length % 64 != 56) {
    message.add(0);
  }
  for (int i = 7; i >= 0; i--) {
    message.add((bitLength >> (i * 8)) & 0xff);
  }

  int h0 = 0x6a09e667;
  int h1 = 0xbb67ae85;
  int h2 = 0x3c6ef372;
  int h3 = 0xa54ff53a;
  int h4 = 0x510e527f;
  int h5 = 0x9b05688c;
  int h6 = 0x1f83d9ab;
  int h7 = 0x5be0cd19;

  final List<int> w = List<int>.filled(64, 0);
  for (int chunkStart = 0; chunkStart < message.length; chunkStart += 64) {
    for (int i = 0; i < 16; i++) {
      final int j = chunkStart + (i * 4);
      w[i] =
          ((message[j] << 24) |
                  (message[j + 1] << 16) |
                  (message[j + 2] << 8) |
                  message[j + 3]) &
              0xffffffff;
    }
    for (int i = 16; i < 64; i++) {
      final int s0 =
          _rotateRight(w[i - 15], 7) ^
          _rotateRight(w[i - 15], 18) ^
          ((w[i - 15] & 0xffffffff) >> 3);
      final int s1 =
          _rotateRight(w[i - 2], 17) ^
          _rotateRight(w[i - 2], 19) ^
          ((w[i - 2] & 0xffffffff) >> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) & 0xffffffff;
    }

    int a = h0;
    int b = h1;
    int c = h2;
    int d = h3;
    int e = h4;
    int f = h5;
    int g = h6;
    int h = h7;

    for (int i = 0; i < 64; i++) {
      final int s1 =
          _rotateRight(e, 6) ^ _rotateRight(e, 11) ^ _rotateRight(e, 25);
      final int ch = (e & f) ^ ((~e) & g);
      final int temp1 = (h + s1 + ch + _sha256K[i] + w[i]) & 0xffffffff;
      final int s0 =
          _rotateRight(a, 2) ^ _rotateRight(a, 13) ^ _rotateRight(a, 22);
      final int maj = (a & b) ^ (a & c) ^ (b & c);
      final int temp2 = (s0 + maj) & 0xffffffff;

      h = g;
      g = f;
      f = e;
      e = (d + temp1) & 0xffffffff;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) & 0xffffffff;
    }

    h0 = (h0 + a) & 0xffffffff;
    h1 = (h1 + b) & 0xffffffff;
    h2 = (h2 + c) & 0xffffffff;
    h3 = (h3 + d) & 0xffffffff;
    h4 = (h4 + e) & 0xffffffff;
    h5 = (h5 + f) & 0xffffffff;
    h6 = (h6 + g) & 0xffffffff;
    h7 = (h7 + h) & 0xffffffff;
  }

  return <int>[h0, h1, h2, h3, h4, h5, h6, h7]
      .map((int value) => value.toUnsigned(32).toRadixString(16).padLeft(8, '0'))
      .join();
}

void _validateProfileDrivenBootstrapFiles(
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
  bool Function(String relPath) exists,
  _HarnessResolution harnessResolution,
) {
  if (!harnessResolution.hasProfile) {
    return;
  }

  const Map<String, List<String>> requiredMarkers = <String, List<String>>{
    'docs/assistant/templates/README.md': <String>[
      'managed bootstrap template set',
      'profile-driven resolution',
      'compatibility during migration',
    ],
    'docs/assistant/templates/BOOTSTRAP_PROFILE_RESOLUTION.md': <String>[
      'docs/assistant/harness_profile.json',
      'docs/assistant/runtime/bootstrap_state.json',
      'openai_docs_mcp',
      'legacy repos may keep their current behavior until a profile is added',
    ],
    'docs/assistant/templates/NEW_PROJECT_BOOTSTRAP_WORKFLOW.md': <String>[
      'bootstrap_profile_wizard.py',
      'check_harness_profile.py',
      'preview_harness_sync.py',
    ],
  };

  final List<String> missingMarkers = <String>[];
  for (final MapEntry<String, List<String>> entry in requiredMarkers.entries) {
    final String relPath = entry.key;
    if (!exists(relPath)) {
      continue;
    }
    final String text = readText(relPath).toLowerCase();
    for (final String marker in entry.value) {
      if (!text.contains(marker)) {
        missingMarkers.add('$relPath -> $marker');
      }
    }
  }
  if (missingMarkers.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD048',
        'Profile-driven bootstrap docs are missing required markers: ${missingMarkers.join(' | ')}',
      ),
    );
  }

  if (exists('docs/assistant/templates/BOOTSTRAP_VERSION.json')) {
    final Map<String, dynamic>? version = _loadJsonObject(
      'docs/assistant/templates/BOOTSTRAP_VERSION.json',
      issues,
      readText,
      'AD048',
      'Bootstrap version metadata',
    );
    if (version != null) {
      final List<dynamic> features = _asList(version['features']);
      if ((version['migration_stage'] ?? '').toString() != 'additive' ||
          !features.map((dynamic item) => item.toString()).contains(
            'harness_profile',
          )) {
        issues.add(
          ValidationIssue(
            'AD048',
            'docs/assistant/templates/BOOTSTRAP_VERSION.json must declare additive phase-1 profile-driven rollout metadata.',
          ),
        );
      }
    }
  }

  if (exists('docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json')) {
    final Map<String, dynamic>? registry = _loadJsonObject(
      'docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json',
      issues,
      readText,
      'AD048',
      'Bootstrap archetype registry',
    );
    if (registry != null) {
      final Map<String, dynamic> modules = _asObject(registry['modules']);
      final Map<String, dynamic> archetypes = _asObject(registry['archetypes']);
      if (!modules.containsKey('openai_docs_mcp') ||
          !archetypes.containsKey('desktop_python_qt')) {
        issues.add(
          ValidationIssue(
            'AD048',
            'docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json must include openai_docs_mcp and desktop_python_qt for phase 1.',
          ),
        );
      }
    }
  }
}

void _validateQtLaunchIdentityDiscipline(
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
) {
  const List<String> requiredDocs = <String>[
    'agent.md',
    'docs/assistant/workflows/WORKTREE_BASELINE_DISCIPLINE_WORKFLOW.md',
    'docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md',
    'docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md',
    'docs/assistant/exec_plans/PLANS.md',
  ];

  for (final String relPath in requiredDocs) {
    final String text = readText(relPath).toLowerCase();
    if (!text.contains('launch_qt_build.py') ||
        !text.contains('head sha') ||
        !text.contains('build under test') ||
        !text.contains('canonical')) {
      issues.add(
        ValidationIssue(
          'AD037',
          '$relPath must require tooling/launch_qt_build.py, canonical build handling, and build-under-test packets with HEAD SHA in GUI handoffs.',
        ),
      );
    }
  }
}

void _validateCommitPushShorthandDiscipline(
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
) {
  const Map<String, List<String>> requiredMarkers = <String, List<String>>{
    'agent.md': <String>[
      'when the user says `commit`',
      'full pending source control tree',
      'logical grouped commits',
      'immediately suggest push',
      'when the user says `push`',
      'push the correct branch',
      'create or update the pr',
      'merge if clean',
      'delete the merged source branch',
      'prune refs',
      'if the user narrows scope explicitly',
    ],
    'docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md': <String>[
      'bare `commit` means full pending-tree triage',
      'bare `push` means push+pr+merge+cleanup',
      'logical grouped commits',
      'do not mix unrelated scopes',
      'after commit, recommend push immediately',
      'wait for required checks or ci',
      'merge when:',
      'cleanup after merge',
      'if the user narrows scope explicitly',
    ],
    'docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md': <String>[
      'ambiguous `commit` or `push` shorthand',
      'validator rules',
    ],
    'docs/assistant/exec_plans/PLANS.md': <String>[
      'assume `commit` means full pending-tree triage plus logical grouped commits',
      'assume `push` means push+pr+merge+cleanup',
      'record any intentional override',
    ],
  };

  for (final MapEntry<String, List<String>> entry in requiredMarkers.entries) {
    final String relPath = entry.key;
    final String text = readText(relPath).toLowerCase();
    final List<String> missing = entry.value
        .where((String marker) => !text.contains(marker))
        .toList();
    if (missing.isNotEmpty) {
      issues.add(
        ValidationIssue(
          'AD038',
          '$relPath must define hardened commit/push shorthand semantics. Missing: ${missing.join(', ')}',
        ),
      );
    }
  }
}

void _validateApprovedBasePromotionDiscipline(
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
  String rootPath,
) {
  final File configFile = File(
    _resolvePath(rootPath, 'docs/assistant/runtime/CANONICAL_BUILD.json'),
  );
  Map<String, dynamic>? config;
  try {
    config = jsonDecode(configFile.readAsStringSync()) as Map<String, dynamic>;
  } catch (_) {
    issues.add(
      ValidationIssue(
        'AD039',
        'docs/assistant/runtime/CANONICAL_BUILD.json must be valid JSON.',
      ),
    );
  }

  if (config != null) {
    final List<String> missingKeys = <String>[
      'canonical_worktree_path',
      'canonical_branch',
      'approved_base_branch',
      'approved_base_head_floor',
      'canonical_head_floor',
    ].where((String key) => !config!.containsKey(key)).toList();
    if (missingKeys.isNotEmpty) {
      issues.add(
        ValidationIssue(
          'AD039',
          'docs/assistant/runtime/CANONICAL_BUILD.json is missing required keys: ${missingKeys.join(', ')}',
        ),
      );
    }
  }

  const Map<String, List<String>> requiredMarkers = <String, List<String>>{
    'agent.md': <String>[
      'approved base branch',
      'merge it into the approved base immediately',
      'workflow violation',
    ],
    'docs/assistant/workflows/WORKTREE_BASELINE_DISCIPLINE_WORKFLOW.md':
        <String>[
          'approved base branch/floor',
          'contains the approved-base floor',
          'merge it into the approved base',
        ],
    'docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md': <String>[
      'approved-base floor',
      'promote that branch into the approved base immediately',
      'next unrelated feature branch',
    ],
    'docs/assistant/exec_plans/PLANS.md': <String>[
      'merge it into the approved base as the default next step',
      'approved-base floor',
    ],
  };

  for (final MapEntry<String, List<String>> entry in requiredMarkers.entries) {
    final String text = readText(entry.key).toLowerCase();
    final List<String> missing = entry.value
        .where((String marker) => !text.contains(marker))
        .toList();
    if (missing.isNotEmpty) {
      issues.add(
        ValidationIssue(
          'AD039',
          '${entry.key} must enforce approved-base promotion and lineage rules. Missing: ${missing.join(', ')}',
        ),
      );
    }
  }
}

void _validateLocalizationScope(
  Map<String, dynamic> manifest,
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
  bool Function(String relPath) exists,
) {
  final Set<String> workflowIds = _extractWorkflowIds(manifest);
  if (!workflowIds.contains('localization_workflow')) {
    issues.add(
      ValidationIssue(
        'AD004',
        'Required workflow id missing: localization_workflow.',
      ),
    );
  }

  if (!exists('docs/assistant/LOCALIZATION_GLOSSARY.md') ||
      !exists('docs/assistant/workflows/LOCALIZATION_WORKFLOW.md')) {
    issues.add(
      ValidationIssue(
        'AD012',
        'Localization glossary/workflow files are missing.',
      ),
    );
  }

  final Map<String, dynamic> contracts =
      (manifest['contracts'] is Map<String, dynamic>)
      ? manifest['contracts'] as Map<String, dynamic>
      : <String, dynamic>{};

  if (!contracts.containsKey('localization_glossary_source_of_truth')) {
    issues.add(
      ValidationIssue(
        'AD012',
        'Manifest is missing localization glossary routing contract.',
      ),
    );
  }

  final String text = readText(
    'docs/assistant/workflows/LOCALIZATION_WORKFLOW.md',
  );
  if (!text.contains('## Expected Outputs') ||
      !text.contains("Don't use this workflow when") ||
      !text.contains('Instead use')) {
    issues.add(
      ValidationIssue(
        'AD005',
        'Localization workflow is missing required routing/heading contracts.',
      ),
    );
  }
}

Map<String, dynamic>? _loadManifest(
  String rootPath,
  List<ValidationIssue> issues,
  bool Function(String relPath) exists,
) {
  final String manifestPath = _resolvePath(
    rootPath,
    'docs/assistant/manifest.json',
  );
  final File manifestFile = File(manifestPath);
  if (!manifestFile.existsSync()) {
    issues.add(
      ValidationIssue(
        'AD002',
        'Manifest file is missing at docs/assistant/manifest.json.',
      ),
    );
    return null;
  }

  Map<String, dynamic> manifest;
  try {
    final dynamic decoded = jsonDecode(manifestFile.readAsStringSync());
    if (decoded is! Map<String, dynamic>) {
      issues.add(
        ValidationIssue('AD002', 'Manifest must decode to a JSON object.'),
      );
      return null;
    }
    manifest = decoded;
  } catch (error) {
    issues.add(ValidationIssue('AD002', 'Manifest JSON parse failed: $error'));
    return null;
  }

  const List<String> requiredTopLevelKeys = <String>[
    'version',
    'module_flags',
    'canonical',
    'bridges',
    'user_guides',
    'workflows',
    'global_commands',
    'contracts',
    'last_updated',
  ];
  final List<String> missingKeys = requiredTopLevelKeys
      .where((String key) => !manifest.containsKey(key))
      .toList();
  if (missingKeys.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD002',
        'Manifest missing required keys: ${missingKeys.join(', ')}',
      ),
    );
  }

  final bool validDate = RegExp(
    r'^\d{4}-\d{2}-\d{2}$',
  ).hasMatch((manifest['last_updated'] ?? '').toString());
  if (!validDate) {
    issues.add(
      ValidationIssue('AD002', 'Manifest last_updated must be YYYY-MM-DD.'),
    );
  }

  if (!exists('docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md')) {
    issues.add(ValidationIssue('AD010', 'Commit workflow doc is missing.'));
  }

  if (!exists('docs/assistant/GOLDEN_PRINCIPLES.md') ||
      !exists('docs/assistant/exec_plans/PLANS.md')) {
    issues.add(
      ValidationIssue(
        'AD019',
        'Missing GOLDEN_PRINCIPLES.md or exec_plans/PLANS.md scaffolding.',
      ),
    );
  }

  if (!exists('docs/assistant/workflows/REFERENCE_DISCOVERY_WORKFLOW.md')) {
    issues.add(
      ValidationIssue('AD015', 'REFERENCE_DISCOVERY_WORKFLOW.md is missing.'),
    );
  }

  if (!exists('tooling/validate_workspace_hygiene.dart') ||
      !exists('test/tooling/validate_workspace_hygiene_test.dart')) {
    issues.add(
      ValidationIssue(
        'AD014',
        'Workspace hygiene validator/tooling files are missing.',
      ),
    );
  }

  return manifest;
}

Map<String, bool> _extractModuleFlags(Map<String, dynamic> manifest) {
  final dynamic raw = manifest['module_flags'];
  if (raw is! Map<String, dynamic>) {
    return <String, bool>{};
  }
  final Map<String, bool> flags = <String, bool>{};
  for (final String key in _requiredModuleFlags) {
    final dynamic value = raw[key];
    if (value is bool) {
      flags[key] = value;
    }
  }
  return flags;
}

void _validateModuleFlags(
  Map<String, dynamic> manifest,
  List<ValidationIssue> issues,
) {
  final dynamic raw = manifest['module_flags'];
  if (raw is! Map<String, dynamic>) {
    issues.add(
      ValidationIssue(
        'AD029',
        'Manifest module_flags must exist as a JSON object.',
      ),
    );
    return;
  }

  final List<String> missing = _requiredModuleFlags
      .where((String key) => !raw.containsKey(key))
      .toList();
  if (missing.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD029',
        'Manifest module_flags missing required keys: ${missing.join(', ')}',
      ),
    );
  }

  final List<String> nonBool = _requiredModuleFlags
      .where((String key) => raw.containsKey(key) && raw[key] is! bool)
      .toList();
  if (nonBool.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD029',
        'Manifest module_flags must be boolean for keys: ${nonBool.join(', ')}',
      ),
    );
  }
}

void _validateManifestPaths(
  Map<String, dynamic> manifest,
  List<ValidationIssue> issues,
  bool Function(String relPath) exists,
) {
  final List<String> invalidRefs = <String>[];

  final List<dynamic> canonical = manifest['canonical'] is List<dynamic>
      ? manifest['canonical'] as List<dynamic>
      : <dynamic>[];
  for (final dynamic entry in canonical) {
    final String path = entry.toString();
    if (path.isEmpty || !exists(path)) {
      invalidRefs.add(path);
    }
  }

  final List<dynamic> userGuides = manifest['user_guides'] is List<dynamic>
      ? manifest['user_guides'] as List<dynamic>
      : <dynamic>[];
  if (manifest['user_guides'] == null) {
    issues.add(
      ValidationIssue('AD021', 'Manifest is missing user_guides key.'),
    );
  }
  for (final dynamic entry in userGuides) {
    final String path = entry.toString();
    if (path.isEmpty || !exists(path)) {
      issues.add(
        ValidationIssue(
          'AD022',
          'Manifest user guide path does not exist: $path',
        ),
      );
    }
  }

  final List<dynamic> bridges = manifest['bridges'] is List<dynamic>
      ? manifest['bridges'] as List<dynamic>
      : <dynamic>[];
  for (final dynamic bridge in bridges) {
    if (bridge is! Map<String, dynamic>) {
      invalidRefs.add('bridges entry is not object');
      continue;
    }
    final String bridgeDoc = (bridge['doc'] ?? '').toString();
    final String canonicalDoc = (bridge['canonical_doc'] ?? '').toString();
    if (bridgeDoc.isEmpty || !exists(bridgeDoc)) {
      invalidRefs.add(bridgeDoc);
    }
    if (canonicalDoc.isEmpty || !exists(canonicalDoc)) {
      invalidRefs.add(canonicalDoc);
    }
  }

  final List<dynamic> workflows = manifest['workflows'] is List<dynamic>
      ? manifest['workflows'] as List<dynamic>
      : <dynamic>[];
  for (final dynamic item in workflows) {
    if (item is! Map<String, dynamic>) {
      invalidRefs.add('workflow entry is not object');
      continue;
    }
    final String docPath = (item['doc'] ?? '').toString();
    if (docPath.isEmpty || !exists(docPath)) {
      invalidRefs.add(docPath);
    }
    for (final String field in <String>[
      'scope',
      'primary_files',
      'targeted_tests',
      'validation_commands',
    ]) {
      final dynamic value = item[field];
      if ((field == 'scope' && (value == null || value.toString().isEmpty)) ||
          (field != 'scope' && (value is! List || value.isEmpty))) {
        invalidRefs.add('workflow ${item['id']} missing non-empty $field');
      }
    }
  }

  if (invalidRefs.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD003',
        'Manifest paths/schema references are missing or invalid: ${invalidRefs.join(', ')}',
      ),
    );
  }
}

void _validateWorkflowIds(
  Map<String, dynamic> manifest,
  List<ValidationIssue> issues,
) {
  final Set<String> workflowIds = _extractWorkflowIds(manifest);
  final List<String> missingIds = _requiredWorkflowIds
      .where((String id) => !workflowIds.contains(id))
      .toList();
  if (missingIds.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD004',
        'Manifest missing required workflow IDs: ${missingIds.join(', ')}',
      ),
    );
  }
  if (!workflowIds.contains('reference_discovery')) {
    issues.add(
      ValidationIssue(
        'AD016',
        'Manifest missing reference_discovery workflow id.',
      ),
    );
  }

  final Map<String, bool> moduleFlags = _extractModuleFlags(manifest);
  final List<String> missingModuleWorkflowIds = <String>[];
  for (final MapEntry<String, List<String>> entry
      in _requiredWorkflowIdsByModule.entries) {
    if (moduleFlags[entry.key] != true) {
      continue;
    }
    for (final String workflowId in entry.value) {
      if (!workflowIds.contains(workflowId)) {
        missingModuleWorkflowIds.add(workflowId);
      }
    }
  }
  if (missingModuleWorkflowIds.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD030',
        'Manifest missing module-conditioned workflow IDs: ${missingModuleWorkflowIds.join(', ')}',
      ),
    );
  }
}

void _validateWorkflowDocs(
  Map<String, dynamic> manifest,
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
  bool Function(String relPath) exists,
) {
  final Set<String> workflowDocs = <String>{};
  final List<dynamic> workflows = manifest['workflows'] is List<dynamic>
      ? manifest['workflows'] as List<dynamic>
      : <dynamic>[];
  for (final dynamic entry in workflows) {
    if (entry is! Map<String, dynamic>) {
      continue;
    }
    final String docPath = (entry['doc'] ?? '').toString();
    if (docPath.isNotEmpty) {
      workflowDocs.add(docPath);
    }
  }

  final List<String> missingHeadings = <String>[];
  final List<String> missingExpected = <String>[];
  final List<String> missingNegativeRouting = <String>[];
  final List<String> missingCrossPlatformCommands = <String>[];
  final List<String> missingStageTokenText = <String>[];
  for (final String docPath in workflowDocs) {
    if (!exists(docPath)) {
      continue;
    }
    final String text = readText(docPath);
    for (final String heading in _requiredWorkflowHeadings) {
      if (!text.contains(heading)) {
        missingHeadings.add('$docPath -> $heading');
      }
    }
    if (!text.contains('## Expected Outputs')) {
      missingExpected.add(docPath);
    }
    if (!text.contains("Don't use this workflow when") ||
        !text.contains('Instead use')) {
      missingNegativeRouting.add(docPath);
    }
    final String lower = text.toLowerCase();
    final bool hasPowerShell = lower.contains('```powershell');
    final bool hasPosix = lower.contains('```bash') || lower.contains('```sh');
    if (!hasPowerShell || !hasPosix) {
      missingCrossPlatformCommands.add(docPath);
    }
    if (docPath.endsWith('STAGED_EXECUTION_WORKFLOW.md') &&
        !RegExp(r'NEXT_STAGE_\d+').hasMatch(text)) {
      missingStageTokenText.add(docPath);
    }
  }

  if (missingHeadings.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD005',
        'Workflow docs missing required headings: ${missingHeadings.join(' | ')}',
      ),
    );
  }
  if (missingExpected.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD006',
        'Workflow docs missing Expected Outputs: ${missingExpected.join(', ')}',
      ),
    );
  }
  if (missingNegativeRouting.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD007',
        'Workflow docs missing explicit negative-routing text: ${missingNegativeRouting.join(', ')}',
      ),
    );
  }
  if (missingCrossPlatformCommands.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD031',
        'Workflow docs missing cross-platform command blocks (PowerShell + POSIX): ${missingCrossPlatformCommands.join(', ')}',
      ),
    );
  }
  if (missingStageTokenText.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD032',
        'Staged execution workflow is missing NEXT_STAGE_X token guidance: ${missingStageTokenText.join(', ')}',
      ),
    );
  }

  final String indexText = readText('docs/assistant/INDEX.md');
  final List<String> missingDiscoverability = workflowDocs
      .where((String path) => exists(path) && !indexText.contains(path))
      .toList();
  if (missingDiscoverability.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD036',
        'Workflow docs are not discoverable from docs index: ${missingDiscoverability.join(', ')}',
      ),
    );
  }

  final Map<String, dynamic> contracts =
      manifest['contracts'] is Map<String, dynamic>
      ? manifest['contracts'] as Map<String, dynamic>
      : <String, dynamic>{};

  if (!exists('docs/assistant/workflows/PERFORMANCE_WORKFLOW.md') ||
      !exists('docs/assistant/PERFORMANCE_BASELINES.md') ||
      !contracts.containsKey('workspace_performance_source_of_truth')) {
    issues.add(
      ValidationIssue(
        'AD013',
        'Workspace performance workflow/baseline or routing contracts are missing.',
      ),
    );
  }

  if (!exists('docs/assistant/LOCALIZATION_GLOSSARY.md') ||
      !exists('docs/assistant/workflows/LOCALIZATION_WORKFLOW.md') ||
      !contracts.containsKey('localization_glossary_source_of_truth')) {
    issues.add(
      ValidationIssue(
        'AD012',
        'Localization glossary/workflow routing contracts are missing.',
      ),
    );
  }
}

void _validateCanonicalBridgePolicies(
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
) {
  final String canonical = readText('APP_KNOWLEDGE.md').toLowerCase();
  final String bridge = readText(
    'docs/assistant/APP_KNOWLEDGE.md',
  ).toLowerCase();

  final bool canonicalPhrase = canonical.contains(
    'canonical for app-level architecture and status',
  );
  final bool bridgePhrase =
      bridge.contains('intentionally shorter') && bridge.contains('defer');
  final bool sourceTruthPhrase = bridge.contains('source code is final truth');

  if (!canonicalPhrase || !bridgePhrase || !sourceTruthPhrase) {
    issues.add(
      ValidationIssue(
        'AD008',
        'Canonical/bridge contract phrases are missing.',
      ),
    );
  }

  if (bridge.contains('canonical for app-level architecture and status')) {
    issues.add(
      ValidationIssue(
        'AD011',
        'Bridge doc conflicts with canonical policy by claiming canonical authority.',
      ),
    );
  }
}

void _validateCommands(
  Map<String, dynamic> manifest,
  List<ValidationIssue> issues,
) {
  final List<String> allCommands = <String>[];

  if (manifest['global_commands'] is List<dynamic>) {
    allCommands.addAll(
      (manifest['global_commands'] as List<dynamic>).map(
        (dynamic cmd) => cmd.toString(),
      ),
    );
  }

  if (manifest['workflows'] is List<dynamic>) {
    for (final dynamic entry in manifest['workflows'] as List<dynamic>) {
      if (entry is! Map<String, dynamic>) {
        continue;
      }
      for (final String field in <String>[
        'validation_commands',
        'targeted_tests',
      ]) {
        if (entry[field] is List<dynamic>) {
          allCommands.addAll(
            (entry[field] as List<dynamic>).map(
              (dynamic cmd) => cmd.toString(),
            ),
          );
        }
      }
    }
  }

  final RegExp bashOnlyPattern = RegExp(
    r'(\bgrep\b|\bawk\b|\bsed\b|\bchmod\b|\bchown\b|\bbash\b|\bsource\b|\bexport\b|#!/bin/bash|rm\s+-rf|\bls\s+-la\b)',
    caseSensitive: false,
  );

  final List<String> flagged = allCommands
      .where((String command) => bashOnlyPattern.hasMatch(command))
      .toList();
  if (flagged.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD009',
        'Manifest contains bash-only or non-PowerShell-safe commands: ${flagged.join(' | ')}',
      ),
    );
  }
}

void _validateCoreContracts(
  Map<String, dynamic> manifest,
  List<ValidationIssue> issues,
) {
  final Map<String, dynamic> contracts =
      manifest['contracts'] is Map<String, dynamic>
      ? manifest['contracts'] as Map<String, dynamic>
      : <String, dynamic>{};

  final List<String> missing = _requiredContractKeys
      .where((String key) => !contracts.containsKey(key))
      .toList();
  for (final String key in <String>[
    'canonical_precedence_policy',
    'docs_sync_prompt_policy',
  ]) {
    if (!contracts.containsKey(key)) {
      missing.add(key);
    }
  }
  if (missing.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD018',
        'Manifest is missing required contract keys: ${missing.join(', ')}',
      ),
    );
  }

  if (!contracts.containsKey('post_change_docs_sync_prompt_policy') ||
      !contracts.containsKey('inspiration_reference_discovery_policy')) {
    issues.add(
      ValidationIssue(
        'AD017',
        'Manifest is missing docs-sync or inspiration discovery contracts.',
      ),
    );
  }

  for (final String contractKey in <String>[
    'post_change_docs_sync_prompt_policy',
    'docs_sync_prompt_policy',
  ]) {
    final String value = (contracts[contractKey] ?? '').toString();
    final String lower = value.toLowerCase();
    if (!value.contains(_docsSyncPrompt) ||
        !lower.contains(_docsSyncPromptCondition) ||
        !lower.contains(_docsSyncPromptImmediateNeed) ||
        !lower.contains(_docsSyncPromptDeferredPass) ||
        !lower.contains(_docsSyncPromptNoRepeat)) {
      issues.add(
        ValidationIssue(
          'AD017',
          'Manifest $contractKey must preserve the exact docs-sync prompt plus the deferred-default/immediate-need conditions.',
        ),
      );
    }
  }

  final List<String> requiredUserGuideContracts = <String>[
    'user_guides_support_usage_policy',
    'user_guides_canonical_deference_policy',
    'user_guides_update_sync_policy',
  ];
  final List<String> missingUserGuideContracts = requiredUserGuideContracts
      .where((String key) => !contracts.containsKey(key))
      .toList();
  if (missingUserGuideContracts.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD027',
        'Manifest missing user-guide contract keys: ${missingUserGuideContracts.join(', ')}',
      ),
    );
  }

  final Map<String, bool> moduleFlags = _extractModuleFlags(manifest);
  final List<String> missingModuleContracts = <String>[];
  for (final MapEntry<String, List<String>> entry
      in _requiredContractKeysByModule.entries) {
    if (moduleFlags[entry.key] != true) {
      continue;
    }
    for (final String contractKey in entry.value) {
      if (!contracts.containsKey(contractKey)) {
        missingModuleContracts.add(contractKey);
      }
    }
  }
  if (missingModuleContracts.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD033',
        'Manifest missing module-conditioned contract keys: ${missingModuleContracts.join(', ')}',
      ),
    );
  }
}

void _validateRunbookPolicies(
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
) {
  final Map<String, String> docs = <String, String>{
    'AGENTS.md': readText('AGENTS.md'),
    'agent.md': readText('agent.md'),
  };

  final List<String> missingSections = <String>[];
  for (final MapEntry<String, String> entry in docs.entries) {
    final String docName = entry.key;
    final String text = entry.value;
    for (final String heading in <String>[
      '## Approval Gates',
      '## ExecPlans',
      '## Worktree Isolation',
    ]) {
      if (!text.contains(heading)) {
        missingSections.add('$docName -> $heading');
      }
    }
    if (!text.contains(_docsSyncPrompt) ||
        !text.toLowerCase().contains(_docsSyncPromptCondition) ||
        !text.toLowerCase().contains(_docsSyncPromptImmediateNeed) ||
        !text.toLowerCase().contains(_docsSyncPromptDeferredPass) ||
        !text.toLowerCase().contains(_docsSyncPromptNoRepeat) ||
        !text.contains('REFERENCE_DISCOVERY_WORKFLOW.md')) {
      missingSections.add('$docName -> docs-sync/reference policy text');
    }

    if (!text.contains('APP_USER_GUIDE.md') ||
        !text.contains('PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md')) {
      issues.add(
        ValidationIssue(
          'AD026',
          '$docName omits support routing to user guides.',
        ),
      );
    }
  }

  if (missingSections.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD020',
        'AGENTS/runbook governance sections or policies missing: ${missingSections.join(' | ')}',
      ),
    );
  }

  final String ciText = readText(
    'docs/assistant/workflows/CI_REPO_WORKFLOW.md',
  ).toLowerCase();
  final String commitText = readText(
    'docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md',
  ).toLowerCase();
  final String docsText = readText(
    'docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md',
  ).toLowerCase();
  if (!ciText.contains('worktree') ||
      !commitText.contains('worktree') ||
      !docsText.contains('worktree')) {
    issues.add(
      ValidationIssue(
        'AD020',
        'Required workflows are missing worktree isolation guidance.',
      ),
    );
  }
}

void _validateUserGuides(
  Map<String, dynamic> manifest,
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
  bool Function(String relPath) exists,
) {
  if (manifest['user_guides'] == null) {
    issues.add(
      ValidationIssue('AD021', 'Manifest user_guides key is missing.'),
    );
    return;
  }
  if (manifest['user_guides'] is! List<dynamic>) {
    issues.add(
      ValidationIssue('AD021', 'Manifest user_guides must be a list.'),
    );
    return;
  }

  final List<dynamic> userGuides = manifest['user_guides'] as List<dynamic>;
  final List<String> missingRequiredPaths = <String>[];
  for (final String requiredPath in const <String>[
    'docs/assistant/features/APP_USER_GUIDE.md',
    'docs/assistant/features/PRIMARY_FEATURE_USER_GUIDE.md',
  ]) {
    final bool present = userGuides
        .map((dynamic item) => item.toString())
        .contains(requiredPath);
    if (!present) {
      missingRequiredPaths.add(requiredPath);
    }
  }
  if (missingRequiredPaths.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD021',
        'Manifest user_guides missing required paths: ${missingRequiredPaths.join(', ')}',
      ),
    );
  }

  final List<String> headingMisses = <String>[];
  for (final dynamic entry in userGuides) {
    final String path = entry.toString();
    if (!exists(path)) {
      continue;
    }
    final String text = readText(path);
    for (final String heading in _requiredUserGuideHeadings) {
      if (!text.contains(heading)) {
        headingMisses.add('$path -> $heading');
      }
    }
  }
  if (headingMisses.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD025',
        'User guides are missing required headings: ${headingMisses.join(' | ')}',
      ),
    );
  }

  final String indexText = readText('docs/assistant/INDEX.md');
  final List<String> missingDiscoverability = userGuides
      .map((dynamic item) => item.toString())
      .where((String path) => !indexText.contains(path))
      .toList();
  if (missingDiscoverability.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD023',
        'User guides are not discoverable from docs index: ${missingDiscoverability.join(', ')}',
      ),
    );
  }
}

void _validateDocsMaintenance(
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
) {
  final String text = readText(
    'docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md',
  ).toLowerCase();
  if (!text.contains('user-guide') || !text.contains('sync')) {
    issues.add(
      ValidationIssue(
        'AD028',
        'Docs maintenance workflow lacks user-guide sync guidance.',
      ),
    );
  }
  if (!text.contains('issue_memory.md') ||
      !text.contains('issue_memory.json') ||
      !text.contains('consult') ||
      !text.contains('bootstrap')) {
    issues.add(
      ValidationIssue(
        'AD041',
        'Docs maintenance workflow must require issue-memory updates/consultation and bootstrap escalation rules.',
      ),
    );
  }
  if (!text.contains(_docsSyncPromptCondition) ||
      !text.contains(_docsSyncPromptImmediateNeed) ||
      !text.contains(_docsSyncPromptDeferredPass) ||
      !text.contains(_docsSyncPromptNoRepeat)) {
    issues.add(
      ValidationIssue(
        'AD041',
        'Docs maintenance workflow must state the deferred-default docs-sync rule plus the immediate-need and no-repeat conditions.',
      ),
    );
  }
  if (!text.contains('live-state contamination') ||
      !text.contains('fragmented diagnostics') ||
      !text.contains('harness_isolation_and_diagnostics_workflow.md')) {
    issues.add(
      ValidationIssue(
        'AD041',
        'Docs maintenance workflow must escalate repeated live-state contamination and fragmented diagnostics into the harness isolation workflow.',
      ),
    );
  }
  if (!text.contains('session_resume.md') ||
      !text.contains('active/completed execplan lifecycle state') ||
      !text.contains('scratch outputs')) {
    issues.add(
      ValidationIssue(
        'AD041',
        'Docs maintenance workflow must repair stale continuity state and scratch-output drift during docs sync.',
      ),
    );
  }
}

void _validateQtRenderScratchPathGuidance(
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
) {
  const String expectedPath = 'tmp/qt_ui_review';
  const String legacyPath = 'tmp_ui_review';
  final String toolText = readText('tooling/qt_render_review.py').toLowerCase();
  if (!toolText.contains('"tmp" / "qt_ui_review"') ||
      toolText.contains('"tmp_ui_review"')) {
    issues.add(
      ValidationIssue(
        'AD047',
        'tooling/qt_render_review.py must default deterministic Qt render-review scratch output to tmp/qt_ui_review.',
      ),
    );
  }

  for (final String path in <String>[
    'docs/assistant/QT_UI_PLAYBOOK.md',
    'docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md',
  ]) {
    final String text = readText(path).toLowerCase();
    if (!text.contains(expectedPath) || text.contains(legacyPath)) {
      issues.add(
        ValidationIssue(
          'AD047',
          '$path must route deterministic Qt render-review scratch output through $expectedPath and not $legacyPath.',
        ),
      );
    }
  }
}

void _validateIssueMemory(
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
  bool Function(String relPath) exists,
  String rootPath,
) {
  const String mdPath = 'docs/assistant/ISSUE_MEMORY.md';
  const String jsonPath = 'docs/assistant/ISSUE_MEMORY.json';
  if (!exists(mdPath) || !exists(jsonPath)) {
    issues.add(
      ValidationIssue(
        'AD042',
        'Issue memory files must exist at $mdPath and $jsonPath.',
      ),
    );
    return;
  }

  final String mdText = readText(mdPath).toLowerCase();
  for (final String marker in <String>[
    'assistant docs sync',
    'update codex bootstrap',
    'ucbs',
    'operational trigger',
    'wording trigger',
    'repeat count',
    'accepted fix',
    'bootstrap relevance',
    'docs-sync relevance',
  ]) {
    if (!mdText.contains(marker)) {
      issues.add(
        ValidationIssue(
          'AD042',
          '$mdPath is missing required issue-memory marker: $marker',
        ),
      );
    }
  }

  Map<String, dynamic> issueMemory;
  try {
    final dynamic decoded = jsonDecode(readText(jsonPath));
    if (decoded is! Map<String, dynamic>) {
      issues.add(
        ValidationIssue('AD042', '$jsonPath must decode to a JSON object.'),
      );
      return;
    }
    issueMemory = decoded;
  } catch (error) {
    issues.add(ValidationIssue('AD042', '$jsonPath JSON parse failed: $error'));
    return;
  }

  final List<String> missingTopLevel = _requiredIssueMemoryTopLevelKeys
      .where((String key) => !issueMemory.containsKey(key))
      .toList();
  if (missingTopLevel.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD042',
        '$jsonPath is missing required top-level keys: ${missingTopLevel.join(', ')}',
      ),
    );
  }

  final String lastUpdated = (issueMemory['last_updated'] ?? '').toString();
  final RegExp isoPattern = RegExp(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$');
  if (!isoPattern.hasMatch(lastUpdated)) {
    issues.add(
      ValidationIssue(
        'AD042',
        '$jsonPath last_updated must be an ISO-8601 UTC timestamp.',
      ),
    );
  }

  final dynamic rawIssues = issueMemory['issues'];
  if (rawIssues is! List || rawIssues.isEmpty) {
    issues.add(
      ValidationIssue(
        'AD042',
        '$jsonPath must include a non-empty issues list.',
      ),
    );
    return;
  }

  bool seededIssueFound = false;
  final Set<String> issueIds = <String>{};
  for (final dynamic item in rawIssues) {
    if (item is! Map<String, dynamic>) {
      issues.add(
        ValidationIssue(
          'AD042',
          '$jsonPath issues entries must be JSON objects.',
        ),
      );
      continue;
    }
    final List<String> missingIssueKeys = _requiredIssueMemoryIssueKeys
        .where((String key) => !item.containsKey(key))
        .toList();
    if (missingIssueKeys.isNotEmpty) {
      issues.add(
        ValidationIssue(
          'AD042',
          '$jsonPath issue ${(item['id'] ?? '<missing id>')} is missing keys: ${missingIssueKeys.join(', ')}',
        ),
      );
    }

    final String id = (item['id'] ?? '').toString();
    if (id.isNotEmpty) {
      issueIds.add(id);
    }
    if (id == 'workflow-wrong-build-under-test') {
      seededIssueFound = true;
    }

    final String status = (item['status'] ?? '').toString();
    if (!<String>{
      'open',
      'mitigated',
      'resolved',
      'regressed',
    }.contains(status)) {
      issues.add(
        ValidationIssue(
          'AD042',
          '$jsonPath issue $id has invalid status: $status',
        ),
      );
    }

    final String triggerSource = (item['trigger_source'] ?? '').toString();
    if (!<String>{'operational', 'wording', 'both'}.contains(triggerSource)) {
      issues.add(
        ValidationIssue(
          'AD042',
          '$jsonPath issue $id has invalid trigger_source: $triggerSource',
        ),
      );
    }

    final String bootstrapRelevance = (item['bootstrap_relevance'] ?? '')
        .toString();
    if (!<String>{
      'none',
      'possible',
      'required',
    }.contains(bootstrapRelevance)) {
      issues.add(
        ValidationIssue(
          'AD042',
          '$jsonPath issue $id has invalid bootstrap_relevance: $bootstrapRelevance',
        ),
      );
    }
  }

  if (!seededIssueFound) {
    issues.add(
      ValidationIssue(
        'AD042',
        '$jsonPath must seed workflow-wrong-build-under-test as the initial repeated issue entry.',
      ),
    );
  }

  for (final String requiredId in <String>[
    'harness-live-state-contamination',
    'workflow-fragmented-multi-surface-diagnostics',
  ]) {
    if (!issueIds.contains(requiredId)) {
      issues.add(
        ValidationIssue(
          'AD042',
          '$jsonPath must include required durable issue entry: $requiredId',
        ),
      );
    }
  }
}

void _validateProjectLocalOperationalLayer(
  Map<String, dynamic> manifest,
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
  bool Function(String relPath) exists,
) {
  const String envPath = 'docs/assistant/LOCAL_ENV_PROFILE.local.md';
  const String capabilitiesPath = 'docs/assistant/LOCAL_CAPABILITIES.md';
  const String workflowPath =
      'docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md';

  for (final String path in <String>[envPath, capabilitiesPath, workflowPath]) {
    if (!exists(path)) {
      issues.add(
        ValidationIssue(
          'AD043',
          'Project-local operational doc is missing at $path.',
        ),
      );
      return;
    }
  }

  final String indexText = readText('docs/assistant/INDEX.md');
  final List<String> missingIndexRouting = <String>[
    envPath,
    capabilitiesPath,
    workflowPath,
  ].where((String path) => !indexText.contains(path)).toList();
  if (missingIndexRouting.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD043',
        'Project-local operational docs are not discoverable from docs index: ${missingIndexRouting.join(', ')}',
      ),
    );
  }

  final List<String> manifestPaths = <String>[];
  if (manifest['canonical'] is List<dynamic>) {
    manifestPaths.addAll(
      (manifest['canonical'] as List<dynamic>).map(
        (dynamic entry) => entry.toString(),
      ),
    );
  }
  if (manifest['workflows'] is List<dynamic>) {
    for (final dynamic entry in manifest['workflows'] as List<dynamic>) {
      if (entry is Map<String, dynamic>) {
        manifestPaths.add((entry['doc'] ?? '').toString());
      }
    }
  }
  final List<String> missingManifestRouting = <String>[
    envPath,
    capabilitiesPath,
    workflowPath,
  ].where((String path) => !manifestPaths.contains(path)).toList();
  if (missingManifestRouting.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD043',
        'Project-local operational docs are missing from manifest routing: ${missingManifestRouting.join(', ')}',
      ),
    );
  }

  final String envText = readText(envPath).toLowerCase();
  for (final String marker in <String>[
    'windows 11 home 64-bit',
    'windows + wsl',
    'ryzen 9 7940hs',
    '32 gb ram',
    'rtx 4070 laptop gpu',
    'radeon 780m',
    'prefer windows',
    'prefer wsl',
    'same-host',
    'listener ownership',
    'no secrets',
  ]) {
    if (!envText.contains(marker)) {
      issues.add(
        ValidationIssue(
          'AD043',
          '$envPath is missing required host/routing marker: $marker',
        ),
      );
    }
  }

  final String capabilitiesText = readText(capabilitiesPath).toLowerCase();
  for (final String marker in <String>[
    'local capabilities',
    'gog',
    'tooling/launch_qt_build.py',
    'windows',
    'wsl',
    'test isolation',
    'listener-ownership',
  ]) {
    if (!capabilitiesText.contains(marker)) {
      issues.add(
        ValidationIssue(
          'AD043',
          '$capabilitiesPath is missing required capability marker: $marker',
        ),
      );
    }
  }

  final String workflowText = readText(workflowPath).toLowerCase();
  for (final String marker in <String>[
    '1. installation exists',
    '2. auth/account exists',
    '3. host matches app runtime',
    '4. localhost listener ownership is correct',
    '5. live smoke check passes',
    'same-host validation rule',
    'owned by the expected process',
    'gog',
    'unavailable',
    'failed',
  ]) {
    if (!workflowText.contains(marker)) {
      issues.add(
        ValidationIssue(
          'AD043',
          '$workflowPath is missing required host-integration marker: $marker',
        ),
      );
    }
  }
}

void _validateProjectHarnessAndRoadmapGovernance(
  Map<String, dynamic> manifest,
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
  bool Function(String relPath) exists,
  String rootPath,
) {
  final Map<String, bool> moduleFlags = _extractModuleFlags(manifest);
  const String harnessWorkflowPath =
      'docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md';
  const String roadmapWorkflowPath =
      'docs/assistant/workflows/ROADMAP_WORKFLOW.md';
  const String sessionResumePath = 'docs/assistant/SESSION_RESUME.md';

  if (moduleFlags['project_harness_sync'] == true) {
    final Map<String, dynamic> contracts =
        manifest['contracts'] is Map<String, dynamic>
        ? manifest['contracts'] as Map<String, dynamic>
        : <String, dynamic>{};
    final List<dynamic> workflows = manifest['workflows'] is List<dynamic>
        ? manifest['workflows'] as List<dynamic>
        : <dynamic>[];
    if (!exists(harnessWorkflowPath)) {
      issues.add(
        ValidationIssue(
          'AD045',
          'Project harness sync workflow is missing at $harnessWorkflowPath.',
        ),
      );
    }

    final String harnessWorkflowText = readText(
      harnessWorkflowPath,
    ).toLowerCase();
    for (final String marker in <String>[
      'implement the template files',
      'sync project harness',
      'audit project harness',
      'check project harness',
      'docs/assistant/templates/*',
      'update codex bootstrap',
      'continuity or merge cleanup behavior',
      'resolution-first sync workflow',
      'check_harness_profile.py',
      'preview_harness_sync.py',
      'bootstrap_state.json',
      'legacy repo case',
      'commit_publish_workflow.md',
      'docs_maintenance_workflow.md',
      'separate logical commit scopes by default',
    ]) {
      if (!harnessWorkflowText.contains(marker)) {
        issues.add(
          ValidationIssue(
            'AD045',
            '$harnessWorkflowPath is missing required project-harness marker: $marker',
          ),
        );
      }
    }

    final String harnessPolicy =
        (contracts['project_harness_sync_policy'] ?? '')
            .toString()
            .toLowerCase();
    final String templateProtection =
        (contracts['vendored_template_protection_policy'] ?? '')
            .toString()
            .toLowerCase();
    final String cleanupCompletePush =
        (contracts['cleanup_complete_push_policy'] ?? '')
            .toString()
            .toLowerCase();
    final String postMergeRepair =
        (contracts['post_merge_repair_default_policy'] ?? '')
            .toString()
            .toLowerCase();
    final String scratchRoot = (contracts['scratch_root_default_policy'] ?? '')
        .toString()
        .toLowerCase();
    if (!harnessPolicy.contains('implement the template files') ||
        !harnessPolicy.contains('docs/assistant/templates/*') ||
        !templateProtection.contains('docs/assistant/templates/*')) {
      issues.add(
        ValidationIssue(
          'AD045',
          'Manifest contracts must make local harness apply and vendored-template protection explicit.',
        ),
      );
    }
    if (!cleanupCompletePush.contains('bare push') ||
        !cleanupCompletePush.contains('session_resume.md') ||
        !cleanupCompletePush.contains('scratch outputs') ||
        !postMergeRepair.contains('follow-up branch/pr') ||
        !postMergeRepair.contains('main') ||
        !scratchRoot.contains('tmp/') ||
        !scratchRoot.contains('stricter')) {
      issues.add(
        ValidationIssue(
          'AD045',
          'Manifest project-harness cleanup contracts must define cleanup-complete push, post-merge repair default, and ignored scratch-root defaults.',
        ),
      );
    }

    Map<String, dynamic>? harnessWorkflowEntry;
    for (final dynamic item in workflows) {
      if (item is! Map<String, dynamic>) {
        continue;
      }
      if ((item['id'] ?? '').toString() == 'project_harness_sync_workflow') {
        harnessWorkflowEntry = item;
        break;
      }
    }
    final List<dynamic> primaryFilesRaw =
        harnessWorkflowEntry?['primary_files'] is List<dynamic>
        ? harnessWorkflowEntry!['primary_files'] as List<dynamic>
        : <dynamic>[];
    final Set<String> primaryFiles = primaryFilesRaw
        .map((dynamic item) => item.toString())
        .toSet();
    final List<String> missingPrimaryFiles = <String>[
      'docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md',
      'docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md',
      'docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md',
      'docs/assistant/workflows/ROADMAP_WORKFLOW.md',
      'docs/assistant/SESSION_RESUME.md',
    ].where((String path) => !primaryFiles.contains(path)).toList();
    if (missingPrimaryFiles.isNotEmpty) {
      issues.add(
        ValidationIssue(
          'AD045',
          'Manifest project_harness_sync_workflow.primary_files must include continuity/cleanup governance docs. Missing: ${missingPrimaryFiles.join(', ')}',
        ),
      );
    }

    final Map<String, List<String>> routingDocs = <String, List<String>>{
      'agent.md': <String>[
        'implement the template files',
        'sync project harness',
        'audit project harness',
        'check project harness',
        'project_harness_sync_workflow.md',
        'update codex bootstrap',
      ],
      'AGENTS.md': <String>[
        'implement the template files',
        'sync project harness',
        'audit project harness',
        'check project harness',
        'project_harness_sync_workflow.md',
        'update codex bootstrap',
      ],
      'README.md': <String>[
        'implement the template files',
        'sync project harness',
        'audit project harness',
        'check project harness',
        'update codex bootstrap',
      ],
      'docs/assistant/INDEX.md': <String>['project_harness_sync_workflow.md'],
    };
    for (final MapEntry<String, List<String>> entry in routingDocs.entries) {
      final String text = readText(entry.key).toLowerCase();
      final List<String> missing = entry.value
          .where((String marker) => !text.contains(marker))
          .toList();
      if (missing.isNotEmpty) {
        issues.add(
          ValidationIssue(
            'AD045',
            '${entry.key} must route local project-harness sync clearly. Missing: ${missing.join(', ')}',
          ),
        );
      }
    }
  }

  if (moduleFlags['roadmap_governance'] == true) {
    final Map<String, dynamic> contracts =
        manifest['contracts'] is Map<String, dynamic>
        ? manifest['contracts'] as Map<String, dynamic>
        : <String, dynamic>{};
    if (!exists(roadmapWorkflowPath) || !exists(sessionResumePath)) {
      issues.add(
        ValidationIssue(
          'AD046',
          'Roadmap governance requires both $roadmapWorkflowPath and $sessionResumePath.',
        ),
      );
      return;
    }

    final List<dynamic> canonical = manifest['canonical'] is List<dynamic>
        ? manifest['canonical'] as List<dynamic>
        : <dynamic>[];
    if (!canonical
        .map((dynamic item) => item.toString())
        .contains(sessionResumePath)) {
      issues.add(
        ValidationIssue(
          'AD046',
          'Manifest canonical routing must include $sessionResumePath when roadmap governance is active.',
        ),
      );
    }

    final String resumePolicy =
        (contracts['roadmap_resume_anchor_policy'] ?? '')
            .toString()
            .toLowerCase();
    final String dormantMainPolicy =
        (contracts['roadmap_dormant_main_policy'] ?? '')
            .toString()
            .toLowerCase();
    final String authorityPolicy =
        (contracts['roadmap_active_worktree_authority_policy'] ?? '')
            .toString()
            .toLowerCase();
    final String updateOrderPolicy =
        (contracts['roadmap_update_order_policy'] ?? '')
            .toString()
            .toLowerCase();
    if (!resumePolicy.contains('docs/assistant/session_resume.md') ||
        !resumePolicy.contains('resume master plan') ||
        !dormantMainPolicy.contains('main') ||
        !dormantMainPolicy.contains('dormant roadmap state') ||
        !dormantMainPolicy.contains('no active roadmap') ||
        !dormantMainPolicy.contains('execplan flow') ||
        !authorityPolicy.contains('session_resume.md') ||
        !authorityPolicy.contains('active wave execplan') ||
        !updateOrderPolicy.contains('active wave execplan') ||
        !updateOrderPolicy.contains('docs/assistant/session_resume.md')) {
      issues.add(
        ValidationIssue(
          'AD046',
          'Manifest roadmap contracts must define the resume anchor, active-worktree authority, and update-order rule.',
        ),
      );
    }

    final String roadmapWorkflowText = readText(
      roadmapWorkflowPath,
    ).toLowerCase();
    for (final String marker in <String>[
      'docs/assistant/session_resume.md',
      'resume master plan',
      'dormant roadmap state',
      'normal execplan flow',
      'the active roadmap tracker is the sequence source',
      'the active wave execplan is the implementation-detail source',
      '1. active wave execplan',
      '2. active roadmap tracker',
      '3. `docs/assistant/session_resume.md`',
      'do not treat roadmap mode as the default',
    ]) {
      if (!roadmapWorkflowText.contains(marker)) {
        issues.add(
          ValidationIssue(
            'AD046',
            '$roadmapWorkflowPath is missing required roadmap marker: $marker',
          ),
        );
      }
    }

    final String sessionOriginalText = readText(sessionResumePath);
    final String sessionText = sessionOriginalText.toLowerCase();
    for (final String marker in <String>[
      'resume master plan',
      'roadmap anchor file',
      'authoritative worktree',
      'branch:',
      'next concrete action',
      'issue memory is only for repeatable governance/workflow failures',
    ]) {
      if (!sessionText.contains(marker)) {
        issues.add(
          ValidationIssue(
            'AD046',
            '$sessionResumePath is missing required session-resume marker: $marker',
          ),
        );
      }
    }

    final bool dormantRoadmapMarker = sessionText.contains(
      'dormant roadmap state',
    );
    final bool dormantNoActiveRoadmap = sessionText.contains(
      'no active roadmap currently open on this worktree',
    );
    final bool dormantRoadmap = dormantRoadmapMarker || dormantNoActiveRoadmap;
    if (dormantRoadmap) {
      for (final String marker in <String>[
        'dormant roadmap state',
        'no active roadmap currently open on this worktree',
        'normal execplan flow',
      ]) {
        if (!sessionText.contains(marker)) {
          issues.add(
            ValidationIssue(
              'AD046',
              '$sessionResumePath is missing required dormant-roadmap marker: $marker',
            ),
          );
        }
      }
    } else {
      for (final String marker in <String>[
        'active roadmap tracker',
        'active wave execplan',
      ]) {
        if (!sessionText.contains(marker)) {
          issues.add(
            ValidationIssue(
              'AD046',
              '$sessionResumePath is missing required active-roadmap marker: $marker',
            ),
          );
        }
      }
    }

    final String? branchName = _extractSessionResumeBranch(sessionOriginalText);
    if (branchName == null || branchName.trim().isEmpty) {
      issues.add(
        ValidationIssue(
          'AD046',
          '$sessionResumePath must name an authoritative branch.',
        ),
      );
    } else if (_isGitRepo(rootPath) &&
        !_gitBranchExists(rootPath, branchName.trim()) &&
        !_sessionResumeBranchAllowedWithoutRef(rootPath, branchName.trim())) {
      issues.add(
        ValidationIssue(
          'AD046',
          '$sessionResumePath points to a branch that does not exist in this repo: $branchName',
        ),
      );
    }

    final Map<String, List<String>> routingDocs = <String, List<String>>{
      'agent.md': <String>[
        'resume master plan',
        'session_resume.md',
        'dormant roadmap state',
        'normal execplan flow',
      ],
      'AGENTS.md': <String>[
        'resume master plan',
        'session_resume.md',
        'dormant roadmap state',
      ],
      'README.md': <String>[
        'resume master plan',
        'session_resume.md',
        'dormant roadmap state',
        'normal execplan flow',
      ],
      'docs/assistant/INDEX.md': <String>[
        'session_resume.md',
        'roadmap_workflow.md',
      ],
      'APP_KNOWLEDGE.md': <String>[
        'session_resume.md',
        'issue memory remains a reusable repeated-issue registry',
        'active roadmap tracker',
        'dormant roadmap state',
      ],
      'docs/assistant/APP_KNOWLEDGE.md': <String>[
        'session_resume.md',
        'issue memory is not roadmap history',
        'active roadmap tracker',
        'dormant roadmap state',
      ],
    };
    for (final MapEntry<String, List<String>> entry in routingDocs.entries) {
      final String text = readText(entry.key).toLowerCase();
      final List<String> missing = entry.value
          .where((String marker) => !text.contains(marker))
          .toList();
      if (missing.isNotEmpty) {
        issues.add(
          ValidationIssue(
            'AD046',
            '${entry.key} must route roadmap resume continuity. Missing: ${missing.join(', ')}',
          ),
        );
      }
    }
  }
}

String? _extractSessionResumeBranch(String sessionText) {
  for (final String line in LineSplitter.split(sessionText)) {
    final String trimmed = line.trim();
    if (!trimmed.toLowerCase().startsWith('- branch:')) {
      continue;
    }
    final String branch = trimmed.substring('- Branch:'.length).trim();
    if (branch.isEmpty) {
      return null;
    }
    if (branch.startsWith('`') && branch.endsWith('`') && branch.length >= 2) {
      return branch.substring(1, branch.length - 1);
    }
    return branch;
  }
  return null;
}

bool _isGitRepo(String rootPath) {
  try {
    final ProcessResult result = Process.runSync('git', <String>[
      '-C',
      rootPath,
      'rev-parse',
      '--is-inside-work-tree',
    ]);
    return result.exitCode == 0 && result.stdout.toString().trim() == 'true';
  } catch (_) {
    return false;
  }
}

bool _gitBranchExists(String rootPath, String branchName) {
  for (final String ref in <String>[
    'refs/heads/$branchName',
    'refs/remotes/origin/$branchName',
  ]) {
    try {
      final ProcessResult result = Process.runSync('git', <String>[
        '-C',
        rootPath,
        'show-ref',
        '--verify',
        '--quiet',
        ref,
      ]);
      if (result.exitCode == 0) {
        return true;
      }
    } catch (_) {
      return false;
    }
  }
  return false;
}

bool _sessionResumeBranchAllowedWithoutRef(String rootPath, String branchName) {
  final Set<String> allowedBranches = <String>{};

  final Map<String, dynamic>? canonicalBuild = _loadCanonicalBuildConfig(
    rootPath,
  );
  if (canonicalBuild != null) {
    for (final String key in <String>[
      'canonical_branch',
      'approved_base_branch',
    ]) {
      final String value = (canonicalBuild[key] ?? '').toString().trim();
      if (value.isNotEmpty) {
        allowedBranches.add(value);
      }
    }
  }

  for (final String key in <String>[
    'GITHUB_HEAD_REF',
    'GITHUB_REF_NAME',
    'GITHUB_BASE_REF',
  ]) {
    final String value = (Platform.environment[key] ?? '').trim();
    if (value.isNotEmpty) {
      allowedBranches.add(value);
    }
  }

  final String? currentBranch = _gitCurrentBranchName(rootPath);
  if (currentBranch != null &&
      currentBranch.isNotEmpty &&
      currentBranch != 'HEAD') {
    allowedBranches.add(currentBranch);
  }

  return allowedBranches.contains(branchName);
}

Map<String, dynamic>? _loadCanonicalBuildConfig(String rootPath) {
  final File file = File(
    _resolvePath(rootPath, 'docs/assistant/runtime/CANONICAL_BUILD.json'),
  );
  if (!file.existsSync()) {
    return null;
  }
  try {
    final dynamic decoded = jsonDecode(file.readAsStringSync());
    if (decoded is Map<String, dynamic>) {
      return decoded;
    }
  } catch (_) {
    return null;
  }
  return null;
}

String? _gitCurrentBranchName(String rootPath) {
  try {
    final ProcessResult result = Process.runSync('git', <String>[
      '-C',
      rootPath,
      'rev-parse',
      '--abbrev-ref',
      'HEAD',
    ]);
    if (result.exitCode != 0) {
      return null;
    }
    final String branchName = result.stdout.toString().trim();
    if (branchName.isEmpty) {
      return null;
    }
    return branchName;
  } catch (_) {
    return null;
  }
}

void _validateHarnessIsolationAndDiagnostics(
  Map<String, dynamic> manifest,
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
  bool Function(String relPath) exists,
) {
  const String workflowPath =
      'docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md';

  if (!exists(workflowPath)) {
    issues.add(
      ValidationIssue(
        'AD044',
        'Harness isolation workflow is missing at $workflowPath.',
      ),
    );
    return;
  }

  final String indexText = readText('docs/assistant/INDEX.md');
  if (!indexText.contains(workflowPath)) {
    issues.add(
      ValidationIssue(
        'AD044',
        'Harness isolation workflow must be discoverable from docs index.',
      ),
    );
  }

  bool manifestRouted = false;
  if (manifest['workflows'] is List<dynamic>) {
    for (final dynamic entry in manifest['workflows'] as List<dynamic>) {
      if (entry is Map<String, dynamic> &&
          entry['id'] == 'harness_isolation_and_diagnostics_workflow' &&
          entry['doc'] == workflowPath) {
        manifestRouted = true;
      }
    }
  }
  if (!manifestRouted) {
    issues.add(
      ValidationIssue(
        'AD044',
        'Manifest must route harness_isolation_and_diagnostics_workflow to $workflowPath.',
      ),
    );
  }

  final String workflowText = readText(workflowPath).toLowerCase();
  for (final String marker in <String>[
    'temporary filesystem and environment state',
    'authenticated machine state',
    'non-live or ephemeral ports',
    'listener ownership and runtime conflict rules',
    'visible runtime status',
    'workflow_context',
    'one durable app-owned session artifact',
    'support packet order',
    'do not create separate browser or extension report files',
  ]) {
    if (!workflowText.contains(marker)) {
      issues.add(
        ValidationIssue(
          'AD044',
          '$workflowPath is missing required harness marker: $marker',
        ),
      );
    }
  }

  final Map<String, List<String>> routingDocs = <String, List<String>>{
    'APP_KNOWLEDGE.md': <String>[
      workflowPath.toLowerCase(),
      'localhost listeners',
      'browser/app bridges',
      'handoff/run/finalization',
    ],
    'docs/assistant/APP_KNOWLEDGE.md': <String>[
      workflowPath.toLowerCase(),
      'listener ownership',
      'test isolation',
      'handoff/run/finalization',
    ],
  };
  for (final MapEntry<String, List<String>> entry in routingDocs.entries) {
    final String text = readText(entry.key).toLowerCase();
    final List<String> missing = entry.value
        .where((String marker) => !text.contains(marker))
        .toList();
    if (missing.isNotEmpty) {
      issues.add(
        ValidationIssue(
          'AD044',
          '${entry.key} must route harness isolation and diagnostics guidance. Missing: ${missing.join(', ')}',
        ),
      );
    }
  }
}

void _validateExternalSourceRegistry(
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
  bool Function(String relPath) exists,
) {
  const String path = 'docs/assistant/EXTERNAL_SOURCE_REGISTRY.md';
  if (!exists(path)) {
    issues.add(
      ValidationIssue('AD034', 'External source registry is missing at $path.'),
    );
    return;
  }

  final String text = readText(path);
  final String lower = text.toLowerCase();
  for (final String key in <String>[
    'source_url',
    'contract_or_workflow',
    'fact_summary',
    'verification_date',
  ]) {
    if (!lower.contains(key)) {
      issues.add(
        ValidationIssue(
          'AD034',
          'External source registry missing required field marker: $key',
        ),
      );
    }
  }

  final RegExp rowPattern = RegExp(
    r'^\|\s*(https?://[^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|$',
    multiLine: true,
  );
  final Iterable<RegExpMatch> rows = rowPattern.allMatches(text);
  if (rows.isEmpty) {
    issues.add(
      ValidationIssue(
        'AD034',
        'External source registry has no valid source rows.',
      ),
    );
    return;
  }

  const List<String> allowedHosts = <String>[
    'developers.openai.com',
    'platform.openai.com',
    'playwright.dev',
    'developer.chrome.com',
    'docs.github.com',
    'learn.microsoft.com',
  ];
  final List<String> badHosts = <String>[];
  for (final RegExpMatch match in rows) {
    final String url = (match.group(1) ?? '').trim();
    final Uri? parsed = Uri.tryParse(url);
    final String host = (parsed?.host ?? '').toLowerCase();
    if (!allowedHosts.contains(host)) {
      badHosts.add(url);
    }
  }
  if (badHosts.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD035',
        'External source registry includes non-official domains: ${badHosts.join(', ')}',
      ),
    );
  }
}

void _validateTemplatePolicy(
  Map<String, dynamic> manifest,
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
) {
  final String indexText = readText('docs/assistant/INDEX.md').toLowerCase();
  final Map<String, dynamic> contracts =
      manifest['contracts'] is Map<String, dynamic>
      ? manifest['contracts'] as Map<String, dynamic>
      : <String, dynamic>{};

  final bool indexPolicy =
      indexText.contains('docs/assistant/templates/*') &&
      indexText.contains('read-on-demand');
  final bool contractPolicy =
      contracts.containsKey('template_read_policy') &&
      contracts.containsKey('template_path_routing_regression_protection');
  if (!indexPolicy || !contractPolicy) {
    issues.add(
      ValidationIssue(
        'AD024',
        'Template-path routing regression protections are missing.',
      ),
    );
  }
}

void _validateBootstrapTemplateIntegrity(
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
  bool Function(String relPath) exists,
) {
  const String mapPath = 'docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json';
  if (!exists(mapPath)) {
    issues.add(
      ValidationIssue(
        'AD039',
        'Bootstrap template map is missing at $mapPath.',
      ),
    );
    return;
  }

  Map<String, dynamic> templateMap;
  try {
    final dynamic decoded = jsonDecode(readText(mapPath));
    if (decoded is! Map<String, dynamic>) {
      issues.add(
        ValidationIssue(
          'AD039',
          'Bootstrap template map must decode to a JSON object.',
        ),
      );
      return;
    }
    templateMap = decoded;
  } catch (error) {
    issues.add(
      ValidationIssue(
        'AD039',
        'Bootstrap template map JSON parse failed: $error',
      ),
    );
    return;
  }

  if ((templateMap['entrypoint'] ?? '').toString() !=
      'docs/assistant/templates/CODEX_PROJECT_BOOTSTRAP_PROMPT.md') {
    issues.add(
      ValidationIssue(
        'AD039',
        'Bootstrap template map must point entrypoint to docs/assistant/templates/CODEX_PROJECT_BOOTSTRAP_PROMPT.md.',
      ),
    );
  }

  final dynamic rawModules = templateMap['modules'];
  if (rawModules is! List<dynamic>) {
    issues.add(
      ValidationIssue(
        'AD039',
        'Bootstrap template map must include a modules list.',
      ),
    );
    return;
  }

  final dynamic rawTargets = templateMap['targets'];
  if (rawTargets is! List<dynamic>) {
    issues.add(
      ValidationIssue(
        'AD039',
        'Bootstrap template map must include a targets list for the phase-1 profile-driven rollout.',
      ),
    );
  }

  final Set<String> moduleIds = <String>{};
  final Map<String, List<String>> moduleTopicsById = <String, List<String>>{};
  final List<String> invalidModuleRefs = <String>[];
  for (final dynamic module in rawModules) {
    if (module is! Map<String, dynamic>) {
      invalidModuleRefs.add('module entry is not object');
      continue;
    }
    final String id = (module['id'] ?? '').toString();
    final String path = (module['path'] ?? '').toString();
    final dynamic topics = module['topics'];
    moduleIds.add(id);
    if (id.isEmpty || path.isEmpty || !exists(path)) {
      invalidModuleRefs.add('$id -> $path');
    }
    if (topics is! List || topics.isEmpty) {
      invalidModuleRefs.add('$id missing non-empty topics');
      continue;
    }
    moduleTopicsById[id] = topics
        .map((dynamic item) => item.toString().toLowerCase())
        .toList();
  }

  final List<String> missingModuleIds = _requiredBootstrapModuleIds
      .where((String id) => !moduleIds.contains(id))
      .toList();
  if (invalidModuleRefs.isNotEmpty || missingModuleIds.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD039',
        'Bootstrap template map is incomplete. Invalid refs: ${invalidModuleRefs.join(', ')}. Missing modules: ${missingModuleIds.join(', ')}',
      ),
    );
  }

  if (rawTargets is List<dynamic>) {
    final Map<String, Map<String, String>> targetsByDestination =
        <String, Map<String, String>>{};
    final List<String> invalidTargets = <String>[];
    for (final dynamic target in rawTargets) {
      if (target is! Map<String, dynamic>) {
        invalidTargets.add('target entry is not object');
        continue;
      }
      final String destination = (target['destination'] ?? '').toString();
      final String template = (target['template'] ?? '').toString();
      final String policy = (target['policy'] ?? '').toString();
      if (destination.isEmpty || template.isEmpty || policy.isEmpty) {
        invalidTargets.add(
          'target missing destination/template/policy: $destination',
        );
        continue;
      }
      targetsByDestination[destination] = <String, String>{
        'template': template,
        'policy': policy,
      };
    }

    final List<String> missingTargets = <String>[];
    for (final MapEntry<String, Map<String, String>> entry
        in _requiredBootstrapTargets.entries) {
      final Map<String, String>? actual = targetsByDestination[entry.key];
      if (actual == null) {
        missingTargets.add(entry.key);
        continue;
      }
      if (actual['template'] != entry.value['template'] ||
          actual['policy'] != entry.value['policy']) {
        invalidTargets.add(
          '${entry.key} -> template/policy mismatch (${actual['template']}, ${actual['policy']})',
        );
      }
    }

    if (invalidTargets.isNotEmpty || missingTargets.isNotEmpty) {
      issues.add(
        ValidationIssue(
          'AD039',
          'Bootstrap template map targets are incomplete. Invalid targets: ${invalidTargets.join(', ')}. Missing targets: ${missingTargets.join(', ')}',
        ),
      );
    }
  }

  final List<String> missingTopicMarkers = <String>[];
  for (final MapEntry<String, List<String>> entry
      in _requiredBootstrapTopicsByModule.entries) {
    final List<String> topics = moduleTopicsById[entry.key] ?? <String>[];
    for (final String marker in entry.value) {
      if (!topics.contains(marker)) {
        missingTopicMarkers.add('${entry.key} -> $marker');
      }
    }
  }
  if (missingTopicMarkers.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD039',
        'Bootstrap template map topics are missing required markers: ${missingTopicMarkers.join(', ')}',
      ),
    );
  }

  final List<String> missingMarkers = <String>[];
  for (final MapEntry<String, List<String>> entry
      in _requiredBootstrapMarkers.entries) {
    final String relPath = entry.key;
    final String text = readText(relPath).toLowerCase();
    for (final String marker in entry.value) {
      if (!text.contains(marker)) {
        missingMarkers.add('$relPath -> $marker');
      }
    }
  }
  if (missingMarkers.isNotEmpty) {
    issues.add(
      ValidationIssue(
        'AD040',
        'Bootstrap template docs are missing required module markers: ${missingMarkers.join(' | ')}',
      ),
    );
  }
}

Set<String> _extractWorkflowIds(Map<String, dynamic> manifest) {
  if (manifest['workflows'] is! List<dynamic>) {
    return <String>{};
  }
  return (manifest['workflows'] as List<dynamic>)
      .whereType<Map<String, dynamic>>()
      .map((Map<String, dynamic> item) => (item['id'] ?? '').toString())
      .where((String id) => id.isNotEmpty)
      .toSet();
}

String _resolvePath(String rootPath, String relPath) {
  final String normalized = relPath.replaceAll('/', Platform.pathSeparator);
  return '$rootPath${Platform.pathSeparator}$normalized';
}

int _runCli(List<String> args) {
  bool localizationScope = false;
  for (int i = 0; i < args.length; i++) {
    if (args[i] == '--scope' && i + 1 < args.length) {
      localizationScope = args[i + 1].toLowerCase() == 'localization';
      i++;
    }
  }

  final List<ValidationIssue> issues = validateAgentDocs(
    rootPath: Directory.current.path,
    localizationScope: localizationScope,
  );

  if (issues.isEmpty) {
    stdout.writeln(
      localizationScope
          ? 'PASS (localization scope): agent docs validation succeeded.'
          : 'PASS: agent docs validation succeeded.',
    );
    return 0;
  }

  stdout.writeln(
    localizationScope
        ? 'FAIL (localization scope): ${issues.length} issue(s).'
        : 'FAIL: ${issues.length} issue(s).',
  );
  for (final ValidationIssue issue in issues) {
    stdout.writeln(issue.toString());
  }
  return 1;
}

void main(List<String> args) {
  exit(_runCli(args));
}
