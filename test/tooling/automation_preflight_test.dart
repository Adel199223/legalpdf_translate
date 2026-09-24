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
    return preflight.CommandResult(exitCode: 1, stdout: '', stderr: 'broken');
  }
  if (key == 'npx --yes --package @playwright/cli playwright-cli --version') {
    return preflight.CommandResult(exitCode: 0, stdout: '1.59.0-alpha\n', stderr: '');
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
    return preflight.CommandResult(exitCode: 1, stdout: '', stderr: 'broken');
  }
  if (key == 'npx --yes --package @playwright/cli playwright-cli --version') {
    return preflight.CommandResult(exitCode: 0, stdout: '1.59.0-alpha\n', stderr: '');
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
  if (key == 'npm --version' || key == 'npx --version') {
    return preflight.CommandResult(exitCode: 0, stdout: 'ok\n', stderr: '');
  }
  if (key == 'npx playwright --version' || key == 'npx --yes --package @playwright/cli playwright-cli --version') {
    return preflight.CommandResult(exitCode: 0, stdout: 'ok\n', stderr: '');
  }
  if (command.first == 'which' || command.first == 'where') {
    return preflight.CommandResult(exitCode: 1, stdout: '', stderr: '');
  }
  return preflight.CommandResult(exitCode: 1, stdout: '', stderr: 'unsupported: $key');
}

preflight.CommandResult _runnerWindowsEdgeFallback(List<String> command) {
  final String key = command.join(' ');
  if (key == 'node --version' || key == 'npm --version' || key == 'npx --version') {
    return preflight.CommandResult(exitCode: 0, stdout: 'ok\n', stderr: '');
  }
  if (key == 'npx playwright --version') {
    return preflight.CommandResult(exitCode: 1, stdout: '', stderr: 'broken');
  }
  if (key == 'npx --yes --package @playwright/cli playwright-cli --version') {
    return preflight.CommandResult(exitCode: 0, stdout: '1.59.0-alpha\n', stderr: '');
  }
  if (key == r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe --version') {
    return preflight.CommandResult(exitCode: 0, stdout: '', stderr: '');
  }
  if (key ==
      "powershell -NoProfile -Command (Get-Item 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe').VersionInfo.ProductVersion") {
    return preflight.CommandResult(exitCode: 0, stdout: '136.0.3240.92\n', stderr: '');
  }
  if (command.first == 'which' || command.first == 'where') {
    return preflight.CommandResult(exitCode: 1, stdout: '', stderr: '');
  }
  return preflight.CommandResult(exitCode: 1, stdout: '', stderr: 'unsupported: $key');
}

preflight.CommandResult _runnerWindowsEdgeSessionMessage(List<String> command) {
  final String key = command.join(' ');
  if (key == 'node --version' || key == 'npm --version' || key == 'npx --version') {
    return preflight.CommandResult(exitCode: 0, stdout: 'ok\n', stderr: '');
  }
  if (key == 'npx playwright --version') {
    return preflight.CommandResult(exitCode: 0, stdout: 'Version 1.59.0\n', stderr: '');
  }
  if (command.length >= 2 && (command.first == 'which' || command.first == 'where')) {
    if (command[1] == 'msedge') {
      return preflight.CommandResult(
        exitCode: 0,
        stdout: r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe' '\n',
        stderr: '',
      );
    }
    return preflight.CommandResult(exitCode: 1, stdout: '', stderr: '');
  }
  if (key == r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe --version') {
    return preflight.CommandResult(
      exitCode: 0,
      stdout: 'Opening in existing browser session.\n',
      stderr: '',
    );
  }
  if (key ==
      "powershell -NoProfile -Command (Get-Item 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe').VersionInfo.ProductVersion") {
    return preflight.CommandResult(exitCode: 0, stdout: '136.0.3240.92\n', stderr: '');
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
      environment: <String, String>{
        'AUTOMATION_PREFLIGHT_DISABLE_WINDOWS_BROWSER_FALLBACK': '1',
      },
    );
    _expect(result['preferred_host_status'] == 'available', 'Expected available host status');
    _expect(result['automation_browser_source'] == 'playwright_managed',
        'Expected playwright_managed browser source');
    _expect(result['toolchain']['playwright_probe_source'] == 'playwright_cli_wrapper',
        'Expected playwright CLI wrapper probe source');
  }, failures);

  _runCase('detects standard Windows Edge install path when browser is not on PATH', () {
    final Map<String, dynamic> result = preflight.runAutomationPreflight(
      runner: _runnerWindowsEdgeFallback,
      environment: <String, String>{
        'AUTOMATION_PREFLIGHT_ASSUME_WINDOWS': '1',
        'LOCALAPPDATA': r'C:\Users\FA507\AppData\Local',
      },
    );
    _expect(result['preferred_host_status'] == 'available', 'Expected available host status');
    _expect(result['automation_browser_source'] == 'system', 'Expected system browser source');
    _expect(
      result['automation_browser_binary'] == r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
      'Expected standard Edge fallback path',
    );
    _expect(
      result['automation_browser_version'] == '136.0.3240.92',
      'Expected Windows file-version fallback',
    );
  }, failures);

  _runCase('reads Windows browser file version without opening its session', () {
    final Map<String, dynamic> result = preflight.runAutomationPreflight(
      runner: _runnerWindowsEdgeSessionMessage,
      environment: <String, String>{
        'AUTOMATION_PREFLIGHT_ASSUME_WINDOWS': '1',
      },
    );
    _expect(result['preferred_host_status'] == 'available', 'Expected available host status');
    _expect(
      result['automation_browser_version'] == '136.0.3240.92',
      'Expected Windows file-version fallback when --version reports session text',
    );
  }, failures);

  for (final String route in <String>['environment', 'path', 'fallback']) {
    _runCase('Windows $route discovery never executes the browser', () {
      final List<List<String>> commands = <List<String>>[];
      preflight.CommandResult runner(List<String> command) {
        commands.add(List<String>.of(command));
        if (command.first.toLowerCase().endsWith('msedge.exe')) {
          throw _CaseFailure('Version inspection attempted to launch Edge');
        }
        return route == 'path'
            ? _runnerWindowsEdgeSessionMessage(command)
            : _runnerWindowsEdgeFallback(command);
      }

      final Map<String, dynamic> result = preflight.runAutomationPreflight(
        runner: runner,
        environment: <String, String>{
          'AUTOMATION_PREFLIGHT_ASSUME_WINDOWS': '1',
          if (route == 'environment')
            'AUTOMATION_BROWSER_BINARY':
                r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        },
      );
      _expect(result['automation_browser_version'] == '136.0.3240.92',
          'Expected actual file-version metadata');
      _expect(commands.where((List<String> command) => command.first == 'powershell').length == 1,
          'Expected one metadata read');
    }, failures);
  }

  _runCase('missing Windows version metadata does not launch a browser fallback', () {
    preflight.CommandResult runner(List<String> command) {
      if (command.first.toLowerCase().endsWith('msedge.exe')) {
        throw _CaseFailure('Missing metadata attempted to launch Edge');
      }
      if (command.first == 'powershell') {
        return preflight.CommandResult(exitCode: 1, stdout: '', stderr: 'unavailable');
      }
      return _runnerWindowsEdgeFallback(command);
    }

    final Map<String, dynamic> result = preflight.runAutomationPreflight(
      runner: runner,
      environment: <String, String>{'AUTOMATION_PREFLIGHT_ASSUME_WINDOWS': '1'},
    );
    _expect(result['automation_browser_version'] == '',
        'Unavailable metadata must remain unknown');
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

  stdout.writeln('All automation preflight tests passed (9 cases).');
}
