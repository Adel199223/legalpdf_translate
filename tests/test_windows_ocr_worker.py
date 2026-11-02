"""Contract of the optional, bounded Portuguese Windows OCR reader."""
import binascii
import hashlib
import json
import os
from pathlib import Path
import struct
from types import SimpleNamespace
import zlib

import pytest

from legalpdf_translate import ordinary_windows_ocr_worker as worker


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data))


def png(width=160, height=64):
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(b"\x00" * (width + 1) * height)) + chunk(b"IEND", b""))


def result():
    return {"version": 1, "language": "pt-PT", "width": 160, "height": 64,
            "lines": [{"text": "Olá Porto", "words": [
                {"text": "Olá", "box": [1, 2, 18, 10]}, {"text": "Porto", "box": [23, 2, 26, 10]}]}]}


def test_public_reads_validated_pixel_boxes(monkeypatch):
    monkeypatch.setattr(worker, "os", SimpleNamespace(name="nt"))
    sent = []
    def local(payload, seconds):
        sent.append(payload)
        assert 0 < seconds <= worker._TIMEOUT
        return json.dumps(result(), ensure_ascii=False).encode("utf-8")
    monkeypatch.setattr(worker, "_run", local)
    image = png()
    assert worker.recognize_png(image) == tuple(result()["lines"])
    assert sent == [image]
    assert worker.recognize_png(image, language="en-US") == ()
    assert worker.recognize_png(bytearray(image)) == ()
    monkeypatch.setattr(worker, "os", SimpleNamespace(name="posix"))
    assert worker.recognize_png(image) == ()
    assert sent == [image]


@pytest.mark.parametrize("mutator", [
    lambda p: p[:-1],
    lambda p: p + b"x",
    lambda p: p[:-12] + chunk(b"acTL", b"12345678") + p[-12:],
    lambda p: p[:-12] + chunk(b"iTXt", b"text") + p[-12:],
    lambda p: p[:16] + bytes([p[16] ^ 1]) + p[17:],
    lambda p: png(4097, 1),
    lambda p: b"x" * (worker._MAX_BYTES + 1),
])
def test_invalid_rasters_are_never_dispatched(monkeypatch, mutator):
    monkeypatch.setattr(worker, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(worker, "_run", lambda *_: pytest.fail("invalid raster dispatched"))
    assert worker.recognize_png(mutator(png())) == ()


@pytest.mark.parametrize("variant", [
    "wrong_width", "wrong_language", "boolean_version", "duplicates", "non_utf8", "over_limit",
    "foreign_field", "invalid_text", "line_word_mismatch", "negative_coordinate",
    "off_canvas", "zero_area", "nonfinite", "boolean_coordinate", "no_words",
])
def test_untrusted_worker_output_is_not_evidence(monkeypatch, variant):
    monkeypatch.setattr(worker, "os", SimpleNamespace(name="nt"))
    data = result()
    line = data["lines"][0]
    word = line["words"][0]
    if variant == "wrong_width":
        data["width"] += 1
    elif variant == "wrong_language":
        data["language"] = "en"
    elif variant == "boolean_version":
        data["version"] = True
    elif variant == "foreign_field":
        word["confidence"] = 1
    elif variant == "invalid_text":
        line["text"] += "\u202e"
    elif variant == "line_word_mismatch":
        line["text"] = "Olá Coimbra"
    elif variant == "negative_coordinate":
        word["box"][0] = -1
    elif variant == "off_canvas":
        word["box"][2] = 160
    elif variant == "zero_area":
        word["box"][2] = 0
    elif variant == "nonfinite":
        word["box"][0] = float("nan")
    elif variant == "boolean_coordinate":
        word["box"][0] = True
    elif variant == "no_words":
        line["words"] = []
    payload = json.dumps(data).encode()
    if variant == "duplicates":
        payload = payload.replace(b'"version": 1', b'"version": 1, "version": 1')
    elif variant == "non_utf8":
        payload = b"\xff"
    elif variant == "over_limit":
        payload = b"x" * (worker._MAX_OUTPUT + 1)
    monkeypatch.setattr(worker, "_run", lambda *_: payload)
    assert worker.recognize_png(png()) == ()


def test_local_worker_failure_or_contention_abstains(monkeypatch):
    monkeypatch.setattr(worker, "os", SimpleNamespace(name="nt"))
    def unavailable(*_):
        raise OSError("local worker unavailable")
    monkeypatch.setattr(worker, "_run", unavailable)
    assert worker.recognize_png(png()) == ()
    monkeypatch.setattr(worker, "_SLOTS", SimpleNamespace(acquire=lambda **_: False))
    monkeypatch.setattr(worker, "_run", lambda *_: pytest.fail("no slot was available"))
    assert worker.recognize_png(png()) == ()


@pytest.mark.skipif(os.name != "nt", reason="Windows executable and file-sharing contract")
def test_fixed_windows_command_and_pinned_script(tmp_path, monkeypatch):
    monkeypatch.setenv("SystemRoot", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "untrusted-test-placeholder")
    argv, env, system = worker._command()
    exe = system / "WindowsPowerShell/v1.0/powershell.exe"
    script = Path(worker.__file__).with_suffix(".ps1").resolve()
    assert system.is_absolute() and system != tmp_path and Path(argv[0]) == exe
    assert argv[1:] == ["-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    assert set(env) == {"SystemRoot", "WINDIR", "PATH", "PSModulePath", "PSModuleAnalysisCachePath"}
    assert hashlib.sha256(script.read_bytes()).hexdigest() == worker._SCRIPT_SHA256
    fixture = tmp_path / "program.ps1"
    fixture.write_bytes(script.read_bytes())
    with worker._pinned_script(fixture):
        with pytest.raises(OSError):
            fixture.open("r+b")
    fixture.write_bytes(script.read_bytes() + b" ")
    with pytest.raises(ValueError):
        with worker._pinned_script(fixture):
            pytest.fail("changed script was accepted")

