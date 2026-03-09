import 'dart:convert';
import 'dart:io';

typedef CommandRunner = CommandResult Function(List<String> command);

class CommandResult {
  CommandResult({
    required this.exitCode,
    required this.stdout,
    required this.stderr,
  });

  final int exitCode;
  final String stdout;
  final String stderr;
}

class _ToolCheck {
  _ToolCheck({required this.available, required this.version});

  final bool available;
  final String version;
}

CommandResult _defaultRunner(List<String> command) {
  if (command.isEmpty) {
    return CommandResult(exitCode: 1, stdout: '', stderr: 'empty command');
  }
  final ProcessResult result = Process.runSync(
    command.first,
    command.sublist(1),
    runInShell: true,
  );
  return CommandResult(
    exitCode: result.exitCode,
    stdout: (result.stdout ?? '').toString(),
    stderr: (result.stderr ?? '').toString(),
  );
}

String _firstLine(String text) {
  return text
      .split(RegExp(r'\r?\n'))
      .map((String line) => line.trim())
      .firstWhere((String line) => line.isNotEmpty, orElse: () => '');
}

String _resolveOnPath(String command, CommandRunner runner) {
  final List<String> probe = Platform.isWindows
      ? <String>['where', command]
      : <String>['which', command];
  final CommandResult result = runner(probe);
  if (result.exitCode != 0) {
    return '';
  }
  return _firstLine(result.stdout);
}

_ToolCheck _checkToolVersion(String command, List<String> args, CommandRunner runner) {
  final CommandResult result = runner(<String>[command, ...args]);
  if (result.exitCode != 0) {
    return _ToolCheck(available: false, version: '');
  }
  final String line = _firstLine('${result.stdout}\n${result.stderr}');
  return _ToolCheck(available: true, version: line);
}

Map<String, dynamic> runAutomationPreflight({
  CommandRunner? runner,
  Map<String, String>? environment,
}) {
  final CommandRunner run = runner ?? _defaultRunner;
  final Map<String, String> env = environment ?? Platform.environment;

  final _ToolCheck node = _checkToolVersion('node', <String>['--version'], run);
  final _ToolCheck npm = _checkToolVersion('npm', <String>['--version'], run);
  final _ToolCheck npx = _checkToolVersion('npx', <String>['--version'], run);
  final _ToolCheck playwright = _checkToolVersion('npx', <String>['playwright', '--version'], run);

  String browserBinary = '';
  String browserVersion = '';
  String browserSource = 'system';

  final String envBinary = (env['AUTOMATION_BROWSER_BINARY'] ?? '').trim();
  if (envBinary.isNotEmpty) {
    browserBinary = envBinary;
    final _ToolCheck bin = _checkToolVersion(envBinary, <String>['--version'], run);
    browserVersion = bin.version;
    browserSource = 'system';
  } else {
    const List<String> candidates = <String>[
      'google-chrome',
      'chrome',
      'chromium',
      'chromium-browser',
      'msedge',
      'microsoft-edge',
      'chrome.exe',
      'msedge.exe',
    ];
    for (final String candidate in candidates) {
      final String resolved = _resolveOnPath(candidate, run);
      if (resolved.isEmpty) {
        continue;
      }
      browserBinary = resolved;
      final _ToolCheck bin = _checkToolVersion(resolved, <String>['--version'], run);
      browserVersion = bin.version;
      browserSource = 'system';
      break;
    }
  }

  if (browserBinary.isEmpty && playwright.available) {
    browserBinary = 'playwright:chromium';
    browserVersion = playwright.version;
    browserSource = 'playwright_managed';
  }

  final bool toolchainReady = node.available && npm.available && npx.available;
  final bool preferredHostAvailable = toolchainReady && playwright.available;

  return <String, dynamic>{
    'automation_host_selected': 'local',
    'preferred_host_status': preferredHostAvailable ? 'available' : 'unavailable',
    'fallback_host_status': 'n/a',
    'toolchain': <String, dynamic>{
      'node_available': node.available,
      'node_version': node.version,
      'npm_available': npm.available,
      'npm_version': npm.version,
      'npx_available': npx.available,
      'npx_version': npx.version,
      'playwright_available': playwright.available,
      'playwright_version': playwright.version,
    },
    'automation_browser_binary': browserBinary,
    'automation_browser_version': browserVersion,
    'automation_browser_source': browserSource,
    'stale_copy_audit': <String>[],
    'manual_operator_checks_status': 'pending',
    'failure_semantics': <String, String>{
      'unavailable': 'host/toolchain cannot execute automation preflight or flow',
      'failed': 'automation executed but flow assertions failed',
    },
  };
}

int _runCli() {
  final Map<String, dynamic> payload = runAutomationPreflight();
  stdout.writeln(const JsonEncoder.withIndent('  ').convert(payload));
  return 0;
}

void main(List<String> args) {
  exit(_runCli());
}
