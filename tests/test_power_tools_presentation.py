from __future__ import annotations

import json

from .browser_esm_probe import run_browser_esm_json_probe


def test_power_tools_presentation_module_builds_bootstrap_state() -> None:
    script = r"""
const presentation = await import(__POWER_TOOLS_PRESENTATION_MODULE_URL__);
const malicious = "<img src=x onerror=alert(1)><script>bad()</script>";

const fullPayload = {
  glossary: {
    project_glossary_path: `C:/glossaries/${malicious}.json`,
    personal_glossaries_by_lang: {
      EN: {
        term: malicious,
      },
    },
    project_glossaries_by_lang: {
      FR: {
        term: "tribunal",
      },
    },
    enabled_tiers_by_target_lang: {
      EN: ["personal", malicious],
    },
    prompt_addendum_by_lang: {
      EN: `Use ${malicious}`,
    },
  },
  glossary_builder: {
    defaults: {
      source_mode: "pdf_paths",
      target_lang: "FR",
      mode: "headers_only",
      lemma_effort: "low",
      lemma_enabled: false,
      run_dirs: ["C:/Run-B", `C:/Run-${malicious}`],
      pdf_paths: ["C:/one.pdf", `C:/two-${malicious}.pdf`],
    },
    last_result: {
      suggestions: [
        {
          source: malicious,
          target: "safe-text-only",
        },
      ],
    },
    latest_run_dirs: [
      {
        name: "Builder duplicate",
        run_dir: "c:/run-a",
      },
      {
        name: `Builder ${malicious}`,
        run_dir: "C:/Run-B",
        has_run_state: true,
      },
      {
        name: "Builder C",
        run_dir: "C:/Run-C",
        has_calibration_report: true,
      },
    ],
  },
  calibration: {
    defaults: {
      pdf_path: `C:/input-${malicious}.pdf`,
      output_dir: `C:/out-${malicious}`,
      target_lang: "AR",
      sample_pages: 0,
      user_seed: malicious,
      excerpt_max_chars: 0,
      include_excerpts: false,
    },
  },
  diagnostics: {
    outputs_root: "C:/outputs",
    runtime_metadata_path: "C:/runtime/metadata.json",
    latest_window_trace: {
      launch_session_id: malicious,
      arm_path: "C:/trace/armed.json",
    },
    latest_run_dirs: [
      {
        name: `Diagnostics ${malicious}`,
        run_dir: "C:/Run-A",
        modified_at_iso: "2026-05-13T08:00:00Z",
        has_run_summary: true,
      },
      {
        name: "Diagnostics duplicate",
        run_dir: "c:/run-a",
      },
      {
        name: "No path",
        run_dir: "",
      },
      null,
    ],
  },
};

const cases = {
  full: presentation.buildPowerToolsBootstrapPresentation(fullPayload),
  empty: presentation.buildPowerToolsBootstrapPresentation({}),
  nullSafe: presentation.buildPowerToolsBootstrapPresentation(null),
  noRuns: presentation.buildPowerToolsBootstrapPresentation({
    diagnostics: {
      latest_window_trace: {},
    },
  }),
};

console.log(JSON.stringify({
  exportType: typeof presentation.buildPowerToolsBootstrapPresentation,
  cases,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__POWER_TOOLS_PRESENTATION_MODULE_URL__": "power_tools_presentation.js"},
        timeout_seconds=20,
    )

    assert results["exportType"] == "function"

    malicious = "<img src=x onerror=alert(1)><script>bad()</script>"
    full = results["cases"]["full"]

    assert full["glossaryForm"]["projectPath"] == f"C:/glossaries/{malicious}.json"
    assert json.loads(full["glossaryForm"]["personalJson"]) == {"EN": {"term": malicious}}
    assert json.loads(full["glossaryForm"]["projectJson"]) == {"FR": {"term": "tribunal"}}
    assert json.loads(full["glossaryForm"]["enabledTiersJson"]) == {
        "EN": ["personal", malicious]
    }
    assert json.loads(full["glossaryForm"]["promptAddendumJson"]) == {
        "EN": f"Use {malicious}"
    }

    assert full["builderDefaults"]["sourceMode"] == "pdf_paths"
    assert full["builderDefaults"]["targetLang"] == "FR"
    assert full["builderDefaults"]["mode"] == "headers_only"
    assert full["builderDefaults"]["lemmaEffort"] == "low"
    assert full["builderDefaults"]["lemmaEnabled"] is False
    assert full["builderDefaults"]["runDirs"] == f"C:/Run-B\nC:/Run-{malicious}"
    assert full["builderDefaults"]["pdfPaths"] == f"C:/one.pdf\nC:/two-{malicious}.pdf"
    assert json.loads(full["builderDefaults"]["approvedJson"]) == [
        {"source": malicious, "target": "safe-text-only"}
    ]

    assert full["calibrationDefaults"] == {
        "pdf_path": f"C:/input-{malicious}.pdf",
        "output_dir": f"C:/out-{malicious}",
        "target_lang": "AR",
        "sample_pages": 0,
        "user_seed": malicious,
        "excerpt_max_chars": 0,
        "include_excerpts": False,
    }

    assert [item["run_dir"] for item in full["latestRunDirs"]] == [
        "C:/Run-A",
        "C:/Run-B",
        "C:/Run-C",
    ]
    assert full["latestRunDirs"][0]["name"] == f"Diagnostics {malicious}"
    assert full["latestRunDirs"][1]["name"] == f"Builder {malicious}"
    assert full["status"] == {
        "tone": "ok",
        "message": (
            "Advanced glossary, quality-check, and troubleshooting tools are ready. "
            "3 recent run folder(s) are available."
        ),
    }
    assert full["diagnostics"]["value"] == {
        "outputs_root": "C:/outputs",
        "runtime_metadata_path": "C:/runtime/metadata.json",
        "latest_run_dirs": full["latestRunDirs"],
        "latest_window_trace": {
            "launch_session_id": malicious,
            "arm_path": "C:/trace/armed.json",
        },
    }
    assert full["diagnostics"]["hint"] == f"Latest startup trace session: {malicious}"
    assert full["diagnostics"]["open"] is False

    empty = results["cases"]["empty"]
    assert empty["glossaryForm"] == {
        "projectPath": "",
        "personalJson": "{}",
        "projectJson": "{}",
        "enabledTiersJson": "{}",
        "promptAddendumJson": "{}",
    }
    assert empty["builderDefaults"] == {
        "sourceMode": "run_folders",
        "targetLang": "EN",
        "mode": "full_text",
        "lemmaEffort": "high",
        "lemmaEnabled": None,
        "runDirs": "",
        "pdfPaths": "",
    }
    assert empty["calibrationDefaults"] == {
        "pdf_path": "",
        "output_dir": "",
        "target_lang": "EN",
        "sample_pages": 5,
        "user_seed": "",
        "excerpt_max_chars": 200,
        "include_excerpts": None,
    }
    assert empty["latestRunDirs"] == []
    assert empty["status"]["message"] == "Advanced glossary, quality-check, and troubleshooting tools are ready."
    assert empty["diagnostics"] == {
        "value": {
            "outputs_root": "",
            "runtime_metadata_path": "",
            "latest_run_dirs": [],
            "latest_window_trace": {},
        },
        "hint": "Troubleshooting bundle, run report, and startup trace defaults appear here.",
        "open": False,
    }
    assert results["cases"]["nullSafe"] == empty
    assert results["cases"]["noRuns"]["status"] == empty["status"]
