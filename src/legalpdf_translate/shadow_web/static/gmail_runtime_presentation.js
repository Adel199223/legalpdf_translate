function objectValue(value) {
  return value && typeof value === "object" ? value : {};
}

function trimmed(value) {
  return String(value || "").trim();
}

function identitySource({ runtime = {}, shellBuildIdentity = null, bootstrap = {} } = {}) {
  const runtimeIdentity = runtime.build_identity;
  if (runtimeIdentity && typeof runtimeIdentity === "object") {
    return runtimeIdentity;
  }
  if (shellBuildIdentity && typeof shellBuildIdentity === "object") {
    return shellBuildIdentity;
  }
  const bootstrapIdentity = bootstrap.buildIdentity;
  if (bootstrapIdentity && typeof bootstrapIdentity === "object") {
    return bootstrapIdentity;
  }
  return {};
}

export function buildGmailRuntimePayload({
  runtime = {},
  bootstrap = {},
  runtimeMode = "",
} = {}) {
  const resolvedRuntime = objectValue(runtime);
  const resolvedBootstrap = objectValue(bootstrap);
  return {
    ...resolvedRuntime,
    build_branch: trimmed(resolvedRuntime.build_branch || resolvedBootstrap.buildBranch),
    build_sha: trimmed(resolvedRuntime.build_sha || resolvedBootstrap.buildSha),
    asset_version: trimmed(resolvedRuntime.asset_version || resolvedBootstrap.assetVersion),
    live_data: resolvedRuntime.live_data === true || runtimeMode === "live",
  };
}

export function buildGmailBuildIdentity({
  runtime = {},
  shellBuildIdentity = null,
  bootstrap = {},
} = {}) {
  const resolvedRuntime = objectValue(runtime);
  const identity = identitySource({
    runtime: resolvedRuntime,
    shellBuildIdentity,
    bootstrap: objectValue(bootstrap),
  });
  return {
    ...identity,
    branch: trimmed(identity.branch || resolvedRuntime.build_branch),
    head_sha: trimmed(identity.head_sha || resolvedRuntime.build_sha),
  };
}

export function buildGmailBuildProvenance({
  runtime = {},
  buildIdentity = {},
} = {}) {
  const resolvedRuntime = objectValue(runtime);
  const resolvedIdentity = objectValue(buildIdentity);
  const branch = trimmed(resolvedIdentity.branch || resolvedRuntime.build_branch);
  const buildSha = trimmed(resolvedIdentity.head_sha || resolvedRuntime.build_sha);
  const assetVersion = trimmed(resolvedRuntime.asset_version);
  const pieces = [];
  if (branch && buildSha) {
    pieces.push(`${branch}@${buildSha}`);
  } else if (buildSha || branch) {
    pieces.push(buildSha || branch);
  }
  if (assetVersion) {
    pieces.push(`assets ${assetVersion}`);
  }
  return {
    branch,
    buildSha,
    assetVersion,
    label: pieces.join(" | ") || "Unavailable",
  };
}

export function buildGmailRuntimeGuardSessionKey({
  runtimeMode = "",
  workspaceId = "",
  buildIdentity = {},
} = {}) {
  const resolvedIdentity = objectValue(buildIdentity);
  const mode = trimmed(runtimeMode) || "unknown-mode";
  const workspace = trimmed(workspaceId) || "unknown-workspace";
  const branch = trimmed(resolvedIdentity.branch) || "unknown-branch";
  const buildSha = trimmed(resolvedIdentity.head_sha) || "unknown-sha";
  return `legalpdf.gmail.noncanonical.${mode}.${workspace}.${branch}.${buildSha}`;
}

export function buildGmailRuntimeGuardDiagnostics({
  guard = {},
  operation = "",
  buildIdentity = {},
  runtime = {},
} = {}) {
  const resolvedGuard = objectValue(guard);
  const details = Array.isArray(resolvedGuard.details) ? resolvedGuard.details : [];
  return {
    error: "noncanonical_live_runtime",
    message: trimmed(resolvedGuard.message),
    operation: trimmed(operation),
    build_label: trimmed(resolvedGuard.buildLabel),
    build_identity: objectValue(buildIdentity),
    runtime: objectValue(runtime),
    details,
    acknowledged: Boolean(resolvedGuard.acknowledged),
  };
}
