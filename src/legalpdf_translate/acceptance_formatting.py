"""Exclusive offline assembly using a separately image-reviewed partition.

The caller authenticates historical source/language/preferences evidence and
the exact reviewed manifest. This seam authenticates physical original bundles,
revalidates the partition against actual images, and checks the produced OOXML.
It neither reclassifies original source geometry nor certifies rendered layout.
No ordinary setting, provider, native application or saved original is changed.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from pathlib import Path

from .acceptance_assembly import (
    AcceptanceAssemblyError, PageBundleRef, assembly_binding, _directory,
    _digest, _read_bundle, _committed_contents, _ignored_layout_metadata,
)
from .reviewed_formatting import FormattingPageInput, validate_reviewed_formatting
from .structured_artifacts import (
    _decode, _hash_value, _json, _names, _publish_file_exclusive, _read_file,
)
from .types import TargetLang

VERSION = 'reviewed_partition_case_assembly_v1'


def partition_assembly_binding(page_bundles: Sequence[PageBundleRef], *,
        full_case_pages: Sequence[int], source_file_sha256: str, lang: TargetLang,
        preferences_sha256: str, formatting_manifest_sha256: str) -> dict:
    """Exact expected caller-guard result, not an authorization by itself."""
    if not _hash_value(formatting_manifest_sha256):
        raise AcceptanceAssemblyError('formatting_invalid_manifest_hash')
    original = assembly_binding(page_bundles, full_case_pages=full_case_pages,
        source_file_sha256=source_file_sha256, lang=lang, preferences_sha256=preferences_sha256)
    return {'version': VERSION, 'original_case': original,
            'formatting_manifest_sha256': formatting_manifest_sha256}


def _provenance(refs, originals, *, lang, preferences_sha256):
    # Recovery commits must retain their exact original protocol identities;
    # the new layout manifest is not a replacement for recovery provenance.
    for ref, content in zip(refs, originals):
        record = ref.expected_commit
        recovery = _decode(content['target']).get('metadata', {}).get('recovery')
        if recovery is not None and (not isinstance(recovery, dict)
                or recovery.get('lang') != lang.value
                or recovery.get('preferences_sha256') != preferences_sha256):
            raise AcceptanceAssemblyError('formatting_recovery_language_or_preferences_mismatch')
        if record['protocol_identity']['protocol'] != 'legal_blocks_v2':
            if (not isinstance(recovery, dict)
                    or recovery.get('version') != record['protocol_identity']['protocol']
                    or _digest(_json(recovery)) != record['protocol_identity']['fingerprint']
                    or _digest(_json({'recovery': record['protocol_identity'], 'page': record['page_number']}))
                        != record['page_fingerprint'] or record.get('page_result') is not None):
                raise AcceptanceAssemblyError('formatting_recovery_provenance_mismatch')


def assemble_reviewed_partition_case(page_bundles: Sequence[PageBundleRef], *,
        full_case_pages: Sequence[int], source_file_sha256: str, lang: TargetLang,
        preferences_sha256: str, formatting_manifest: bytes, expected_manifest_sha256: str,
        source_images: Sequence[bytes], output_dir: Path,
        evidence_guard: Callable[[], Mapping], writer=None) -> Path:
    """Publish one fresh internal review artifact; never resume or overwrite.

    ``writer`` is a trusted internal testing seam, not an external plug-in.
    Its returned bytes always undergo the independent production checker. The
    detached validator is called here; callers cannot substitute a forged
    projection dataclass. Native rendering and every-page review remain later.
    """
    if not callable(evidence_guard):
        raise AcceptanceAssemblyError('formatting_evidence_guard_required')
    if not isinstance(page_bundles, (tuple, list)) or any(
            not isinstance(ref, PageBundleRef) for ref in page_bundles):
        raise AcceptanceAssemblyError('formatting_invalid_page_references')
    if lang not in (TargetLang.FR, TargetLang.EN, TargetLang.AR):
        raise AcceptanceAssemblyError('formatting_writer_language_not_yet_supported')
    if (not isinstance(source_images, (tuple, list)) or len(source_images) != len(page_bundles)
            or any(type(raw) is not bytes for raw in source_images)):
        raise AcceptanceAssemblyError('formatting_invalid_image_inputs')
    images = tuple(source_images)
    refs = tuple(PageBundleRef(Path(ref.pages_dir), deepcopy(ref.expected_commit),
        ref.commit_file_sha256, ref.evidence_identity_sha256,
        ref.ignored_layout_sidecars) for ref in page_bundles)
    binding = partition_assembly_binding(refs, full_case_pages=full_case_pages,
        source_file_sha256=source_file_sha256, lang=lang, preferences_sha256=preferences_sha256,
        formatting_manifest_sha256=expected_manifest_sha256)
    output_dir = Path(output_dir)
    if not output_dir.is_absolute() or '..' in output_dir.parts:
        raise AcceptanceAssemblyError('formatting_absolute_output_required')
    _directory(output_dir.parent)
    if any(output_dir == ref.pages_dir or output_dir.is_relative_to(ref.pages_dir)
            or ref.pages_dir.is_relative_to(output_dir) for ref in refs):
        raise AcceptanceAssemblyError('formatting_output_overlaps_evidence')

    def guard():
        if _json(evidence_guard()) != _json(binding):
            raise AcceptanceAssemblyError('formatting_historical_binding_mismatch')

    guard()
    originals = [_read_bundle(ref) for ref in refs]
    _provenance(refs, originals, lang=lang, preferences_sha256=preferences_sha256)
    projection = validate_reviewed_formatting(formatting_manifest,
        expected_manifest_sha256=expected_manifest_sha256, pages=[
            FormattingPageInput(_decode(content['source']), _decode(content['target']),
                ref.commit_file_sha256, ref.expected_commit['bundle_sha256'], image)
            for ref, content, image in zip(refs, originals, images)],
        source_file_sha256=source_file_sha256, target_lang=lang.value,
        preferences_sha256=preferences_sha256)
    guard()
    if any(_read_bundle(ref) != content for ref, content in zip(refs, originals)):
        raise AcceptanceAssemblyError('formatting_original_changed')
    output_dir.mkdir(exist_ok=False)
    staging = output_dir / 'pages'
    staging.mkdir()
    for ref, content in zip(refs, originals):
        for kind, name in _names(ref.expected_commit['page_number']).items():
            _publish_file_exclusive(staging / name, content[kind])
    names = {name for ref in refs for name in _names(ref.expected_commit['page_number']).values()}

    def check():
        guard()
        _directory(output_dir)
        _directory(staging)
        if {p.name for p in staging.iterdir()} != names:
            raise AcceptanceAssemblyError('formatting_unexpected_staged_file')
        for ref, content in zip(refs, originals):
            if (_read_bundle(ref) != content or _read_bundle(PageBundleRef(staging,
                    ref.expected_commit, ref.commit_file_sha256, ref.evidence_identity_sha256)) != _committed_contents(content)):
                raise AcceptanceAssemblyError('formatting_evidence_changed')
        guard()
        if any(_read_bundle(ref) != content for ref, content in zip(refs, originals)):
            raise AcceptanceAssemblyError('formatting_original_changed')

    check()
    from .reviewed_formatting_writer import build_reviewed_docx, validate_reviewed_docx
    artifact = (writer or build_reviewed_docx)(projection)
    check()
    validate_reviewed_docx(artifact.docx_bytes, artifact.source_map_bytes, projection=projection)
    output = output_dir / f'formatted_{lang.value}.docx'
    source_map = output.with_suffix('.source_map.json')
    files = {output: artifact.docx_bytes, source_map: artifact.source_map_bytes,
             output_dir / 'reviewed_formatting.json': formatting_manifest}
    for path, raw in files.items():
        _publish_file_exclusive(path, raw)
    check()
    if {p.name for p in output_dir.iterdir()} != {'pages', *(p.name for p in files)}:
        raise AcceptanceAssemblyError('formatting_unexpected_output_file')
    if any(_read_file(path, maximum=64 * 1024 * 1024) != raw for path, raw in files.items()):
        raise AcceptanceAssemblyError('formatting_output_changed')
    manifest = {'version': VERSION, 'binding': binding, 'binding_sha256': _digest(_json(binding)),
        'original_commits': [ref.expected_commit for ref in refs],
        'formatting_manifest_sha256': expected_manifest_sha256,
        'docx_sha256': _digest(artifact.docx_bytes), 'source_map_sha256': _digest(artifact.source_map_bytes),
        'source_image_sha256s': [_digest(raw) for raw in images],
        'complete_source_page_set': True, 'original_artifacts_unchanged': True,
        'visible_text_coverage': 'exact_unique_fragment_part_locators',
        'source_geometry_status': 'not_verified', 'layout_review_required': True,
        'rendered_page_count': None, 'rendered_layout_acceptance': 'not_evaluated',
        'fidelity_acceptance': 'not_evaluated', 'workflow_resumed': False,
        'provider_dispatch_count': 0, 'assembly_cost_usd': '0'}
    manifest.update(_ignored_layout_metadata(refs))
    _publish_file_exclusive(output_dir / 'assembly.json', _json(manifest))
    return output
