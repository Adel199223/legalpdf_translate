"""Cross-process export exclusion and conservative recovery; never controls Word."""

from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import threading

_THREAD_SLOT = threading.Lock()


class WordPdfBusy(RuntimeError):
    pass


class WordPdfRecoveryRequired(RuntimeError):
    pass


def runtime_root() -> Path:
    root = os.environ.get('APPDATA')
    if not root:
        raise WordPdfRecoveryRequired('The Word export state directory is unavailable.')
    return Path(root) / 'LegalPDFTranslate' / 'word_pdf_export_v2'


def read_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        if path.stat().st_size > 32768:
            raise ValueError('oversized')
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(value, dict):
            raise ValueError('invalid')
        return value
    except (OSError, ValueError):
        return {'status': 'invalid', 'launch_attempted': True}


def _kernel32():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    return kernel


def _identity_gone(pid: object, start_ticks: object) -> bool:
    """PID reuse is not the old process; access denied is not proof of exit."""
    try:
        process_id, expected = int(pid), int(start_ticks)
        if os.name != 'nt' or process_id <= 0 or expected <= 0:
            return False
        kernel = _kernel32()
        handle = kernel.OpenProcess(0x1000, False, process_id)
        if not handle:
            return ctypes.get_last_error() == 87  # ERROR_INVALID_PARAMETER: no such PID
        try:
            exit_code = wintypes.DWORD()
            if kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)) and exit_code.value != 259:
                return True
            values = [wintypes.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(handle, *(ctypes.byref(v) for v in values)):
                return False
            actual = (values[0].dwHighDateTime << 32) + values[0].dwLowDateTime + 504911232000000000
            return actual != expected
        finally:
            kernel.CloseHandle(handle)
    except (TypeError, ValueError, OSError, OverflowError):
        return False


def _no_word_processes() -> bool:
    """Read-only conservative recovery check, no COM attachment or process kill."""
    if os.name != 'nt':
        return False
    class ProcessEntry(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                    ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
                    ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                    ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', wintypes.LONG),
                    ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260)]
    kernel = _kernel32()
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        return False
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        found = kernel.Process32FirstW(handle, ctypes.byref(entry))
        if not found:
            return False
        while found:
            if entry.szExeFile.casefold() == 'winword.exe':
                return False
            found = kernel.Process32NextW(handle, ctypes.byref(entry))
        return ctypes.get_last_error() == 18  # ERROR_NO_MORE_FILES
    finally:
        kernel.CloseHandle(handle)


def _previous_operation_finished(state: dict) -> bool:
    if not state:
        return True
    if state.get('status') == 'invalid':
        return False
    if state.get('cleanup_status') == 'confirmed' and state.get('status') in {'succeeded', 'failed'}:
        return True
    if state.get('parent_helper_stopped') is not True and not _identity_gone(state.get('helper_pid'), state.get('helper_start_ticks')):
        return False
    if state.get('process_identity_verified') is True or state.get('word_identity_verified') is True:
        return _identity_gone(state.get('word_pid'), state.get('word_start_ticks'))
    # Unknown activation can have created a COM server: only a Word-free host
    # AND a demonstrably exited helper permit re-entry. Never guess a PID to kill.
    return _no_word_processes()


@contextmanager
def word_pdf_slot():
    """Nonblocking per-user exclusion shared by browser, Qt and readiness probes."""
    if not _THREAD_SLOT.acquire(blocking=False):
        raise WordPdfBusy('Another Word PDF operation is already running. Try again when it finishes.')
    stream = None
    locked = False
    try:
        root = runtime_root()
        root.mkdir(parents=True, exist_ok=True)
        stream = (root / 'export.lock').open('a+b')
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as exc:
            raise WordPdfBusy('Another Word PDF operation is already running. Try again when it finishes.') from exc
        state_path = root / 'active.json'
        if not _previous_operation_finished(read_state(state_path)):
            raise WordPdfRecoveryRequired(
                'An earlier Word export has not finished safely. Save your open Word documents, close Word, '
                'then retry. If this message remains, export the saved DOCX manually and select that PDF.'
            )
        yield state_path
    finally:
        try:
            if stream is not None:
                try:
                    if locked:
                        stream.seek(0)
                        if os.name == 'nt':
                            import msvcrt
                            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                finally:
                    stream.close()
        finally:
            _THREAD_SLOT.release()
