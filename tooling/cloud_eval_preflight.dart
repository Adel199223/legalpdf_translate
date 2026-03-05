import 'dart:convert';
import 'dart:io';

Map<String, dynamic> runCloudEvalPreflight({
  required String rootPath,
  Map<String, String>? environment,
}) {
  final Map<String, String> env = environment ?? Platform.environment;

  final String workflowPath =
      '$rootPath${Platform.pathSeparator}.github${Platform.pathSeparator}workflows${Platform.pathSeparator}python-package.yml';
  final File workflowFile = File(workflowPath);
  final String workflowText = workflowFile.existsSync()
      ? workflowFile.readAsStringSync()
      : '';
  final bool workflowDispatchDetected =
      RegExp(r'\bworkflow_dispatch\b').hasMatch(workflowText);

  final String requiredSecretsRaw =
      (env['CLOUD_EVAL_REQUIRED_SECRETS'] ?? 'OPENAI_API_KEY').trim();
  final List<String> requiredSecrets = requiredSecretsRaw
      .split(',')
      .map((String part) => part.trim())
      .where((String part) => part.isNotEmpty)
      .toList();

  final Map<String, bool> secretNamePresence = <String, bool>{};
  for (final String name in requiredSecrets) {
    secretNamePresence[name] = (env[name] ?? '').trim().isNotEmpty;
  }

  final String heavyRunReason =
      (env['CLOUD_HEAVY_RUN_TRIGGER_REASON'] ?? '').trim();
  final bool preflightReady = workflowDispatchDetected && requiredSecrets.isNotEmpty;
  final String cloudPreflightStatus = preflightReady ? 'ready' : 'unavailable';

  return <String, dynamic>{
    'execution_venue_selected': 'cloud',
    'heavy_run_trigger_reason': heavyRunReason.isEmpty ? 'n/a' : heavyRunReason,
    'cloud_preflight_status': cloudPreflightStatus,
    'cloud_failure_semantics': cloudPreflightStatus == 'ready' ? 'n/a' : 'unavailable',
    'cloud_to_local_fallback_used': false,
    'manual_acceptance_status': 'pending',
    'auto_apply_block_enforced': true,
    'workflow_dispatch_detected': workflowDispatchDetected,
    'required_secret_env_names': requiredSecrets,
    'secret_name_presence': secretNamePresence,
    'failure_semantics': <String, String>{
      'unavailable': 'cloud environment/tooling/preflight prerequisites are not satisfied',
      'failed': 'cloud workflow ran but logic/assertion checks failed',
      'n/a': 'no cloud failure classification needed for this packet',
    },
  };
}

int _runCli() {
  final Map<String, dynamic> payload = runCloudEvalPreflight(
    rootPath: Directory.current.path,
  );
  stdout.writeln(const JsonEncoder.withIndent('  ').convert(payload));
  return 0;
}

void main(List<String> args) {
  exit(_runCli());
}
