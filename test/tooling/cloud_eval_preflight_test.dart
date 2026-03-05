import 'dart:io';

import '../../tooling/cloud_eval_preflight.dart' as cloud;

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

String _fixtureRoot({required bool includeWorkflowDispatch}) {
  final Directory fixture =
      Directory.systemTemp.createTempSync('cloud_eval_preflight_fixture_');
  final Directory workflowDir = Directory(
      '${fixture.path}${Platform.pathSeparator}.github${Platform.pathSeparator}workflows');
  workflowDir.createSync(recursive: true);
  final File workflow =
      File('${workflowDir.path}${Platform.pathSeparator}python-package.yml');
  workflow.writeAsStringSync(includeWorkflowDispatch
      ? 'name: CI\non:\n  push:\n  workflow_dispatch:\n'
      : 'name: CI\non:\n  push:\n');
  return fixture.path;
}

void main() {
  final List<String> failures = <String>[];

  _runCase('ready when workflow_dispatch exists', () {
    final String root = _fixtureRoot(includeWorkflowDispatch: true);
    final Map<String, dynamic> result = cloud.runCloudEvalPreflight(
      rootPath: root,
      environment: <String, String>{
        'CLOUD_EVAL_REQUIRED_SECRETS': 'OPENAI_API_KEY,GH_TOKEN',
      },
    );
    _expect(result['workflow_dispatch_detected'] == true,
        'Expected workflow_dispatch_detected=true');
    _expect(result['cloud_preflight_status'] == 'ready',
        'Expected cloud_preflight_status=ready');
    _expect(result['execution_venue_selected'] == 'cloud',
        'Expected execution_venue_selected=cloud');
  }, failures);

  _runCase('unavailable without workflow_dispatch', () {
    final String root = _fixtureRoot(includeWorkflowDispatch: false);
    final Map<String, dynamic> result = cloud.runCloudEvalPreflight(
      rootPath: root,
      environment: <String, String>{
        'CLOUD_EVAL_REQUIRED_SECRETS': 'OPENAI_API_KEY',
      },
    );
    _expect(result['workflow_dispatch_detected'] == false,
        'Expected workflow_dispatch_detected=false');
    _expect(result['cloud_preflight_status'] == 'unavailable',
        'Expected cloud_preflight_status=unavailable');
    _expect(result['cloud_failure_semantics'] == 'unavailable',
        'Expected cloud_failure_semantics=unavailable');
  }, failures);

  _runCase('unavailable with empty required secret names list', () {
    final String root = _fixtureRoot(includeWorkflowDispatch: true);
    final Map<String, dynamic> result = cloud.runCloudEvalPreflight(
      rootPath: root,
      environment: <String, String>{
        'CLOUD_EVAL_REQUIRED_SECRETS': ',',
      },
    );
    _expect(result['cloud_preflight_status'] == 'unavailable',
        'Expected cloud_preflight_status=unavailable');
  }, failures);

  if (failures.isNotEmpty) {
    stderr.writeln('Cloud eval preflight tests failed: ${failures.length} case(s).');
    for (final String failure in failures) {
      stderr.writeln(failure);
    }
    exit(1);
  }

  stdout.writeln('All cloud eval preflight tests passed (3 cases).');
}
