from __future__ import annotations

import json

from .browser_esm_probe import run_browser_esm_json_probe


def test_power_tools_action_presentation_module_builds_action_results() -> None:
    script = r"""
const presentation = await import(__POWER_TOOLS_PRESENTATION_MODULE_URL__);
const malicious = "<img src=x onerror=alert(1)><script>bad()</script>";

const glossarySavePayload = {
  status: "ok",
  normalized_payload: {
    project_glossary_path: `C:/glossary/${malicious}.json`,
  },
};
const glossaryExportPayload = {
  status: "ok",
  normalized_payload: {
    markdown_path: `C:/exports/${malicious}.md`,
  },
};
const builderRunPayload = {
  status: "ok",
  normalized_payload: {
    pages_scanned: 7,
    sources_processed: 2,
    artifact_dir: `C:/artifacts/${malicious}`,
    suggestions: [
      {
        source: malicious,
        target: "safe-text-only",
      },
    ],
  },
};
const calibrationPayload = {
  status: "ok",
  normalized_payload: {
    report_md_path: `C:/reports/${malicious}.md`,
    report_json_path: String.raw`C:\cases\run-1\quality-report.json`,
  },
};
const debugBundlePayload = {
  status: "ok",
  normalized_payload: {
    bundle_path: `C:/bundles/${malicious}.zip`,
  },
};
const runReportPayload = {
  status: "ok",
  normalized_payload: {
    report_path: `C:/reports/${malicious}.md`,
  },
};
const armTracePayload = {
  status: "ok",
  normalized_payload: {
    arm_path: `C:/trace/${malicious}.json`,
  },
};

const cases = {
  glossarySave: presentation.buildPowerToolsGlossarySavePresentation(glossarySavePayload),
  glossaryExport: presentation.buildPowerToolsGlossaryExportPresentation(glossaryExportPayload),
  glossaryExportFallback: presentation.buildPowerToolsGlossaryExportPresentation({ normalized_payload: {} }),
  builderRun: presentation.buildPowerToolsBuilderRunPresentation(builderRunPayload),
  builderRunFallback: presentation.buildPowerToolsBuilderRunPresentation({ normalized_payload: {} }),
  builderApply: presentation.buildPowerToolsBuilderApplyPresentation({ status: "ok" }),
  calibrationRun: presentation.buildPowerToolsCalibrationRunPresentation(calibrationPayload),
  calibrationRunPosix: presentation.buildPowerToolsCalibrationRunPresentation({
    normalized_payload: {
      report_json_path: "/tmp/legalpdf/run/report.json",
    },
  }),
  calibrationRunFallback: presentation.buildPowerToolsCalibrationRunPresentation({ normalized_payload: {} }),
  debugBundle: presentation.buildPowerToolsDebugBundlePresentation(debugBundlePayload),
  debugBundleFallback: presentation.buildPowerToolsDebugBundlePresentation({ normalized_payload: {} }),
  runReport: presentation.buildPowerToolsRunReportPresentation(runReportPayload),
  runReportFallback: presentation.buildPowerToolsRunReportPresentation({ normalized_payload: {} }),
  armTrace: presentation.buildPowerToolsArmWindowTracePresentation(armTracePayload),
  armTraceFallback: presentation.buildPowerToolsArmWindowTracePresentation({ normalized_payload: {} }),
  nullSafe: presentation.buildPowerToolsBuilderRunPresentation(null),
};

console.log(JSON.stringify({
  exportTypes: {
    glossarySave: typeof presentation.buildPowerToolsGlossarySavePresentation,
    glossaryExport: typeof presentation.buildPowerToolsGlossaryExportPresentation,
    builderRun: typeof presentation.buildPowerToolsBuilderRunPresentation,
    builderApply: typeof presentation.buildPowerToolsBuilderApplyPresentation,
    calibrationRun: typeof presentation.buildPowerToolsCalibrationRunPresentation,
    debugBundle: typeof presentation.buildPowerToolsDebugBundlePresentation,
    runReport: typeof presentation.buildPowerToolsRunReportPresentation,
    armTrace: typeof presentation.buildPowerToolsArmWindowTracePresentation,
  },
  cases,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__POWER_TOOLS_PRESENTATION_MODULE_URL__": "power_tools_presentation.js"},
        timeout_seconds=20,
    )

    assert results["exportTypes"] == {
        "glossarySave": "function",
        "glossaryExport": "function",
        "builderRun": "function",
        "builderApply": "function",
        "calibrationRun": "function",
        "debugBundle": "function",
        "runReport": "function",
        "armTrace": "function",
    }

    malicious = "<img src=x onerror=alert(1)><script>bad()</script>"

    glossary_save = results["cases"]["glossarySave"]
    assert glossary_save["status"] == {
        "slot": "power-tools",
        "tone": "ok",
        "message": "Glossary setup saved.",
    }
    assert glossary_save["diagnostics"]["slot"] == "power-tools-glossary"
    assert glossary_save["diagnostics"]["hint"] == (
        "Advanced glossary data was saved to browser settings and project glossary storage."
    )
    assert glossary_save["diagnostics"]["open"] is False
    assert glossary_save["diagnostics"]["value"]["normalized_payload"]["project_glossary_path"] == (
        f"C:/glossary/{malicious}.json"
    )
    assert glossary_save["resultFields"] == {}

    glossary_export = results["cases"]["glossaryExport"]
    assert glossary_export["status"]["message"] == "Glossary markdown exported."
    assert glossary_export["diagnostics"]["slot"] == "power-tools-glossary"
    assert glossary_export["diagnostics"]["hint"] == f"C:/exports/{malicious}.md"
    assert results["cases"]["glossaryExportFallback"]["diagnostics"]["hint"] == (
        "Glossary markdown export completed."
    )

    builder_run = results["cases"]["builderRun"]
    assert builder_run["status"] == {
        "slot": "power-tools",
        "tone": "ok",
        "message": "Built glossary suggestions from 7 page(s) across 2 source(s).",
    }
    assert builder_run["diagnostics"]["slot"] == "power-tools-builder"
    assert builder_run["diagnostics"]["hint"] == f"C:/artifacts/{malicious}"
    assert json.loads(builder_run["resultFields"]["approvedJson"]) == [
        {"source": malicious, "target": "safe-text-only"}
    ]
    builder_run_fallback = results["cases"]["builderRunFallback"]
    assert builder_run_fallback["status"]["message"] == (
        "Built glossary suggestions from 0 page(s) across 0 source(s)."
    )
    assert builder_run_fallback["diagnostics"]["hint"] == "Glossary builder run completed."
    assert builder_run_fallback["resultFields"] == {}
    assert results["cases"]["nullSafe"] == builder_run_fallback

    builder_apply = results["cases"]["builderApply"]
    assert builder_apply["status"]["message"] == "Glossary suggestions applied."
    assert builder_apply["diagnostics"]["slot"] == "power-tools-builder"
    assert builder_apply["diagnostics"]["hint"] == (
        "Selected glossary suggestions were merged into personal and project glossaries."
    )
    assert builder_apply["resultFields"] == {}

    calibration_run = results["cases"]["calibrationRun"]
    assert calibration_run["status"]["message"] == "Quality check completed."
    assert calibration_run["diagnostics"]["slot"] == "power-tools-calibration"
    assert calibration_run["diagnostics"]["hint"] == f"C:/reports/{malicious}.md"
    assert calibration_run["resultFields"] == {"diagnosticsRunDir": "C:\\cases\\run-1"}
    assert results["cases"]["calibrationRunPosix"]["resultFields"] == {
        "diagnosticsRunDir": "/tmp/legalpdf/run"
    }
    calibration_fallback = results["cases"]["calibrationRunFallback"]
    assert calibration_fallback["diagnostics"]["hint"] == "Quality-check files were generated."
    assert calibration_fallback["resultFields"] == {}

    debug_bundle = results["cases"]["debugBundle"]
    assert debug_bundle["status"]["message"] == "Troubleshooting bundle created."
    assert debug_bundle["diagnostics"]["slot"] == "power-tools-diagnostics"
    assert debug_bundle["diagnostics"]["hint"] == f"C:/bundles/{malicious}.zip"
    assert results["cases"]["debugBundleFallback"]["diagnostics"]["hint"] == (
        "Troubleshooting bundle created."
    )

    run_report = results["cases"]["runReport"]
    assert run_report["status"]["message"] == "Run report generated."
    assert run_report["diagnostics"]["slot"] == "power-tools-diagnostics"
    assert run_report["diagnostics"]["hint"] == f"C:/reports/{malicious}.md"
    assert results["cases"]["runReportFallback"]["diagnostics"]["hint"] == "Run report generated."

    arm_trace = results["cases"]["armTrace"]
    assert arm_trace["status"]["message"] == (
        "The next Gmail startup click will capture a troubleshooting window trace."
    )
    assert arm_trace["diagnostics"]["slot"] == "power-tools-diagnostics"
    assert arm_trace["diagnostics"]["hint"] == f"C:/trace/{malicious}.json"
    assert results["cases"]["armTraceFallback"]["diagnostics"]["hint"] == (
        "The next Gmail startup click will capture a troubleshooting window trace."
    )
