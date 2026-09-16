import json

from legalpdf_translate.run_report import build_run_report_markdown, build_run_report_payload
from tests.test_run_report import _seed_run_dir


def test_report_retains_known_and_unknown_dispatch_cost(tmp_path):
    run_dir = _seed_run_dir(tmp_path)
    summary_path = run_dir / "run_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["dispatch_accounting"] = {"coverage_status": "incomplete", "call_count": 3,
        "provider_dispatch_count": 2, "not_dispatched_count": 1,
        "known_cost_usd": "0.012", "cost_usd": None, "unknown_cost_count": 1}
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    payload = build_run_report_payload(run_dir=run_dir, admin_mode=False,
        include_sanitized_snippets=False)
    assert payload["budget"]["dispatch_accounting"] == summary["dispatch_accounting"]
    markdown = build_run_report_markdown(run_dir=run_dir, admin_mode=False,
        include_sanitized_snippets=False)
    assert "Provider accounting: `incomplete`, `2` dispatches" in markdown
    assert "complete cost is unknown" in markdown


def test_report_exposes_blocked_budget_even_with_observed_known_charge(tmp_path):
    run_dir = _seed_run_dir(tmp_path)
    path = run_dir / "run_summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary["dispatch_accounting"] = {"coverage_status": "incomplete", "call_count": 1,
        "provider_dispatch_count": 1, "known_cost_usd": "0.021", "cost_usd": None,
        "budget_incomplete_count": 1}
    path.write_text(json.dumps(summary), encoding="utf-8")
    markdown = build_run_report_markdown(run_dir=run_dir, admin_mode=False,
        include_sanitized_snippets=False)
    assert "Hard-budget reconciliation is blocked or uncertain" in markdown
    assert "acceptance is blocked" in markdown
    assert "Some provider usage" not in markdown
