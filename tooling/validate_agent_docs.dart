import 'dart:convert';
import 'dart:io';

class ValidationIssue {
  ValidationIssue(this.ruleId, this.message);

  final String ruleId;
  final String message;

  @override
  String toString() => '$ruleId: $message';
}

const List<String> _requiredFiles = <String>[
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
  'docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md',
  'docs/assistant/runtime/CANONICAL_BUILD.json',
  'docs/assistant/templates/CODEX_PROJECT_BOOTSTRAP_PROMPT.md',
  'docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json',
  'docs/assistant/templates/BOOTSTRAP_CORE_CONTRACT.md',
  'docs/assistant/templates/BOOTSTRAP_ISSUE_MEMORY_SYSTEM.md',
  'docs/assistant/templates/BOOTSTRAP_MODULES_AND_TRIGGERS.md',
  'docs/assistant/templates/BOOTSTRAP_LOCAL_ENV_OVERLAY.md',
  'docs/assistant/templates/BOOTSTRAP_CAPABILITY_DISCOVERY.md',
  'docs/assistant/templates/BOOTSTRAP_WORKTREE_BUILD_IDENTITY.md',
  'docs/assistant/templates/BOOTSTRAP_HOST_INTEGRATION_PREFLIGHT.md',
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

const List<String> _requiredWorkflowIds = <String>[
  'feature_workflow',
  'data_workflow',
  'localization_workflow',
  'workspace_performance_workflow',
  'reference_discovery',
  'ci_repo_ops',
  'commit_publish_ops',
  'docs_maintenance_workflow',
];

const List<String> _requiredModuleFlags = <String>[
  'core_contract',
  'beginner_layer',
  'localization_performance',
  'reference_discovery',
  'browser_automation_environment_provenance',
  'cloud_machine_evaluation_local_acceptance',
  'staged_execution',
  'openai_docs_citation',
];

const Map<String, List<String>> _requiredWorkflowIdsByModule =
    <String, List<String>>{
      'staged_execution': <String>['staged_execution_workflow'],
      'browser_automation_environment_provenance': <String>[
        'browser_automation_env_provenance'
      ],
      'cloud_machine_evaluation_local_acceptance': <String>[
        'cloud_machine_evaluation'
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
  'user_guides_support_usage_policy',
  'user_guides_canonical_deference_policy',
  'user_guides_update_sync_policy',
  'template_path_routing_regression_protection',
  'issue_memory_policy',
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
      'staged_execution': <String>['stage_gate_policy'],
      'reference_discovery': <String>['reference_discovery_policy'],
      'openai_docs_citation': <String>[
        'openai_docs_citation_freshness_policy'
      ],
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
const String _docsSyncPromptNoRepeat =
    'already ran during the same task/pass';

const Map<String, List<String>> _requiredBootstrapMarkers =
    <String, List<String>>{
      'docs/assistant/templates/CODEX_PROJECT_BOOTSTRAP_PROMPT.md': <String>[
        'bootstrap execution order',
        'bootstrap_template_map.json',
        'bootstrap_core_contract.md',
        'bootstrap_issue_memory_system.md',
        'bootstrap_modules_and_triggers.md',
        'read-on-demand',
      ],
      'docs/assistant/templates/BOOTSTRAP_CORE_CONTRACT.md': <String>[
        'docs/assistant/issue_memory.md',
        'docs/assistant/issue_memory.json',
        'commit and push shorthand defaults',
        'full pending-tree triage',
        'push+pr+merge+cleanup',
        'openai / codex freshness rule',
        'relevant touched-scope docs still remain unsynced',
        'must not ask the prompt again',
      ],
      'docs/assistant/templates/BOOTSTRAP_ISSUE_MEMORY_SYSTEM.md': <String>[
        'required generated files',
        'docs/assistant/issue_memory.md',
        'docs/assistant/issue_memory.json',
        'operational triggers take priority',
        'wording triggers are secondary signals',
        'assistant docs sync',
        'update codex bootstrap',
        'repeat_count >= 2',
        'do not preseed fake incidents',
      ],
      'docs/assistant/templates/BOOTSTRAP_MODULES_AND_TRIGGERS.md': <String>[
        'issue memory system',
        'always on',
        'worktree / build identity',
        'auto-conditional',
        'runnable app',
        'local desktop workflow',
        'merge-immediately-after-acceptance discipline',
        'trigger matrix',
        'stage-gate rules',
        'reference discovery rules',
        'browser automation rules',
      ],
      'docs/assistant/templates/BOOTSTRAP_LOCAL_ENV_OVERLAY.md': <String>[
        'windows 11 home 64-bit',
        'windows + wsl',
        'local_env_profile.local.md',
        'same-host rule',
      ],
      'docs/assistant/templates/BOOTSTRAP_CAPABILITY_DISCOVERY.md': <String>[
        'agents.md',
        'local_capabilities.md',
        'openai-docs',
        'dynamic discovery',
      ],
      'docs/assistant/templates/BOOTSTRAP_WORKTREE_BUILD_IDENTITY.md': <String>[
        'auto-activation rule',
        'runnable app',
        'gui',
        'merge-immediately-after-acceptance',
        'latest approved baseline rule',
        'build under test identity packet',
        'canonical runnable build rule',
        'worktree path',
      ],
      'docs/assistant/templates/BOOTSTRAP_HOST_INTEGRATION_PREFLIGHT.md': <String>[
        'tool installation exists on the target host',
        'same-host validation rule',
        'gmail draft feature backed by a local authenticated cli is just one example',
        'live smoke check',
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
        'dart run tooling/validate_agent_docs.dart',
        'docs sync prompt rule',
        'relevant touched-scope docs still remain unsynced',
        'already ran during the same task/pass',
      ],
    };

const List<String> _requiredBootstrapModuleIds = <String>[
  'core_contract',
  'issue_memory_system',
  'modules_and_triggers',
  'local_env_overlay',
  'capability_discovery',
  'worktree_build_identity',
  'host_integration_preflight',
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

  if (!localizationScope) {
    final List<String> missing =
        _requiredFiles.where((String path) => !exists(path)).toList();
    if (missing.isNotEmpty) {
      issues.add(ValidationIssue(
        'AD001',
        'Required files are missing: ${missing.join(', ')}',
      ));
    }
  }

  final Map<String, dynamic>? manifest = _loadManifest(rootPath, issues, exists);
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
    _validateProjectLocalOperationalLayer(manifest, issues, readText, exists);
    _validateTemplatePolicy(manifest, issues, readText);
    _validateBootstrapTemplateIntegrity(issues, readText, exists);
    _validateExternalSourceRegistry(issues, readText, exists);
  } else {
    _validateLocalizationScope(manifest, issues, readText, exists);
  }

  return issues;
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
      issues.add(ValidationIssue(
        'AD037',
        '$relPath must require tooling/launch_qt_build.py, canonical build handling, and build-under-test packets with HEAD SHA in GUI handoffs.',
      ));
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
      issues.add(ValidationIssue(
        'AD038',
        '$relPath must define hardened commit/push shorthand semantics. Missing: ${missing.join(', ')}',
      ));
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
    issues.add(ValidationIssue(
      'AD039',
      'docs/assistant/runtime/CANONICAL_BUILD.json must be valid JSON.',
    ));
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
      issues.add(ValidationIssue(
        'AD039',
        'docs/assistant/runtime/CANONICAL_BUILD.json is missing required keys: ${missingKeys.join(', ')}',
      ));
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
      issues.add(ValidationIssue(
        'AD039',
        '${entry.key} must enforce approved-base promotion and lineage rules. Missing: ${missing.join(', ')}',
      ));
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
    issues.add(ValidationIssue(
      'AD004',
      'Required workflow id missing: localization_workflow.',
    ));
  }

  if (!exists('docs/assistant/LOCALIZATION_GLOSSARY.md') ||
      !exists('docs/assistant/workflows/LOCALIZATION_WORKFLOW.md')) {
    issues.add(ValidationIssue(
      'AD012',
      'Localization glossary/workflow files are missing.',
    ));
  }

  final Map<String, dynamic> contracts =
      (manifest['contracts'] is Map<String, dynamic>)
          ? manifest['contracts'] as Map<String, dynamic>
          : <String, dynamic>{};

  if (!contracts.containsKey('localization_glossary_source_of_truth')) {
    issues.add(ValidationIssue(
      'AD012',
      'Manifest is missing localization glossary routing contract.',
    ));
  }

  final String text = readText('docs/assistant/workflows/LOCALIZATION_WORKFLOW.md');
  if (!text.contains('## Expected Outputs') ||
      !text.contains("Don't use this workflow when") ||
      !text.contains('Instead use')) {
    issues.add(ValidationIssue(
      'AD005',
      'Localization workflow is missing required routing/heading contracts.',
    ));
  }
}

Map<String, dynamic>? _loadManifest(
  String rootPath,
  List<ValidationIssue> issues,
  bool Function(String relPath) exists,
) {
  final String manifestPath = _resolvePath(rootPath, 'docs/assistant/manifest.json');
  final File manifestFile = File(manifestPath);
  if (!manifestFile.existsSync()) {
    issues.add(ValidationIssue(
      'AD002',
      'Manifest file is missing at docs/assistant/manifest.json.',
    ));
    return null;
  }

  Map<String, dynamic> manifest;
  try {
    final dynamic decoded = jsonDecode(manifestFile.readAsStringSync());
    if (decoded is! Map<String, dynamic>) {
      issues.add(ValidationIssue('AD002', 'Manifest must decode to a JSON object.'));
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
    issues.add(ValidationIssue(
      'AD002',
      'Manifest missing required keys: ${missingKeys.join(', ')}',
    ));
  }

  final bool validDate = RegExp(r'^\d{4}-\d{2}-\d{2}$')
      .hasMatch((manifest['last_updated'] ?? '').toString());
  if (!validDate) {
    issues.add(ValidationIssue(
      'AD002',
      'Manifest last_updated must be YYYY-MM-DD.',
    ));
  }

  if (!exists('docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md')) {
    issues.add(ValidationIssue('AD010', 'Commit workflow doc is missing.'));
  }

  if (!exists('docs/assistant/GOLDEN_PRINCIPLES.md') ||
      !exists('docs/assistant/exec_plans/PLANS.md')) {
    issues.add(ValidationIssue(
      'AD019',
      'Missing GOLDEN_PRINCIPLES.md or exec_plans/PLANS.md scaffolding.',
    ));
  }

  if (!exists('docs/assistant/workflows/REFERENCE_DISCOVERY_WORKFLOW.md')) {
    issues.add(ValidationIssue(
      'AD015',
      'REFERENCE_DISCOVERY_WORKFLOW.md is missing.',
    ));
  }

  if (!exists('tooling/validate_workspace_hygiene.dart') ||
      !exists('test/tooling/validate_workspace_hygiene_test.dart')) {
    issues.add(ValidationIssue(
      'AD014',
      'Workspace hygiene validator/tooling files are missing.',
    ));
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
    issues.add(ValidationIssue(
      'AD029',
      'Manifest module_flags must exist as a JSON object.',
    ));
    return;
  }

  final List<String> missing = _requiredModuleFlags
      .where((String key) => !raw.containsKey(key))
      .toList();
  if (missing.isNotEmpty) {
    issues.add(ValidationIssue(
      'AD029',
      'Manifest module_flags missing required keys: ${missing.join(', ')}',
    ));
  }

  final List<String> nonBool = _requiredModuleFlags
      .where((String key) => raw.containsKey(key) && raw[key] is! bool)
      .toList();
  if (nonBool.isNotEmpty) {
    issues.add(ValidationIssue(
      'AD029',
      'Manifest module_flags must be boolean for keys: ${nonBool.join(', ')}',
    ));
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
    issues.add(ValidationIssue('AD021', 'Manifest is missing user_guides key.'));
  }
  for (final dynamic entry in userGuides) {
    final String path = entry.toString();
    if (path.isEmpty || !exists(path)) {
      issues.add(ValidationIssue(
        'AD022',
        'Manifest user guide path does not exist: $path',
      ));
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
      'validation_commands'
    ]) {
      final dynamic value = item[field];
      if ((field == 'scope' && (value == null || value.toString().isEmpty)) ||
          (field != 'scope' && (value is! List || value.isEmpty))) {
        invalidRefs.add('workflow ${item['id']} missing non-empty $field');
      }
    }
  }

  if (invalidRefs.isNotEmpty) {
    issues.add(ValidationIssue(
      'AD003',
      'Manifest paths/schema references are missing or invalid: ${invalidRefs.join(', ')}',
    ));
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
    issues.add(ValidationIssue(
      'AD004',
      'Manifest missing required workflow IDs: ${missingIds.join(', ')}',
    ));
  }
  if (!workflowIds.contains('reference_discovery')) {
    issues.add(ValidationIssue(
      'AD016',
      'Manifest missing reference_discovery workflow id.',
    ));
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
    issues.add(ValidationIssue(
      'AD030',
      'Manifest missing module-conditioned workflow IDs: ${missingModuleWorkflowIds.join(', ')}',
    ));
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
    final bool hasPosix =
        lower.contains('```bash') || lower.contains('```sh');
    if (!hasPowerShell || !hasPosix) {
      missingCrossPlatformCommands.add(docPath);
    }
    if (docPath.endsWith('STAGED_EXECUTION_WORKFLOW.md') &&
        !RegExp(r'NEXT_STAGE_\d+').hasMatch(text)) {
      missingStageTokenText.add(docPath);
    }
  }

  if (missingHeadings.isNotEmpty) {
    issues.add(ValidationIssue(
      'AD005',
      'Workflow docs missing required headings: ${missingHeadings.join(' | ')}',
    ));
  }
  if (missingExpected.isNotEmpty) {
    issues.add(ValidationIssue(
      'AD006',
      'Workflow docs missing Expected Outputs: ${missingExpected.join(', ')}',
    ));
  }
  if (missingNegativeRouting.isNotEmpty) {
    issues.add(ValidationIssue(
      'AD007',
      'Workflow docs missing explicit negative-routing text: ${missingNegativeRouting.join(', ')}',
    ));
  }
  if (missingCrossPlatformCommands.isNotEmpty) {
    issues.add(ValidationIssue(
      'AD031',
      'Workflow docs missing cross-platform command blocks (PowerShell + POSIX): ${missingCrossPlatformCommands.join(', ')}',
    ));
  }
  if (missingStageTokenText.isNotEmpty) {
    issues.add(ValidationIssue(
      'AD032',
      'Staged execution workflow is missing NEXT_STAGE_X token guidance: ${missingStageTokenText.join(', ')}',
    ));
  }

  final String indexText = readText('docs/assistant/INDEX.md');
  final List<String> missingDiscoverability = workflowDocs
      .where((String path) => exists(path) && !indexText.contains(path))
      .toList();
  if (missingDiscoverability.isNotEmpty) {
    issues.add(ValidationIssue(
      'AD036',
      'Workflow docs are not discoverable from docs index: ${missingDiscoverability.join(', ')}',
    ));
  }

  final Map<String, dynamic> contracts =
      manifest['contracts'] is Map<String, dynamic>
          ? manifest['contracts'] as Map<String, dynamic>
          : <String, dynamic>{};

  if (!exists('docs/assistant/workflows/PERFORMANCE_WORKFLOW.md') ||
      !exists('docs/assistant/PERFORMANCE_BASELINES.md') ||
      !contracts.containsKey('workspace_performance_source_of_truth')) {
    issues.add(ValidationIssue(
      'AD013',
      'Workspace performance workflow/baseline or routing contracts are missing.',
    ));
  }

  if (!exists('docs/assistant/LOCALIZATION_GLOSSARY.md') ||
      !exists('docs/assistant/workflows/LOCALIZATION_WORKFLOW.md') ||
      !contracts.containsKey('localization_glossary_source_of_truth')) {
    issues.add(ValidationIssue(
      'AD012',
      'Localization glossary/workflow routing contracts are missing.',
    ));
  }
}

void _validateCanonicalBridgePolicies(
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
) {
  final String canonical = readText('APP_KNOWLEDGE.md').toLowerCase();
  final String bridge = readText('docs/assistant/APP_KNOWLEDGE.md').toLowerCase();

  final bool canonicalPhrase =
      canonical.contains('canonical for app-level architecture and status');
  final bool bridgePhrase =
      bridge.contains('intentionally shorter') && bridge.contains('defer');
  final bool sourceTruthPhrase = bridge.contains('source code is final truth');

  if (!canonicalPhrase || !bridgePhrase || !sourceTruthPhrase) {
    issues.add(ValidationIssue(
      'AD008',
      'Canonical/bridge contract phrases are missing.',
    ));
  }

  if (bridge.contains('canonical for app-level architecture and status')) {
    issues.add(ValidationIssue(
      'AD011',
      'Bridge doc conflicts with canonical policy by claiming canonical authority.',
    ));
  }
}

void _validateCommands(
  Map<String, dynamic> manifest,
  List<ValidationIssue> issues,
) {
  final List<String> allCommands = <String>[];

  if (manifest['global_commands'] is List<dynamic>) {
    allCommands.addAll((manifest['global_commands'] as List<dynamic>)
        .map((dynamic cmd) => cmd.toString()));
  }

  if (manifest['workflows'] is List<dynamic>) {
    for (final dynamic entry in manifest['workflows'] as List<dynamic>) {
      if (entry is! Map<String, dynamic>) {
        continue;
      }
      for (final String field in <String>['validation_commands', 'targeted_tests']) {
        if (entry[field] is List<dynamic>) {
          allCommands.addAll((entry[field] as List<dynamic>)
              .map((dynamic cmd) => cmd.toString()));
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
    issues.add(ValidationIssue(
      'AD009',
      'Manifest contains bash-only or non-PowerShell-safe commands: ${flagged.join(' | ')}',
    ));
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
    issues.add(ValidationIssue(
      'AD018',
      'Manifest is missing required contract keys: ${missing.join(', ')}',
    ));
  }

  if (!contracts.containsKey('post_change_docs_sync_prompt_policy') ||
      !contracts.containsKey('inspiration_reference_discovery_policy')) {
    issues.add(ValidationIssue(
      'AD017',
      'Manifest is missing docs-sync or inspiration discovery contracts.',
    ));
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
    issues.add(ValidationIssue(
      'AD027',
      'Manifest missing user-guide contract keys: ${missingUserGuideContracts.join(', ')}',
    ));
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
    issues.add(ValidationIssue(
      'AD033',
      'Manifest missing module-conditioned contract keys: ${missingModuleContracts.join(', ')}',
    ));
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
        !text.toLowerCase().contains(_docsSyncPromptNoRepeat) ||
        !text.contains('REFERENCE_DISCOVERY_WORKFLOW.md')) {
      missingSections.add('$docName -> docs-sync/reference policy text');
    }

    if (!text.contains('APP_USER_GUIDE.md') ||
        !text.contains('PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md')) {
      issues.add(ValidationIssue(
        'AD026',
        '$docName omits support routing to user guides.',
      ));
    }
  }

  if (missingSections.isNotEmpty) {
    issues.add(ValidationIssue(
      'AD020',
      'AGENTS/runbook governance sections or policies missing: ${missingSections.join(' | ')}',
    ));
  }

  final String ciText =
      readText('docs/assistant/workflows/CI_REPO_WORKFLOW.md').toLowerCase();
  final String commitText =
      readText('docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md').toLowerCase();
  final String docsText =
      readText('docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md').toLowerCase();
  if (!ciText.contains('worktree') ||
      !commitText.contains('worktree') ||
      !docsText.contains('worktree')) {
    issues.add(ValidationIssue(
      'AD020',
      'Required workflows are missing worktree isolation guidance.',
    ));
  }
}

void _validateUserGuides(
  Map<String, dynamic> manifest,
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
  bool Function(String relPath) exists,
) {
  if (manifest['user_guides'] == null) {
    issues.add(ValidationIssue('AD021', 'Manifest user_guides key is missing.'));
    return;
  }
  if (manifest['user_guides'] is! List<dynamic>) {
    issues.add(ValidationIssue('AD021', 'Manifest user_guides must be a list.'));
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
    issues.add(ValidationIssue(
      'AD021',
      'Manifest user_guides missing required paths: ${missingRequiredPaths.join(', ')}',
    ));
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
    issues.add(ValidationIssue(
      'AD025',
      'User guides are missing required headings: ${headingMisses.join(' | ')}',
    ));
  }

  final String indexText = readText('docs/assistant/INDEX.md');
  final List<String> missingDiscoverability = userGuides
      .map((dynamic item) => item.toString())
      .where((String path) => !indexText.contains(path))
      .toList();
  if (missingDiscoverability.isNotEmpty) {
    issues.add(ValidationIssue(
      'AD023',
      'User guides are not discoverable from docs index: ${missingDiscoverability.join(', ')}',
    ));
  }
}

void _validateDocsMaintenance(
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
) {
  final String text =
      readText('docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md')
          .toLowerCase();
  if (!text.contains('user-guide') || !text.contains('sync')) {
    issues.add(ValidationIssue(
      'AD028',
      'Docs maintenance workflow lacks user-guide sync guidance.',
    ));
  }
  if (!text.contains('issue_memory.md') ||
      !text.contains('issue_memory.json') ||
      !text.contains('consult') ||
      !text.contains('bootstrap')) {
    issues.add(ValidationIssue(
      'AD041',
      'Docs maintenance workflow must require issue-memory updates/consultation and bootstrap escalation rules.',
    ));
  }
  if (!text.contains(_docsSyncPromptCondition) ||
      !text.contains(_docsSyncPromptNoRepeat)) {
    issues.add(ValidationIssue(
      'AD041',
      'Docs maintenance workflow must state that the docs-sync prompt is only asked when relevant docs remain unsynced and not repeated after same-pass sync.',
    ));
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
    issues.add(ValidationIssue(
      'AD042',
      'Issue memory files must exist at $mdPath and $jsonPath.',
    ));
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
      issues.add(ValidationIssue(
        'AD042',
        '$mdPath is missing required issue-memory marker: $marker',
      ));
    }
  }

  Map<String, dynamic> issueMemory;
  try {
    final dynamic decoded = jsonDecode(readText(jsonPath));
    if (decoded is! Map<String, dynamic>) {
      issues.add(ValidationIssue(
        'AD042',
        '$jsonPath must decode to a JSON object.',
      ));
      return;
    }
    issueMemory = decoded;
  } catch (error) {
    issues.add(ValidationIssue(
      'AD042',
      '$jsonPath JSON parse failed: $error',
    ));
    return;
  }

  final List<String> missingTopLevel = _requiredIssueMemoryTopLevelKeys
      .where((String key) => !issueMemory.containsKey(key))
      .toList();
  if (missingTopLevel.isNotEmpty) {
    issues.add(ValidationIssue(
      'AD042',
      '$jsonPath is missing required top-level keys: ${missingTopLevel.join(', ')}',
    ));
  }

  final String lastUpdated = (issueMemory['last_updated'] ?? '').toString();
  final RegExp isoPattern = RegExp(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$');
  if (!isoPattern.hasMatch(lastUpdated)) {
    issues.add(ValidationIssue(
      'AD042',
      '$jsonPath last_updated must be an ISO-8601 UTC timestamp.',
    ));
  }

  final dynamic rawIssues = issueMemory['issues'];
  if (rawIssues is! List || rawIssues.isEmpty) {
    issues.add(ValidationIssue(
      'AD042',
      '$jsonPath must include a non-empty issues list.',
    ));
    return;
  }

  bool seededIssueFound = false;
  for (final dynamic item in rawIssues) {
    if (item is! Map<String, dynamic>) {
      issues.add(ValidationIssue(
        'AD042',
        '$jsonPath issues entries must be JSON objects.',
      ));
      continue;
    }
    final List<String> missingIssueKeys = _requiredIssueMemoryIssueKeys
        .where((String key) => !item.containsKey(key))
        .toList();
    if (missingIssueKeys.isNotEmpty) {
      issues.add(ValidationIssue(
        'AD042',
        '$jsonPath issue ${(item['id'] ?? '<missing id>')} is missing keys: ${missingIssueKeys.join(', ')}',
      ));
    }

    final String id = (item['id'] ?? '').toString();
    if (id == 'workflow-wrong-build-under-test') {
      seededIssueFound = true;
    }

    final String status = (item['status'] ?? '').toString();
    if (!<String>{'open', 'mitigated', 'resolved', 'regressed'}
        .contains(status)) {
      issues.add(ValidationIssue(
        'AD042',
        '$jsonPath issue $id has invalid status: $status',
      ));
    }

    final String triggerSource = (item['trigger_source'] ?? '').toString();
    if (!<String>{'operational', 'wording', 'both'}.contains(triggerSource)) {
      issues.add(ValidationIssue(
        'AD042',
        '$jsonPath issue $id has invalid trigger_source: $triggerSource',
      ));
    }

    final String bootstrapRelevance =
        (item['bootstrap_relevance'] ?? '').toString();
    if (!<String>{'none', 'possible', 'required'}
        .contains(bootstrapRelevance)) {
      issues.add(ValidationIssue(
        'AD042',
        '$jsonPath issue $id has invalid bootstrap_relevance: $bootstrapRelevance',
      ));
    }
  }

  if (!seededIssueFound) {
    issues.add(ValidationIssue(
      'AD042',
      '$jsonPath must seed workflow-wrong-build-under-test as the initial repeated issue entry.',
    ));
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
      issues.add(ValidationIssue(
        'AD043',
        'Project-local operational doc is missing at $path.',
      ));
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
    issues.add(ValidationIssue(
      'AD043',
      'Project-local operational docs are not discoverable from docs index: ${missingIndexRouting.join(', ')}',
    ));
  }

  final List<String> manifestPaths = <String>[];
  if (manifest['canonical'] is List<dynamic>) {
    manifestPaths.addAll((manifest['canonical'] as List<dynamic>)
        .map((dynamic entry) => entry.toString()));
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
    issues.add(ValidationIssue(
      'AD043',
      'Project-local operational docs are missing from manifest routing: ${missingManifestRouting.join(', ')}',
    ));
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
    'no secrets',
  ]) {
    if (!envText.contains(marker)) {
      issues.add(ValidationIssue(
        'AD043',
        '$envPath is missing required host/routing marker: $marker',
      ));
    }
  }

  final String capabilitiesText = readText(capabilitiesPath).toLowerCase();
  for (final String marker in <String>[
    'local capabilities',
    'gog',
    'tooling/launch_qt_build.py',
    'windows',
    'wsl',
  ]) {
    if (!capabilitiesText.contains(marker)) {
      issues.add(ValidationIssue(
        'AD043',
        '$capabilitiesPath is missing required capability marker: $marker',
      ));
    }
  }

  final String workflowText = readText(workflowPath).toLowerCase();
  for (final String marker in <String>[
    '1. installation exists',
    '2. auth/account exists',
    '3. host matches app runtime',
    '4. live smoke check passes',
    'same-host validation rule',
    'gog',
    'unavailable',
    'failed',
  ]) {
    if (!workflowText.contains(marker)) {
      issues.add(ValidationIssue(
        'AD043',
        '$workflowPath is missing required host-integration marker: $marker',
      ));
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
    issues.add(ValidationIssue(
      'AD034',
      'External source registry is missing at $path.',
    ));
    return;
  }

  final String text = readText(path);
  final String lower = text.toLowerCase();
  for (final String key in <String>[
    'source_url',
    'contract_or_workflow',
    'fact_summary',
    'verification_date'
  ]) {
    if (!lower.contains(key)) {
      issues.add(ValidationIssue(
        'AD034',
        'External source registry missing required field marker: $key',
      ));
    }
  }

  final RegExp rowPattern = RegExp(
    r'^\|\s*(https?://[^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|$',
    multiLine: true,
  );
  final Iterable<RegExpMatch> rows = rowPattern.allMatches(text);
  if (rows.isEmpty) {
    issues.add(ValidationIssue(
      'AD034',
      'External source registry has no valid source rows.',
    ));
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
    issues.add(ValidationIssue(
      'AD035',
      'External source registry includes non-official domains: ${badHosts.join(', ')}',
    ));
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

  final bool indexPolicy = indexText.contains('docs/assistant/templates/*') &&
      indexText.contains('read-on-demand');
  final bool contractPolicy = contracts.containsKey('template_read_policy') &&
      contracts.containsKey('template_path_routing_regression_protection');
  if (!indexPolicy || !contractPolicy) {
    issues.add(ValidationIssue(
      'AD024',
      'Template-path routing regression protections are missing.',
    ));
  }
}

void _validateBootstrapTemplateIntegrity(
  List<ValidationIssue> issues,
  String Function(String relPath) readText,
  bool Function(String relPath) exists,
) {
  const String mapPath = 'docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json';
  if (!exists(mapPath)) {
    issues.add(ValidationIssue(
      'AD039',
      'Bootstrap template map is missing at $mapPath.',
    ));
    return;
  }

  Map<String, dynamic> templateMap;
  try {
    final dynamic decoded = jsonDecode(readText(mapPath));
    if (decoded is! Map<String, dynamic>) {
      issues.add(ValidationIssue(
        'AD039',
        'Bootstrap template map must decode to a JSON object.',
      ));
      return;
    }
    templateMap = decoded;
  } catch (error) {
    issues.add(ValidationIssue(
      'AD039',
      'Bootstrap template map JSON parse failed: $error',
    ));
    return;
  }

  if ((templateMap['entrypoint'] ?? '').toString() !=
      'docs/assistant/templates/CODEX_PROJECT_BOOTSTRAP_PROMPT.md') {
    issues.add(ValidationIssue(
      'AD039',
      'Bootstrap template map must point entrypoint to docs/assistant/templates/CODEX_PROJECT_BOOTSTRAP_PROMPT.md.',
    ));
  }

  final dynamic rawModules = templateMap['modules'];
  if (rawModules is! List<dynamic>) {
    issues.add(ValidationIssue(
      'AD039',
      'Bootstrap template map must include a modules list.',
    ));
    return;
  }

  final Set<String> moduleIds = <String>{};
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
    }
  }

  final List<String> missingModuleIds = _requiredBootstrapModuleIds
      .where((String id) => !moduleIds.contains(id))
      .toList();
  if (invalidModuleRefs.isNotEmpty || missingModuleIds.isNotEmpty) {
    issues.add(ValidationIssue(
      'AD039',
      'Bootstrap template map is incomplete. Invalid refs: ${invalidModuleRefs.join(', ')}. Missing modules: ${missingModuleIds.join(', ')}',
    ));
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
    issues.add(ValidationIssue(
      'AD040',
      'Bootstrap template docs are missing required module markers: ${missingMarkers.join(' | ')}',
    ));
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
    stdout.writeln(localizationScope
        ? 'PASS (localization scope): agent docs validation succeeded.'
        : 'PASS: agent docs validation succeeded.');
    return 0;
  }

  stdout.writeln(localizationScope
      ? 'FAIL (localization scope): ${issues.length} issue(s).'
      : 'FAIL: ${issues.length} issue(s).');
  for (final ValidationIssue issue in issues) {
    stdout.writeln(issue.toString());
  }
  return 1;
}

void main(List<String> args) {
  exit(_runCli(args));
}
