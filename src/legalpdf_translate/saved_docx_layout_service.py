"""Local, workspace-owned formatting snapshots for saved Word documents.

This lane never restores translation jobs or loads settings/credentials. It owns
only new snapshots and derivatives. Original uploads and failed attempts remain
available; a durable completion marker, never a filename, establishes success.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from functools import wraps
import hashlib
import importlib.util
import json
import math
import multiprocessing
import os
from pathlib import Path
import re
import stat
import time
import uuid

from .run_workspace_lock import RunWorkspaceBusy, run_workspace_slot

VERSION = "saved_docx_layout_service_v1"
PROFILE = "saved_docx_source_region_review_v1"
DOCX_MAX_BYTES = 32 * 1024 * 1024
PDF_MAX_BYTES = 64 * 1024 * 1024
SNAPSHOT_MAX_BYTES = 64 * 1024 * 1024
DECISIONS_MAX_BYTES = 8 * 1024 * 1024
RECORD_MAX_BYTES = 8 * 1024 * 1024
MAX_SOURCE_PAGES = 100
MAX_PAGE_PIXELS = 12_000_000
MAX_RASTER_BYTES = 256 * 1024 * 1024
MAX_REVIEWS = 256
MAX_GENERATIONS = 1000
MAX_BUILDS = 256
MAX_GENERATION_BYTES = 128 * 1024 * 1024
RENDER_DPI = 144
PAGE_TIMEOUT_SECONDS = 30.0
IMPORT_TIMEOUT_SECONDS = 300.0
_ID = re.compile(r"[a-f0-9]{32}\Z")
_HASH = re.compile(r"[a-f0-9]{64}\Z")
_CODE = re.compile(r"[a-z][a-z0-9_]{0,120}\Z")


class SavedDocxLayoutServiceError(ValueError):
    """Content-free errors suitable for the local HTTP boundary."""

    def __init__(self, code, status=422):
        self.code = code if code.startswith("saved_docx_layout_") else "saved_docx_layout_" + code
        self.status = self.status_code = status
        super().__init__(self.code)


def _fail(code, status=422):
    raise SavedDocxLayoutServiceError(code, status) from None


def _public(function):
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except SavedDocxLayoutServiceError:
            raise
        except RunWorkspaceBusy:
            _fail("busy", 409)
        except Exception as exc:
            code = getattr(exc, "code", None)
            if isinstance(code, str) and _CODE.fullmatch(code):
                status = getattr(exc, "status", 422)
                _fail(code, status if status in {404, 409, 413, 422, 503} else 422)
            _fail("operation_failed")
    return call


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _encode(value, maximum=RECORD_MAX_BYTES):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                     allow_nan=False).encode("utf-8")
    if not 0 < len(raw) <= maximum:
        _fail("record_limit", 413)
    return raw


def _decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _fail("invalid_record")
            result[key] = value
        return result
    def constant(_):
        _fail("invalid_record")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def _identifier(value):
    if type(value) is not str or not _ID.fullmatch(value):
        _fail("invalid_id")
    return value


def _integer(value, *, maximum=MAX_GENERATIONS):
    if type(value) is not int or not 1 <= value <= maximum:
        _fail("invalid_generation")
    return value


def _raw_bytes(value, maximum):
    if type(value) is not bytes or not 0 < len(value) <= maximum:
        _fail("input_limit", 413)
    return value


def _direct(path, *, directory=False, missing=False):
    path = Path(path).expanduser().absolute()
    if ".." in path.parts or str(path).startswith(("\\\\", "//")):
        _fail("invalid_path")
    for item in reversed((path, *path.parents)):
        try:
            info = item.lstat()
        except FileNotFoundError:
            if missing:
                continue
            _fail("not_found", 404)
        if (item.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400
                or (item != path or directory) and not stat.S_ISDIR(info.st_mode)):
            _fail("indirect_path")
        if item == path and not directory and (not stat.S_ISREG(info.st_mode)
                                               or getattr(info, "st_nlink", 1) != 1):
            _fail("indirect_path")
    return path.resolve(strict=not missing)


def _mkdir(path):
    path = _direct(path, directory=True, missing=True)
    # Validate every existing ancestor before making any new directory.
    for item in reversed((path, *path.parents)):
        if not item.exists():
            try:
                item.mkdir(exist_ok=False)
            except FileExistsError:
                pass
        _direct(item, directory=True)
    return path


def _read(path, maximum=RECORD_MAX_BYTES):
    path = _direct(path)
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if before.st_size > maximum:
            _fail("record_limit", 413)
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    final = _direct(path).stat()
    identity = lambda i: (i.st_dev, i.st_ino, i.st_size, i.st_mtime_ns)
    if identity(before) != identity(after) or identity(after) != identity(final) or len(raw) != before.st_size:
        _fail("record_changed", 409)
    return raw


def _atomic(path, raw):
    """Publish a new immutable file; retain an interrupted temporary sibling."""
    _direct(path.parent, directory=True)
    if path.exists() or path.is_symlink():
        _fail("publication_conflict", 409)
    temporary = path.parent / (".pending-" + uuid.uuid4().hex)
    with temporary.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    # All callers hold their workspace/review lock. Windows rename itself also
    # refuses an existing destination; the lock provides that contract on POSIX.
    if path.exists() or path.is_symlink():
        _fail("publication_conflict", 409)
    os.rename(temporary, path)
    if _read(path, max(len(raw), 1)) != raw:
        _fail("publication_changed", 409)


def _write(path, value, maximum=RECORD_MAX_BYTES):
    raw = _encode(value, maximum)
    _atomic(path, raw)
    return raw


def _write_once(path, value):
    raw = _encode(value)
    if path.exists():
        if _read(path) != raw:
            _fail("receipt_changed", 409)
    else:
        _atomic(path, raw)


def _folders(root, maximum):
    if not root.exists():
        return []
    _direct(root, directory=True)
    result = []
    with os.scandir(root) as entries:
        for entry in entries:
            if entry.name == ".run_workspace.lock" or entry.name.startswith(".pending-"):
                continue
            if len(result) >= maximum:
                _fail("registry_limit", 413)
            result.append(_direct(root / _identifier(entry.name), directory=True))
    return sorted(result)


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _prepare_worker(folder_text, language, module_root, channel):
    """Spawn target: bounded package parsing and local PDF rasterization only."""
    try:
        if str(Path(__file__).resolve().parent) != module_root:
            _fail("worker_source_changed")
        from .saved_docx_layout import inspect_docx
        import fitz
        fitz.TOOLS.mupdf_display_errors(False)
        fitz.TOOLS.mupdf_display_warnings(False)
        folder = Path(folder_text)
        snapshot = inspect_docx(_read(folder / "original.docx", DOCX_MAX_BYTES), language)
        _write(folder / "snapshot.json", snapshot, SNAPSHOT_MAX_BYTES)
        pages = []
        aggregate = 0
        images = _mkdir(folder / "images")
        with fitz.open(folder / "source.pdf") as document:
            if not document.is_pdf or document.needs_pass or not 1 <= document.page_count <= MAX_SOURCE_PAGES:
                _fail("unsupported_pdf")
            for index in range(document.page_count):
                channel.send(("page", index + 1))
                page = document.load_page(index)
                width = math.ceil(page.rect.width * RENDER_DPI / 72)
                height = math.ceil(page.rect.height * RENDER_DPI / 72)
                if not 1 <= width * height <= MAX_PAGE_PIXELS or width < 1 or height < 1:
                    _fail("raster_limit", 413)
                raster = page.get_pixmap(matrix=fitz.Matrix(RENDER_DPI / 72, RENDER_DPI / 72), alpha=False)
                if raster.width * raster.height > MAX_PAGE_PIXELS:
                    _fail("raster_limit", 413)
                raw = raster.tobytes("png")
                aggregate += len(raw)
                if aggregate > MAX_RASTER_BYTES:
                    _fail("raster_limit", 413)
                _atomic(images / f"page-{index + 1:04d}.png", raw)
                pages.append({"page_number": index + 1, "width_px": raster.width, "height_px": raster.height,
                    "image_sha256": _sha(raw), "rotation": page.rotation, "render_dpi": RENDER_DPI,
                    "backend": "pymupdf", "backend_version": str(fitz.VersionBind)})
                channel.send(("done", index + 1))
        _write(folder / "pages.json", pages)
        channel.send(("complete",))
    except Exception as exc:
        code = getattr(exc, "code", "saved_docx_layout_import_failed")
        if type(code) is not str or not _CODE.fullmatch(code):
            code = "saved_docx_layout_import_failed"
        try:
            channel.send(("error", code, getattr(exc, "status", 422)))
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        channel.close()


def _prepare_import(folder, language):
    """Kill only this owned worker at either deadline; there is no fallback."""
    context = multiprocessing.get_context("spawn")
    receiving, sending = context.Pipe(duplex=False)
    worker = context.Process(target=_prepare_worker,
        args=(str(folder), language, str(Path(__file__).resolve().parent), sending), daemon=True)
    started = time.monotonic()
    page_started = None
    complete = False
    worker.start()
    sending.close()
    try:
        while True:
            now = time.monotonic()
            remaining = IMPORT_TIMEOUT_SECONDS - (now - started)
            if page_started is not None:
                remaining = min(remaining, PAGE_TIMEOUT_SECONDS - (now - page_started))
            if remaining <= 0:
                _fail("import_timeout", 409)
            if receiving.poll(min(0.25, remaining)):
                try:
                    message = receiving.recv()
                except EOFError:
                    _fail("import_worker_failed")
                if message[0] == "page":
                    page_started = time.monotonic()
                elif message[0] == "done":
                    page_started = None
                elif message[0] == "error":
                    code = message[1] if type(message[1]) is str and _CODE.fullmatch(message[1]) else "import_failed"
                    _fail(code, message[2] if message[2] in {409, 413, 422, 503} else 422)
                elif message[0] == "complete":
                    complete = True
                    break
                else:
                    _fail("import_worker_failed")
            elif not worker.is_alive():
                _fail("import_worker_failed")
        worker.join(timeout=min(2.0, max(0.0, IMPORT_TIMEOUT_SECONDS - (time.monotonic() - started))))
        if worker.is_alive() or worker.exitcode != 0 or not complete:
            _fail("import_worker_failed")
    finally:
        receiving.close()
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=2)
        if worker.is_alive():
            worker.kill()
            worker.join(timeout=2)
        worker.close()


class SavedDocxLayoutService:
    enabled = True

    @_public
    def __init__(self, root, *, mode, workspace_id):
        if (mode not in {"live", "shadow"} or type(workspace_id) is not str
                or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?", workspace_id)):
            _fail("invalid_owner")
        self.app_root = _direct(root, directory=True, missing=True)
        self.root = self.app_root / "saved_docx_layout" / workspace_id
        self._owner = {"mode": mode, "workspace_id": workspace_id, "root": str(self.root)}

    @_public
    def capabilities(self):
        available = importlib.util.find_spec("fitz") is not None
        return {"status": "available" if available else "unavailable", "available": available,
            "languages": ["EN", "AR", "FR"], "profile": PROFILE,
            "provider_required": False, "native_renderer_required": False,
            "limits": {"docx_bytes": DOCX_MAX_BYTES, "pdf_bytes": PDF_MAX_BYTES,
                "expanded_package_bytes": 128 * 1024 * 1024, "expanded_member_bytes": 32 * 1024 * 1024,
                "zip_members": 2048, "body_paragraphs": 10000, "content_codepoints": 8_000_000,
                "source_pages": MAX_SOURCE_PAGES, "page_pixels": MAX_PAGE_PIXELS,
                "raster_bytes": MAX_RASTER_BYTES, "render_dpi": RENDER_DPI,
                "page_seconds": PAGE_TIMEOUT_SECONDS, "import_seconds": IMPORT_TIMEOUT_SECONDS,
                "reviews": MAX_REVIEWS, "generations": MAX_GENERATIONS, "builds": MAX_BUILDS,
                "generation_bytes": MAX_GENERATION_BYTES}}

    def _workspace(self, *, create=False):
        if not self.root.exists():
            if not create:
                _fail("not_found", 404)
            _mkdir(self.root)
        root = _direct(self.root, directory=True)
        owner_file = root / "owner.json"
        expected = {"version": VERSION, "owner": self._owner}
        if not owner_file.exists() and create:
            with run_workspace_slot(root):
                _write_once(owner_file, expected)
        if _decode(_read(owner_file)) != expected:
            _fail("owner_changed", 409)
        return root

    def _folder(self, review_id):
        self._workspace()
        return _direct(self.root / "reviews" / _identifier(review_id), directory=True)

    @contextmanager
    def _scope(self, review_id):
        folder = self._folder(review_id)
        with run_workspace_slot(folder):
            self._workspace()
            yield folder

    def _load(self, folder, *, images=False, complete=True):
        manifest_raw = _read(folder / "import.json")
        manifest = _decode(manifest_raw)
        marker = _decode(_read(folder / "import_complete.json")) if complete else {"manifest_sha256": _sha(manifest_raw)}
        if (manifest.get("version") != VERSION or manifest.get("owner") != self._owner
                or manifest.get("review_id") != folder.name or marker != {"manifest_sha256": _sha(manifest_raw)}):
            _fail("import_changed", 409)
        retained = {}
        for name, maximum in (("original.docx", DOCX_MAX_BYTES), ("source.pdf", PDF_MAX_BYTES),
                              ("snapshot.json", SNAPSHOT_MAX_BYTES), ("pages.json", RECORD_MAX_BYTES)):
            raw = _read(folder / name, maximum)
            if manifest["files"].get(name) != {"sha256": _sha(raw), "bytes": len(raw)}:
                _fail("snapshot_changed", 409)
            retained[name] = raw
        snapshot = _decode(retained["snapshot.json"])
        pages = _decode(retained["pages.json"])
        if (snapshot.get("docx_sha256") != manifest["files"]["original.docx"]["sha256"]
                or snapshot.get("target_lang") != manifest["target_lang"]
                or type(pages) is not list or not 1 <= len(pages) <= MAX_SOURCE_PAGES):
            _fail("snapshot_changed", 409)
        aggregate = 0
        for number, page in enumerate(pages, 1):
            if (page.get("page_number") != number or type(page.get("width_px")) is not int
                    or type(page.get("height_px")) is not int
                    or min(page["width_px"], page["height_px"]) < 1
                    or page["width_px"] * page["height_px"] > MAX_PAGE_PIXELS
                    or type(page.get("image_sha256")) is not str or not _HASH.fullmatch(page["image_sha256"])):
                _fail("snapshot_changed", 409)
            if images:
                raw = _read(folder / "images" / f"page-{number:04d}.png", MAX_RASTER_BYTES)
                aggregate += len(raw)
                if aggregate > MAX_RASTER_BYTES or _sha(raw) != page["image_sha256"]:
                    _fail("source_image_changed", 409)
        return manifest, snapshot, pages

    def _generations(self, folder):
        from .saved_docx_layout import default_decisions, validate_decisions
        _, snapshot, pages = self._load(folder)
        root = _direct(folder / "generations", directory=True)
        files = sorted(root.glob("*.json"))
        if not 1 <= len(files) <= MAX_GENERATIONS:
            _fail("generation_changed", 409)
        previous = None
        total = 0
        rows = []
        seen_nonces = set()
        for number, path in enumerate(files, 1):
            if path.name != f"{number:06d}.json":
                _fail("generation_changed", 409)
            raw = _read(path, DECISIONS_MAX_BYTES + RECORD_MAX_BYTES)
            total += len(raw)
            if total > MAX_GENERATION_BYTES:
                _fail("generation_limit", 413)
            row = _decode(raw)
            if (set(row) != {"version", "generation", "previous_sha256", "save_nonce", "request_sha256", "decisions"}
                    or row["version"] != VERSION or type(row["generation"]) is not int
                    or row["generation"] != number or row["previous_sha256"] != previous):
                _fail("generation_changed", 409)
            normalized = validate_decisions(snapshot, pages, row["decisions"])
            if _encode(normalized, DECISIONS_MAX_BYTES) != _encode(row["decisions"], DECISIONS_MAX_BYTES):
                _fail("generation_changed", 409)
            if number == 1:
                if (row["save_nonce"] is not None or row["request_sha256"] is not None
                        or normalized != default_decisions(snapshot, pages)):
                    _fail("generation_changed", 409)
            else:
                nonce = _identifier(row["save_nonce"])
                if nonce in seen_nonces or type(row["request_sha256"]) is not str or not _HASH.fullmatch(row["request_sha256"]):
                    _fail("generation_changed", 409)
                expected_request = _sha(_encode({"expected_generation": number - 1, "decisions": normalized},
                                                DECISIONS_MAX_BYTES + RECORD_MAX_BYTES))
                if row["request_sha256"] != expected_request:
                    _fail("generation_changed", 409)
                seen_nonces.add(nonce)
            previous = _sha(raw)
            rows.append(row)
        return rows, previous, total

    def _save_receipt(self, folder, row):
        if row["save_nonce"] is not None:
            _mkdir(folder / "saves")
            _write_once(folder / "saves" / (row["save_nonce"] + ".json"),
                {"generation": row["generation"], "save_nonce": row["save_nonce"],
                 "request_sha256": row["request_sha256"]})

    def _verified_artifact(self, folder, attempt, intent):
        record_raw = _read(attempt / "result.json")
        record = _decode(record_raw)
        if (record.get("version") != VERSION or record.get("intent_sha256") != _sha(_read(attempt / "intent.json"))
                or record.get("artifact_id") != intent["artifact_id"] or record.get("generation") != intent["generation"]
                or set(record.get("files", {})) != {"docx", "source_map", "receipt"}):
            _fail("artifact_changed", 409)
        values = {}
        for kind, name, maximum in (("docx", "output.docx", DOCX_MAX_BYTES),
                                     ("source_map", "source_map.json", SNAPSHOT_MAX_BYTES),
                                     ("receipt", "receipt.json", RECORD_MAX_BYTES)):
            raw = _read(attempt / name, maximum)
            if record["files"][kind] != {"sha256": _sha(raw), "bytes": len(raw)}:
                _fail("artifact_changed", 409)
            values[kind] = raw
        receipt = _decode(values["receipt"])
        if (receipt.get("review_id") != folder.name or receipt.get("artifact_id") != intent["artifact_id"]
                or receipt.get("generation") != intent["generation"]
                or receipt.get("decision_sha256") != intent["decision_sha256"]
                or receipt.get("docx_sha256") != _sha(values["docx"])
                or receipt.get("source_map_sha256") != _sha(values["source_map"])
                or receipt.get("provider_dispatch_count") != 0
                or receipt.get("rendered_layout_acceptance") != "not_evaluated"):
            _fail("artifact_changed", 409)
        marker = {"result_sha256": _sha(record_raw)}
        complete_path = attempt / "complete.json"
        if complete_path.exists():
            if _decode(_read(complete_path)) != marker:
                _fail("artifact_changed", 409)
        else:
            # All exact publication evidence exists; finish only its marker.
            _write(complete_path, marker)
        return values

    def _builds(self, folder, manifest, generations):
        rows, artifacts = [], []
        for attempt in _folders(folder / "builds", MAX_BUILDS):
            intent_path = attempt / "intent.json"
            if not intent_path.exists():
                rows.append({"operation_nonce": attempt.name, "status": "incomplete", "generation": None})
                continue
            intent = _decode(_read(intent_path))
            generation = intent.get("generation")
            if (intent.get("version") != VERSION or intent.get("owner") != self._owner
                    or intent.get("review_id") != folder.name or intent.get("operation_nonce") != attempt.name
                    or type(generation) is not int or not 1 <= generation <= len(generations)
                    or intent.get("decision_sha256") != _sha(_encode(generations[generation - 1]["decisions"], DECISIONS_MAX_BYTES))
                    or intent.get("input_files") != manifest["files"]):
                _fail("build_changed", 409)
            _identifier(intent["artifact_id"])
            row = {"operation_nonce": attempt.name, "generation": generation, "status": "incomplete"}
            if (attempt / "complete.json").exists() or (attempt / "result.json").exists():
                self._verified_artifact(folder, attempt, intent)
                row.update(status="built", artifact_id=intent["artifact_id"])
                artifacts.append({"artifact_id": intent["artifact_id"], "generation": generation,
                                  "kinds": ["docx", "source_map", "receipt"]})
            rows.append(row)
        return rows, artifacts

    def _view(self, folder, manifest, snapshot, pages, generations):
        decisions = generations[-1]["decisions"]
        builds, artifacts = self._builds(folder, manifest, generations)
        reviewed = decisions.get("review", {}).get("document_reviewed") is True
        status = "reviewed" if reviewed else "draft" if len(generations) > 1 else "imported"
        if any(row["generation"] == len(generations) for row in artifacts):
            status = "built"
        qualifications = [{"paragraph_id": row["paragraph_id"], "reason": row["unmapped_reason"]}
                          for row in decisions.get("paragraphs", []) if row.get("unmapped_reason")]
        return {"review_id": folder.name, "import_nonce": manifest["import_nonce"],
            "created_at": manifest["created_at"], "generation": len(generations), "status": status,
            "target_lang": manifest["target_lang"], "paragraphs": [{k: row[k] for k in
                ("id", "ordinal", "text", "has_page_break")} for row in snapshot["paragraphs"]],
            "pages": deepcopy(pages), "decisions": deepcopy(decisions), "qualifications": qualifications,
            "builds": builds, "artifacts": artifacts, "saves": [{"save_nonce": row["save_nonce"],
                "generation": row["generation"]} for row in generations if row["save_nonce"] is not None],
            "rendered_layout_acceptance": "not_evaluated"}

    @_public
    def import_document(self, source_pdf, saved_docx, target_lang, import_nonce):
        from .saved_docx_layout import default_decisions, validate_decisions
        _raw_bytes(source_pdf, PDF_MAX_BYTES)
        _raw_bytes(saved_docx, DOCX_MAX_BYTES)
        _identifier(import_nonce)
        if target_lang not in {"EN", "AR", "FR"}:
            _fail("invalid_language")
        if not self.capabilities()["available"]:
            _fail("renderer_unavailable", 503)
        root = self._workspace(create=True)
        identity = {"source_pdf_sha256": _sha(source_pdf), "saved_docx_sha256": _sha(saved_docx), "target_lang": target_lang}
        with run_workspace_slot(root):
            imports = _mkdir(root / "imports")
            imported = imports / (import_nonce + ".json")
            if imported.exists():
                record = _decode(_read(imported))
                if record.get("identity") != identity or record.get("owner") != self._owner:
                    _fail("nonce_conflict", 409)
                folder = self._folder(record["review_id"])
                with run_workspace_slot(folder):
                    if not (folder / "import_complete.json").exists():
                        _fail("import_incomplete", 409)
                    manifest, snapshot, pages = self._load(folder)
                    generations, _, _ = self._generations(folder)
                    return self._view(folder, manifest, snapshot, pages, generations)
            reviews = _mkdir(root / "reviews")
            if len(_folders(reviews, MAX_REVIEWS)) >= MAX_REVIEWS:
                _fail("registry_limit", 413)
            review_id = uuid.uuid4().hex
            folder = reviews / review_id
            folder.mkdir()
            _write(imported, {"version": VERSION, "owner": self._owner, "identity": identity, "review_id": review_id})
            with run_workspace_slot(folder):
                try:
                    _atomic(folder / "source.pdf", source_pdf)
                    _atomic(folder / "original.docx", saved_docx)
                    _prepare_import(folder, target_lang)
                    snapshot = _decode(_read(folder / "snapshot.json", SNAPSHOT_MAX_BYTES))
                    pages = _decode(_read(folder / "pages.json"))
                    decisions = validate_decisions(snapshot, pages, default_decisions(snapshot, pages))
                    files = {}
                    for name, maximum in (("source.pdf", PDF_MAX_BYTES), ("original.docx", DOCX_MAX_BYTES),
                                          ("snapshot.json", SNAPSHOT_MAX_BYTES), ("pages.json", RECORD_MAX_BYTES)):
                        raw = _read(folder / name, maximum)
                        files[name] = {"sha256": _sha(raw), "bytes": len(raw)}
                    if (files["source.pdf"]["sha256"] != identity["source_pdf_sha256"]
                            or files["original.docx"]["sha256"] != identity["saved_docx_sha256"]):
                        _fail("import_inputs_changed", 409)
                    manifest = {"version": VERSION, "owner": self._owner, "review_id": review_id,
                        "import_nonce": import_nonce, "target_lang": target_lang, "created_at": _utc(), "files": files}
                    manifest_raw = _write(folder / "import.json", manifest)
                    _mkdir(folder / "generations")
                    _write(folder / "generations" / "000001.json", {"version": VERSION, "generation": 1,
                        "previous_sha256": None, "save_nonce": None, "request_sha256": None, "decisions": decisions},
                        DECISIONS_MAX_BYTES + RECORD_MAX_BYTES)
                    manifest, snapshot, pages = self._load(folder, images=True, complete=False)
                    _write(folder / "import_complete.json", {"manifest_sha256": _sha(manifest_raw)})
                    generations, _, _ = self._generations(folder)
                    return self._view(folder, manifest, snapshot, pages, generations)
                except Exception as exc:
                    code = getattr(exc, "code", "saved_docx_layout_import_failed")
                    if type(code) is not str or not _CODE.fullmatch(code):
                        code = "saved_docx_layout_import_failed"
                    _write_once(folder / "import_failed.json", {"code": code})
                    raise

    @_public
    def list_reviews(self):
        if not self.root.exists():
            return []
        self._workspace()
        result = []
        for folder in _folders(self.root / "reviews", MAX_REVIEWS):
            if not (folder / "import_complete.json").exists():
                continue
            try:
                view = self.read(folder.name)
            except SavedDocxLayoutServiceError as exc:
                if exc.status == 409 and exc.code == "saved_docx_layout_busy":
                    result.append({"review_id": folder.name, "status": "building", "builds": [], "artifacts": []})
                    continue
                raise
            result.append({k: view[k] for k in ("review_id", "import_nonce", "generation", "status", "target_lang",
                                               "created_at", "builds", "artifacts")}
                          | {"page_count": len(view["pages"]), "paragraph_count": len(view["paragraphs"])})
        return sorted(result, key=lambda r: r.get("created_at", ""), reverse=True)

    @_public
    def read(self, review_id):
        with self._scope(review_id) as folder:
            manifest, snapshot, pages = self._load(folder)
            generations, _, _ = self._generations(folder)
            for row in generations:
                self._save_receipt(folder, row)
            return self._view(folder, manifest, snapshot, pages, generations)

    @_public
    def image(self, review_id, page_number):
        with self._scope(review_id) as folder:
            _, _, pages = self._load(folder)
            if type(page_number) is not int or not 1 <= page_number <= len(pages):
                _fail("page_not_found", 404)
            raw = _read(folder / "images" / f"page-{page_number:04d}.png", MAX_RASTER_BYTES)
            if _sha(raw) != pages[page_number - 1]["image_sha256"]:
                _fail("source_image_changed", 409)
            return raw

    @_public
    def save_decisions(self, review_id, expected_generation, save_nonce, decisions):
        from .saved_docx_layout import validate_decisions
        _integer(expected_generation)
        _identifier(save_nonce)
        _encode(decisions, DECISIONS_MAX_BYTES)
        with self._scope(review_id) as folder:
            manifest, snapshot, pages = self._load(folder)
            normalized = validate_decisions(snapshot, pages, decisions)
            request_hash = _sha(_encode({"expected_generation": expected_generation, "decisions": normalized},
                                       DECISIONS_MAX_BYTES + RECORD_MAX_BYTES))
            generations, previous, total = self._generations(folder)
            matching = [row for row in generations if row["save_nonce"] == save_nonce]
            if matching:
                if matching[0]["request_sha256"] != request_hash:
                    _fail("nonce_conflict", 409)
                self._save_receipt(folder, matching[0])
                return self._view(folder, manifest, snapshot, pages, generations)
            if expected_generation != len(generations):
                _fail("generation_conflict", 409)
            number = len(generations) + 1
            if number > MAX_GENERATIONS:
                _fail("generation_limit", 413)
            row = {"version": VERSION, "generation": number, "previous_sha256": previous,
                   "save_nonce": save_nonce, "request_sha256": request_hash, "decisions": normalized}
            raw = _encode(row, DECISIONS_MAX_BYTES + RECORD_MAX_BYTES)
            if total + len(raw) > MAX_GENERATION_BYTES:
                _fail("generation_limit", 413)
            _atomic(folder / "generations" / f"{number:06d}.json", raw)
            self._save_receipt(folder, row)
            generations.append(row)
            return self._view(folder, manifest, snapshot, pages, generations)

    @_public
    def build(self, review_id, expected_generation, operation_nonce, review_confirmed):
        from .saved_docx_layout import validate_decisions
        from .saved_docx_layout_writer import build_docx
        _integer(expected_generation)
        _identifier(operation_nonce)
        if review_confirmed is not True:
            _fail("review_required", 409)
        with self._scope(review_id) as folder:
            manifest, snapshot, pages = self._load(folder, images=True)
            generations, _, _ = self._generations(folder)
            builds, artifacts = self._builds(folder, manifest, generations)
            matching = next((row for row in builds if row["operation_nonce"] == operation_nonce), None)
            if matching is not None:
                if matching["generation"] != expected_generation:
                    _fail("nonce_conflict", 409)
                if matching["status"] != "built":
                    _fail("build_incomplete", 409)
                return self._view(folder, manifest, snapshot, pages, generations) | {
                    "operation_nonce": operation_nonce, "artifact_id": matching["artifact_id"]}
            if expected_generation != len(generations):
                _fail("generation_conflict", 409)
            decisions = validate_decisions(snapshot, pages, generations[-1]["decisions"], require_review=True)
            if len(builds) >= MAX_BUILDS:
                _fail("build_limit", 413)
            root = _mkdir(folder / "builds")
            attempt = root / operation_nonce
            attempt.mkdir()
            artifact_id = uuid.uuid4().hex
            intent = {"version": VERSION, "owner": self._owner, "review_id": review_id,
                "operation_nonce": operation_nonce, "artifact_id": artifact_id, "generation": expected_generation,
                "decision_sha256": _sha(_encode(decisions, DECISIONS_MAX_BYTES)), "input_files": manifest["files"]}
            intent_raw = _write(attempt / "intent.json", intent)
            result = build_docx(_read(folder / "original.docx", DOCX_MAX_BYTES), snapshot, pages, decisions)
            _raw_bytes(result.docx_bytes, DOCX_MAX_BYTES)
            mapping = _encode(result.source_map, SNAPSHOT_MAX_BYTES)
            # Recheck all retained inputs/generations before publishing bytes.
            checked, _, _ = self._load(folder, images=True)
            checked_generations, _, _ = self._generations(folder)
            if checked != manifest or checked_generations != generations:
                _fail("inputs_changed", 409)
            qualifications = [{"paragraph_id": row["paragraph_id"], "reason": row["unmapped_reason"]}
                              for row in decisions["paragraphs"] if row.get("unmapped_reason")]
            receipt = {"version": VERSION, "profile": PROFILE, "review_id": review_id,
                "artifact_id": artifact_id, "generation": expected_generation,
                "input_files": manifest["files"], "decision_sha256": intent["decision_sha256"],
                "docx_sha256": _sha(result.docx_bytes), "source_map_sha256": _sha(mapping),
                "writer_version": result.source_map.get("writer_version", result.source_map.get("version")),
                "exact_text_preserved": True, "provider_dispatch_count": 0,
                "rendered_layout_acceptance": "not_evaluated", "qualifications": qualifications}
            raw_receipt = _encode(receipt)
            _atomic(attempt / "output.docx", result.docx_bytes)
            _atomic(attempt / "source_map.json", mapping)
            _atomic(attempt / "receipt.json", raw_receipt)
            _write(attempt / "result.json", {"version": VERSION, "intent_sha256": _sha(intent_raw),
                "artifact_id": artifact_id, "generation": expected_generation, "files": {
                    kind: {"sha256": _sha(raw), "bytes": len(raw)} for kind, raw in
                    (("docx", result.docx_bytes), ("source_map", mapping), ("receipt", raw_receipt))}})
            self._verified_artifact(folder, attempt, intent)
            return self._view(folder, manifest, snapshot, pages, generations) | {
                "operation_nonce": operation_nonce, "artifact_id": artifact_id}

    @_public
    def artifact(self, review_id, artifact_id, kind):
        _identifier(artifact_id)
        if kind not in {"docx", "source_map", "receipt"}:
            _fail("artifact_not_found", 404)
        with self._scope(review_id) as folder:
            manifest, _, _ = self._load(folder, images=True)
            generations, _, _ = self._generations(folder)
            builds, _ = self._builds(folder, manifest, generations)
            row = next((r for r in builds if r.get("artifact_id") == artifact_id and r["status"] == "built"), None)
            if row is None:
                _fail("artifact_not_found", 404)
            attempt = folder / "builds" / row["operation_nonce"]
            return self._verified_artifact(folder, attempt, _decode(_read(attempt / "intent.json")))[kind]
