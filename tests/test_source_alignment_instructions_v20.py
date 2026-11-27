"""Prospective source alignment; historical requests and recovery remain immutable."""
from copy import deepcopy
from pathlib import Path
import shutil
from io import BytesIO

import fitz
from PIL import Image

import pytest

from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_layout_manager as manager_module
from legalpdf_translate import ordinary_layout_reproposal as proof
from legalpdf_translate import ordinary_source_line_map as source_lines
from legalpdf_translate.ordinary_layout_contracts import OrdinaryLayoutError, decode, digest, encode
from tests import test_ordinary_layout_reproposal as legacy

HISTORICAL_RECIPES = {
    "_adjacent_lrm_emphasis_v9_policy": "source_image_unreviewed_v1:2fa52c6380e15c835e870ceda262b9f77d8f482d177fd559f7a6f6d96bbddf9a",
    "_body_columns_v3_policy": "source_image_unreviewed_v1:1e4a11e243d8a6a27dd7fa30c54e4475dfae4a3f74a68e789eef1be15362ab4b",
    "_bounded_page_reproposal_v11_policy": "source_image_unreviewed_v1:a74507cdf6ee71f80aa0a9be5c8e89bae8adee593707cbae631ca3abf80f86f1",
    "_bounded_signature_label_v16_policy": "source_image_unreviewed_v1:66aebf0e66a977414a7358a5833fdda5f8118e59791ff25fdbb9a7c7377e442c",
    "_clock_direction_policy": "source_image_unreviewed_v1:d3c89ef63893696d339f350c00500a4cd865f594ce56ed9a45472bb350b5e0b7",
    "_complete_lrm_emphasis_policy": "source_image_unreviewed_v1:f60c0c62ac3964ad6231764b98132529fa0afe6b9cb3149bff9145c56d370b58",
    "_contact_folio_overlap_v19_policy": "source_image_unreviewed_v1:99e1d522ab5d17a6a2daba542b7c90b20bb2b2dc36a3f49d53f55fd6153d75a4",
    "_contact_folio_v18_policy": "source_image_unreviewed_v1:afe45a0e6c1cbe948304d81d58f36a02c1d89f8c398678382d5478612db251d9",
    "_heading_columns_v4_policy": "source_image_unreviewed_v1:a1f0b680bfd07d5c2ca3a7d11d47939c96f8639271a38764897fdeabd346f81a",
    "_in_body_terminal_closing_v8_policy": "source_image_unreviewed_v1:e94583acb61d29114e653489cef5be0685dbd640ca8190a8faa70c4b1a6d48fc",
    "_in_flow_folio_bridges_v13_policy": "source_image_unreviewed_v1:e7a5a9bd3ae6001a528b9f75015382525a944728d7541890be1f5de3802724e5",
    "_inline_folio_direction_policy": "source_image_unreviewed_v1:7c54ccb193b2fb707fc8164f591f5cb9769e6ab800300be8bda227307dcbf2dd",
    "_labeled_folio_direction_v14_policy": "source_image_unreviewed_v1:f8a091d4e79093cb6c77ebacb07f1fa3392424e9b4088e5e6774991e0de46b49",
    "_local_footer_closing_v17_policy": "source_image_unreviewed_v1:26897ec487653c9ad2e97c566edb423c08b8688bd58e5ea6e9acb6e05a809ea3",
    "_per_page_reproposal_v12_policy": "source_image_unreviewed_v1:0e24c65876e24537a509627fcf39b03519b25c7909f7323dd099ddfa933f8409",
    "_plain_list_columns_v6_policy": "source_image_unreviewed_v1:9fd38bcf825d143d0f5109020ad5eacfc42d9d05187dd5ba44ba343152253ecd",
    "_protected_folio_bridges_v10_policy": "source_image_unreviewed_v1:30be490332e41c32685933a91a5e672f8bf3fb7f5a54644123e7b7f078630166",
    "_reference_footer_v5_policy": "source_image_unreviewed_v1:5737c26b2a9de209b945de79eb74813e7b98e772214082e54d198494a58e6f15",
    "_source_bound_v3_policy": "source_image_unreviewed_v1:b6277898f059d84cc7a7171d24663adb7f542534fa5ad5a98b5ae607289eb960",
    "_source_bound_v4_policy": "source_image_unreviewed_v1:bb15bab385eb54f074c00da06fdadfe607c48e2d1933532f590160d80f54ae01",
    "_terminal_closing_group_policy": "source_image_unreviewed_v1:e1d8a9d167debf3bd910de5ae014c092c2b59768cce34e24d3309fb8d3d40095",
    "_terminal_footer_membership_v7_policy": "source_image_unreviewed_v1:9c984629684a91cf7c4ea4901c4ddb9ce5f059b56b2ebbdf55cda4aabaca3ce6",
    "_terminal_punctuation_folio_v15_policy": "source_image_unreviewed_v1:f04fe5fa2d6c03c3552819679455442552261a03a4978ed14bec33cbf35bb769",
    "_terminal_source_layout_policy": "source_image_unreviewed_v1:98a25bdde6fa1f5b950c3b073653a5fc634fdf6248f4015fa9d13ddfae039099",
    "manual_automatic_layout_policy": "source_image_unreviewed_v1:30be490332e41c32685933a91a5e672f8bf3fb7f5a54644123e7b7f078630166"
}

HISTORICAL_VALUES = {
    'source_image_unreviewed_v1:0e24c65876e24537a509627fcf39b03519b25c7909f7323dd099ddfa933f8409',
    'source_image_unreviewed_v1:14d640f395b2b89659e014f32e328c2ea9176b4222538d82d0448b1656e109a4',
    'source_image_unreviewed_v1:17b5eb837ee5767ceebb7a511df2084dd23fd84a9bc965cd757f01b68694f7d5',
    'source_image_unreviewed_v1:1e4a11e243d8a6a27dd7fa30c54e4475dfae4a3f74a68e789eef1be15362ab4b',
    'source_image_unreviewed_v1:26897ec487653c9ad2e97c566edb423c08b8688bd58e5ea6e9acb6e05a809ea3',
    'source_image_unreviewed_v1:2fa52c6380e15c835e870ceda262b9f77d8f482d177fd559f7a6f6d96bbddf9a',
    'source_image_unreviewed_v1:30be490332e41c32685933a91a5e672f8bf3fb7f5a54644123e7b7f078630166',
    'source_image_unreviewed_v1:5737c26b2a9de209b945de79eb74813e7b98e772214082e54d198494a58e6f15',
    'source_image_unreviewed_v1:66aebf0e66a977414a7358a5833fdda5f8118e59791ff25fdbb9a7c7377e442c',
    'source_image_unreviewed_v1:7a2f8d7d4c43368ad58cc57f8b515f3386cbfbd4a0dd45054e68108d4e19a17a',
    'source_image_unreviewed_v1:7c54ccb193b2fb707fc8164f591f5cb9769e6ab800300be8bda227307dcbf2dd',
    'source_image_unreviewed_v1:98a25bdde6fa1f5b950c3b073653a5fc634fdf6248f4015fa9d13ddfae039099',
    'source_image_unreviewed_v1:99e1d522ab5d17a6a2daba542b7c90b20bb2b2dc36a3f49d53f55fd6153d75a4',
    'source_image_unreviewed_v1:9c984629684a91cf7c4ea4901c4ddb9ce5f059b56b2ebbdf55cda4aabaca3ce6',
    'source_image_unreviewed_v1:9fd38bcf825d143d0f5109020ad5eacfc42d9d05187dd5ba44ba343152253ecd',
    'source_image_unreviewed_v1:a1f0b680bfd07d5c2ca3a7d11d47939c96f8639271a38764897fdeabd346f81a',
    'source_image_unreviewed_v1:a74507cdf6ee71f80aa0a9be5c8e89bae8adee593707cbae631ca3abf80f86f1',
    'source_image_unreviewed_v1:afe45a0e6c1cbe948304d81d58f36a02c1d89f8c398678382d5478612db251d9',
    'source_image_unreviewed_v1:b6277898f059d84cc7a7171d24663adb7f542534fa5ad5a98b5ae607289eb960',
    'source_image_unreviewed_v1:bb15bab385eb54f074c00da06fdadfe607c48e2d1933532f590160d80f54ae01',
    'source_image_unreviewed_v1:d3c89ef63893696d339f350c00500a4cd865f594ce56ed9a45472bb350b5e0b7',
    'source_image_unreviewed_v1:e0c5fa5ea5ca1633d89daa45e93c3f5ce04b579f5916194cc5495f1b64c715d9',
    'source_image_unreviewed_v1:e1d8a9d167debf3bd910de5ae014c092c2b59768cce34e24d3309fb8d3d40095',
    'source_image_unreviewed_v1:e7a5a9bd3ae6001a528b9f75015382525a944728d7541890be1f5de3802724e5',
    'source_image_unreviewed_v1:e94583acb61d29114e653489cef5be0685dbd640ca8190a8faa70c4b1a6d48fc',
    'source_image_unreviewed_v1:f04fe5fa2d6c03c3552819679455442552261a03a4978ed14bec33cbf35bb769',
    'source_image_unreviewed_v1:f60c0c62ac3964ad6231764b98132529fa0afe6b9cb3149bff9145c56d370b58',
    'source_image_unreviewed_v1:f8a091d4e79093cb6c77ebacb07f1fa3392424e9b4088e5e6774991e0de46b49',
}


# The three oldest metadata recipes did not grant local source-folio proof.
HISTORICAL_SOURCE_FOLIO_VALUES = HISTORICAL_VALUES - {
    'source_image_unreviewed_v1:14d640f395b2b89659e014f32e328c2ea9176b4222538d82d0448b1656e109a4',
    'source_image_unreviewed_v1:17b5eb837ee5767ceebb7a511df2084dd23fd84a9bc965cd757f01b68694f7d5',
    'source_image_unreviewed_v1:7a2f8d7d4c43368ad58cc57f8b515f3386cbfbd4a0dd45054e68108d4e19a17a',
}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    legacy.isolate_provider(monkeypatch)


def fingerprint(recipe):
    return recipe.split(":", 1)[1]


def test_historical_instruction_bytes_and_all_28_concrete_recipes_are_fixed():
    assert digest(manager_module.INSTRUCTIONS.encode()) == "64bd523ddc088c76e0f402131bb36b6ec916bad34f0ebee0fcb101ade37ed260"
    assert digest(manager_module.INSTRUCTIONS_V2.encode()) == "59050be51461d0d8352102cdcbf27271c5b7ef6e1486eaea3804cde28852fe45"
    for name, expected in HISTORICAL_RECIPES.items():
        assert getattr(auto, name)() == expected, name
    current = auto._source_alignment_v20_policy()
    assert auto.frozen_automatic_layout_policy() == current
    assert current not in HISTORICAL_VALUES
    assert auto._metadata_normalization_policies() == HISTORICAL_VALUES | {current}
    assert auto._source_folio_policies() == HISTORICAL_SOURCE_FOLIO_VALUES | {current}
    for value in {fingerprint(recipe) for recipe in HISTORICAL_VALUES} | {None, "unknown"}:
        assert manager_module.instructions_for_render_policy(value) == manager_module.INSTRUCTIONS
    assert manager_module.instructions_for_render_policy(fingerprint(current)) == manager_module.INSTRUCTIONS_SOURCE_ALIGNMENT_V1


def test_v20_identity_changes_only_instructions_and_keeps_complete_v19_capabilities(monkeypatch):
    identities = []
    def record(value):
        identities.append(deepcopy(value))
        return encode(value)
    monkeypatch.setattr(auto, "encode", record)
    old, new = auto._contact_folio_overlap_v19_policy(), auto._source_alignment_v20_policy()
    old_identity, new_identity = identities
    assert old_identity.pop("instructions_sha256") == digest(manager_module.INSTRUCTIONS.encode())
    assert new_identity.pop("instructions_sha256") == digest(manager_module.INSTRUCTIONS_SOURCE_ALIGNMENT_V1.encode())
    assert new_identity.pop("native_source_line_map_policy") == source_lines.recipe_descriptor()
    assert old_identity == new_identity
    old_hash, new_hash = map(fingerprint, (old, new))
    for helper in (auto._source_folio_inline_direction_version, auto._proposal_repair_version,
            auto._source_folio_direction_version, auto._terminal_source_layout_versions,
            auto._emphasis_normalization_version, auto._clock_direction_version,
            auto._source_normalization_version, auto._band_normalization_version):
        assert helper(new_hash) == helper(old_hash), helper.__name__
        assert helper(new_hash) is not None
    assert auto._proposal_render_profile(new_hash) == new_hash
    assert proof.automatic_policy(proof.POLICY_V2, new_hash) == new
    assert not auto.supports_manual_layout_recovery(new)
    with pytest.raises(OrdinaryLayoutError):
        proof.automatic_policy(proof.POLICY_V2, "0" * 64)


@pytest.mark.parametrize("error", [None, "ordinary_layout_proposal_coverage", "ordinary_layout_invalid_source_footer_evidence"])
def test_initial_and_replacement_wire_changes_only_versioned_guidance_and_source_map(error):
    _, view, proposal, historical = legacy.synthetic()
    old = proof.expected_policy(1, proof.POLICY_V2, fingerprint(auto._contact_folio_overlap_v19_policy()))
    new = proof.expected_policy(1, proof.POLICY_V2, fingerprint(auto._source_alignment_v20_policy()))
    prior = None if error is None else {"intent": {"request_sha256": "1" * 64},
        "raw": encode(proposal).decode(), "validation": {"error_code": error}}
    old_request = proof.page_request(view, 1, old, prior=prior)
    pdf, frame = native_source()
    view["pages"] = [frame]
    old_request = proof.page_request(view, 1, old, prior=prior)
    new_request = proof.page_request(view, 1, new, prior=prior,
        source_pdf=pdf, source_pdf_sha256=digest(pdf))
    historical_request = proof.page_request(view, 1, historical, prior=prior)
    old_instructions = old_request.pop("instructions")
    new_instructions = new_request.pop("instructions")
    suffix = "" if error is None else proof.INSTRUCTIONS + (proof.FOOTER_CONSTRAINT_INSTRUCTIONS
        if error == "ordinary_layout_invalid_source_footer_evidence" else "")
    assert old_instructions == manager_module.INSTRUCTIONS + suffix
    assert new_instructions == manager_module.INSTRUCTIONS_SOURCE_ALIGNMENT_V1 + suffix
    new_payload = decode(new_request["prompt_text"])
    assert new_payload.pop(source_lines.KEY) == source_lines.derive_source_line_map(pdf, frame,
        expected_source_sha256=digest(pdf), selected_page_count=1)
    new_request["prompt_text"] = encode(new_payload).decode()
    assert old_request == new_request
    if prior is None:
        assert historical_request == dict(old_request, instructions=old_instructions)


@pytest.fixture(scope="module", params=["v19", "v20"])
def completed_case(request, tmp_path_factory):
    patch = pytest.MonkeyPatch()
    legacy.isolate_provider(patch)
    policy = auto._contact_folio_overlap_v19_policy() if request.param == "v19" else auto._source_alignment_v20_policy()
    case = legacy.normal_start(tmp_path_factory.mktemp(request.param), patch, page_count=1,
        saved_policy=policy,
        damage=lambda p, n, proposal, *_: legacy.invalid_decision(proposal) if n == 0 else None)
    case.saved_policy = policy
    yield case
    patch.undo()


def test_normal_start_initial_replacement_and_saved_witness_use_their_exact_recipe(completed_case):
    case = completed_case
    result = case.job["result"]["automatic_layout"]
    assert result["status"] == "automatic_unreviewed", result
    assert [page for page, _ in case.calls] == [1, 1]
    instructions = manager_module.instructions_for_render_policy(fingerprint(case.saved_policy))
    assert [request["instructions"] for _, request in case.calls] == [instructions, instructions + proof.INSTRUCTIONS]
    witness, kwargs = legacy.witness_context(case)
    _, summary = proof.verify_witness(witness, **kwargs)
    assert summary["provider_dispatch_count"] == 2
    assert witness["manifest"]["policy"][proof.RENDER_KEY] == fingerprint(case.saved_policy)
    payloads = [decode(request["input"][0]["content"][0]["text"]) for _, request in case.calls]
    if case.saved_policy == auto._source_alignment_v20_policy():
        assert payloads[0][source_lines.KEY] == payloads[1][source_lines.KEY]
        assert payloads[0][source_lines.KEY]["status"] == "available"
    else:
        assert all(source_lines.KEY not in payload for payload in payloads)


@pytest.mark.parametrize("restart", [False, True])
def test_saved_read_resume_completed_rebuild_preserve_bytes_and_spend(completed_case, restart):
    case = completed_case
    before = {p: p.read_bytes() for root in (case.operation, Path(case.baseline["run_dir"]) / "ordinary_auto_layout")
        for p in root.rglob("*") if p.is_file() and p.suffix != ".lock"}
    def forbidden(*args, **kwargs):
        pytest.fail("Saved operation attempted provider dispatch or new accounting capacity")
    manager = manager_module.OrdinaryLayoutManager(case.manager.service.root.parents[2],
        mode="shadow", workspace_id="fictional", job_resolver=case.manager.job_resolver,
        provider_factory=forbidden, accounting_factory=forbidden, suggestion_policy=forbidden) if restart else case.manager
    state = manager.service.state(case.job["job_id"])
    assert state["delivery"]["artifact_id"] == case.job["result"]["automatic_layout"]["candidate_id"]
    result = auto.run_automatic_layout(manager, case.app.state.ordinary_layouts._accounting,
        case.job["job_id"], case.saved_policy)
    rebuilt = auto.run_completed_unreviewed_rebuild(manager, case.app.state.ordinary_layouts._accounting, case.job["job_id"])
    assert result["reused_durable_candidate"] and rebuilt["reused_durable_candidate"]
    assert result["sha256"] == rebuilt["sha256"] == case.job["result"]["automatic_layout"]["sha256"]
    assert result["layout_costs"] == rebuilt["layout_costs"]
    assert len(case.calls) == 2
    assert all(p.read_bytes() == raw for p, raw in before.items())


@pytest.mark.parametrize("fault", [None, "missing_intent", "changed_instructions", "changed_source_map"])
def test_settled_recovery_is_zero_call_and_tampered_witness_rejected(completed_case, tmp_path, fault):
    case = completed_case
    operation = tmp_path / "operation"
    shutil.copytree(case.operation, operation)
    witness, kwargs = legacy.witness_context(case)
    if fault == "missing_intent":
        (operation / "attempts/page-0001/attempt-01.intent.json").unlink()
        with pytest.raises((OrdinaryLayoutError, FileNotFoundError)):
            proof.operation_witness(operation, **kwargs, restore_aliases=True, seal=True)
    elif fault in {"changed_instructions", "changed_source_map"}:
        name = "page-0001/attempt-00.intent.json"
        intent = decode(witness["records"][name])
        if fault == "changed_instructions":
            intent["request"]["instructions"] = manager_module.INSTRUCTIONS if case.saved_policy == auto._source_alignment_v20_policy() else manager_module.INSTRUCTIONS_SOURCE_ALIGNMENT_V1
        else:
            payload = decode(intent["request"]["prompt_text"])
            payload[source_lines.KEY] = {"status": "available", "lines": [{"text": "Forged source evidence"}]}
            intent["request"]["prompt_text"] = encode(payload).decode()
        with fitz.open(stream=kwargs["source_pdf"], filetype="pdf") as document:
            image = document[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).tobytes("png")
        _, intent["request_sha256"] = proof.native_request(intent["request"], image, witness["manifest"]["policy"]["model"])
        witness["records"][name] = encode(intent).decode()
        with pytest.raises(OrdinaryLayoutError):
            proof.verify_witness(witness, **kwargs)
    else:
        for name in ("page-0001.response.json", "attempts/page-0001/attempt-01.validation.json", "attempts/page-0001/selection.json"):
            (operation / name).unlink()
        restored, _, _ = proof.operation_witness(operation, **kwargs, restore_aliases=True, seal=True)
        assert restored == witness
    assert len(case.calls) == 2


@pytest.mark.parametrize("recipe", [auto._local_footer_closing_v17_policy, auto._contact_folio_v18_policy, auto._contact_folio_overlap_v19_policy])
def test_unfinished_saved_start_uses_checkpoint_recipe_under_current_v20(tmp_path, monkeypatch, recipe):
    exercise_unfinished(tmp_path, monkeypatch, recipe())


@pytest.mark.parametrize("fault", ["source", "pages", "policy", "missing"])
def test_unfinished_v19_requires_exact_checkpoint_source_pages_and_policy(tmp_path, monkeypatch, fault):
    exercise_unfinished(tmp_path, monkeypatch, auto._contact_folio_overlap_v19_policy(), fault)


def exercise_unfinished(tmp_path, monkeypatch, saved_policy, fault=None):
    original = auto.run_automatic_layout
    observations = []
    dispatches = []
    def current_start(manager, accounting, job_id, frozen_policy, **kwargs):
        # Translation has frozen/saved the historical recipe, but automatic layout
        # has not prepared or dispatched: restart now sees the current product.
        checkpoint = Path(accounting.jobs.trusted_ordinary_baseline_identity(job_id,
            runtime_mode="shadow", workspace_id="fictional")["run_dir"]) / "run_state.json"
        raw = checkpoint.read_bytes()
        with monkeypatch.context() as current:
            current.setattr(auto, "frozen_automatic_layout_policy", auto._source_alignment_v20_policy)
            provider = manager.provider_factory
            def tracked_provider(*args, **kwargs):
                client = provider(*args, **kwargs)
                create = client.create_page_response
                def tracked_create(*args, **kwargs):
                    dispatches.append(1)
                    return create(*args, **kwargs)
                client.create_page_response = tracked_create
                return client
            current.setattr(manager, "provider_factory", tracked_provider)
            if fault:
                payload = decode(raw)
                if fault == "source": payload["pdf_fingerprint"] = "0" * 64
                elif fault == "pages": payload["pages"] = {}
                elif fault == "policy": payload["settings"]["ordinary_auto_layout_policy"] = auto._source_alignment_v20_policy()
                if fault == "missing": checkpoint.unlink()
                else: checkpoint.write_bytes(encode(payload))
                before = len(dispatches)
                try:
                    if fault == "policy":
                        # The primary assembly recipe independently binds this setting.
                        # Its parser rejects the inconsistent checkpoint before layout.
                        from legalpdf_translate.checkpoint import PrimaryAssemblyRecipeError
                        with pytest.raises(PrimaryAssemblyRecipeError, match="^Invalid saved primary assembly recipe\\.$"):
                            original(manager, accounting, job_id, frozen_policy, **kwargs)
                        observations.append("invalid_primary_assembly_recipe")
                    else:
                        with pytest.raises(OrdinaryLayoutError) as rejected:
                            original(manager, accounting, job_id, frozen_policy, **kwargs)
                        assert rejected.value.code == "ordinary_layout_automatic_policy_changed"
                        observations.append(rejected.value.code)
                    assert len(dispatches) == before == 0
                finally:
                    checkpoint.write_bytes(raw)
            return original(manager, accounting, job_id, frozen_policy, **kwargs)
    monkeypatch.setattr(auto, "run_automatic_layout", current_start)
    case = legacy.normal_start(tmp_path, monkeypatch, saved_policy=saved_policy, page_count=1)
    assert case.job["result"]["automatic_layout"]["status"] == "automatic_unreviewed"
    assert len(case.calls) == 1 and case.calls[0][1]["instructions"] == manager_module.INSTRUCTIONS
    witness, kwargs = legacy.witness_context(case)
    assert proof.verify_witness(witness, **kwargs)[1]["provider_dispatch_count"] == 1
    assert witness["manifest"]["policy"][proof.RENDER_KEY] == fingerprint(saved_policy)
    assert len(dispatches) == 1
    expected = "invalid_primary_assembly_recipe" if fault == "policy" else "ordinary_layout_automatic_policy_changed"
    assert observations == ([expected] if fault else [])


# Every fixture is fictional and exercises the native PDF path without a provider.
def native_source(kind="normal"):
    with fitz.open() as document:
        page = document.new_page(width=600, height=800)
        if kind == "raster":
            raster = Image.new("RGB", (300, 400), "white")
            encoded = BytesIO(); raster.save(encoded, format="PNG")
            page.insert_image(page.rect, stream=encoded.getvalue())
        else:
            page.insert_text((45, 70), "Colored source heading", color=(0, .2, .7))
            if kind == "columns":
                page.insert_text((45, 130), "Left column first line")
                page.insert_text((330, 130), "Right column first line")
                page.insert_text((45, 150), "Left short last")
                page.insert_text((330, 150), "Right short last")
            elif kind == "centered":
                for y, text in ((130, "A genuinely centered longer line"), (150, "Short last")):
                    x = (600 - fitz.get_text_length(text, fontsize=11)) / 2
                    page.insert_text((x, y), text, fontsize=11)
            else:
                page.insert_text((65, 130), "An indented first line of source body.", color=(.2, .2, .2))
                page.insert_text((45, 150), "A longer following line stays at the leading edge.")
                page.insert_text((45, 170), "Short last line.")
            if kind == "hidden": page.insert_text((45, 210), "Hidden source", render_mode=3)
            elif kind == "transparent": page.insert_text((45, 210), "Transparent source", fill_opacity=0)
            elif kind == "stroke": page.insert_text((45, 210), "Unsupported stroke", render_mode=1)
            elif kind == "white": page.insert_text((45, 210), "White painted source", color=(1, 1, 1))
        if kind == "rotated": page.set_rotation(90)
        if kind == "crop": page.set_cropbox(fitz.Rect(10, 10, 590, 790))
        other = document.new_page(width=600, height=800)
        other.insert_text((45, 80), "A different second source page")
        raw = document.tobytes()
    with fitz.open(stream=raw, filetype="pdf") as document:
        page = document[0]
        raster = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        frame = {"page_number": 1, "width_px": raster.width, "height_px": raster.height,
            "image_sha256": digest(raster.tobytes("png")), "rotation": page.rotation,
            "render_dpi": 144, "backend": "pymupdf", "backend_version": fitz.VersionBind}
    return raw, frame


def derive(pdf, frame, count=1):
    return source_lines.derive_source_line_map(pdf, frame,
        expected_source_sha256=digest(pdf), selected_page_count=count)


@pytest.mark.parametrize("kind", ["normal", "centered", "columns", "white"])
def test_native_map_is_complete_reproducible_advisory_and_does_not_assign_targets(kind):
    pdf, frame = native_source(kind)
    frame_before = deepcopy(frame)
    result = derive(pdf, frame)
    assert result["status"] == "available"
    assert result == derive(pdf, frame) and frame == frame_before
    assert result["source_pdf_sha256"] == digest(pdf)
    assert result["frame"]["image_sha256"] == frame["image_sha256"]
    assert result["advisory"] is True and result["bounds_kind"] == "normalized_native_font_metrics"
    with fitz.open(stream=pdf, filetype="pdf") as document:
        page = document[0]
        expected = [{"line_id": f"p0001-b{b:04d}-l{n:04d}",
            "text": "".join(span["text"] for span in line["spans"]),
            "bbox": [v / (600 if i % 2 == 0 else 800) for i, v in enumerate(line["bbox"])]}
            for b, block in enumerate(page.get_text("dict", flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES, sort=False)["blocks"])
            for n, line in enumerate(block.get("lines", [])) if any(span["text"] for span in line["spans"])]
        assert result["lines"] == expected
        assert result["page_content_sha256"] == digest(page.read_contents())
    assert all(set(line) == {"line_id", "text", "bbox"} for line in result["lines"])
    result["lines"][0]["text"] = "Changed returned copy"
    assert derive(pdf, frame)["lines"] == expected


@pytest.mark.parametrize("kind,reason", [("raster", "no_native_text"),
    ("rotated", "unsupported_page_geometry"), ("crop", "unsupported_page_geometry"),
    ("hidden", "unsupported_text_visibility"), ("transparent", "unsupported_text_visibility"),
    ("stroke", "unsupported_text_visibility")])
def test_unsupported_native_maps_omit_the_entire_page(kind, reason):
    pdf, frame = native_source(kind)
    result = derive(pdf, frame)
    assert result["status"] == "unavailable" and result["reason"] == reason
    assert result["lines"] == []


@pytest.mark.parametrize("cap", ["MAX_LINES", "MAX_TEXT_CODEPOINTS", "MAX_TRACES", "MAX_PAGE_BYTES", "MAX_OPERATION_BYTES"])
def test_native_map_caps_never_return_partial_evidence(monkeypatch, cap):
    pdf, frame = native_source()
    monkeypatch.setattr(source_lines, cap, 1)
    assert derive(pdf, frame)["reason"] == "limit_exceeded"
    assert derive(pdf, frame)["lines"] == []


@pytest.mark.parametrize("fault", ["source", "page", "image", "dimensions", "dpi"])
def test_native_request_rejects_wrong_pdf_page_or_frame(fault):
    pdf, frame = native_source()
    _, view, _, _ = legacy.synthetic()
    view["pages"] = [frame]
    policy = proof.expected_policy(1, proof.POLICY_V2, fingerprint(auto._source_alignment_v20_policy()))
    expected = digest(pdf)
    if fault == "source": pdf = native_source("columns")[0]
    elif fault == "page":
        frame["page_number"] = 2
        for choice in view["decisions"]["paragraphs"]:
            choice["regions"][0]["page_number"] = 2
    elif fault == "image": frame["image_sha256"] = "0" * 64
    elif fault == "dimensions": frame["height_px"] += 1
    else: frame["render_dpi"] = 72
    with pytest.raises(OrdinaryLayoutError, match="source_line_map_(context|frame)_changed"):
        proof.page_request(view, frame["page_number"], policy, source_pdf=pdf, source_pdf_sha256=expected)


def test_native_map_is_inside_existing_native_reservation_for_initial_and_replacement():
    from legalpdf_translate.ordinary_layout_accounting import layout_accounting_policy
    from legalpdf_translate.openai_client import _request_accounting_details, _validate_dispatch_input_bound
    from types import SimpleNamespace
    pdf, frame = native_source("columns")
    _, view, proposal, _ = legacy.synthetic()
    view["pages"] = [frame]
    policy = proof.expected_policy(1, proof.POLICY_V2, fingerprint(auto._source_alignment_v20_policy()))
    limits = layout_accounting_policy().accounting_arguments()["dispatch_limits"]["openai:layout_suggestion:gpt-5.2"]
    with fitz.open(stream=pdf, filetype="pdf") as document:
        image = document[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).tobytes("png")
    for prior in (None, {"intent": {"request_sha256": "1" * 64}, "raw": encode(proposal).decode(),
            "validation": {"error_code": "ordinary_layout_proposal_coverage"}}):
        request = proof.page_request(view, 1, policy, prior=prior, source_pdf=pdf, source_pdf_sha256=digest(pdf))
        sdk, _ = proof.native_request(request, image, policy["model"])
        observed = _request_accounting_details(sdk)[1]
        _validate_dispatch_input_bound(SimpleNamespace(hard_budget=True), limits, observed)
        assert observed["input_bytes"] + limits["max_image_input_tokens"] < limits["max_input_tokens"] == 400000



def test_invalid_geometry_omits_the_whole_map(monkeypatch):
    pdf, frame = native_source()
    original = fitz.Page.get_text
    def invalid(page, *args, **kwargs):
        result = original(page, *args, **kwargs)
        if args and args[0] == "dict":
            result["blocks"][0]["lines"][0]["bbox"] = (float("nan"), 0, 10, 10)
        return result
    monkeypatch.setattr(fitz.Page, "get_text", invalid)
    result = derive(pdf, frame)
    assert result["status"] == "unavailable" and result["reason"] == "invalid_geometry" and result["lines"] == []


def test_native_optional_layer_flags_omit_the_whole_map(monkeypatch):
    pdf, frame = native_source()
    original = fitz.Page.get_texttrace
    def layered(page):
        traces = original(page)
        traces[0]["layer"] = "Optional visibility"
        return traces
    monkeypatch.setattr(fitz.Page, "get_texttrace", layered)
    result = derive(pdf, frame)
    assert result["reason"] == "unsupported_text_visibility" and result["lines"] == []


def test_request_map_cache_is_operation_local_and_replacement_reuses_exact_map(monkeypatch):
    pdf, frame = native_source()
    _, view, proposal, _ = legacy.synthetic()
    view["pages"] = [frame]
    policy = proof.expected_policy(1, proof.POLICY_V2, fingerprint(auto._source_alignment_v20_policy()))
    calls = []
    original = source_lines.derive_source_line_map
    def tracked(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(source_lines, "derive_source_line_map", tracked)
    cache = {}
    request = proof.page_request(view, 1, policy, source_pdf=pdf, source_pdf_sha256=digest(pdf), _source_line_map_cache=cache)
    prior = {"intent": {"request_sha256": "1" * 64}, "raw": encode(proposal).decode(),
        "validation": {"error_code": "ordinary_layout_proposal_coverage"}}
    replacement = proof.page_request(view, 1, policy, prior=prior, source_pdf=pdf,
        source_pdf_sha256=digest(pdf), _source_line_map_cache=cache)
    assert calls == [1]
    assert decode(request["prompt_text"])[source_lines.KEY] == decode(replacement["prompt_text"])[source_lines.KEY]
    with pytest.raises(OrdinaryLayoutError, match="source_line_map_context_changed"):
        proof.page_request(view, 1, policy, source_pdf=native_source("columns")[0],
            source_pdf_sha256=digest(pdf), _source_line_map_cache=cache)
    assert calls == [1]



def capacity_repair_case(emphasis_count=400):
    """Local-contract counterexample; not a claimed provider-produced response."""
    from docx import Document
    from legalpdf_translate.saved_docx_layout import inspect_docx, default_decisions
    from tests.test_ordinary_auto_layout_workflow import _proposal
    with fitz.open() as source:
        page = source.new_page(width=600, height=800)
        for n in range(220):
            page.insert_text((20, 20 + n * 3.4), "Ordinary source line " + str(n) + " " + "x" * 45, fontsize=2.4)
        pdf = source.tobytes()
        raster = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = raster.tobytes("png")
        frame = {"page_number": 1, "width_px": raster.width, "height_px": raster.height,
            "image_sha256": digest(image), "rotation": 0, "render_dpi": 144,
            "backend": "pymupdf", "backend_version": fitz.VersionBind}
    document = Document()
    for _ in range(10): document.add_paragraph("Fictional text word. " * 150)
    raw = BytesIO(); document.save(raw)
    snapshot = inspect_docx(raw.getvalue(), "EN")
    decisions = default_decisions(snapshot, [frame])
    for choice in decisions["paragraphs"]:
        choice["regions"] = [{"page_number": 1, "bbox_px": [0, 0, frame["width_px"], frame["height_px"]]}]
    view = {"target_lang": "EN", "paragraphs": [{key: row[key] for key in ("id", "ordinal", "text", "has_page_break")}
        for row in snapshot["paragraphs"]], "pages": [frame], "decisions": decisions}
    proposal = _proposal(view, 1)
    proposal.update(version="ordinary_layout_proposal_v3", paragraph_partitions=[],
        source_coverage_findings=[], source_layout_evidence=[])
    for choice in proposal["paragraphs"]:
        choice["emphasis"] = [{"start": 0, "end": 9, "bold": True, "italic": False, "underline": False}
            for _ in range(emphasis_count)]
    old = proof.expected_policy(1, proof.POLICY_V2, fingerprint(auto._contact_folio_overlap_v19_policy()))
    new = proof.expected_policy(1, proof.POLICY_V2, fingerprint(auto._source_alignment_v20_policy()))
    outcome = proof.validation(snapshot, view, proposal, old)
    assert outcome == {"valid": False, "error_code": "ordinary_layout_invalid_proposal_decisions"}
    assert proof.eligible(snapshot, view, proposal, old, outcome["error_code"])
    assert len(encode(proposal)) < 2 * 1024 * 1024 and emphasis_count <= 1000
    prior = {"intent": {"request_sha256": "1" * 64}, "raw": encode(proposal).decode(), "validation": outcome}
    return pdf, image, view, old, new, prior


def native_bound(request, image, model):
    from legalpdf_translate.ordinary_layout_accounting import layout_accounting_policy
    from legalpdf_translate.openai_client import _request_accounting_details
    sdk, _ = proof.native_request(request, image, model)
    observed = _request_accounting_details(sdk)[1]
    limits = layout_accounting_policy().accounting_arguments()["dispatch_limits"][f"openai:layout_suggestion:{model}"]
    return observed, limits


def test_optional_map_never_consumes_an_admitted_large_same_page_replacement(monkeypatch):
    from legalpdf_translate.openai_client import _validate_dispatch_input_bound
    from types import SimpleNamespace
    pdf, image, view, old, new, prior = capacity_repair_case()
    assert sum(len(row["text"]) for row in view["paragraphs"]) == 31500
    kwargs = {"source_pdf": pdf, "source_pdf_sha256": digest(pdf)}
    historical = proof.page_request(view, 1, old, prior=prior)
    old_observed, limits = native_bound(historical, image, old["model"])
    _validate_dispatch_input_bound(SimpleNamespace(hard_budget=True), limits, old_observed)
    initial = proof.page_request(view, 1, new, **kwargs)
    source_map = decode(initial["prompt_text"])[source_lines.KEY]
    assert source_map["status"] == "available" and len(source_map["lines"]) == 220
    with monkeypatch.context() as unmitigated:
        unmitigated.setattr(proof, "_within_existing_input_bound", lambda *args: True)
        oversized = proof.page_request(view, 1, new, prior=prior, **kwargs)
    oversized_observed, _ = native_bound(oversized, image, new["model"])
    assert oversized_observed["input_bytes"] + limits["max_image_input_tokens"] > limits["max_input_tokens"]
    replacement = proof.page_request(view, 1, new, prior=prior, **kwargs)
    reduced = decode(replacement["prompt_text"])[source_lines.KEY]
    assert reduced == {**source_map, "status": "unavailable", "reason": "request_capacity", "lines": []}
    observed, _ = native_bound(replacement, image, new["model"])
    _validate_dispatch_input_bound(SimpleNamespace(hard_budget=True), limits, observed)
    assert replacement["response_format"] == historical["response_format"]
    # Independent reconstruction follows the same completed-envelope derivation.
    assert replacement == proof.page_request(view, 1, new, prior=deepcopy(prior), **kwargs)
    assert initial == proof.page_request(view, 1, new, **kwargs)
    assert proof.native_request(replacement, image, new["model"])[1] == proof.native_request(
        proof.page_request(view, 1, new, prior=deepcopy(prior), **kwargs), image, new["model"])[1]
    assert source_map == decode(initial["prompt_text"])[source_lines.KEY]
    assert len(encode({"initial": initial, "replacement": replacement, "failed_response": prior["raw"]})) < 8 * 1024 * 1024


def test_capacity_fallback_preserves_guard_when_base_replacement_is_already_too_large():
    from legalpdf_translate.openai_client import _validate_dispatch_input_bound
    from types import SimpleNamespace
    pdf, image, view, old, new, prior = capacity_repair_case(emphasis_count=600)
    for policy in (old, new):
        request = proof.page_request(view, 1, policy, prior=prior, source_pdf=pdf, source_pdf_sha256=digest(pdf))
        if policy is new:
            evidence = decode(request["prompt_text"])[source_lines.KEY]
            assert evidence["status"] == "unavailable" and evidence["reason"] == "request_capacity" and evidence["lines"] == []
        observed, limits = native_bound(request, image, policy["model"])
        with pytest.raises(ValueError, match="reserved input token upper bound"):
            _validate_dispatch_input_bound(SimpleNamespace(hard_budget=True), limits, observed)
