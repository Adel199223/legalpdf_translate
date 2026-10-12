import json
from types import SimpleNamespace

from legalpdf_translate.failed_output_evidence import retain_failed_output


def evaluation(text="[[Example]]", ok=False):
    return SimpleNamespace(ok=ok, normalized_text=text, ar_violation_kind="expected_token_mismatch")


def retain(root, **kwargs):
    options = dict(keep_intermediates=True, page=1, attempt=1,
                   raw_output="```\n[[Example]]\n```", evaluation=evaluation(), expected_tokens=["Required"])
    options.update(kwargs)
    return retain_failed_output(root, **options)


def test_failed_body_retained_privately_with_hashed_literal_delta(tmp_path, capsys):
    path = retain(tmp_path, primary_normalized_text="[[Primary]] [[Primary]]")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["raw_output"]["text"] == "```\n[[Example]]\n```"
    assert data["expected_token_packaging_delta"]["missing_occurrences"] == 1
    assert data["primary_token_packaging_delta"]["missing_occurrences"] == 2
    assert "Required" not in json.dumps(data["expected_token_packaging_delta"])
    assert capsys.readouterr().out == "" and capsys.readouterr().err == ""


def test_off_or_success_does_not_create_private_evidence(tmp_path):
    before = set(tmp_path.iterdir())
    assert retain(tmp_path, keep_intermediates=False) is None
    assert retain(tmp_path, evaluation=evaluation(ok=True)) is None
    assert set(tmp_path.iterdir()) == before


def test_repeat_failures_preserve_evidence_and_have_per_attempt_bound(tmp_path):
    first = retain(tmp_path)
    before = first.read_bytes()
    for _ in range(7):
        assert retain(tmp_path, raw_output="different response")
    assert retain(tmp_path) is None
    assert first.read_bytes() == before
    assert retain(tmp_path, attempt=2)
    assert len(list(first.parent.glob("*.json"))) == 9


def test_multibyte_response_and_hashed_samples_are_bounded(tmp_path):
    body = "ع" * 100_000
    normalized = "".join("[[Example" + str(number) + "]]" for number in range(100))
    path = retain(tmp_path, raw_output=body, evaluation=evaluation(normalized))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["raw_output"]["truncated"]
    assert data["raw_output"]["bytes"] == len(body.encode("utf-8"))
    assert len(data["raw_output"]["text"].encode("utf-8")) <= 32 * 1024
    delta = data["expected_token_packaging_delta"]
    assert len(delta["added_hashed_samples"]) == 32 and delta["samples_truncated"]
    assert path.stat().st_size <= 512 * 1024


def test_failure_evidence_io_problem_does_not_replace_validation(tmp_path):
    (tmp_path / "failed_output_evidence").write_text("not a directory")
    assert retain(tmp_path) is None
    assert (tmp_path / "failed_output_evidence").read_text() == "not a directory"
