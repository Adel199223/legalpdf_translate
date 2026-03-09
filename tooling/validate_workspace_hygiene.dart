import 'dart:convert';
import 'dart:io';

class HygieneIssue {
  HygieneIssue(this.ruleId, this.message);

  final String ruleId;
  final String message;

  @override
  String toString() => '$ruleId: $message';
}

const List<String> _requiredVscodePatterns = <String>[
  '**/.venv/**',
  '**/__pycache__/**',
  '**/.pytest_cache/**',
  '**/.mypy_cache/**',
  '**/build/**',
  '**/dist/**',
  '**/*_run/**',
];

List<HygieneIssue> validateWorkspaceHygiene({required String rootPath}) {
  final List<HygieneIssue> issues = <HygieneIssue>[];

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

  if (!exists('docs/assistant/workflows/PERFORMANCE_WORKFLOW.md') ||
      !exists('docs/assistant/PERFORMANCE_BASELINES.md')) {
    issues.add(HygieneIssue(
      'WH001',
      'Performance workflow/baselines are missing.',
    ));
  }

  if (!exists('.vscode/settings.json')) {
    issues.add(HygieneIssue(
      'WH002',
      '.vscode/settings.json is missing.',
    ));
    return issues;
  }

  final String baselineText = readText('docs/assistant/PERFORMANCE_BASELINES.md');
  final String baselineLower = baselineText.toLowerCase();
  if (!baselineLower.contains('single source-of-truth') ||
      !baselineLower.contains('do not duplicate exclusion/policy tables')) {
    issues.add(HygieneIssue(
      'WH003',
      'Performance baselines file is missing anti-duplication policy text.',
    ));
  }

  if (!baselineLower.contains('outside workspace root')) {
    issues.add(HygieneIssue(
      'WH004',
      'Performance baselines missing environment-outside-workspace default policy.',
    ));
  }

  final File manifestFile =
      File(_resolvePath(rootPath, 'docs/assistant/manifest.json'));
  if (!manifestFile.existsSync()) {
    issues.add(HygieneIssue('WH005', 'Manifest missing for hygiene validation.'));
  } else {
    try {
      final dynamic decoded = jsonDecode(manifestFile.readAsStringSync());
      if (decoded is! Map<String, dynamic>) {
        issues.add(HygieneIssue('WH005', 'Manifest JSON object expected.'));
      } else {
        final Map<String, dynamic> contracts =
            decoded['contracts'] is Map<String, dynamic>
                ? decoded['contracts'] as Map<String, dynamic>
                : <String, dynamic>{};
        for (final String key in <String>[
          'workspace_performance_source_of_truth',
          'environment_outside_workspace_default_policy',
          'worktree_isolation_policy',
        ]) {
          if (!contracts.containsKey(key)) {
            issues.add(HygieneIssue(
              'WH005',
              'Manifest missing workspace contract key: $key',
            ));
          }
        }
      }
    } catch (error) {
      issues.add(HygieneIssue('WH005', 'Manifest parse failed: $error'));
    }
  }

  final Map<String, dynamic> settings =
      _loadJsonFile(_resolvePath(rootPath, '.vscode/settings.json'), issues);
  final Map<String, dynamic> watcherExclude =
      settings['files.watcherExclude'] is Map<String, dynamic>
          ? settings['files.watcherExclude'] as Map<String, dynamic>
          : <String, dynamic>{};
  final Map<String, dynamic> searchExclude =
      settings['search.exclude'] is Map<String, dynamic>
          ? settings['search.exclude'] as Map<String, dynamic>
          : <String, dynamic>{};

  final List<String> missingWatcher = _requiredVscodePatterns
      .where((String pattern) => watcherExclude[pattern] != true)
      .toList();
  if (missingWatcher.isNotEmpty) {
    issues.add(HygieneIssue(
      'WH006',
      'files.watcherExclude missing required patterns: ${missingWatcher.join(', ')}',
    ));
  }

  final List<String> missingSearch = _requiredVscodePatterns
      .where((String pattern) => searchExclude[pattern] != true)
      .toList();
  if (missingSearch.isNotEmpty) {
    issues.add(HygieneIssue(
      'WH007',
      'search.exclude missing required patterns: ${missingSearch.join(', ')}',
    ));
  }

  final String workflowText =
      readText('docs/assistant/workflows/PERFORMANCE_WORKFLOW.md').toLowerCase();
  if (!workflowText.contains('code --status') ||
      !workflowText.contains("don't use this workflow when") ||
      !workflowText.contains('instead use') ||
      !workflowText.contains('performance_baselines.md')) {
    issues.add(HygieneIssue(
      'WH008',
      'Performance workflow is missing required diagnosis/routing/baseline references.',
    ));
  }

  return issues;
}

Map<String, dynamic> _loadJsonFile(String path, List<HygieneIssue> issues) {
  final File file = File(path);
  if (!file.existsSync()) {
    return <String, dynamic>{};
  }
  try {
    final dynamic decoded = jsonDecode(file.readAsStringSync());
    if (decoded is Map<String, dynamic>) {
      return decoded;
    }
    issues.add(HygieneIssue('WH009', 'Expected JSON object at $path.'));
    return <String, dynamic>{};
  } catch (error) {
    issues.add(HygieneIssue('WH009', 'JSON parse failed at $path: $error'));
    return <String, dynamic>{};
  }
}

String _resolvePath(String rootPath, String relPath) {
  final String normalized = relPath.replaceAll('/', Platform.pathSeparator);
  return '$rootPath${Platform.pathSeparator}$normalized';
}

int _runCli() {
  final List<HygieneIssue> issues =
      validateWorkspaceHygiene(rootPath: Directory.current.path);
  if (issues.isEmpty) {
    stdout.writeln('PASS: workspace hygiene validation succeeded.');
    return 0;
  }

  stdout.writeln('FAIL: ${issues.length} workspace hygiene issue(s).');
  for (final HygieneIssue issue in issues) {
    stdout.writeln(issue.toString());
  }
  return 1;
}

void main(List<String> args) {
  exit(_runCli());
}
