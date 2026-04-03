function normalizePath(value) {
  return String(value || "")
    .trim()
    .replace(/\\/g, "/")
    .replace(/\/+$/g, "")
    .toLowerCase();
}

function shortBuildLabel(branch, buildSha) {
  if (branch && buildSha) {
    return `${branch}@${buildSha}`;
  }
  return branch || buildSha || "unknown build";
}

export function deriveGmailLiveRuntimeGuard({
  runtime = {},
  buildIdentity = {},
  acknowledged = false,
} = {}) {
  const liveData = Boolean(runtime.live_data);
  const isCanonical = buildIdentity && buildIdentity.is_canonical === false ? false : true;
  const active = liveData && !isCanonical;
  const reasons = Array.isArray(buildIdentity?.reasons)
    ? buildIdentity.reasons
      .map((item) => String(item || "").trim())
      .filter(Boolean)
    : [];
  const branch = String(buildIdentity?.branch || runtime.build_branch || "").trim();
  const buildSha = String(buildIdentity?.head_sha || runtime.build_sha || "").trim();
  const canonicalBranch = String(buildIdentity?.canonical_branch || "").trim() || "main";
  const worktreePath = String(buildIdentity?.worktree_path || "").trim();
  const canonicalWorktreePath = String(buildIdentity?.canonical_worktree_path || "").trim();
  const sameWorktree = normalizePath(worktreePath) !== "" && normalizePath(worktreePath) === normalizePath(canonicalWorktreePath);
  const buildLabel = shortBuildLabel(branch, buildSha);
  const details = sameWorktree
    ? [
      `This live Gmail workspace is running from ${buildLabel} in the canonical worktree path.`,
      `Close this browser app, switch ${canonicalWorktreePath || "the canonical worktree"} back to ${canonicalBranch}, and relaunch the browser app before retrying Preview or Prepare.`,
    ]
    : [
      `This live Gmail workspace is running from ${buildLabel} instead of the canonical ${canonicalBranch} runtime.`,
      `Close this browser app and relaunch from ${canonicalWorktreePath || "the canonical worktree"} before retrying Preview or Prepare.`,
    ];
  if (reasons.length) {
    details.push(`Why this build is noncanonical: ${reasons.join(" | ")}`);
  }
  return {
    active,
    blocked: active && !acknowledged,
    acknowledged: Boolean(acknowledged),
    branch,
    buildSha,
    canonicalBranch,
    worktreePath,
    canonicalWorktreePath,
    reasons,
    buildLabel,
    title: "Live Gmail is running from a noncanonical build",
    message: sameWorktree
      ? `Preview and Prepare are paused because the live browser app is running from ${buildLabel} in the canonical worktree path instead of ${canonicalBranch}.`
      : `Preview and Prepare are paused because the live browser app is running from ${buildLabel} instead of the canonical ${canonicalBranch} runtime.`,
    primaryLabel: "Restart from Canonical Main",
    secondaryLabel: "Continue Anyway",
    details,
  };
}

