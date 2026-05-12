export const GMAIL_REFRESH_POLICY_DEFAULTS = {
  autoRefreshDelayMs: 220,
  autoRefreshThrottleMs: 1400,
  passiveRefreshCooldownMs: 6000,
  warmupPollIntervalMs: 900,
  warmupPollTimeoutMs: 15000,
};

function numberOrDefault(value, fallback = 0) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function refreshTimings(timings = {}) {
  return {
    autoRefreshDelayMs: numberOrDefault(
      timings.autoRefreshDelayMs,
      GMAIL_REFRESH_POLICY_DEFAULTS.autoRefreshDelayMs,
    ),
    autoRefreshThrottleMs: numberOrDefault(
      timings.autoRefreshThrottleMs,
      GMAIL_REFRESH_POLICY_DEFAULTS.autoRefreshThrottleMs,
    ),
    passiveRefreshCooldownMs: numberOrDefault(
      timings.passiveRefreshCooldownMs,
      GMAIL_REFRESH_POLICY_DEFAULTS.passiveRefreshCooldownMs,
    ),
    warmupPollIntervalMs: numberOrDefault(
      timings.warmupPollIntervalMs,
      GMAIL_REFRESH_POLICY_DEFAULTS.warmupPollIntervalMs,
    ),
    warmupPollTimeoutMs: numberOrDefault(
      timings.warmupPollTimeoutMs,
      GMAIL_REFRESH_POLICY_DEFAULTS.warmupPollTimeoutMs,
    ),
  };
}

function stoppedWarmupDecision() {
  return { action: "stop", delayMs: 0, warmupPollUntil: 0 };
}

function passiveDecision(action, { delayMs = 0, lastPassiveRefreshAt = 0, replace = false } = {}) {
  return {
    action,
    delayMs,
    lastPassiveRefreshAt,
    replace,
  };
}

export function isGmailWarmupPendingStatus(value) {
  const normalized = String(value ?? "").trim().toLowerCase();
  return normalized === "warming" || normalized === "delayed";
}

export function buildGmailWarmupPollingDecision(options = {}) {
  const {
    activeView = "",
    needsWarmupPolling = false,
    warmupPollUntil = 0,
    lastRefreshAt = 0,
    now = 0,
    timings = {},
  } = options || {};
  if (activeView !== "gmail-intake" || !needsWarmupPolling) {
    return stoppedWarmupDecision();
  }

  const policy = refreshTimings(timings);
  const currentTime = numberOrDefault(now, 0);
  let nextWarmupPollUntil = numberOrDefault(warmupPollUntil, 0);
  if (!nextWarmupPollUntil || nextWarmupPollUntil < currentTime) {
    nextWarmupPollUntil = currentTime + policy.warmupPollTimeoutMs;
  }
  if (currentTime >= nextWarmupPollUntil) {
    return stoppedWarmupDecision();
  }

  const elapsed = currentTime - numberOrDefault(lastRefreshAt, 0);
  const delayMs = Math.max(
    policy.autoRefreshDelayMs,
    policy.warmupPollIntervalMs - Math.max(0, elapsed),
  );
  return {
    action: "schedule",
    delayMs,
    warmupPollUntil: nextWarmupPollUntil,
  };
}

export function buildGmailPassiveRefreshDecision(options = {}) {
  const {
    activeView = "",
    needsWarmupPolling = false,
    stableWorkspaceState = false,
    lastPassiveRefreshAt = 0,
    lastRefreshAt = 0,
    now = 0,
    timings = {},
  } = options || {};
  const previousPassiveRefreshAt = numberOrDefault(lastPassiveRefreshAt, 0);
  if (activeView !== "gmail-intake") {
    return passiveDecision("stop", { lastPassiveRefreshAt: previousPassiveRefreshAt });
  }
  if (needsWarmupPolling) {
    return passiveDecision("warmup", { lastPassiveRefreshAt: previousPassiveRefreshAt });
  }
  if (stableWorkspaceState) {
    return passiveDecision("stop", { lastPassiveRefreshAt: previousPassiveRefreshAt });
  }

  const currentTime = numberOrDefault(now, 0);
  const policy = refreshTimings(timings);
  if (currentTime - previousPassiveRefreshAt < policy.passiveRefreshCooldownMs) {
    return passiveDecision("skip", { lastPassiveRefreshAt: previousPassiveRefreshAt });
  }

  const elapsed = currentTime - numberOrDefault(lastRefreshAt, 0);
  const delayMs = Math.max(policy.autoRefreshDelayMs, policy.autoRefreshThrottleMs - elapsed);
  return passiveDecision("schedule", {
    delayMs,
    lastPassiveRefreshAt: currentTime,
    replace: true,
  });
}
