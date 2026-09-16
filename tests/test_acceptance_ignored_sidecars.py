"""Explicit unused-sidecar proof at real assembly boundaries; synthetic only."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace

import pytest

from legalpdf_translate import acceptance_assembly as mixed
from legalpdf_translate import acceptance_formatting as formatted
from legalpdf_translate.document_structure import PageStructure, StructureBlock
from legalpdf_translate.docx_writer import assemble_docx
from legalpdf_translate.formatting_support import digest_text, fingerprint
from legalpdf_translate.reviewed_formatting_writer import build_reviewed_docx
from legalpdf_translate.structured_artifacts import StructuredArtifactError, publish_structured_page
from legalpdf_translate.types import TargetLang
from tests.test_reviewed_formatting import packet
from tests.test_reviewed_formatting_v2 import region_packet


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


@pytest.fixture(params=["mixed", "reviewed_v1", "reviewed_v2"])
def case(tmp_path, request):
    mode = request.param
    if mode == "mixed":
        text = "Decisão fictícia.\nPedido admitido."
        source = PageStructure(1, digest_text(text), [StructureBlock("p0001_b0001", text, uncertain=True)],
            source_text_sha256=digest_text(text), source_file_sha256="a" * 64, uncertain=True).to_dict()
        target = deepcopy(source)
        target["blocks"][0]["text"] = "Décision fictive.\nDemande admise."
        target["translation_sha256"] = digest_text(target["blocks"][0]["text"])
    else:
        manifest, page = region_packet(columns=True) if mode == "reviewed_v2" else packet()
        source, target = deepcopy(page.source_structure), deepcopy(page.target_structure)
    folder = tmp_path / "original"
    record = publish_structured_page(folder, source_structure=source, translated_structure=target,
        translated_text=target["blocks"][0]["text"],
        protocol_identity={"protocol": "legal_blocks_v2", "fingerprint": "b" * 64},
        page_fingerprint="c" * 64)
    commit_hash = sha((folder / "page_0001.commit.json").read_bytes())
    refs = [mixed.PageBundleRef(folder, record, commit_hash, "e" * 64)]
    args = dict(page_bundles=refs, full_case_pages=[1], source_file_sha256="a" * 64,
        lang=TargetLang.FR, preferences_sha256="d" * 64, output_dir=tmp_path / "assembled")
    if mode != "mixed":
        manifest["pages"][0].update(commit_file_sha256=commit_hash, bundle_sha256=record["bundle_sha256"],
            source_structure_sha256=fingerprint(source), target_structure_sha256=fingerprint(target))
        raw = encode(manifest)
        args.update(formatting_manifest=raw, expected_manifest_sha256=sha(raw),
                    source_images=(page.source_image_bytes,))
    result = SimpleNamespace(mode=mode, args=args, folder=folder)
    rebind(result)
    return result


def binding(case):
    keys = ("page_bundles", "full_case_pages", "source_file_sha256", "lang", "preferences_sha256")
    values = {key: case.args[key] for key in keys}
    if case.mode == "mixed":
        return mixed.assembly_binding(**values)
    return formatted.partition_assembly_binding(**values,
        formatting_manifest_sha256=case.args["expected_manifest_sha256"])


def rebind(case):
    expected = binding(case)
    case.args["evidence_guard"] = lambda: deepcopy(expected)


def pin(case, suffixes=("layout.json", "layout_eligibility.json")):
    pins = []
    for suffix in suffixes:
        name = "page_0001." + suffix
        content = encode({"unused_derivative": suffix, "text": "MUST NEVER BECOME TRANSLATION CONTENT"})
        (case.folder / name).write_bytes(content)
        pins.append((name, sha(content)))
    case.args["page_bundles"][0] = replace(case.args["page_bundles"][0],
        ignored_layout_sidecars=tuple(sorted(pins)))
    rebind(case)


def run(case, *, action=None):
    if action is None:
        builder = mixed.assemble_mixed_case if case.mode == "mixed" else formatted.assemble_reviewed_partition_case
        return builder(**case.args)
    if case.mode == "mixed":
        def writer(folder, output, **kwargs):
            result = assemble_docx(folder, output, **kwargs)
            action(folder)
            return result
        return mixed.assemble_mixed_case(**case.args, writer=writer)
    def writer(projection):
        result = build_reviewed_docx(projection)
        action(case.args["output_dir"] / "pages")
        return result
    return formatted.assemble_reviewed_partition_case(**case.args, writer=writer)


def original_binding(case, value):
    return value if case.mode == "mixed" else value["original_case"]


@pytest.mark.parametrize("suffixes", [("layout.json",), ("layout_eligibility.json",),
                                     ("layout.json", "layout_eligibility.json")])
def test_pinned_unused_sidecars_remain_in_originals_and_never_enter_four_artifact_staging(case, suffixes):
    pin(case, suffixes)
    before = {path.name: path.read_bytes() for path in case.folder.iterdir()}
    refs_before = deepcopy(case.args["page_bundles"])
    observed = []
    output = run(case, action=lambda folder: observed.append({path.name for path in folder.iterdir()}))
    expected = {"page_0001." + suffix for suffix in ("txt", "source_structure.json", "structure.json", "commit.json")}
    assert observed == [expected]
    assert {path.name: path.read_bytes() for path in case.folder.iterdir()} == before
    assert case.args["page_bundles"] == refs_before
    assert {path.name for path in (output.parent / "pages").iterdir()} == expected
    assert all((output.parent / "pages" / name).read_bytes() == before[name] for name in expected)
    report = json.loads((output.parent / "assembly.json").read_bytes())
    retained = report["ignored_layout_sidecars"]
    assert retained["retained_in_original_locations"] is True
    assert retained["used_for_assembly"] is False and retained["copied_to_staging"] is False
    assert retained["pages"][0]["files"] == [
        {"name": name, "sha256": digest} for name, digest in refs_before[0].ignored_layout_sidecars]
    row = original_binding(case, report["binding"])["pages"][0]
    assert row["ignored_layout_sidecars"]["policy"] == retained["policy"]
    assert row["ignored_layout_sidecars"]["files"] == retained["pages"][0]["files"]
    assert report["original_commits"] == [ref.expected_commit for ref in refs_before]
    assert report["provider_dispatch_count"] == 0 and report["assembly_cost_usd"] == "0"
    assert report["workflow_resumed"] is False


def test_empty_default_keeps_original_binding_and_output_metadata_schema(case):
    ref = case.args["page_bundles"][0]
    assert ref.ignored_layout_sidecars == ()
    expected = {"version": "mixed_structured_case_assembly_v1", "full_case_pages": [1],
        "source_file_sha256": "a" * 64, "target_lang": "FR", "preferences_sha256": "d" * 64,
        "pages": [{"page_number": 1, "commit_file_sha256": ref.commit_file_sha256,
            "bundle_sha256": ref.expected_commit["bundle_sha256"], "evidence_identity_sha256": "e" * 64}]}
    assert original_binding(case, binding(case)) == expected
    output = run(case)
    assert "ignored_layout_sidecars" not in json.loads((output.parent / "assembly.json").read_bytes())


@pytest.mark.parametrize("suffix", ["layout.json", "layout_eligibility.json"])
def test_default_still_rejects_unbound_sidecars(case, suffix):
    (case.folder / ("page_0001." + suffix)).write_bytes(b"{}")
    with pytest.raises(StructuredArtifactError, match="unbound_layout"):
        run(case)
    assert not case.args["output_dir"].exists()


def test_sidecar_pins_are_part_of_external_source_evidence_guard(case):
    before = case.args["evidence_guard"]
    pin(case)
    case.args["evidence_guard"] = before
    with pytest.raises(StructuredArtifactError, match="historical_binding"):
        run(case)
    assert not case.args["output_dir"].exists()


@pytest.mark.parametrize("value", [None, [], (("page_0001.layout.json", "x"),),
    (("../page_0001.layout.json", "a" * 64),), (("page_0002.layout.json", "a" * 64),),
    (("page_0001.structure.json", "a" * 64),), (("*.layout.json", "a" * 64),),
    (("page_0001.layout.json", "a" * 64), ("page_0001.layout.json", "a" * 64)),
    (("page_0001.layout_eligibility.json", "a" * 64), ("page_0001.layout.json", "a" * 64)),
    (["page_0001.layout.json", "a" * 64],)])
def test_allowlist_is_immutable_exact_page_names_unique_sorted_and_hash_bound(case, value):
    case.args["page_bundles"][0] = replace(case.args["page_bundles"][0], ignored_layout_sidecars=value)
    with pytest.raises(StructuredArtifactError, match="invalid_ignored_layout"):
        run(case)
    assert not case.args["output_dir"].exists()


@pytest.mark.parametrize("action", ["modify", "remove", "add_other", "wrong_hash"])
def test_pinned_sidecar_inventory_must_match_before_output(case, action):
    pin(case, ("layout.json",))
    path = case.folder / "page_0001.layout.json"
    if action == "remove":
        path.unlink()
    elif action == "modify":
        path.write_bytes(path.read_bytes() + b"changed")
    elif action == "add_other":
        (case.folder / "page_0001.layout_eligibility.json").write_bytes(b"{}")
    else:
        case.args["page_bundles"][0] = replace(case.args["page_bundles"][0],
            ignored_layout_sidecars=((path.name, "f" * 64),))
        rebind(case)
    with pytest.raises(StructuredArtifactError):
        run(case)
    assert not case.args["output_dir"].exists()


@pytest.mark.parametrize("phase", [1, 2, 4, 6])
def test_bound_sidecar_changes_across_source_guard_phases_fail_without_success_marker(case, phase):
    pin(case)
    original_guard, calls = case.args["evidence_guard"], 0
    def guard():
        nonlocal calls
        calls += 1
        if calls == phase:
            path = case.folder / "page_0001.layout.json"
            path.write_bytes(path.read_bytes() + b"changed")
        return original_guard()
    case.args["evidence_guard"] = guard
    with pytest.raises(StructuredArtifactError):
        run(case)
    assert not (case.args["output_dir"] / "assembly.json").exists()


@pytest.mark.parametrize("action", ["modify", "remove", "add_other"])
def test_sidecars_cannot_change_or_appear_during_writer(case, action):
    pin(case, ("layout.json",))
    def change(_):
        path = case.folder / "page_0001.layout.json"
        if action == "remove":
            path.unlink()
        elif action == "modify":
            path.write_bytes(b"changed")
        else:
            (case.folder / "page_0001.layout_eligibility.json").write_bytes(b"{}")
    with pytest.raises(StructuredArtifactError):
        run(case, action=change)
    assert not (case.args["output_dir"] / "assembly.json").exists()


@pytest.mark.parametrize("suffix", ["layout.json", "layout_eligibility.json"])
def test_pins_never_authorize_staged_sidecars_even_with_identical_bytes(case, suffix):
    pin(case)
    def change(folder):
        name = "page_0001." + suffix
        (folder / name).write_bytes((case.folder / name).read_bytes())
    with pytest.raises(StructuredArtifactError, match="unexpected_staged"):
        run(case, action=change)
    assert not (case.args["output_dir"] / "assembly.json").exists()


def test_pinned_layout_file_must_be_a_regular_file_not_a_directory(case):
    pin(case, ("layout.json",))
    path = case.folder / "page_0001.layout.json"
    path.unlink()
    path.mkdir()
    with pytest.raises(StructuredArtifactError):
        run(case)
    assert not case.args["output_dir"].exists()


def test_pinned_sidecar_hash_does_not_authorize_a_symbolic_link(case):
    pin(case, ("layout.json",))
    path = case.folder / "page_0001.layout.json"
    retained = case.folder.parent / "linked_layout.json"
    retained.write_bytes(path.read_bytes())
    path.unlink()
    try:
        path.symlink_to(retained)
    except OSError:
        pytest.skip("Host does not permit symbolic links in the synthetic workspace.")
    with pytest.raises(StructuredArtifactError):
        run(case)
    assert not case.args["output_dir"].exists()


def test_sidecar_size_is_bounded_even_when_its_hash_is_correct(case):
    path = case.folder / "page_0001.layout.json"
    raw = b"x" * (8 * 1024 * 1024 + 1)
    path.write_bytes(raw)
    case.args["page_bundles"][0] = replace(case.args["page_bundles"][0],
        ignored_layout_sidecars=((path.name, sha(raw)),))
    rebind(case)
    with pytest.raises(StructuredArtifactError, match="oversized"):
        run(case)
    assert not case.args["output_dir"].exists()


def test_sidecar_opt_in_never_weakens_original_commit_proof(case):
    pin(case)
    path = case.folder / "page_0001.txt"
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(StructuredArtifactError):
        run(case)
    assert not case.args["output_dir"].exists()
