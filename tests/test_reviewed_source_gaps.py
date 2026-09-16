"""Explicit reviewed source gaps; historical capped profiles stay unchanged."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from legalpdf_translate.reviewed_formatting import SOURCE_GAP_POLICY, ReviewedFormattingError
from legalpdf_translate.reviewed_formatting_writer import (
    build_reviewed_docx, validate_reviewed_docx, ReviewedFormattingWriterError,
)
from tests.test_reviewed_formatting import packet, validate
from tests.test_reviewed_formatting_v2 import region_packet


@pytest.mark.parametrize("columns", [False,True])
def test_source_gap_profile_keeps_large_declared_gaps_without_font_fitting(columns):
    manifest,page=region_packet(columns=columns)
    before=deepcopy((manifest,page))
    capped=build_reviewed_docx(validate(manifest,page))
    manifest["spacing_policy"]=SOURCE_GAP_POLICY
    projection=validate(manifest,page)
    artifact=build_reviewed_docx(projection)
    validate_reviewed_docx(artifact.docx_bytes,artifact.source_map_bytes,projection=projection)
    mapping=json.loads(artifact.source_map_bytes)
    assert mapping["spacing_policy"]==SOURCE_GAP_POLICY
    old=json.loads(capped.source_map_bytes)
    changed=False
    for original,current in zip(old["pages"][0]["fragments"],mapping["pages"][0]["fragments"]):
        left,right=original["spacing"],current["spacing"]
        assert right["basis"]==SOURCE_GAP_POLICY and not right["gap_capped"]
        assert abs(right["space_before_pt"]-right["source_gap_pt"]) <= .025001
        assert right["source_gap_pt"]==left["source_gap_pt"]
        changed |= right["space_before_pt"]>48
        for field in ("source_range","target_range","source_text_sha256","target_text_sha256"):
            assert current[field]==original[field]
    assert changed
    # Removing only this selection reproduces the old semantic source map.
    # ZIP timestamps can change the DOCX hash across separate builds.
    manifest.pop("spacing_policy")
    assert (manifest,page)==before
    rebuilt=json.loads(build_reviewed_docx(validate(manifest,page)).source_map_bytes)
    old.pop("docx_sha256")
    rebuilt.pop("docx_sha256")
    assert rebuilt==old


@pytest.mark.parametrize("policy", [None,False,[],{},"fit_to_page","other"])
def test_unrecognized_explicit_spacing_policy_rejected(policy):
    manifest,page=region_packet()
    manifest["spacing_policy"]=policy
    with pytest.raises(ReviewedFormattingError): validate(manifest,page)


def test_v1_cannot_acquire_reviewed_gap_policy():
    manifest,page=packet()
    original=validate(manifest,page)
    manifest["spacing_policy"]=SOURCE_GAP_POLICY
    with pytest.raises(ReviewedFormattingError): validate(manifest,page)
    with pytest.raises(ReviewedFormattingWriterError):
        build_reviewed_docx(replace(original,spacing_policy=SOURCE_GAP_POLICY))


def test_checker_rejects_restoring_a_cap_or_swapping_gap_policy():
    manifest,page=region_packet(columns=True)
    manifest["spacing_policy"]=SOURCE_GAP_POLICY
    projection=validate(manifest,page)
    artifact=build_reviewed_docx(projection)
    with pytest.raises(ReviewedFormattingWriterError):
        validate_reviewed_docx(artifact.docx_bytes,artifact.source_map_bytes,
                              projection=replace(projection,spacing_policy=None))
    mapping=json.loads(artifact.source_map_bytes)
    row=next(f for f in mapping["pages"][0]["fragments"] if f["spacing"]["space_before_pt"]>48)
    row["spacing"]["space_before_pt"]=48
    with pytest.raises(ReviewedFormattingWriterError):
        validate_reviewed_docx(artifact.docx_bytes,json.dumps(mapping).encode(),projection=projection)
