from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

from legalpdf_translate import word_automation as word


def test_windows_timeout_recovers_trailing_phase_without_exception_output(monkeypatch):
    calls = iter([subprocess.TimeoutExpired('fake', 1), ('LEGALPDF_WORD_PHASE:open_document', '')])
    def communicate(**kwargs):
        value = next(calls)
        if isinstance(value, Exception):
            raise value
        return value
    process = SimpleNamespace(pid=4242, communicate=communicate, poll=lambda: None, kill=lambda: None)
    monkeypatch.setattr(word.subprocess, 'Popen', lambda *args, **kwargs: process)
    monkeypatch.setattr(word, '_terminate_windows_process_tree', lambda *args: (True, 'mocked'))
    result = word._run_command(action='export_pdf', command=('fake',), success_message='ok', timeout_seconds=1)
    assert result.failure_phase == 'open_document'


def test_pdf_journal_controls_success_not_stdout(tmp_path, monkeypatch):
    state = tmp_path / 'state.json'
    state.write_text(json.dumps({'status':'succeeded', 'cleanup_status':'ambiguous', 'phase':'cleanup'}))
    monkeypatch.setattr(word.subprocess, 'Popen', lambda *args, **kwargs: SimpleNamespace(
        pid=4242, returncode=0, communicate=lambda **kw: ('OK', 'sensitive test content'), poll=lambda: 0))
    result = word._run_pdf_command(action='export_pdf', command=('fake', 'private script'), state_path=state, timeout_seconds=1)
    assert not result.ok
    assert 'sensitive test content' not in result.details
    assert result.command == ('fake',)
    assert result.stdout == result.stderr == ''


def test_pdf_timeout_preserves_primary_phase_and_no_word_tree_kill(tmp_path, monkeypatch):
    state = tmp_path / 'state.json'
    state.write_text(json.dumps({'primary_failure_phase':'open_document','primary_hresult':'0x80010001',
                                'phase':'quit_word','cleanup_status':'in_progress','ownership':'proven'}))
    calls = iter([subprocess.TimeoutExpired('private script', 1), ('private text', '')])
    def communicate(**kwargs):
        value = next(calls)
        if isinstance(value, Exception):
            raise value
        return value
    killed = []
    process = SimpleNamespace(pid=4242, communicate=communicate, poll=lambda: None, kill=lambda: killed.append(4242))
    monkeypatch.setattr(word.subprocess, 'Popen', lambda *args, **kwargs: process)
    monkeypatch.setattr(word, '_terminate_windows_process_tree', lambda *args: pytest.fail('no tree kill'))
    result = word._run_pdf_command(action='export_pdf', command=('fake','private script'), state_path=state, timeout_seconds=1)
    assert not result.ok
    assert result.failure_code == 'timeout'
    assert result.failure_phase == 'open_document'
    assert result.cleanup_succeeded is False
    assert killed == [4242]
    assert 'private' not in result.details
    assert '0x80010001' in result.details


@pytest.mark.parametrize('diagnostic,code', [
    (b'ConstrainedLanguage private source path', 'host_policy_blocked'),
    (b'ParserError private document text', 'export_failed'),
])
def test_pdf_helper_setup_failure_is_sanitized_and_recoverable(tmp_path, monkeypatch, diagnostic, code):
    state = tmp_path / 'state.json'
    state.write_text(json.dumps({'status': 'starting', 'launch_attempted': True}))
    monkeypatch.setattr(word.subprocess, 'Popen', lambda *args, **kwargs: SimpleNamespace(
        pid=4242, returncode=1, communicate=lambda **kw: (None, diagnostic), poll=lambda: 1))
    result = word._run_pdf_command(action='export_pdf', command=('fake', 'private script'),
                                   state_path=state, timeout_seconds=1)
    assert not result.ok
    assert result.failure_phase == 'helper_setup'
    assert result.failure_code == code
    assert result.cleanup_succeeded
    assert 'private' not in result.details
    assert json.loads(state.read_text())['launch_attempted'] is False


def test_pdf_helper_spawn_failure_does_not_quarantine_word(tmp_path, monkeypatch):
    state = tmp_path / 'state.json'
    state.write_text(json.dumps({'status': 'starting', 'launch_attempted': True}))
    def fail_spawn(*args, **kwargs):
        raise OSError('private executable details')
    monkeypatch.setattr(word.subprocess, 'Popen', fail_spawn)
    result = word._run_pdf_command(action='export_pdf', command=('fake', 'private script'),
                                   state_path=state, timeout_seconds=1)
    assert not result.ok
    assert result.failure_phase == 'start_helper'
    assert result.cleanup_succeeded
    assert result.cleanup_details == 'No Word activation occurred.'
    assert 'private' not in result.details


def test_pdf_helper_io_error_stops_retained_helper(tmp_path, monkeypatch):
    state = tmp_path / 'state.json'
    state.write_text(json.dumps({'status': 'running', 'phase': 'open_document'}))
    calls = iter([OSError('private pipe failure'), (None, b'')])
    def communicate(**kwargs):
        value = next(calls)
        if isinstance(value, Exception):
            raise value
        return value
    killed = []
    monkeypatch.setattr(word.subprocess, 'Popen', lambda *a, **kw: SimpleNamespace(
        pid=4242, returncode=1, communicate=communicate, poll=lambda: None,
        kill=lambda: killed.append(4242)))
    result = word._run_pdf_command(action='export_pdf', command=('fake',), state_path=state, timeout_seconds=1)
    assert not result.ok
    assert killed == [4242]
    assert json.loads(state.read_text())['parent_helper_stopped'] is True


def test_pdf_timeout_before_child_journal_can_recover_after_word_is_closed(tmp_path, monkeypatch):
    from legalpdf_translate import word_pdf_control as control
    state = tmp_path / 'state.json'
    state.write_text(json.dumps({'status': 'starting', 'launch_attempted': True}))
    calls = iter([subprocess.TimeoutExpired('fake', 1), (None, b'')])
    def communicate(**kwargs):
        value = next(calls)
        if isinstance(value, Exception):
            raise value
        return value
    monkeypatch.setattr(word.subprocess, 'Popen', lambda *a, **kw: SimpleNamespace(
        pid=4242, communicate=communicate, poll=lambda: None, kill=lambda: None))
    result = word._run_pdf_command(action='export_pdf', command=('fake',), state_path=state, timeout_seconds=1)
    assert not result.ok
    monkeypatch.setattr(control, '_no_word_processes', lambda: False)
    assert not control._previous_operation_finished(control.read_state(state))
    monkeypatch.setattr(control, '_no_word_processes', lambda: True)
    assert control._previous_operation_finished(control.read_state(state))


def test_pdf_lock_release_error_does_not_deny_completed_publication(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from legalpdf_translate import word_pdf_control as control, word_pdf_artifacts as artifacts
    source, target = tmp_path / 'source.docx', tmp_path / 'output.pdf'
    @contextmanager
    def slot():
        yield tmp_path / 'state.json'
        raise OSError('private lock path')
    @contextmanager
    def staged(*args):
        yield source, target
        target.write_bytes(b'new verified test PDF')
    monkeypatch.setattr(control, 'word_pdf_slot', slot)
    monkeypatch.setattr(artifacts, 'staged_pdf_export', staged)
    monkeypatch.setattr(word, '_is_windows_host', lambda: True)
    monkeypatch.setattr(word, '_resolve_powershell_path', lambda: 'fake')
    monkeypatch.setattr(word, '_build_pdf_export_powershell_script', lambda *a, **kw: 'fake')
    monkeypatch.setattr(word, '_run_pdf_command', lambda **kw: word.WordAutomationResult(
        ok=True, action='export_pdf', message='Word document exported to PDF.', cleanup_succeeded=True))
    result = word.export_docx_to_pdf_in_word(source, target)
    assert result.ok
    assert 'verified and saved' in result.details
    assert 'private' not in result.details
    assert target.read_bytes() == b'new verified test PDF'
