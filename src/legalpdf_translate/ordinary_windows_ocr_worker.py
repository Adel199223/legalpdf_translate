"""Read Portuguese word boxes from a bounded PNG using the installed Windows OCR engine."""
from __future__ import annotations

import binascii
from contextlib import contextmanager
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
from threading import BoundedSemaphore, Timer
from time import monotonic

_MAX_BYTES = 16 * 1024 * 1024
_MAX_SIDE = 4096
_MAX_PIXELS = 16_000_000
_MAX_OUTPUT = 1024 * 1024
_TIMEOUT = 12.0
_SCRIPT_SHA256 = "aaa18daa48d16f59a07b5ac7c3c6310dadac79baac0b138a0d5a2ae4404855c6"
_SLOTS = BoundedSemaphore(2)


def _png_size(png: bytes) -> tuple[int, int] | None:
    if type(png) is not bytes or not 45 <= len(png) <= _MAX_BYTES or png[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    data = memoryview(png)
    offset = 8
    dimensions = None
    image_data = False
    for _ in range(4096):
        if offset + 12 > len(data):
            return None
        size, kind = struct.unpack_from(">I4s", data, offset)
        end = offset + 8 + size
        if end + 4 > len(data) or binascii.crc32(data[offset + 4:end]) != struct.unpack_from(">I", data, end)[0]:
            return None
        if dimensions is None:
            if kind != b"IHDR" or size != 13:
                return None
            width, height, depth, color, compression, filtering, interlace = struct.unpack_from(">IIBBBBB", data, offset + 8)
            depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
            if (not 1 <= width <= _MAX_SIDE or not 1 <= height <= _MAX_SIDE or width * height > _MAX_PIXELS
                    or depth not in depths.get(color, ()) or compression or filtering or interlace not in (0, 1)):
                return None
            dimensions = (width, height)
        elif kind == b"IEND":
            return dimensions if image_data and size == 0 and end + 4 == len(data) else None
        elif kind == b"IDAT":
            image_data = image_data or size > 0
        elif kind not in (b"PLTE", b"tRNS", b"pHYs", b"sRGB", b"gAMA", b"cHRM", b"bKGD", b"sBIT"):
            # The app renders a single raster. Do not interpret animated frames or compressed metadata.
            return None
        offset = end + 4
    return None


def _command() -> tuple[list[str], dict[str, str], Path] | None:
    buffer = ctypes.create_unicode_buffer(32768)
    count = ctypes.windll.kernel32.GetSystemDirectoryW(buffer, len(buffer))
    if not 0 < count < len(buffer):
        return None
    system = Path(buffer.value)
    powershell = system / "WindowsPowerShell" / "v1.0"
    exe = powershell / "powershell.exe"
    script = Path(__file__).resolve().with_suffix(".ps1")
    if not exe.is_file() or script.is_symlink() or not script.is_file():
        return None
    argv = [str(exe), "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    environment = {"SystemRoot": str(system.parent), "WINDIR": str(system.parent), "PATH": str(system),
                   "PSModulePath": str(powershell / "Modules"), "PSModuleAnalysisCachePath": "NUL"}
    return argv, environment, system


@contextmanager
def _pinned_script(script: Path):
    """Keep the authenticated script open without Windows write/delete sharing through execution."""
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    open_file = kernel.CreateFileW
    open_file.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                          wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    open_file.restype = wintypes.HANDLE
    # GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT.
    handle = open_file(str(script), 0x80000000, 1, None, 3, 0x00200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise OSError("OCR worker unavailable")
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except OSError:
        kernel.CloseHandle(wintypes.HANDLE(handle))
        raise
    with os.fdopen(fd, "rb") as file:
        body = file.read(16_385)
        if len(body) > 16_384 or hashlib.sha256(body).hexdigest() != _SCRIPT_SHA256:
            raise ValueError("OCR worker changed")
        yield


def _run(png: bytes, timeout: float) -> bytes:
    command = _command()
    if command is None:
        return b""
    argv, environment, cwd = command
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    with _pinned_script(Path(argv[-1])), subprocess.Popen(
        argv, executable=argv[0], cwd=cwd, env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, shell=False, close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW,
        startupinfo=startup,
    ) as process:
        assert process.stdin is not None and process.stdout is not None
        timer = Timer(timeout, process.kill)
        timer.daemon = True
        timer.start()
        try:
            process.stdin.write(png)
            process.stdin.close()
            output = process.stdout.read(_MAX_OUTPUT + 1)
            if len(output) > _MAX_OUTPUT:
                return b""
            return output if process.wait(timeout=timeout) == 0 else b""
        finally:
            if process.poll() is None:
                process.kill()
            timer.cancel()


def _object(items):
    result = dict(items)
    if len(items) != len(result):
        raise ValueError("duplicate OCR field")
    return result


def _text(value, limit):
    return (type(value) is str and 0 < len(value) <= limit and bool(value.strip())
            and all(char.isprintable() or char == "\u00a0" for char in value))


def _lines(raw: bytes, dimensions: tuple[int, int]) -> tuple[dict, ...]:
    if not raw or len(raw) > _MAX_OUTPUT:
        return ()
    obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_object)
    if (type(obj) is not dict or set(obj) != {"version", "language", "width", "height", "lines"}
            or type(obj["version"]) is not int or obj["version"] != 1 or obj["language"] != "pt-PT"
            or type(obj["width"]) is not int or type(obj["height"]) is not int
            or (obj["width"], obj["height"]) != dimensions or type(obj["lines"]) is not list
            or len(obj["lines"]) > 1000):
        return ()
    width, height = dimensions
    words_seen = chars_seen = 0
    for line in obj["lines"]:
        if (type(line) is not dict or set(line) != {"text", "words"} or not _text(line["text"], 4096)
                or type(line["words"]) is not list or not line["words"]):
            return ()
        words_seen += len(line["words"])
        chars_seen += len(line["text"])
        if words_seen > 6000 or chars_seen > 64_000:
            return ()
        for word in line["words"]:
            if type(word) is not dict or set(word) != {"text", "box"} or not _text(word["text"], 1024):
                return ()
            box = word["box"]
            if type(box) is not list or len(box) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in box):
                return ()
            x, y, w, h = box
            if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
                return ()
        if "".join(line["text"].split()) != "".join("".join(w["text"].split()) for w in line["words"]):
            return ()
    return tuple(obj["lines"])


def recognize_png(png: bytes, *, language: str = "pt-PT") -> tuple[dict, ...]:
    """Run only the fixed local program. Unavailable or inconsistent evidence contributes no words."""
    if os.name != "nt" or type(language) is not str or language != "pt-PT":
        return ()
    dimensions = _png_size(png)
    deadline = monotonic() + _TIMEOUT
    if dimensions is None or not _SLOTS.acquire(timeout=_TIMEOUT):
        return ()
    try:
        remaining = deadline - monotonic()
        return _lines(_run(png, remaining), dimensions) if remaining > 0 else ()
    except (OSError, ValueError, OverflowError, RecursionError, subprocess.SubprocessError):
        return ()
    finally:
        _SLOTS.release()

