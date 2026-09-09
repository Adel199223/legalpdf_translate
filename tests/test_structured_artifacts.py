from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from legalpdf_translate import structured_artifacts as artifacts
from legalpdf_translate.document_structure import PageStructure, StructureBlock, text_sha256


IDENTITY = {"protocol": "legal_blocks_v2", "fingerprint": "a" * 64}
PAGE_FINGERPRINT = "c" * 64


def pair():
    source = PageStructure(page_number=1, source_sha256=text_sha256("Aviso\n"),
        source_text_sha256=text_sha256("Aviso\n"), source_file_sha256="b" * 64,
        blocks=[StructureBlock("p0001_b0001", "Aviso"),
                StructureBlock("p0001_b0002", "", role="table_cell", table_id="t1", row=0, col=0)])
    target = source.to_dict()
    target["blocks"][0]["text"] = "Notice"
    target["translation_sha256"] = text_sha256("Notice\n")
    return source, target


def publish(folder: Path, **kwargs):
    source, target = pair()
    return artifacts.publish_structured_page(folder, source_structure=source,
        translated_structure=target, translated_text="Notice\n",
        protocol_identity=IDENTITY, page_fingerprint=PAGE_FINGERPRINT, **kwargs)


def test_commit_is_last_complete_content_free_and_idempotent(tmp_path):
    record = publish(tmp_path)
    assert set(path.name for path in tmp_path.glob("page_*")) == {
        "page_0001.txt", "page_0001.source_structure.json", "page_0001.structure.json", "page_0001.commit.json"}
    assert "Notice" not in json.dumps(record) and "Aviso" not in json.dumps(record)
    assert record == artifacts.validate_structured_page(tmp_path, 1, protocol_identity=IDENTITY,
        page_fingerprint=PAGE_FINGERPRINT, expected_commit=record)
    before = {path.name: path.read_bytes() for path in tmp_path.glob("page_*")}
    assert publish(tmp_path) == record
    assert before == {path.name: path.read_bytes() for path in tmp_path.glob("page_*")}


@pytest.mark.parametrize("name", ["page_0001.txt", "page_0001.source_structure.json", "page_0001.structure.json", "page_0001.commit.json"])
@pytest.mark.parametrize("damage", ["missing", "changed"])
def test_stale_or_missing_artifacts_cannot_resume(tmp_path, name, damage):
    record = publish(tmp_path)
    path = tmp_path / name
    if damage == "missing":
        path.unlink()
    else:
        path.write_text("private stale content", encoding="utf-8")
    with pytest.raises(artifacts.StructuredArtifactError) as caught:
        artifacts.validate_structured_page(tmp_path, 1, protocol_identity=IDENTITY, expected_commit=record)
    assert "private" not in str(caught.value)


@pytest.mark.parametrize("step", [1, 2, 3, 4])
def test_interrupted_publication_never_has_a_valid_commit(tmp_path, monkeypatch, step):
    original = artifacts._publish_file_exclusive
    calls = 0
    def interrupted(path, content):
        nonlocal calls
        calls += 1
        if calls == step:
            raise OSError("synthetic disk failure")
        return original(path, content)
    monkeypatch.setattr(artifacts, "_publish_file_exclusive", interrupted)
    with pytest.raises(OSError):
        publish(tmp_path)
    with pytest.raises(artifacts.StructuredArtifactError):
        artifacts.validate_structured_page(tmp_path, 1, protocol_identity=IDENTITY)
    assert not (tmp_path / "page_0001.commit.json").exists()


def test_lone_txt_is_preserved_not_upgraded_or_overwritten(tmp_path):
    path = tmp_path / "page_0001.txt"
    path.write_text("old saved translation", encoding="utf-8")
    with pytest.raises(artifacts.StructuredArtifactError):
        publish(tmp_path)
    assert path.read_text(encoding="utf-8") == "old saved translation"
    assert len(list(tmp_path.glob("page_*"))) == 1


@pytest.mark.parametrize("change", ["source_hash", "source_file", "target_hash", "geometry", "role", "missing", "duplicate", "extra", "empty", "text_join"])
def test_invalid_pair_is_rejected_before_any_write(tmp_path, change):
    source, target = pair()
    text = "Notice\n"
    if change == "source_hash": source.source_sha256 = "d" * 64
    elif change == "source_file": target["source_file_sha256"] = "d" * 64
    elif change == "target_hash": target["translation_sha256"] = "d" * 64
    elif change == "geometry": target["blocks"][0]["bbox"] = [1, 2, 3, 4]
    elif change == "role": target["blocks"][0]["role"] = "heading"
    elif change == "missing": target["blocks"].pop()
    elif change == "duplicate": target["blocks"].append(deepcopy(target["blocks"][0]))
    elif change == "extra": target["blocks"].append({**target["blocks"][0], "id": "p0001_b0003"})
    elif change == "empty":
        target["blocks"][0]["text"] = ""
        text = "\n"
        target["translation_sha256"] = text_sha256(text)
    elif change == "text_join": text = "Notice"
    folder = tmp_path / "absent"
    with pytest.raises(artifacts.StructuredArtifactError):
        artifacts.publish_structured_page(folder, source_structure=source, translated_structure=target,
            translated_text=text, protocol_identity=IDENTITY, page_fingerprint=PAGE_FINGERPRINT)
    assert not folder.exists()


@pytest.mark.parametrize("where", ["protocol", "page", "expected_commit"])
def test_identity_mismatch_does_not_mutate_evidence(tmp_path, where):
    record = publish(tmp_path)
    before = {path.name: path.read_bytes() for path in tmp_path.glob("page_*")}
    kwargs = {"protocol_identity": IDENTITY, "page_fingerprint": PAGE_FINGERPRINT, "expected_commit": record}
    if where == "protocol": kwargs["protocol_identity"] = {**IDENTITY, "fingerprint": "d" * 64}
    elif where == "page": kwargs["page_fingerprint"] = "d" * 64
    else: kwargs["expected_commit"] = {**record, "page_fingerprint": "d" * 64}
    with pytest.raises(artifacts.StructuredArtifactError):
        artifacts.validate_structured_page(tmp_path, 1, **kwargs)
    assert before == {path.name: path.read_bytes() for path in tmp_path.glob("page_*")}


def test_cancellation_before_publication_creates_no_folder(tmp_path):
    folder = tmp_path / "absent"
    with pytest.raises(artifacts.StructuredArtifactCancelled):
        publish(folder, cancelled=lambda: True)
    assert not folder.exists()


def test_cancellation_between_files_leaves_no_commit(tmp_path):
    checks = 0
    def cancelled():
        nonlocal checks
        checks += 1
        return checks >= 3
    with pytest.raises(artifacts.StructuredArtifactCancelled):
        publish(tmp_path, cancelled=cancelled)
    assert not (tmp_path / "page_0001.commit.json").exists()


def test_duplicate_commit_json_keys_are_rejected(tmp_path):
    publish(tmp_path)
    path = tmp_path / "page_0001.commit.json"
    path.write_text(path.read_text(encoding="utf-8").replace('"version":2', '"version":2,"version":2'), encoding="utf-8")
    with pytest.raises(artifacts.StructuredArtifactError):
        artifacts.validate_structured_page(tmp_path, 1, protocol_identity=IDENTITY)


def test_identical_text_at_distinct_source_ids_and_empty_cells_are_valid(tmp_path):
    source, target = pair()
    source.blocks.insert(1, StructureBlock("p0001_b0003", "Aviso"))
    source.source_sha256 = source.source_text_sha256 = text_sha256("Aviso\nAviso\n")
    target = source.to_dict()
    target["blocks"][0]["text"] = target["blocks"][1]["text"] = "Notice"
    target["translation_sha256"] = text_sha256("Notice\nNotice\n")
    record = artifacts.publish_structured_page(tmp_path, source_structure=source,
        translated_structure=target, translated_text="Notice\nNotice\n",
        protocol_identity=IDENTITY, page_fingerprint=PAGE_FINGERPRINT)
    assert artifacts.validate_structured_page(tmp_path, 1, expected_commit=record) == record


@pytest.mark.parametrize("location", ["page", "block"])
def test_unknown_schema_extension_is_not_silently_discarded(tmp_path, location):
    source, target = pair()
    if location == "page": target["future_geometry"] = "unrecognized"
    else: target["blocks"][0]["future_geometry"] = "unrecognized"
    folder = tmp_path / "absent"
    with pytest.raises(artifacts.StructuredArtifactError, match="unsupported_structure_fields"):
        artifacts.publish_structured_page(folder, source_structure=source, translated_structure=target,
            translated_text="Notice\n", protocol_identity=IDENTITY, page_fingerprint=PAGE_FINGERPRINT)
    assert not folder.exists()


def test_wrong_page_and_path_traversal_commit_are_rejected(tmp_path):
    record = publish(tmp_path)
    with pytest.raises(artifacts.StructuredArtifactError):
        artifacts.validate_commit_record(record, page_number=2)
    record["artifacts"]["source"]["name"] = "../private.json"
    with pytest.raises(artifacts.StructuredArtifactError):
        artifacts.validate_commit_record(record)


def test_exclusive_publication_preserves_file_created_during_dispatch(tmp_path, monkeypatch):
    original = artifacts._publish_file_exclusive
    def intervening_write(path, content):
        path.write_text("external retained edit", encoding="utf-8")
        original(path, content)
    monkeypatch.setattr(artifacts, "_publish_file_exclusive", intervening_write)
    with pytest.raises(FileExistsError):
        publish(tmp_path)
    assert (tmp_path / "page_0001.txt").read_text(encoding="utf-8") == "external retained edit"
    assert not list(tmp_path.glob(".structured-*"))
    assert not (tmp_path / "page_0001.commit.json").exists()


def test_read_limits_apply_before_artifact_parsing(tmp_path, monkeypatch):
    publish(tmp_path)
    monkeypatch.setattr(artifacts, "_MAX_COMMIT_BYTES", 1)
    with pytest.raises(artifacts.StructuredArtifactError, match="oversized"):
        artifacts.validate_structured_page(tmp_path, 1)


@pytest.mark.parametrize("edited", [False, True])
def test_explicit_rebuild_allows_only_txt_edit_and_preserves_original_commit(tmp_path, edited):
    commit = publish(tmp_path)
    if edited:
        (tmp_path / "page_0001.txt").write_text("Human revision with João intact.", encoding="utf-8")
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    result, changed = artifacts.validate_structured_rebuild_page(tmp_path, 1,
        protocol_identity=IDENTITY, expected_commit=commit)
    assert result == commit and changed is edited
    assert before == {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    if edited:
        with pytest.raises(artifacts.StructuredArtifactError):
            artifacts.validate_structured_page(tmp_path, 1, expected_commit=commit)
    else:
        assert artifacts.validate_structured_page(tmp_path, 1, expected_commit=commit) == commit


@pytest.mark.parametrize("kind", ["source", "target", "commit"])
@pytest.mark.parametrize("damage", ["missing", "changed"])
def test_manual_txt_edit_cannot_excuse_missing_or_tampered_other_proof(tmp_path, kind, damage):
    commit = publish(tmp_path)
    (tmp_path / "page_0001.txt").write_text("Human revision", encoding="utf-8")
    path = tmp_path / artifacts._names(1)[kind]
    if damage == "missing":
        path.unlink()
    else:
        path.write_text("{}", encoding="utf-8")
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    with pytest.raises(artifacts.StructuredArtifactError):
        artifacts.validate_structured_rebuild_page(tmp_path, 1,
            protocol_identity=IDENTITY, expected_commit=commit)
    assert before == {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}


@pytest.mark.parametrize("damage", ["missing", "invalid_utf8", "oversized"])
def test_rebuild_does_not_reconstruct_missing_or_unreadable_txt(tmp_path, monkeypatch, damage):
    commit = publish(tmp_path)
    path = tmp_path / "page_0001.txt"
    if damage == "missing":
        path.unlink()
    elif damage == "invalid_utf8":
        path.write_bytes(b"\xff")
    else:
        path.write_text("x" * 10000, encoding="utf-8")
        original = artifacts._read_file
        def bounded(path, **kwargs):
            return original(path, maximum=1000 if path.suffix == ".txt" else kwargs.get("maximum", 8 * 1024 * 1024))
        monkeypatch.setattr(artifacts, "_read_file", bounded)
    with pytest.raises(artifacts.StructuredArtifactError):
        artifacts.validate_structured_rebuild_page(tmp_path, 1, expected_commit=commit)


@pytest.mark.parametrize("guard", ["no_checkpoint_commit", "wrong_checkpoint", "wrong_protocol", "wrong_page"])
def test_rebuild_requires_bound_checkpoint_commit_not_an_orphan_txt(tmp_path, guard):
    commit = publish(tmp_path)
    kwargs = {"expected_commit": commit, "protocol_identity": IDENTITY}
    if guard == "no_checkpoint_commit":
        kwargs["expected_commit"] = None
    elif guard == "wrong_checkpoint":
        kwargs["expected_commit"] = {**commit, "translation_sha256": "d" * 64}
    elif guard == "wrong_protocol":
        kwargs["protocol_identity"] = {**IDENTITY, "fingerprint": "d" * 64}
    with pytest.raises(artifacts.StructuredArtifactError):
        artifacts.validate_structured_rebuild_page(tmp_path, 2 if guard == "wrong_page" else 1, **kwargs)


def test_rebuild_rechecks_original_txt_binding_even_when_all_local_artifact_hashes_match(tmp_path):
    commit = publish(tmp_path)
    commit["artifacts"]["text"]["sha256"] = "d" * 64
    commit["bundle_sha256"] = artifacts._hash(artifacts._json(
        {key: value for key, value in commit.items() if key != "bundle_sha256"}))
    (tmp_path / "page_0001.commit.json").write_bytes(artifacts._json(commit))
    with pytest.raises(artifacts.StructuredArtifactError, match="commit_source_binding_mismatch"):
        artifacts.validate_structured_rebuild_page(tmp_path, 1, expected_commit=commit)
