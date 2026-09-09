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
    clock = [0.0]
    monkeypatch.setattr(control, '_recovery_monotonic', lambda: clock[0])
    monkeypatch.setattr(control, '_recovery_sleep', lambda delay: clock.__setitem__(0, clock[0] + delay))
    journal = {'launch_attempted': True, 'helper_pid': 111, 'helper_start_ticks': '123'}
    monkeypatch.setattr(control, '_identity_gone', lambda *args: False)
    monkeypatch.setattr(control, '_no_word_processes', lambda: True)
    assert not control._previous_operation_finished(journal)
    monkeypatch.setattr(control, '_identity_gone', lambda *args: True)
    assert control._previous_operation_finished(journal)


@pytest.fixture
def recovery_clock(monkeypatch):
    clock = [0.0]
    sleeps = []
    monkeypatch.setattr(control, '_recovery_monotonic', lambda: clock[0])
    def advance(delay):
        sleeps.append(delay)
        clock[0] += delay
    monkeypatch.setattr(control, '_recovery_sleep', advance)
    return clock, sleeps


def test_unknown_launch_requires_five_continuous_word_free_seconds(monkeypatch, recovery_clock):
    clock, sleeps = recovery_clock
    probes = []
    monkeypatch.setattr(control, '_identity_gone', lambda *args: True)
    monkeypatch.setattr(control, '_no_word_processes', lambda: probes.append(clock[0]) or True)
    state = {'launch_attempted': True, 'helper_pid': 111, 'helper_start_ticks': '123'}
    original = dict(state)
    assert control._previous_operation_finished(state)
    assert clock[0] == 5.0 and len(probes) == 21 and len(sleeps) == 20
    assert state == original


def test_delayed_word_child_after_empty_snapshot_blocks_reentry(monkeypatch, recovery_clock):
    clock, _ = recovery_clock
    monkeypatch.setattr(control, '_identity_gone', lambda *args: True)
    monkeypatch.setattr(control, '_no_word_processes', lambda: clock[0] < 2.0)
    state = {'status': 'failed', 'launch_attempted': True, 'cleanup_status': 'ambiguous',
             'process_identity_verified': False, 'word_pid': 789}
    assert not control._previous_operation_finished(state)
    assert clock[0] == 2.0


@pytest.mark.parametrize('observation', [False, None, 1, 'true'])
def test_unknown_inventory_result_is_never_word_free(monkeypatch, recovery_clock, observation):
    monkeypatch.setattr(control, '_no_word_processes', lambda: observation)
    assert not control._stable_word_free()
    assert recovery_clock[1] == []


def test_each_reentry_check_requires_a_fresh_stability_interval(monkeypatch, recovery_clock):
    clock, _ = recovery_clock
    monkeypatch.setattr(control, '_identity_gone', lambda *args: True)
    monkeypatch.setattr(control, '_no_word_processes', lambda: True)
    state = {'parent_helper_stopped': True, 'launch_attempted': True}
    assert control._previous_operation_finished(state)
    assert control._previous_operation_finished(state)
    assert clock[0] == 10.0


def test_stalled_or_backwards_clock_is_bounded_and_not_safe(monkeypatch, recovery_clock):
    monkeypatch.setattr(control, '_no_word_processes', lambda: True)
    sleeps = []
    monkeypatch.setattr(control, '_recovery_sleep', lambda delay: sleeps.append(delay))
    assert not control._stable_word_free()
    assert len(sleeps) == control._WORD_FREE_MAX_PROBES
    values = iter([10.0, 9.0])
    monkeypatch.setattr(control, '_recovery_monotonic', lambda: next(values))
    assert not control._stable_word_free()


def test_live_helper_blocks_without_waiting_for_word_inventory(monkeypatch, recovery_clock):
    monkeypatch.setattr(control, '_identity_gone', lambda *args: False)
    monkeypatch.setattr(control, '_no_word_processes', lambda: pytest.fail('live helper must stop first'))
    assert not control._previous_operation_finished({'launch_attempted': True})
    assert recovery_clock[1] == []


@pytest.mark.parametrize('failure', ['inventory', 'wait', 'clock'])
def test_failed_recovery_observation_is_not_safe(monkeypatch, recovery_clock, failure):
    def broken(*args): raise OSError('synthetic unavailable read')
    monkeypatch.setattr(control, '_no_word_processes', lambda: True)
    monkeypatch.setattr(control, {'inventory': '_no_word_processes', 'wait': '_recovery_sleep',
                                'clock': '_recovery_monotonic'}[failure], broken)
    assert not control._stable_word_free()


@pytest.mark.parametrize('value', [float('inf'), float('nan')])
def test_nonfinite_recovery_clock_never_confirms_safety(monkeypatch, value):
    monkeypatch.setattr(control, '_recovery_monotonic', lambda: value)
    monkeypatch.setattr(control, '_no_word_processes', lambda: pytest.fail('invalid clock must stop first'))
    assert not control._stable_word_free()


def test_recovery_keyboard_interrupt_is_not_swallowed(monkeypatch, recovery_clock):
    def interrupted(): raise KeyboardInterrupt()
    monkeypatch.setattr(control, '_no_word_processes', interrupted)
    with pytest.raises(KeyboardInterrupt): control._stable_word_free()


def test_known_word_pid_is_not_enough_without_identity(monkeypatch):
    monkeypatch.setattr(control, '_identity_gone', lambda *args: True)
    monkeypatch.setattr(control, '_no_word_processes', lambda: False)
    state = {'launch_attempted': True, 'word_pid': 111, 'word_start_ticks': '123'}
    assert not control._previous_operation_finished(state)
    state['word_identity_verified'] = True
    assert control._previous_operation_finished(state)


@pytest.mark.parametrize('diagnostic_version', [None, 1, 2])
def test_legacy_and_new_startup_diagnostics_never_grant_recovery_trust(
    tmp_path, monkeypatch, diagnostic_version
):
    state = {'status': 'failed', 'launch_attempted': True,
             'helper_pid': 111, 'helper_start_ticks': '123',
             'word_pid': 789, 'word_start_ticks': '456',
             'process_identity_verified': False, 'word_identity_verified': False,
             'cleanup_status': 'ambiguous'}
    if diagnostic_version is not None:
        state.update(startup_diagnostics_version=diagnostic_version,
                     startup_identity_checks={'name_matches': True, 'executable_matches': True})
    if diagnostic_version == 2:
        state.update(startup_process_name='WINWORD', startup_process_name_status='captured',
                     startup_expected_process_name='WINWORD',
                     startup_process_name_source='retained_launch_handle',
                     startup_executable_status='compared')
    journal = tmp_path / 'legacy-or-current.json'
    journal.write_text(json.dumps(state), encoding='utf-8')
    before = journal.read_bytes()
    monkeypatch.setattr(control, '_identity_gone', lambda *args: True)
    monkeypatch.setattr(control, '_no_word_processes', lambda: False)
    loaded = control.read_state(journal)
    assert loaded == state
    assert not control._previous_operation_finished(loaded)
    assert journal.read_bytes() == before
    assert loaded == state


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
