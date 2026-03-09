import 'dart:io';

import '../../tooling/automation_preflight.dart' as preflight;

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

preflight.CommandResult _runnerWithSystemBrowser(List<String> command) {
  final String key = command.join(' ');
  if (key == 'node --version') {
    return preflight.CommandResult(exitCode: 0, stdout: 'v22.5.0\n', stderr: '');
  }
  if (key == 'npm --version') {
    return preflight.CommandResult(exitCode: 0, stdout: '10.1.0\n', stderr: '');
  }
  if (key == 'npx --version') {
    return preflight.CommandResult(exitCode: 0, stdout: '10.1.0\n', stderr: '');
  }
  if (key == 'npx playwright --version') {
    return preflight.CommandResult(exitCode: 0, stdout: 'Version 1.54.2\n', stderr: '');
  }
  if (command.length >= 2 && (command.first == 'which' || command.first == 'where')) {
    if (command[1] == 'google-chrome') {
      return preflight.CommandResult(
        exitCode: 0,
        stdout: '/usr/bin/google-chrome\n',
        stderr: '',
      );
    }
    return preflight.CommandResult(exitCode: 1, stdout: '', stderr: '');
  }
  if (command.first == '/usr/bin/google-chrome' && command.length == 2 && command[1] == '--version') {
    return preflight.CommandResult(
      exitCode: 0,
      stdout: 'Google Chrome 141.0.7390.65\n',
      stderr: '',
    );
  }
  return preflight.CommandResult(exitCode: 1, stdout: '', stderr: 'unsupported: $key');
}

preflight.CommandResult _runnerPlaywrightOnly(List<String> command) {
  final String key = command.join(' ');
  if (key == 'node --version' || key == 'npm --version' || key == 'npx --version') {
    return preflight.CommandResult(exitCode: 0, stdout: 'ok\n', stderr: '');
  }
  if (key == 'npx playwright --version') {
    return preflight.CommandResult(exitCode: 0, stdout: 'Version 1.54.2\n', stderr: '');
  }
  if (command.first == 'which' || command.first == 'where') {
    return preflight.CommandResult(exitCode: 1, stdout: '', stderr: '');
  }
  return preflight.CommandResult(exitCode: 1, stdout: '', stderr: 'unsupported: $key');
}

preflight.CommandResult _runnerNodeMissing(List<String> command) {
  final String key = command.join(' ');
  if (key == 'node --version') {
    return preflight.CommandResult(exitCode: 1, stdout: '', stderr: 'missing');
  }
  if (key == 'npm --version' || key == 'npx --version' || key == 'npx playwright --version') {
    return preflight.CommandResult(exitCode: 0, stdout: 'ok\n', stderr: '');
  }
  if (command.first == 'which' || command.first == 'where') {
    return preflight.CommandResult(exitCode: 1, stdout: '', stderr: '');
  }
  return preflight.CommandResult(exitCode: 1, stdout: '', stderr: 'unsupported: $key');
}

void main() {
  final List<String> failures = <String>[];

  _runCase('prefers system browser when available', () {
    final Map<String, dynamic> result = preflight.runAutomationPreflight(
      runner: _runnerWithSystemBrowser,
      environment: <String, String>{},
    );
    _expect(result['preferred_host_status'] == 'available', 'Expected available host status');
    _expect(result['automation_browser_source'] == 'system', 'Expected system browser source');
    _expect((result['automation_browser_binary'] ?? '').toString().isNotEmpty,
        'Expected browser binary path');
  }, failures);

  _runCase('falls back to playwright managed browser source', () {
    final Map<String, dynamic> result = preflight.runAutomationPreflight(
      runner: _runnerPlaywrightOnly,
      environment: <String, String>{},
    );
    _expect(result['preferred_host_status'] == 'available', 'Expected available host status');
    _expect(result['automation_browser_source'] == 'playwright_managed',
        'Expected playwright_managed browser source');
  }, failures);

  _runCase('marks host unavailable when toolchain incomplete', () {
    final Map<String, dynamic> result = preflight.runAutomationPreflight(
      runner: _runnerNodeMissing,
      environment: <String, String>{},
    );
    _expect(result['preferred_host_status'] == 'unavailable',
        'Expected unavailable host status');
  }, failures);

  if (failures.isNotEmpty) {
    stderr.writeln('Automation preflight tests failed: ${failures.length} case(s).');
    for (final String failure in failures) {
      stderr.writeln(failure);
    }
    exit(1);
  }

  stdout.writeln('All automation preflight tests passed (3 cases).');
}
