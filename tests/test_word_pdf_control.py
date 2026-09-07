from __future__ import annotations

import json
import threading
import os
import subprocess
import sys

import pytest

from legalpdf_translate import word_pdf_control as control


def test_slot_rejects_concurrent_export_and_releases_after_exception():
    errors = []
    with pytest.raises(ValueError):
        with control.word_pdf_slot() as state:
            def contender():
                try:
                    with control.word_pdf_slot():
                        errors.append('unexpected acquisition')
                except control.WordPdfBusy:
                    errors.append('busy')
            thread = threading.Thread(target=contender)
            thread.start()
            thread.join(timeout=3)
            assert not thread.is_alive()
            assert errors == ['busy']
            assert not state.exists()
            raise ValueError('synthetic')
    with control.word_pdf_slot():
        pass


def test_uncertain_previous_worker_blocks_new_operation(monkeypatch):
    with control.word_pdf_slot() as state:
        state.write_text(json.dumps({'launch_attempted': True, 'ownership': 'unknown'}))
    monkeypatch.setattr(control, '_no_word_processes', lambda: False)
    with pytest.raises(control.WordPdfRecoveryRequired):
        with control.word_pdf_slot():
            pytest.fail('unsafe re-entry')


def test_unknown_previous_worker_requires_no_word_and_no_helper(monkeypatch):
    journal = {'launch_attempted': True, 'helper_pid': 111, 'helper_start_ticks': '123'}
    monkeypatch.setattr(control, '_identity_gone', lambda *args: False)
    monkeypatch.setattr(control, '_no_word_processes', lambda: True)
    assert not control._previous_operation_finished(journal)
    monkeypatch.setattr(control, '_identity_gone', lambda *args: True)
    assert control._previous_operation_finished(journal)


def test_known_word_pid_is_not_enough_without_identity(monkeypatch):
    monkeypatch.setattr(control, '_identity_gone', lambda *args: True)
    monkeypatch.setattr(control, '_no_word_processes', lambda: False)
    state = {'launch_attempted': True, 'word_pid': 111, 'word_start_ticks': '123'}
    assert not control._previous_operation_finished(state)
    state['word_identity_verified'] = True
    assert control._previous_operation_finished(state)


def test_started_process_identity_recovers_even_if_window_binding_never_completed(monkeypatch):
    state = {'parent_helper_stopped': True, 'process_identity_verified': True,
             'word_identity_verified': False, 'word_pid': 111, 'word_start_ticks': '123'}
    monkeypatch.setattr(control, '_no_word_processes', lambda: pytest.fail('other user Word may remain open'))
    monkeypatch.setattr(control, '_identity_gone', lambda *args: False)
    assert not control._previous_operation_finished(state)
    monkeypatch.setattr(control, '_identity_gone', lambda *args: True)
    assert control._previous_operation_finished(state)


def test_confirmed_cleanup_allows_retry_without_process_inspection(monkeypatch):
    monkeypatch.setattr(control, '_identity_gone', lambda *args: pytest.fail('not needed'))
    assert control._previous_operation_finished({'status':'failed', 'cleanup_status':'confirmed'})


def test_corrupt_journal_is_fail_closed():
    with control.word_pdf_slot() as state:
        state.write_text('{')
    with pytest.raises(control.WordPdfRecoveryRequired):
        with control.word_pdf_slot():
            pytest.fail('unsafe re-entry')


@pytest.mark.skipif(os.name != 'nt', reason='Windows file locking')
def test_file_unlock_error_does_not_leak_thread_slot(monkeypatch):
    import msvcrt
    original = msvcrt.locking
    def broken_unlock(fd, mode, count):
        if mode == msvcrt.LK_UNLCK:
            raise OSError('synthetic unlock error')
        return original(fd, mode, count)
    with monkeypatch.context() as scoped:
        scoped.setattr(msvcrt, 'locking', broken_unlock)
        with pytest.raises(OSError, match='synthetic'):
            with control.word_pdf_slot():
                pass
    with control.word_pdf_slot():
        pass


def test_slot_excludes_another_python_process():
    from pathlib import Path
    env = dict(os.environ, PYTHONPATH=str(Path(control.__file__).resolve().parents[1]))
    script = ('from legalpdf_translate.word_pdf_control import word_pdf_slot, WordPdfBusy\n'
              'try:\n with word_pdf_slot(): print("acquired")\n'
              'except WordPdfBusy: print("busy")')
    with control.word_pdf_slot():
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True,
                                env=env, timeout=10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    assert result.returncode == 0
    assert result.stdout.strip() == 'busy'


@pytest.mark.skipif(os.name != 'nt', reason='Windows process identity')
def test_process_identity_distinguishes_current_pid_reuse_and_missing_pid():
    import ctypes
    from ctypes import wintypes
    kernel = control._kernel32()
    handle = kernel.OpenProcess(0x1000, False, os.getpid())
    try:
        times = [wintypes.FILETIME() for _ in range(4)]
        assert kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times))
        ticks = (times[0].dwHighDateTime << 32) + times[0].dwLowDateTime + 504911232000000000
    finally:
        kernel.CloseHandle(handle)
    assert not control._identity_gone(os.getpid(), ticks)
    assert control._identity_gone(os.getpid(), ticks - 1)
    assert control._identity_gone(4294967294, ticks)
