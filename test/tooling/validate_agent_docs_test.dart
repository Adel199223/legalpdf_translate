import 'dart:convert';
import 'dart:io';

import '../../tooling/validate_agent_docs.dart' as validator;

typedef CaseBody = void Function();

class _CaseFailure implements Exception {
  _CaseFailure(this.message);

  final String message;

  @override
  String toString() => message;
}

void _expect(bool condition, String message) {
  if (!condition) {
    throw _CaseFailure(message);
  }
}

void _runCase(String name, CaseBody body, List<String> failures) {
  try {
    body();
    stdout.writeln('[PASS] $name');
  } catch (error) {
    failures.add('$name -> $error');
    stdout.writeln('[FAIL] $name');
  }
}

String _fixtureRoot() {
  final String repoRoot = Directory.current.path;
  final Directory fixture =
      Directory.systemTemp.createTempSync('agent_docs_validator_fixture_');

  final List<String> seedPaths = <String>[
    'AGENTS.md',
    'agent.md',
    'APP_KNOWLEDGE.md',
    '.vscode/settings.json',
    'docs/assistant',
    'tooling/validate_agent_docs.dart',
    'tooling/validate_workspace_hygiene.dart',
    'tooling/automation_preflight.dart',
    'tooling/cloud_eval_preflight.dart',
    'test/tooling/validate_agent_docs_test.dart',
    'test/tooling/validate_workspace_hygiene_test.dart',
    'test/tooling/automation_preflight_test.dart',
    'test/tooling/cloud_eval_preflight_test.dart',
  ];

  for (final String path in seedPaths) {
    final String source = _resolve(repoRoot, path);
    final String target = _resolve(fixture.path, path);
    final FileSystemEntityType type = FileSystemEntity.typeSync(source);
    if (type == FileSystemEntityType.directory) {
      _copyDirectory(Directory(source), Directory(target));
    } else if (type == FileSystemEntityType.file) {
      final File targetFile = File(target);
      targetFile.parent.createSync(recursive: true);
      targetFile.writeAsBytesSync(File(source).readAsBytesSync());
    }
  }

  return fixture.path;
}

String _resolve(String root, String relPath) {
  final String normalized = relPath.replaceAll('/', Platform.pathSeparator);
  return '$root${Platform.pathSeparator}$normalized';
}

void _copyDirectory(Directory source, Directory destination) {
  destination.createSync(recursive: true);
  for (final FileSystemEntity entity in source.listSync(recursive: false)) {
    final List<String> segments = entity.path.split(RegExp(r'[\\/]'));
    final String name = segments.isEmpty ? '' : segments.last;
    if (name.isEmpty) {
      continue;
    }
    final String targetPath = _resolve(destination.path, name);
    if (entity is Directory) {
      _copyDirectory(entity, Directory(targetPath));
    } else if (entity is File) {
      final File targetFile = File(targetPath);
      targetFile.parent.createSync(recursive: true);
      targetFile.writeAsBytesSync(entity.readAsBytesSync());
    }
  }
}

void _removePath(String root, String relPath) {
  final String path = _resolve(root, relPath);
  final FileSystemEntityType type = FileSystemEntity.typeSync(path);
  if (type == FileSystemEntityType.file) {
    File(path).deleteSync();
  } else if (type == FileSystemEntityType.directory) {
    Directory(path).deleteSync(recursive: true);
  }
}

void _replaceInFile(String root, String relPath, String from, String to) {
  final File file = File(_resolve(root, relPath));
  final String text = file.readAsStringSync();
  file.writeAsStringSync(text.replaceAll(from, to));
}

Map<String, dynamic> _readJson(String root, String relPath) {
  final File file = File(_resolve(root, relPath));
  return jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
}

void _writeJson(String root, String relPath, Map<String, dynamic> value) {
  final File file = File(_resolve(root, relPath));
  file.writeAsStringSync(const JsonEncoder.withIndent('  ').convert(value));
}

bool _hasRule(List<validator.ValidationIssue> issues, String ruleId) {
  return issues.any((validator.ValidationIssue issue) => issue.ruleId == ruleId);
}

void main() {
  final List<String> failures = <String>[];

  _runCase('passes for current fixture', () {
    final String root = _fixtureRoot();
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(issues.isEmpty, 'Expected no issues, got: $issues');
  }, failures);

  _runCase('fails when required workflow file missing', () {
    final String root = _fixtureRoot();
    _removePath(root, 'docs/assistant/workflows/REFERENCE_DISCOVERY_WORKFLOW.md');
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD001') || _hasRule(issues, 'AD015'),
        'Expected AD001 or AD015');
  }, failures);

  _runCase('fails when required workflow ID missing', () {
    final String root = _fixtureRoot();
    final Map<String, dynamic> manifest = _readJson(root, 'docs/assistant/manifest.json');
    final List<dynamic> workflows = manifest['workflows'] as List<dynamic>;
    workflows.removeWhere((dynamic item) =>
        item is Map<String, dynamic> && item['id'] == 'ci_repo_ops');
    _writeJson(root, 'docs/assistant/manifest.json', manifest);
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD004'), 'Expected AD004');
  }, failures);

  _runCase('fails when canonical bridge phrase removed', () {
    final String root = _fixtureRoot();
    _replaceInFile(
      root,
      'docs/assistant/APP_KNOWLEDGE.md',
      'intentionally shorter',
      'short',
    );
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD008'), 'Expected AD008');
  }, failures);

  _runCase('fails when manifest paths are broken', () {
    final String root = _fixtureRoot();
    final Map<String, dynamic> manifest = _readJson(root, 'docs/assistant/manifest.json');
    manifest['user_guides'] = <String>['docs/assistant/features/MISSING.md'];
    _writeJson(root, 'docs/assistant/manifest.json', manifest);
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD022'), 'Expected AD022');
  }, failures);

  _runCase('fails when localization workflow ID missing', () {
    final String root = _fixtureRoot();
    final Map<String, dynamic> manifest = _readJson(root, 'docs/assistant/manifest.json');
    final List<dynamic> workflows = manifest['workflows'] as List<dynamic>;
    workflows.removeWhere((dynamic item) =>
        item is Map<String, dynamic> && item['id'] == 'localization_workflow');
    _writeJson(root, 'docs/assistant/manifest.json', manifest);
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD004'), 'Expected AD004');
  }, failures);

  _runCase('fails when workspace performance contracts missing', () {
    final String root = _fixtureRoot();
    final Map<String, dynamic> manifest = _readJson(root, 'docs/assistant/manifest.json');
    final Map<String, dynamic> contracts = manifest['contracts'] as Map<String, dynamic>;
    contracts.remove('workspace_performance_source_of_truth');
    _writeJson(root, 'docs/assistant/manifest.json', manifest);
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD013') || _hasRule(issues, 'AD018'),
        'Expected AD013 or AD018');
  }, failures);

  _runCase('fails when workspace hygiene validator files missing', () {
    final String root = _fixtureRoot();
    _removePath(root, 'tooling/validate_workspace_hygiene.dart');
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD001') || _hasRule(issues, 'AD014'),
        'Expected AD001 or AD014');
  }, failures);

  _runCase('fails when reference_discovery ID missing', () {
    final String root = _fixtureRoot();
    final Map<String, dynamic> manifest = _readJson(root, 'docs/assistant/manifest.json');
    final List<dynamic> workflows = manifest['workflows'] as List<dynamic>;
    workflows.removeWhere((dynamic item) =>
        item is Map<String, dynamic> && item['id'] == 'reference_discovery');
    _writeJson(root, 'docs/assistant/manifest.json', manifest);
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD016') || _hasRule(issues, 'AD004'),
        'Expected AD016 or AD004');
  }, failures);

  _runCase('fails when docs-sync/inspiration contracts missing', () {
    final String root = _fixtureRoot();
    final Map<String, dynamic> manifest = _readJson(root, 'docs/assistant/manifest.json');
    final Map<String, dynamic> contracts = manifest['contracts'] as Map<String, dynamic>;
    contracts.remove('post_change_docs_sync_prompt_policy');
    contracts.remove('inspiration_reference_discovery_policy');
    _writeJson(root, 'docs/assistant/manifest.json', manifest);
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD017'), 'Expected AD017');
  }, failures);

  _runCase('fails when AGENTS docs-sync phrase removed', () {
    final String root = _fixtureRoot();
    _replaceInFile(
      root,
      'AGENTS.md',
      'Would you like me to run Assistant Docs Sync for this change now?',
      'removed',
    );
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD020'), 'Expected AD020');
  }, failures);

  _runCase('fails when GOLDEN_PRINCIPLES missing', () {
    final String root = _fixtureRoot();
    _removePath(root, 'docs/assistant/GOLDEN_PRINCIPLES.md');
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD019') || _hasRule(issues, 'AD001'),
        'Expected AD019 or AD001');
  }, failures);

  _runCase('fails when PLANS scaffold missing', () {
    final String root = _fixtureRoot();
    _removePath(root, 'docs/assistant/exec_plans/PLANS.md');
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD019') || _hasRule(issues, 'AD001'),
        'Expected AD019 or AD001');
  }, failures);

  _runCase('fails when Approval Gates heading missing', () {
    final String root = _fixtureRoot();
    _replaceInFile(root, 'agent.md', '## Approval Gates', '## Gate');
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD020'), 'Expected AD020');
  }, failures);

  _runCase('fails when worktree guidance removed', () {
    final String root = _fixtureRoot();
    _replaceInFile(root, 'docs/assistant/workflows/CI_REPO_WORKFLOW.md', 'worktree', 'tree');
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD020'), 'Expected AD020');
  }, failures);

  _runCase('fails when workflow misses Expected Outputs', () {
    final String root = _fixtureRoot();
    _replaceInFile(
      root,
      'docs/assistant/workflows/TRANSLATION_WORKFLOW.md',
      '## Expected Outputs',
      '## Outputs',
    );
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD006') || _hasRule(issues, 'AD005'),
        'Expected AD006 or AD005');
  }, failures);

  _runCase('fails when workflow misses negative routing text', () {
    final String root = _fixtureRoot();
    _replaceInFile(
      root,
      'docs/assistant/workflows/TRANSLATION_WORKFLOW.md',
      "Don't use this workflow when",
      'Do not use this flow when',
    );
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD007'), 'Expected AD007');
  }, failures);

  _runCase('fails when required governance contracts missing', () {
    final String root = _fixtureRoot();
    final Map<String, dynamic> manifest = _readJson(root, 'docs/assistant/manifest.json');
    final Map<String, dynamic> contracts = manifest['contracts'] as Map<String, dynamic>;
    contracts.remove('golden_principles_source_of_truth');
    contracts.remove('execplan_policy');
    contracts.remove('approval_gates_policy');
    contracts.remove('worktree_isolation_policy');
    contracts.remove('doc_gardening_policy');
    _writeJson(root, 'docs/assistant/manifest.json', manifest);
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD018'), 'Expected AD018');
  }, failures);

  _runCase('fails when user guide headings missing', () {
    final String root = _fixtureRoot();
    _replaceInFile(
      root,
      'docs/assistant/features/APP_USER_GUIDE.md',
      '## For Agents: Support Interaction Contract',
      '## Support Contract',
    );
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD025'), 'Expected AD025');
  }, failures);

  _runCase('fails when runbook omits support routing', () {
    final String root = _fixtureRoot();
    _replaceInFile(
      root,
      'agent.md',
      'docs/assistant/features/APP_USER_GUIDE.md',
      'docs/assistant/features/REMOVED.md',
    );
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD026'), 'Expected AD026');
  }, failures);

  _runCase('fails when user guide contracts missing', () {
    final String root = _fixtureRoot();
    final Map<String, dynamic> manifest = _readJson(root, 'docs/assistant/manifest.json');
    final Map<String, dynamic> contracts = manifest['contracts'] as Map<String, dynamic>;
    contracts.remove('user_guides_support_usage_policy');
    contracts.remove('user_guides_canonical_deference_policy');
    contracts.remove('user_guides_update_sync_policy');
    _writeJson(root, 'docs/assistant/manifest.json', manifest);
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD027'), 'Expected AD027');
  }, failures);

  _runCase('fails when docs maintenance omits user-guide sync', () {
    final String root = _fixtureRoot();
    _replaceInFile(
      root,
      'docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md',
      'sync',
      'align',
    );
    _replaceInFile(
      root,
      'docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md',
      'Sync',
      'Align',
    );
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD028'), 'Expected AD028');
  }, failures);

  _runCase('fails when module_flags missing', () {
    final String root = _fixtureRoot();
    final Map<String, dynamic> manifest = _readJson(root, 'docs/assistant/manifest.json');
    manifest.remove('module_flags');
    _writeJson(root, 'docs/assistant/manifest.json', manifest);
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD002') || _hasRule(issues, 'AD029'),
        'Expected AD002 or AD029');
  }, failures);

  _runCase('fails when module-conditioned workflow missing', () {
    final String root = _fixtureRoot();
    final Map<String, dynamic> manifest = _readJson(root, 'docs/assistant/manifest.json');
    final List<dynamic> workflows = manifest['workflows'] as List<dynamic>;
    workflows.removeWhere((dynamic item) =>
        item is Map<String, dynamic> && item['id'] == 'staged_execution_workflow');
    _writeJson(root, 'docs/assistant/manifest.json', manifest);
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD030'), 'Expected AD030');
  }, failures);

  _runCase('fails when module-conditioned contracts missing', () {
    final String root = _fixtureRoot();
    final Map<String, dynamic> manifest = _readJson(root, 'docs/assistant/manifest.json');
    final Map<String, dynamic> contracts = manifest['contracts'] as Map<String, dynamic>;
    contracts.remove('stage_gate_policy');
    contracts.remove('openai_docs_citation_freshness_policy');
    _writeJson(root, 'docs/assistant/manifest.json', manifest);
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD033'), 'Expected AD033');
  }, failures);

  _runCase('fails when workflow misses POSIX commands', () {
    final String root = _fixtureRoot();
    _replaceInFile(
      root,
      'docs/assistant/workflows/TRANSLATION_WORKFLOW.md',
      '```bash',
      '```txt',
    );
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD031'), 'Expected AD031');
  }, failures);

  _runCase('fails when staged workflow token guidance missing', () {
    final String root = _fixtureRoot();
    _replaceInFile(
      root,
      'docs/assistant/workflows/STAGED_EXECUTION_WORKFLOW.md',
      'NEXT_STAGE_X',
      'NEXT TOKEN',
    );
    _replaceInFile(
      root,
      'docs/assistant/workflows/STAGED_EXECUTION_WORKFLOW.md',
      'NEXT_STAGE_2',
      'NEXT TOKEN 2',
    );
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD032'), 'Expected AD032');
  }, failures);

  _runCase('fails when external source registry missing', () {
    final String root = _fixtureRoot();
    _removePath(root, 'docs/assistant/EXTERNAL_SOURCE_REGISTRY.md');
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD001') || _hasRule(issues, 'AD034'),
        'Expected AD001 or AD034');
  }, failures);

  _runCase('fails when source registry includes non-official domain', () {
    final String root = _fixtureRoot();
    _replaceInFile(
      root,
      'docs/assistant/EXTERNAL_SOURCE_REGISTRY.md',
      'https://developers.openai.com/api/reference/resources/responses/methods/create',
      'https://example.com/not-official',
    );
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD035'), 'Expected AD035');
  }, failures);

  _runCase('fails localization scope when glossary contract missing', () {
    final String root = _fixtureRoot();
    final Map<String, dynamic> manifest = _readJson(root, 'docs/assistant/manifest.json');
    final Map<String, dynamic> contracts = manifest['contracts'] as Map<String, dynamic>;
    contracts.remove('localization_glossary_source_of_truth');
    _writeJson(root, 'docs/assistant/manifest.json', manifest);
    final List<validator.ValidationIssue> issues = validator.validateAgentDocs(
      rootPath: root,
      localizationScope: true,
    );
    _expect(_hasRule(issues, 'AD012'), 'Expected AD012');
  }, failures);

  _runCase('fails when workflow doc is not discoverable from index', () {
    final String root = _fixtureRoot();
    _replaceInFile(
      root,
      'docs/assistant/INDEX.md',
      'docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md',
      'docs/assistant/workflows/MISSING_REFERENCE_LOCKED_QT_UI_WORKFLOW.md',
    );
    final List<validator.ValidationIssue> issues =
        validator.validateAgentDocs(rootPath: root);
    _expect(_hasRule(issues, 'AD036'), 'Expected AD036');
  }, failures);

  if (failures.isNotEmpty) {
    stderr.writeln('Agent docs validator tests failed: ${failures.length} case(s).');
    for (final String failure in failures) {
      stderr.writeln(failure);
    }
    exit(1);
  }

  stdout.writeln('All agent docs validator tests passed (29 cases).');
}
