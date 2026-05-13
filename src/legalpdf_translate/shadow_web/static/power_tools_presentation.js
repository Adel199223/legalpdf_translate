function prettyJson(value) {
  return JSON.stringify(value ?? {}, null, 2);
}

function joinLines(values) {
  return (Array.isArray(values) ? values : []).join("\n");
}

function mergeLatestRunDirs(powerTools = {}) {
  const diagnostics = powerTools?.diagnostics?.latest_run_dirs || [];
  const builder = powerTools?.glossary_builder?.latest_run_dirs || [];
  const seen = new Set();
  const output = [];
  for (const item of [...diagnostics, ...builder]) {
    const runDir = String(item?.run_dir || "").trim();
    if (!runDir || seen.has(runDir.toLowerCase())) {
      continue;
    }
    seen.add(runDir.toLowerCase());
    output.push(item);
  }
  return output;
}

function buildGlossaryForm(glossary = {}) {
  return {
    projectPath: glossary.project_glossary_path || "",
    personalJson: prettyJson(glossary.personal_glossaries_by_lang || {}),
    projectJson: prettyJson(glossary.project_glossaries_by_lang || {}),
    enabledTiersJson: prettyJson(glossary.enabled_tiers_by_target_lang || {}),
    promptAddendumJson: prettyJson(glossary.prompt_addendum_by_lang || {}),
  };
}

function buildBuilderDefaults(builder = {}) {
  const defaults = builder.defaults || {};
  const builderDefaults = {
    sourceMode: defaults.source_mode || "run_folders",
    targetLang: defaults.target_lang || "EN",
    mode: defaults.mode || "full_text",
    lemmaEffort: defaults.lemma_effort || "high",
    lemmaEnabled: defaults.lemma_enabled ?? null,
    runDirs: joinLines(defaults.run_dirs),
    pdfPaths: joinLines(defaults.pdf_paths),
  };
  if (builder.last_result?.suggestions) {
    builderDefaults.approvedJson = prettyJson(builder.last_result.suggestions);
  }
  return builderDefaults;
}

function buildCalibrationDefaults(calibration = {}) {
  const defaults = calibration.defaults || {};
  return {
    pdf_path: defaults.pdf_path || "",
    output_dir: defaults.output_dir || "",
    target_lang: defaults.target_lang || "EN",
    sample_pages: defaults.sample_pages ?? 5,
    user_seed: defaults.user_seed || "",
    excerpt_max_chars: defaults.excerpt_max_chars ?? 200,
    include_excerpts: defaults.include_excerpts ?? null,
  };
}

function buildStatus(latestRunDirs = []) {
  const latestCount = latestRunDirs.length;
  return {
    tone: "ok",
    message: latestCount > 0
      ? `Advanced glossary, quality-check, and troubleshooting tools are ready. ${latestCount} recent run folder(s) are available.`
      : "Advanced glossary, quality-check, and troubleshooting tools are ready.",
  };
}

function buildDiagnostics(powerTools = {}, latestRunDirs = []) {
  const diagnostics = powerTools.diagnostics || {};
  const latestWindowTrace = diagnostics.latest_window_trace || {};
  return {
    value: {
      outputs_root: diagnostics.outputs_root || "",
      runtime_metadata_path: diagnostics.runtime_metadata_path || "",
      latest_run_dirs: latestRunDirs,
      latest_window_trace: latestWindowTrace,
    },
    hint: latestWindowTrace.launch_session_id
      ? `Latest startup trace session: ${latestWindowTrace.launch_session_id}`
      : "Troubleshooting bundle, run report, and startup trace defaults appear here.",
    open: false,
  };
}

export function buildPowerToolsBootstrapPresentation(powerTools = {}) {
  const source = powerTools || {};
  const latestRunDirs = mergeLatestRunDirs(source);
  return {
    glossaryForm: buildGlossaryForm(source.glossary || {}),
    builderDefaults: buildBuilderDefaults(source.glossary_builder || {}),
    calibrationDefaults: buildCalibrationDefaults(source.calibration || {}),
    latestRunDirs,
    status: buildStatus(latestRunDirs),
    diagnostics: buildDiagnostics(source, latestRunDirs),
  };
}

function normalizedPayload(payload = {}) {
  return payload?.normalized_payload || {};
}

function buildActionPresentation({
  payload = {},
  diagnosticsSlot = "power-tools-diagnostics",
  message = "",
  hint = "",
  resultFields = {},
} = {}) {
  const diagnosticsValue = payload || { normalized_payload: {} };
  return {
    status: {
      slot: "power-tools",
      tone: "ok",
      message,
    },
    diagnostics: {
      slot: diagnosticsSlot,
      value: diagnosticsValue,
      hint,
      open: false,
    },
    resultFields: resultFields || {},
  };
}

function resultDirectoryFromPath(value) {
  const path = String(value || "").trim();
  if (!path) {
    return "";
  }
  return path.replace(/[\\/][^\\/]+$/, "");
}

export function buildPowerToolsGlossarySavePresentation(payload = {}) {
  return buildActionPresentation({
    payload,
    diagnosticsSlot: "power-tools-glossary",
    message: "Glossary setup saved.",
    hint: "Advanced glossary data was saved to browser settings and project glossary storage.",
  });
}

export function buildPowerToolsGlossaryExportPresentation(payload = {}) {
  const normalized = normalizedPayload(payload);
  return buildActionPresentation({
    payload,
    diagnosticsSlot: "power-tools-glossary",
    message: "Glossary markdown exported.",
    hint: normalized.markdown_path || "Glossary markdown export completed.",
  });
}

export function buildPowerToolsBuilderRunPresentation(payload = {}) {
  const normalized = normalizedPayload(payload);
  const resultFields = {};
  if (normalized.suggestions) {
    resultFields.approvedJson = prettyJson(normalized.suggestions);
  }
  return buildActionPresentation({
    payload,
    diagnosticsSlot: "power-tools-builder",
    message: `Built glossary suggestions from ${normalized.pages_scanned ?? 0} page(s) across ${normalized.sources_processed ?? 0} source(s).`,
    hint: normalized.artifact_dir || "Glossary builder run completed.",
    resultFields,
  });
}

export function buildPowerToolsBuilderApplyPresentation(payload = {}) {
  return buildActionPresentation({
    payload,
    diagnosticsSlot: "power-tools-builder",
    message: "Glossary suggestions applied.",
    hint: "Selected glossary suggestions were merged into personal and project glossaries.",
  });
}

export function buildPowerToolsCalibrationRunPresentation(payload = {}) {
  const normalized = normalizedPayload(payload);
  const diagnosticsRunDir = resultDirectoryFromPath(normalized.report_json_path);
  return buildActionPresentation({
    payload,
    diagnosticsSlot: "power-tools-calibration",
    message: "Quality check completed.",
    hint: normalized.report_md_path || "Quality-check files were generated.",
    resultFields: diagnosticsRunDir ? { diagnosticsRunDir } : {},
  });
}

export function buildPowerToolsDebugBundlePresentation(payload = {}) {
  const normalized = normalizedPayload(payload);
  return buildActionPresentation({
    payload,
    message: "Troubleshooting bundle created.",
    hint: normalized.bundle_path || "Troubleshooting bundle created.",
  });
}

export function buildPowerToolsRunReportPresentation(payload = {}) {
  const normalized = normalizedPayload(payload);
  return buildActionPresentation({
    payload,
    message: "Run report generated.",
    hint: normalized.report_path || "Run report generated.",
  });
}

export function buildPowerToolsArmWindowTracePresentation(payload = {}) {
  const normalized = normalizedPayload(payload);
  return buildActionPresentation({
    payload,
    message: "The next Gmail startup click will capture a troubleshooting window trace.",
    hint: normalized.arm_path || "The next Gmail startup click will capture a troubleshooting window trace.",
  });
}
