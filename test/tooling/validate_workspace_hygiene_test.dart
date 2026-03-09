import 'dart:io';

import '../../tooling/validate_workspace_hygiene.dart' as hygiene;

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
      Directory.systemTemp.createTempSync('workspace_hygiene_fixture_');

  final List<String> seedPaths = <String>[
    '.vscode/settings.json',
    'docs/assistant/manifest.json',
    'docs/assistant/PERFORMANCE_BASELINES.md',
    'docs/assistant/workflows/PERFORMANCE_WORKFLOW.md',
  ];

  for (final String relPath in seedPaths) {
    final String source = _resolve(repoRoot, relPath);
    final String target = _resolve(fixture.path, relPath);
    final File sourceFile = File(source);
    final File targetFile = File(target);
    targetFile.parent.createSync(recursive: true);
    targetFile.writeAsBytesSync(sourceFile.readAsBytesSync());
  }

  return fixture.path;
}

String _resolve(String root, String relPath) {
  final String normalized = relPath.replaceAll('/', Platform.pathSeparator);
  return '$root${Platform.pathSeparator}$normalized';
}

void _remove(String root, String relPath) {
  final String path = _resolve(root, relPath);
  final FileSystemEntityType type = FileSystemEntity.typeSync(path);
  if (type == FileSystemEntityType.file) {
    File(path).deleteSync();
  }
}

void _replaceInFile(String root, String relPath, String from, String to) {
  final File file = File(_resolve(root, relPath));
  final String text = file.readAsStringSync();
  file.writeAsStringSync(text.replaceAll(from, to));
}

bool _hasRule(List<hygiene.HygieneIssue> issues, String ruleId) {
  return issues.any((hygiene.HygieneIssue issue) => issue.ruleId == ruleId);
}

void main() {
  final List<String> failures = <String>[];

  _runCase('passes for workspace hygiene fixture', () {
    final String root = _fixtureRoot();
    final List<hygiene.HygieneIssue> issues =
        hygiene.validateWorkspaceHygiene(rootPath: root);
    _expect(issues.isEmpty, 'Expected no issues, got: $issues');
  }, failures);

  _runCase('fails when performance workflow missing', () {
    final String root = _fixtureRoot();
    _remove(root, 'docs/assistant/workflows/PERFORMANCE_WORKFLOW.md');
    final List<hygiene.HygieneIssue> issues =
        hygiene.validateWorkspaceHygiene(rootPath: root);
    _expect(_hasRule(issues, 'WH001'), 'Expected WH001');
  }, failures);

  _runCase('fails when performance baselines missing', () {
    final String root = _fixtureRoot();
    _remove(root, 'docs/assistant/PERFORMANCE_BASELINES.md');
    final List<hygiene.HygieneIssue> issues =
        hygiene.validateWorkspaceHygiene(rootPath: root);
    _expect(_hasRule(issues, 'WH001'), 'Expected WH001');
  }, failures);

  _runCase('fails when vscode settings missing', () {
    final String root = _fixtureRoot();
    _remove(root, '.vscode/settings.json');
    final List<hygiene.HygieneIssue> issues =
        hygiene.validateWorkspaceHygiene(rootPath: root);
    _expect(_hasRule(issues, 'WH002'), 'Expected WH002');
  }, failures);

  _runCase('fails when anti-duplication policy removed', () {
    final String root = _fixtureRoot();
    _replaceInFile(
      root,
      'docs/assistant/PERFORMANCE_BASELINES.md',
      'Do not duplicate exclusion/policy tables',
      'Duplicate policy allowed',
    );
    final List<hygiene.HygieneIssue> issues =
        hygiene.validateWorkspaceHygiene(rootPath: root);
    _expect(_hasRule(issues, 'WH003'), 'Expected WH003');
  }, failures);

  _runCase('fails when watcher pattern removed', () {
    final String root = _fixtureRoot();
    _replaceInFile(
      root,
      '.vscode/settings.json',
      '"**/.venv/**": true,',
      '',
    );
    final List<hygiene.HygieneIssue> issues =
        hygiene.validateWorkspaceHygiene(rootPath: root);
    _expect(_hasRule(issues, 'WH006') || _hasRule(issues, 'WH007'),
        'Expected WH006 or WH007');
  }, failures);

  _runCase('fails when diagnosis text removed', () {
    final String root = _fixtureRoot();
    _replaceInFile(
      root,
      'docs/assistant/workflows/PERFORMANCE_WORKFLOW.md',
      'code --status',
      'status command',
    );
    final List<hygiene.HygieneIssue> issues =
        hygiene.validateWorkspaceHygiene(rootPath: root);
    _expect(_hasRule(issues, 'WH008'), 'Expected WH008');
  }, failures);

  if (failures.isNotEmpty) {
    stderr.writeln('Workspace hygiene validator tests failed: ${failures.length} case(s).');
    for (final String failure in failures) {
      stderr.writeln(failure);
    }
    exit(1);
  }

  stdout.writeln('All workspace hygiene validator tests passed (7 cases).');
}
