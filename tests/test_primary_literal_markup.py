"""Lossless primary transport repair and raw-derived converted commitments."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from legalpdf_translate import primary_literal_markup as markup
from legalpdf_translate import workflow_semantic_audit as integration
from legalpdf_translate.types import TargetLang
from tests.test_workflow_semantic_audit_integration import offline


LEFT, RIGHT = "CASE90/8", "0712/26.4XYZ"


def token(value):
    return markup.LRI + "[[" + value + "]]" + markup.PDI


def case(sep=" "):
    source = "Processo " + token(LEFT) + " " + token(RIGHT) + "\n" + token(LEFT) + " " + token(RIGHT)
    header = markup.LRI + "[[" + LEFT + sep + "[" + RIGHT + "]]]" + markup.PDI
    raw = "```text\n" + header + "\nالنص العربي محفوظ.\n" + token(LEFT) + " " + token(RIGHT) + "\n```"
    required = [LEFT, RIGHT, LEFT, RIGHT]
    recipe = {"source_field_policy": "baseline_label_value_v1",
        "primary_literal_packaging_version": "lossless_source_components_v3",
        "source_inline_address_join_policy": "source_locative_house_join_v2"}
    return raw, source, required, recipe


@pytest.mark.parametrize("sep", [" ", "  ", " " * 8])
def test_pure_conversion_preserves_visible_line_and_owns_repeated_slots(sep):
    raw, source, required, recipe = case(sep)
    initial, result, groups = markup.evaluate_initial(raw, source, required, 1, recipe)
    assert result.ok, result.defect_reason
    expected = token(LEFT) + sep + "[" + token(RIGHT) + "]"
    assert initial.transformed == raw.replace(initial.conversion["original_owner"]["quote"], expected)
    assert groups[0]["ordinals"] == [0, 1]
    assert groups[0]["complete_protected_sequence"] == required
    markup.guard_group(result.normalized_text, result.normalized_text, groups)


@pytest.mark.parametrize("damage", ["pair", "round", "body", "swap", "scope", "sep", "line"])
def test_pure_same_counts_cannot_waive_converted_enclosure_or_group(damage):
    raw, source, required, recipe = case()
    initial, result, groups = markup.evaluate_initial(raw, source, required, 1, recipe)
    assert result.ok
    header = token(LEFT) + " [" + token(RIGHT) + "]"
    changes = {"pair": token(LEFT) + " " + token(RIGHT),
        "round": token(LEFT) + " (" + token(RIGHT) + ")",
        "body": token(LEFT) + " " + token(RIGHT),
        "swap": token(RIGHT) + " [" + token(LEFT) + "]",
        "scope": markup.LRI + header + markup.PDI,
        "sep": token(LEFT) + "  [" + token(RIGHT) + "]", "line": "عنوان " + header}
    candidate = result.normalized_text.replace(header, changes[damage], 1)
    if damage == "body":
        plain = token(LEFT) + " " + token(RIGHT)
        index = candidate.rfind(plain)
        candidate = candidate[:index] + header + candidate[index + len(plain):]
        assert [t[2] for t in markup._view(candidate)[2]] == required
    with pytest.raises(ValueError):
        markup.guard_group(candidate, result.normalized_text, groups)


@pytest.mark.parametrize("damage", ["two", "nested", "tab", "wide", "mixed", "outside", "lookalike", "same"])
def test_pure_uncertain_or_unsupported_markup_abstains_without_partial_conversion(damage):
    raw, source, required, _ = case()
    if damage == "two": raw = raw.replace("\nالنص", "\n" + raw.splitlines()[1] + "\nالنص")
    elif damage == "nested": raw = raw.replace("[" + RIGHT + "]", "[[" + RIGHT + "]]")
    elif damage == "tab": raw = raw.replace(LEFT + " [", LEFT + "\t[")
    elif damage == "wide": raw = raw.replace(LEFT + " [", LEFT + " " * 9 + "[")
    elif damage == "mixed": raw = raw.replace(LEFT + " [", LEFT + " نص [")
    elif damage == "outside": raw += "commentary"
    elif damage == "lookalike": raw = raw.replace("[" + RIGHT + "]", "［" + RIGHT + "］")
    else: raw = raw.replace(RIGHT, LEFT)
    initial = markup.prepare_initial(raw, source, required, 1)
    assert initial.raw == initial.transformed == raw and initial.conversion is None


@pytest.mark.parametrize("retry", [False, True])
def test_current_fresh_empty_group_selection_and_pruned_local_replay(tmp_path, retry):
    from tests.test_semantic_review_model_integration import setup
    from legalpdf_translate.workflow import TranslationWorkflow
    config, http, flow = setup(tmp_path, primary_retry=retry)
    result = flow.run(config)
    assert result.success, result.error
    saved = flow._last_state.settings["ordinary_semantic_audit_recipe"]
    assert saved[markup.KEY] == markup.POLICY
    context = markup.load_context(state=flow._last_state, run_dir=result.run_dir)
    assert context.groups == {1: []}
    directory = result.run_dir / markup.DIRECTORY
    selection = json.loads((directory / "page_0001.selection.json").read_bytes())
    assert selection["origin"] == ("compliance" if retry else "initial")
    assert selection["native"]["begin"]["purpose"] == ("correction" if retry else "translation")
    before = {p.relative_to(result.run_dir): p.read_bytes() for folder in (markup.DIRECTORY,
        "semantic_source", "semantic_audit", "accounting") for p in (result.run_dir/folder).rglob("*")
        if p.is_file() and p.suffix != ".lock"}
    count = len(http.requests)
    (result.run_dir / "pages" / "page_0001.txt").unlink()
    assert flow.run(replace(config, resume=True)).success
    assert TranslationWorkflow(client=http.client, gui_settings={}).run(replace(config, resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert len(http.requests) == count
    assert not (result.run_dir / "pages" / "page_0001.txt").exists()
    assert all((result.run_dir/path).read_bytes() == raw for path, raw in before.items())


class ConvertedScenario:
    def __init__(self, *, lose=False, repair=True):
        self.lose, self.repair, self.payloads, self.verifiers = lose, repair, [], 0

    def __call__(self, body, data):
        if "text" not in body:
            data["output"][0]["content"][0]["text"] = case()[0]
            return data
        payload = json.loads(body["input"][0]["content"][0]["text"])
        self.payloads.append(deepcopy(payload))
        value = json.loads(data["output"][0]["content"][0]["text"])
        if payload["stage"] == "correction":
            _, primary, _ = markup.evaluate_initial(*case()[:3], 1, case()[3])
            for row in value["pages"]:
                candidate = primary.normalized_text.replace("النص العربي محفوظ.",
                    "طلب المدعى عليه جوابا مفصلا." if "prior_findings" in payload else "طلب المدعى عليه جوابا.")
                if self.lose: candidate = candidate.replace("[" + token(RIGHT) + "]", token(RIGHT), 1)
                row.update(status="corrected", corrected_text=candidate, reason_codes=["material_meaning"])
        elif payload["stage"] == "verification":
            self.verifiers += 1
            if self.repair and self.verifiers == 1:
                value["claim_results"][0]["status"] = "missing"
        data["output"][0]["content"][0]["text"] = json.dumps(value, ensure_ascii=False)
        return data


def converted_workflow(tmp_path, *, lose=False, repair=True):
    import fitz
    from tests.test_semantic_review_model_integration import setup
    scenario = ConvertedScenario(lose=lose, repair=repair)
    config, http, flow = setup(tmp_path, mutate=scenario)
    with fitz.open(config.pdf_path) as pdf:
        pdf[0].insert_text((50, 300), f"Processo {LEFT} [{RIGHT}]\n{LEFT} {RIGHT}")
        pdf.saveIncr()
    return config, http, flow, scenario


def test_current_factory_converted_one_cycle_saved_binding_and_zero_send_pruned_replay(tmp_path, record_property):
    from legalpdf_translate.workflow import TranslationWorkflow
    config, http, flow, scenario = converted_workflow(tmp_path)
    result = flow.run(config)
    assert result.success, result.error
    assert len(http.requests) == 6
    context = markup.load_context(state=flow._last_state, run_dir=result.run_dir)
    assert context.groups[1][0]["ordinals"] == [0, 1]
    assert context.groups[1][0]["complete_protected_sequence"] == [LEFT, RIGHT, LEFT, RIGHT]
    manifest = json.loads((result.run_dir/"semantic_audit/manifest.json").read_bytes())
    assert manifest["consumed_cycles"] == manifest["selected_attempt"] == 1
    assert manifest["repair_trigger"] == "independent_verification"
    assert manifest["binding"]["primary_markup_evidence_sha256"] == context.evidence_sha256
    assert manifest["semantic_repair_policy"][markup.KEY] == markup.descriptor()
    final = scenario.payloads[-1]
    assert final["stage"] == "verification" and not set(final) & {markup.KEY, "prior_findings", "primary_pages"}
    record_property("primary_markup_specimen", json.dumps({"run_dir":str(result.run_dir),
        "pdf_path":str(config.pdf_path),"requests":http.requests},ensure_ascii=False))
    before = {p.relative_to(result.run_dir):p.read_bytes() for folder in (markup.DIRECTORY,
        "semantic_source","semantic_audit","accounting") for p in (result.run_dir/folder).rglob("*")
        if p.is_file() and p.suffix != ".lock"}
    (result.run_dir/"pages/page_0001.txt").unlink()
    assert flow.run(replace(config,resume=True)).success
    assert TranslationWorkflow(client=http.client,gui_settings={}).run(replace(config,resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert len(http.requests) == 6
    assert all((result.run_dir/p).read_bytes() == raw for p,raw in before.items())
    assert not (result.run_dir/"pages/page_0001.txt").exists()


def test_converted_pair_loss_never_reaches_blind_verification(tmp_path):
    config, http, flow, scenario = converted_workflow(tmp_path, lose=True)
    result = flow.run(config)
    assert not result.success
    assert len(http.requests) == 3
    assert [p["stage"] for p in scenario.payloads] == ["source_inventory","correction"]
    assert not (result.run_dir/"semantic_audit/manifest.json").exists()


def test_old_absent_owned_job_does_not_read_a_checkpoint(tmp_path, monkeypatch):
    from legalpdf_translate import checkpoint
    monkeypatch.setattr(checkpoint, "load_run_state", lambda *_: pytest.fail("Historical admission parsed a checkpoint"))
    assert markup.admit_owned_job(run_dir=tmp_path, source_pdf=tmp_path/"source.pdf",
        selected_pages=(1,), target_lang="AR", writer_map={}) is False


@pytest.fixture(scope="module")
def browser_converted(tmp_path_factory):
    import fitz
    from fastapi.testclient import TestClient
    from tests import test_ordinary_auto_layout_workflow as browser
    root = tmp_path_factory.mktemp("primary_markup_browser")
    patch = pytest.MonkeyPatch()
    from datetime import date
    from legalpdf_translate import accounting_policy
    class CatalogDate(date):
        @classmethod
        def today(cls): return cls(2026, 10, 15)
    patch.setattr(accounting_policy, "date", CatalogDate)
    from legalpdf_translate import workflow
    patch.setattr(workflow, "load_environment", lambda: None)
    patch.setattr(workflow, "run_translation_auth_test", lambda **_: pytest.fail("Unexpected auth"))
    patch.setattr(workflow, "resolve_openai_key_with_source", lambda **_: pytest.fail("Unexpected credentials"))
    source, output = root/"source.pdf", root/"output"
    output.mkdir(); browser._source(source, ("digital",))
    with fitz.open(source) as pdf:
        pdf[0].insert_text((50, 330), f"Processo {LEFT} [{RIGHT}]\n{LEFT} {RIGHT}")
        pdf.saveIncr()
    inner = case()[0].split("\n", 1)[1].rsplit("\n", 1)[0]
    app, jobs, sdk, layout_requests = browser._app(root, patch, (inner,), (1,))
    with TestClient(app) as client:
        job_id = browser._start(client, source, output, "AR", start=1,end=1,image_mode="off")
        job = browser._wait(jobs, job_id, timeout_seconds=90)
    yield {"root":root,"app":app,"jobs":jobs,"sdk":sdk,"layout_requests":layout_requests,
        "source":source,"output":output,"job_id":job_id,"job":job}
    patch.undo()


def test_current_normal_Start_private_baseline_and_actual_early_candidate_reuse(browser_converted, record_property):
    from legalpdf_translate import ordinary_auto_layout as automatic
    case = browser_converted; job = case["job"]
    assert job["status"] == "completed", job
    result = job["result"]["automatic_layout"]
    assert result["status"] == "automatic_unreviewed", (result,job["diagnostics"])
    baseline = case["jobs"]._jobs[case["job_id"]]._ordinary_baseline
    assert baseline["primary_markup_admission"]["policy"] == markup.POLICY
    assert len(case["sdk"].requests) == len(case["layout_requests"]) == 1
    layout = case["app"].state.ordinary_layouts.manager_for_context(case["app"].state.shadow_context,"shadow","fictional")
    before = (len(case["sdk"].requests),len(case["sdk"].semantic_requests),len(case["layout_requests"]))
    reused = automatic.run_automatic_layout(layout,case["app"].state.ordinary_layouts._accounting,
        case["job_id"],automatic.frozen_automatic_layout_policy())
    assert reused["reused_durable_candidate"] and reused["sha256"] == result["sha256"]
    assert before == (len(case["sdk"].requests),len(case["sdk"].semantic_requests),len(case["layout_requests"]))
    record_property("primary_markup_browser_specimen",json.dumps({"root":str(case["root"]),
        "run_dir":job["result"]["run_dir"],"job_id":case["job_id"],"baseline":baseline,
        "source":str(case["source"]),"layout_requests":case["layout_requests"]},ensure_ascii=False))


@pytest.mark.parametrize("fault", ["false_empty", "page_float", "ordinal_bool", "span", "neighborhood", "sep", "raw", "native"])
def test_rehashed_raw_record_or_converted_metadata_is_rederived_not_trusted(browser_converted, fault):
    from legalpdf_translate.checkpoint import load_run_state
    run = Path(browser_converted["job"]["result"]["run_dir"])
    state = load_run_state(run/"run_state.json")
    first, selected = run/markup.DIRECTORY/"page_0001.initial.json", run/markup.DIRECTORY/"page_0001.selection.json"
    before = first.read_bytes(), selected.read_bytes()
    initial, selection = json.loads(before[0]), json.loads(before[1])
    if fault == "false_empty": initial.update(conversion=None, groups=[])
    elif fault == "page_float": initial["groups"][0]["page"] = 1.0
    elif fault == "ordinal_bool": initial["groups"][0]["ordinals"][0] = False
    elif fault == "span": initial["groups"][0]["original_owner"]["end"] -= 1
    elif fault == "neighborhood": initial["groups"][0]["neighborhoods"][0] = []
    elif fault == "sep": initial["groups"][0]["sep"] = "  "
    elif fault == "raw": initial["raw_initial"] += "\n"
    else: initial["native"]["begin"]["request_hash"] = "0" * 64
    raw = markup.encode(initial); selection["initial_sha256"] = markup.digest(raw)
    first.write_bytes(raw); selected.write_bytes(markup.encode(selection))
    state.pages["1"][markup.PAGE_HASH] = markup.digest(selected.read_bytes())
    try:
        with pytest.raises(markup.PrimaryMarkupError):
            markup.load_context(state=state, run_dir=run)
    finally:
        first.write_bytes(before[0]); selected.write_bytes(before[1])


@pytest.mark.parametrize("fault", ["proof_missing", "coherent_absence", "strip", "primary", "semantic", "map"])
def test_actual_common_job_admission_rejects_before_existing_candidate_return(browser_converted, fault):
    case = browser_converted; run = Path(case["job"]["result"]["run_dir"])
    job = case["jobs"]._jobs[case["job_id"]]
    checkpoint = run/"run_state.json"; original_checkpoint = checkpoint.read_bytes()
    originals, moved = {}, None
    original_baseline = deepcopy(job._ordinary_baseline)
    try:
        if fault in {"proof_missing", "coherent_absence"}:
            moved = run/"primary_markup_test_hold"; (run/markup.DIRECTORY).rename(moved)
            if fault == "coherent_absence":
                data = json.loads(original_checkpoint)
                data["settings"]["ordinary_semantic_audit_recipe"].pop(markup.KEY)
                data["pages"]["1"].pop(markup.PAGE_HASH)
                checkpoint.write_bytes(markup.encode(data))
        elif fault == "strip":
            data = json.loads(original_checkpoint); data["settings"]["strip_bidi_controls"] = False
            checkpoint.write_bytes(markup.encode(data))
        elif fault == "primary":
            path = run/"pages/page_0001.txt"; originals[path] = path.read_bytes()
            path.write_bytes(originals[path] + b"\n")
        elif fault == "semantic":
            path = run/"semantic_audit/page_0001.txt"; originals[path] = path.read_bytes()
            path.write_bytes(originals[path] + b"\n")
        else:
            job._ordinary_baseline["mapping"]["pages"][0]["translation_sha256"] = "0" * 64
        with pytest.raises((ValueError, RuntimeError)):
            case["jobs"].trusted_ordinary_layout_job(case["job_id"],runtime_mode="shadow",workspace_id="fictional")
    finally:
        for path, raw in originals.items(): path.write_bytes(raw)
        checkpoint.write_bytes(original_checkpoint)
        if moved is not None: moved.rename(run/markup.DIRECTORY)
        job._ordinary_baseline = original_baseline


def test_new_manager_pruned_normal_Resume_reconstructs_expected_owned_identity_without_sends(browser_converted, monkeypatch):
    from fastapi.testclient import TestClient
    from tests import test_ordinary_auto_layout_workflow as browser
    case = browser_converted
    run = Path(case["job"]["result"]["run_dir"])
    primary = run/"pages/page_0001.txt"; before = primary.read_bytes()
    expected = deepcopy(case["jobs"]._jobs[case["job_id"]]._ordinary_baseline["primary_markup_admission"])
    primary.unlink()
    try:
        app,jobs,sdk,layout_requests = browser._app(case["root"],monkeypatch,(),(1,))
        with TestClient(app) as client:
            job_id = browser._start(client,case["source"],case["output"],"AR",start=1,end=1,image_mode="off",resume=True)
            result = browser._wait(jobs,job_id,timeout_seconds=90)
        assert result["status"] == "completed",result
        assert result["result"]["automatic_layout"]["status"] == "automatic_unreviewed",result["result"]
        assert jobs._jobs[job_id]._ordinary_baseline["primary_markup_admission"] == expected
        assert not sdk.requests and not sdk.semantic_requests and not layout_requests
        assert not primary.exists()
    finally:
        primary.write_bytes(before)


@pytest.mark.parametrize("fault", ["unknown", "missing_context", "foreign_context", "context_without_policy"])
def test_direct_engine_requires_saved_policy_and_complete_owned_context_before_any_client_or_directory(tmp_path, fault):
    from types import SimpleNamespace
    from legalpdf_translate import ordinary_semantic_repair as repair
    from tests.test_ordinary_semantic_review import pack, recipe, PDF
    policy, context = markup.POLICY, None
    if fault == "unknown": policy = "unknown"
    elif fault == "foreign_context": context = object()
    elif fault == "context_without_policy": policy, context = None, object()
    directory = tmp_path/"semantic"
    client = SimpleNamespace(model="gpt-6-astra", create_page_response=lambda **_: pytest.fail("Client dispatched"))
    with pytest.raises(markup.PrimaryMarkupError):
        repair.run_semantic_repair(pages=pack(count=1,off=True),recipe=replace(recipe(),model="gpt-6-astra",configured_image_mode="off"),
            pdf_sha256=PDF,evidence_dir=directory,client=client,
            semantic_repair_policy=repair.POLICY_V4,semantic_literal_authority_policy="source_literal_authority_v1",
            semantic_enclosure_authority_policy="source_enclosure_authority_v1",
            source_enclosure_identity_policy="bounded_distinct_additions_v1",
            semantic_unit_reference_policy="caller_unit_refs_v1",source_inventory_max_output_tokens=64000,
            semantic_source_review_policy="source_commitment_visual_v7",semantic_page_coverage_policy="complete_selected_pages_v1",
            primary_literal_markup_policy=policy,primary_markup_context=context,
            stage_guard=lambda **_: pytest.fail("Native stage prepared"))
    assert not directory.exists()


@pytest.mark.parametrize("fault", ["unknown", "null", "strip", "assembly", "source", "pack", "absent"])
def test_saved_markup_selection_is_optional_and_never_changes_user_strip_choice(tmp_path, fault):
    from tests.test_workflow_semantic_review_integration import saved_recipe
    from legalpdf_translate.checkpoint import ordinary_semantic_audit_recipe,SemanticAuditRecipeError,sha256_of_text
    config,saved,settings = saved_recipe(tmp_path)
    settings["ocr_engine"] = config.ocr_engine.value
    assert saved[markup.KEY] == markup.POLICY and ordinary_semantic_audit_recipe(settings) == saved
    if fault == "unknown": saved[markup.KEY] = "unknown"
    elif fault == "null": saved[markup.KEY] = None
    elif fault == "strip": settings["strip_bidi_controls"] = False
    elif fault == "assembly": settings["primary_assembly_recipe"]["version"] = "terminal_labeled_folio_v1"
    elif fault == "source": saved["semantic_source_review_policy"] = "source_commitment_visual_v6"
    elif fault == "pack": saved["primary_literal_packaging_version"] = "lossless_source_components_v2"
    else: saved.pop(markup.KEY)
    if fault == "absent": assert markup.KEY not in ordinary_semantic_audit_recipe(settings)
    else:
        with pytest.raises(SemanticAuditRecipeError): ordinary_semantic_audit_recipe(settings)
    fresh = integration.fresh_recipe(replace(config,strip_bidi_controls=False),"gpt-5.2",
        saved["ordinary_auto_layout_policy"],context_text="",context_hash=sha256_of_text(""))
    assert markup.KEY not in fresh


def test_new_work_is_charged_before_compliance_parser(monkeypatch):
    from legalpdf_translate import validators
    raw,source,required,recipe = case()
    initial,result,groups = markup.evaluate_initial(raw,source,required,1,recipe)
    work=markup.Work();work.used=markup.MAX_WORK
    monkeypatch.setattr(validators,"parse_code_block_output",lambda *_:pytest.fail("Parser ran after exhausted work"))
    with pytest.raises(markup.PrimaryMarkupError,match="work_bound"):
        markup.evaluate_compliance(raw,result,initial,groups,source,required,recipe,work=work)


def test_initial_hard_bounds_precede_new_parser_and_preserve_unsupported_raw(monkeypatch):
    from legalpdf_translate import validators
    raw,source,required,_ = case()
    monkeypatch.setattr(validators,"parse_code_block_output",lambda *_:pytest.fail("Parser ran for oversized input"))
    huge = raw + "x" * markup.MAX_CHARS
    assert markup.prepare_initial(huge,source,required,1).transformed == huge
    assert markup.prepare_initial(raw,source,required * 129,1).transformed == raw


def test_existing_certified_exact_slot_can_project_without_waiving_converted_square(tmp_path):
    from legalpdf_translate import ordinary_semantic_enclosure_authority as authority
    from legalpdf_translate import ordinary_semantic_review as review
    from tests.test_source_literal_authority import example,origins,correction,resolution,INVENTORY,RECIPE
    from tests.test_ordinary_semantic_audit import PDF
    raw,source,_,options = case()
    raw = "```\n" + raw.splitlines()[1] + "\nالنص العربي محفوظ.\n```"
    source = "Processo " + token(LEFT) + " " + token(RIGHT)
    initial,result,groups = markup.evaluate_initial(raw,source,[LEFT,RIGHT],1,options)
    assert result.ok
    page,_,_ = example("image")
    page=replace(page,primary_text=result.normalized_text,source_text=source,
        original_source_text="Processo " + LEFT + " " + RIGHT,expected_ar_tokens=(LEFT,RIGHT))
    pages=[page];registry=authority.freeze(pages,PDF,origins(pages));new=LEFT+"X"
    candidate=page.primary_text.replace(token(LEFT),token(new))
    proposal=correction(pages,[candidate]);eligible=authority.classify(proposal,pages,INVENTORY,RECIPE,registry)
    answer={"version":authority.RESPONSE,"literal_decisions":resolution(registry,eligible,[new])["decisions"],
        "enclosure_observations":[]}
    cert=authority.certificate(review.audit._json(answer),pages,registry,eligible)
    effective=authority.project(pages,registry,cert,identity_policy="bounded_distinct_additions_v1")
    assert authority.validate(proposal,pages,INVENTORY,RECIPE,effective,identity_policy="bounded_distinct_additions_v1")[0][1]==candidate
    context=markup.Context(None,tmp_path,{}, {1:page.primary_text},{1:groups},"fictional-internal-guard-only")
    with pytest.raises(markup.PrimaryMarkupError):markup.guard_candidates(context,{1:candidate})
    markup.guard_candidates(context,{1:candidate},effective_pages=effective.projected_pages)
    with pytest.raises(markup.PrimaryMarkupError):
        markup.guard_candidates(context,{1:candidate+" "+token(LEFT)},effective_pages=effective.projected_pages)
    missing=candidate.replace("["+token(RIGHT)+"]",token(RIGHT))
    with pytest.raises(markup.PrimaryMarkupError):
        markup.guard_candidates(context,{1:missing},effective_pages=effective.projected_pages)


@pytest.mark.parametrize("kind", ["page", "aggregate"])
def test_evidence_pair_and_aggregate_read_bound_precedes_second_record_read(tmp_path, monkeypatch, kind):
    from types import SimpleNamespace
    from tests.test_workflow_semantic_review_integration import saved_recipe
    config,_,settings=saved_recipe(tmp_path);settings["ocr_engine"]=config.ocr_engine.value
    run=tmp_path/"run";(run/markup.DIRECTORY).mkdir(parents=True)
    state=SimpleNamespace(settings=settings,pages={"1":{"status":"done"}},selection_start_page=1,selection_end_page=1)
    first=run/markup.DIRECTORY/"page_0001.initial.json";second=run/markup.DIRECTORY/"page_0001.selection.json"
    # Isolate the read preflight; complete genuine record validity is covered
    # above, and this second JSON must never reach logical replay at all.
    first.write_bytes(markup.encode({"padding":"initial"}));second.write_bytes(markup.encode({"padding":"selection"}))
    pair=first.stat().st_size+second.stat().st_size
    monkeypatch.setattr(markup,"PAGE_BYTES" if kind=="page" else "TOTAL_BYTES",pair-1)
    original=Path.read_bytes;reads=[]
    def observed(path):
        reads.append(path)
        assert path != second,"Second record was read beyond remaining budget"
        return original(path)
    monkeypatch.setattr(Path,"read_bytes",observed)
    with pytest.raises(markup.PrimaryMarkupError,match="evidence_missing_or_bound"):
        markup.load_context(state=state,run_dir=run)
    assert first in reads and second not in reads


@pytest.mark.parametrize("kind", ["oversize", "directory"])
def test_new_owned_source_is_bounded_before_open_or_hash(tmp_path, monkeypatch, kind):
    from types import SimpleNamespace
    from legalpdf_translate import checkpoint
    (tmp_path/"run_state.json").write_bytes(b"{}")
    source=tmp_path/"source.pdf"
    if kind=="oversize":
        with source.open("wb") as handle:handle.truncate(64*1024*1024+1)
    else:source.mkdir()
    state=SimpleNamespace(settings={})
    monkeypatch.setattr(checkpoint,"load_run_state",lambda *_:state)
    monkeypatch.setattr(markup,"load_context",lambda **_:object())
    expected={"new":"explicit-owned-marker"}
    monkeypatch.setattr(markup,"expected_admission",lambda **_:expected)
    original=Path.open
    def observed(path,*args,**kwargs):
        assert path != source,"Oversized/nonregular source was opened before refusal"
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,"open",observed)
    with pytest.raises(markup.PrimaryMarkupError,match="owned_source_bound"):
        markup.admit_owned_job(run_dir=tmp_path,source_pdf=source,selected_pages=(1,),target_lang="AR",
            writer_map={},expected=expected,config=object())


def test_converted_initial_with_other_token_failure_cannot_lose_pair_in_compliance(tmp_path):
    import fitz
    from tests.test_semantic_review_model_integration import setup
    from legalpdf_translate.workflow_components.evaluation import evaluate_output
    extra="DOC54/1";calls=[]
    raw,source,required,recipe=case()
    initial,baseline,groups=markup.evaluate_initial(raw,source,required,1,recipe)
    reply="```\n"+baseline.normalized_text.replace("["+token(RIGHT)+"]",token(RIGHT),1)+"\n"+token(extra)+"\n```"
    def respond(body,data):
        assert "text" not in body,"Pair loss reached a semantic dispatch"
        calls.append(body)
        data["output"][0]["content"][0]["text"]=raw if len(calls)==1 else reply
        return data
    config,http,flow=setup(tmp_path,mutate=respond)
    with fitz.open(config.pdf_path) as pdf:
        pdf[0].insert_text((50,300),f"Processo {LEFT} [{RIGHT}]\n{LEFT} {RIGHT}\n{extra}")
        pdf.saveIncr()
    result=flow.run(config)
    assert not result.success and result.error=="compliance_failure"
    assert len(http.requests)==2 and not (result.run_dir/"semantic_audit").exists()
    record=json.loads((result.run_dir/markup.DIRECTORY/"page_0001.initial.json").read_bytes())
    assert record["groups"] and record["initial_ok"] is False
    capture=json.loads((result.run_dir/"semantic_source/page_0001.json").read_bytes())
    saved=flow._last_state.settings["ordinary_semantic_audit_recipe"]
    _,evaluation,_=markup.evaluate_initial(raw,capture["source_text"],capture["expected_ar_tokens"],1,saved)
    old=evaluate_output(reply,TargetLang.AR,expected_ar_tokens=capture["expected_ar_tokens"],
        ar_source_text=capture["source_text"],primary_normalized_text=evaluation.normalized_text,
        source_field_policy=saved["source_field_policy"],literal_wrapper_policy=saved["primary_literal_packaging_version"],
        source_inline_address_join_policy=saved["source_inline_address_join_policy"])
    assert old.ok,"The additional group guard must be the meaningful refusal"
    assert flow._last_state.pages["1"]["validator_defect_reason"]=="primary_markup_group_loss"
    assert not (result.run_dir/markup.DIRECTORY/"page_0001.selection.json").exists()


def test_native_selected_call_is_logical_not_ordinal_and_other_page_may_be_in_flight(tmp_path):
    from types import SimpleNamespace
    from legalpdf_translate.usage_accounting import DispatchAccounting
    from tests.test_usage_accounting_core import _snapshot,_usage
    identifier="a"*32
    identity={"accounting_id":identifier,"source_sha256":"b"*64,"context_hash":"c"*64,
        "language":"AR","selection":[1,2],"run_started_at":"fictional-start"}
    state=SimpleNamespace(dispatch_accounting={"id":identifier},pdf_fingerprint="b"*64,
        context_hash="c"*64,lang="AR",selection_start_page=1,selection_end_page=2,run_started_at="fictional-start")
    accountant=DispatchAccounting(tmp_path/"accounting"/identifier,run_identity=identity,pricing_snapshot=_snapshot())
    first=accountant.begin(provider="openai",requested_model="model-a",request_hash="d"*64,
        purpose="translation",page_number=1,attempt=3,billing_scope="offline_fixture")
    accountant.finish(first,outcome="succeeded",usage=_usage(),response_id="logical-initial",actual_model="model-a",
        actual_service_tier="default",actual_billing_scope="offline_fixture")
    second=accountant.begin(provider="openai",requested_model="model-a",request_hash="e"*64,
        purpose="translation",page_number=2,attempt=1)
    proof=markup._native(tmp_path,state,1,"logical-initial")
    assert proof["begin"]["attempt"]==3 and accountant.summary()["in_flight_count"]==1
    accountant.finish(second,outcome="succeeded",usage=None,response_id="unknown-selected",actual_model="model-a")
    assert markup._native(tmp_path,state,1,"logical-initial",expected=proof)==proof
    with pytest.raises(markup.PrimaryMarkupError,match="native_settlement"):
        markup._native(tmp_path,state,2,"unknown-selected")
