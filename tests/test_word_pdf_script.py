"""Safety contracts for the unattended helper; these tests never launch Word."""

from pathlib import Path
import base64
import os
import json
import re
import shutil
import subprocess

import pytest

from legalpdf_translate.word_pdf_script import build_pdf_script


def _script(tmp_path: Path) -> str:
    return build_pdf_script(
        tmp_path / "João's staged source.docx",
        tmp_path / "fresh output.pdf",
        state_path=tmp_path / "worker state.json",
        word_executable=tmp_path / "never-executable" / "WINWORD.EXE",
    )


def test_pdf_script_requires_both_export_paths_or_neither(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="together"):
        build_pdf_script(tmp_path / "source.docx", None, state_path=tmp_path / "state.json")
    with pytest.raises(ValueError, match="together"):
        build_pdf_script(None, tmp_path / "out.pdf", state_path=tmp_path / "state.json")


def test_pdf_script_quotes_literal_paths_without_interpolation(tmp_path: Path) -> None:
    script = _script(tmp_path)
    assert str((tmp_path / "João's staged source.docx").resolve()).replace("'", "''") in script
    assert str((tmp_path / "worker state.json").resolve()).replace("'", "''") in script


def test_pdf_script_never_attaches_activates_bootstraps_or_force_kills(tmp_path: Path) -> None:
    script = _script(tmp_path)
    assert "[Diagnostics.Process]::Start($startInfo)" in script
    assert "$startInfo.Arguments = '/w'" in script
    assert "$startInfo.UseShellExecute = $true" in script
    assert "$startInfo.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden" in script
    for forbidden in (
        "GetActiveObject", "-ComObject", "Start-Process", "Stop-Process", "taskkill", ".Kill(",
        ".Activate(", "DisplayAlerts", "SaveNormalPrompt", "Save()", "/automation",
    ):
        assert forbidden not in script


def test_pdf_script_proves_com_bound_process_before_changing_word(tmp_path: Path) -> None:
    script = _script(tmp_path)
    assert "GetWindowThreadProcessId" in script
    assert "$preExistingWordPids -contains $wordProcess.Id" in script
    assert "$wordProcess.SessionId -ne $helperSessionId" in script
    assert "$wordProcess.ProcessName -ine 'WINWORD'" in script
    assert "$wordProcess.StartTime.ToUniversalTime().Ticks -lt $launchStartedTicks" in script
    proven = script.index("$state.ownership = 'proven'")
    assert script.index("$initialDocumentCount -ne 1") < proven
    assert "AccessibleObjectFromWindow" in script
    assert "$word.Hwnd" not in script
    assert "$bootstrapWindow.Hwnd" in script
    assert proven < script.index("$word.Visible = $false")
    assert proven < script.index("$word.AutomationSecurity = 3")


def test_pdf_script_stages_hidden_read_only_open_and_full_print_export(tmp_path: Path) -> None:
    script = _script(tmp_path)
    assert "# ReadOnly=true, AddToRecentFiles=false, Visible=false" in script
    assert "$documents.Open(" in script
    assert "$target, $false, $true, $false," in script
    assert "$missing, $missing, $missing, $missing, $false)" in script
    assert "# PDF, no viewer, print quality, all pages, document content" in script
    assert "$doc.ExportAsFixedFormat(" in script
    assert "$pdfPath, 17, $false, 0, 0, 1, 1, 0, $true, $true," in script


def test_open_uses_common_documented_prefix_without_disputed_optional_tail(tmp_path: Path) -> None:
    # Microsoft VBA and current PIA docs disagree after position 12. Keep their
    # identical common prefix; do not pass a Boolean as optional XMLTransform or
    # DocumentDirection, or request repair, an encoding bypass, or a transform.
    call = re.search(r"\$documents\.Open\((.*?)\)", _script(tmp_path), re.DOTALL)
    assert call is not None
    values = [part.strip() for part in call.group(1).split(",")]
    expected = {
        "FileName": "$target", "ConfirmConversions": "$false", "ReadOnly": "$true",
        "AddToRecentFiles": "$false", "PasswordDocument": "$missing",
        "PasswordTemplate": "$missing", "Revert": "$false",
        "WritePasswordDocument": "$missing", "WritePasswordTemplate": "$missing",
        "Format": "$missing", "Encoding": "$missing", "Visible": "$false",
    }
    assert values == list(expected.values())


def test_export_omits_optional_extension_pointer_and_preserves_native_options(tmp_path: Path) -> None:
    call = re.search(r"\$doc\.ExportAsFixedFormat\((.*?)\)", _script(tmp_path), re.DOTALL)
    assert call is not None
    values = [part.strip() for part in call.group(1).split(",")]
    assert values == [
        "$pdfPath", "17", "$false", "0", "0", "1", "1", "0", "$true", "$true",
        "0", "$true", "$true", "$false",
    ]


def test_pdf_script_persists_durable_atomic_state_and_safe_primary_failure(tmp_path: Path) -> None:
    script = _script(tmp_path)
    for field in (
        "schema_version", "primary_failure_phase", "primary_hresult", "helper_pid",
        "word_pid", "word_start_ticks", "ownership", "cleanup_status", "cleanup_phase",
        "cleanup_hresult", "document_owned",
        "helper_start_ticks", "launch_attempted", "word_identity_verified",
    ):
        assert field in script
    assert "$stream.Flush($true)" in script
    assert "[IO.File]::Replace(" in script
    assert "[IO.File]::Replace($temporaryPath, $statePath, [NullString]::Value)" in script
    assert "[IO.File]::Move(" in script
    assert "if (-not $state.primary_failure_phase)" in script
    assert ".Exception.Message" not in script
    assert "Write-Error" not in script
    assert "Out-String" not in script


def test_pdf_script_limits_retries_to_known_rejected_calls(tmp_path: Path) -> None:
    script = _script(tmp_path)
    assert "$attempt -le 3" in script
    assert "@('0x80010001', '0x8001010A') -notcontains $hresult" in script
    assert "Set-Phase $Phase" in script
    assert "Start-Sleep -Milliseconds 150" in script
    assert "$wordProcess = [Diagnostics.Process]::Start($startInfo)" in script
    assert "Invoke-Com 'launch_word'" not in script
    assert "-not $RetryRead" in script
    for mutation in ("open_document", "export_pdf", "close_document", "quit_word"):
        assert not any(mutation in line and "-RetryRead" in line for line in script.splitlines())


def test_pdf_script_revalidates_identity_and_exact_document_before_cleanup(tmp_path: Path) -> None:
    script = _script(tmp_path)
    assert "function Assert-OwnedProcess" in script
    assert "$wordProcess.StartTime.ToUniversalTime().Ticks.ToString() -ne $state.word_start_ticks" in script
    assert "function Assert-StagedDocument" in script
    assert "[string]::Equals($actualPath, $target, [StringComparison]::OrdinalIgnoreCase)" in script
    assert "Assert-StagedDocument 'cleanup_document_identity'" in script
    assert "if ($remainingCount -ne 1)" in script
    assert "Invoke-Com 'quit_word' { $word.Quit(0) }" in script
    assert "FinalReleaseComObject" in script
    assert "$state.cleanup_status = 'ambiguous'" in script
    assert "Assert-BootstrapUnchanged 'cleanup_bootstrap'" in script
    assert "$bootstrapDoc.Close(0)" not in script
    assert "if ($remainingCount -ne 1)" in script
    assert "SameComIdentity" in script
    assert "Assert-NoProtectedView" in script


def test_preflight_uses_same_ownership_and_cleanup_without_opening_document(tmp_path: Path) -> None:
    script = build_pdf_script(None, None, state_path=tmp_path / "state.json")
    assert "$mode = 'preflight'" in script
    assert "$target = $null" in script
    assert "if ($mode -eq 'export')" in script
    assert "Invoke-Com 'quit_word' { $word.Quit(0) }" in script


def test_documents_com_collection_is_not_unrolled_into_document_items(tmp_path: Path) -> None:
    script = _script(tmp_path)
    assert "return ,(& $Action)" in script
    assert "'get_documents' { ,$word.Documents }" in script


@pytest.mark.skipif(os.name != "nt", reason="PowerShell parser is Windows-only")
@pytest.mark.parametrize("export", [False, True])
def test_generated_helper_parses_without_executing_it(tmp_path: Path, export: bool) -> None:
    powershell = shutil.which("powershell.exe")
    if powershell is None:
        pytest.skip("PowerShell parser unavailable")
    script = _script(tmp_path) if export else build_pdf_script(
        None, None, state_path=tmp_path / "state.json"
    )
    # ParseInput builds an AST only. No generated statement, COM call, native
    # identity function, or Word process is ever executed in this test.
    parser = """
[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
$source = [Console]::In.ReadToEnd()
$tokens = $null
$parseErrors = $null
$null = [Management.Automation.Language.Parser]::ParseInput($source, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -ne 0) {
    $parseErrors | ForEach-Object { Write-Output $_.ErrorId }
    exit 1
}
Write-Output 'PARSE_OK'
"""
    result = subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand",
         base64.b64encode(parser.encode("utf-16-le")).decode("ascii")],
        input=script, capture_output=True, text=True, encoding="utf-8", timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout
    assert result.stdout.strip() == "PARSE_OK"


_FAKE_RUNTIME = r"""
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
namespace WordPdfTest {
    public static class Runtime {
        public static string Scenario = "success";
        public static string StatePath;
        public static DateTime WordStart;
        public static bool WordExited;
        public static bool Reused;
        public static int HwndReads;
        public static FakeWord Word;
        public static string Executable;
        public static bool BootstrapChanged;
        public static bool ProtectedViewAdded;
        public static bool CountDisconnected;
        public static void Record(string action, string phase) {
            Console.WriteLine("FAKE:" + action);
            if (phase != null && !File.ReadAllText(StatePath).Contains("\"phase\":\"" + phase + "\""))
                throw new InvalidOperationException("Phase was not durable before fake operation");
        }
        public static void Fail(string action) {
            if (Scenario == action + "_failure" ||
                (Scenario == "export_and_close_failure" && (action == "export" || action == "close")))
                throw new COMException("PRIVATE_DOCUMENT_TEXT C:/private/case.docx", unchecked((int)0x80004005));
        }
    }
    public class FakeProcess : IDisposable {
        public int Id { get; set; }
        public int SessionId { get { return 12; } }
        public string ProcessName { get { return Id == 789 ? "WINWORD" : "powershell"; } }
        public FakeModule MainModule { get { return new FakeModule(); } }
        public bool HasExited { get { return Runtime.WordExited; } }
        public DateTime StartTime {
            get {
                if (Id != 789) return DateTime.UtcNow.AddMinutes(-5);
                return Runtime.Reused ? Runtime.WordStart.AddMinutes(1) : Runtime.WordStart;
            }
        }
        public static FakeProcess GetCurrentProcess() { return new FakeProcess { Id = 456 }; }
        public static FakeProcess GetProcessById(int pid) { return new FakeProcess { Id = pid }; }
        public static FakeProcess Start(System.Diagnostics.ProcessStartInfo info) {
            Runtime.Record("launch", "launch_word");
            Runtime.Fail("launch");
            if (info.Arguments != "/w" || !info.UseShellExecute || info.WindowStyle != System.Diagnostics.ProcessWindowStyle.Hidden)
                throw new Exception("Incorrect process-first launch");
            if (File.Exists(info.FileName)) throw new Exception("Fake executable must not exist");
            Runtime.Executable = info.FileName;
            Runtime.WordStart = Runtime.Scenario == "preexisting" ? DateTime.UtcNow.AddHours(-1) : DateTime.UtcNow;
            Runtime.Word = new FakeWord();
            return new FakeProcess { Id = 789 };
        }
        public void Refresh() { }
        public bool WaitForExit(int timeout) { Runtime.Record("wait_exit", "confirm_word_exit"); return Runtime.WordExited; }
        public void Dispose() { }
    }
    public class FakeModule { public string FileName { get { return Runtime.Executable; } } }
    public static class FakeMarshal {
        public static bool IsComObject(object obj) { return true; }
        public static int FinalReleaseComObject(object obj) { Runtime.Record("release", null); return 0; }
        public static int ReleaseComObject(object obj) { Runtime.Record("release_extra", null); return 0; }
    }
    public class FakeWord {
        public FakeDocuments Documents { get; private set; }
        public FakeDocument Bootstrap { get; private set; }
        public FakeCountCollection ProtectedViewWindows { get { return new FakeCountCollection(
            Runtime.Scenario == "protected_view" || Runtime.ProtectedViewAdded ? 1 : 0); } }
        public int GetHwnd() {
                Runtime.HwndReads++;
                Runtime.Record("hwnd", null);
                if (Runtime.Scenario == "transient_read" && Runtime.HwndReads <= 2)
                    throw new COMException("PRIVATE_DOCUMENT_TEXT", unchecked((int)0x80010001));
                if (Runtime.Scenario == "permanent_read")
                    throw new COMException("PRIVATE_DOCUMENT_TEXT", unchecked((int)0x80004005));
                return 123;
        }
        public bool Visible { set { Runtime.Record("visible", "set_hidden"); if (value) throw new Exception("Visible"); } }
        public int AutomationSecurity { set { Runtime.Record("security", "disable_automation_macros"); if (value != 3) throw new Exception("Macros"); } }
        public FakeWord() {
            Documents = new FakeDocuments();
            Bootstrap = new FakeDocument(Documents, "", true);
            Documents.Items.Add(Bootstrap);
            if (Runtime.Scenario == "preexisting_document") Documents.Items.Add(new FakeDocument(Documents, "USER_DOCUMENT"));
        }
        public void Quit(object save) {
            Runtime.Record("quit", "quit_word");
            Runtime.Fail("quit");
            if (Documents.Count != 1 || !Object.ReferenceEquals(Documents.Items[0], Bootstrap) || Bootstrap.Closed)
                throw new Exception("Only the exact validated bootstrap may remain for scoped quit");
            Runtime.WordExited = true;
        }
    }
    public class FakeWindow {
        public FakeWord Application { get { return Runtime.Word; } }
        public FakeDocument Document { get { return Runtime.Word.Bootstrap; } }
        public int GetHwnd() {
            if (Runtime.Word.Bootstrap.Closed) throw new Exception("Closed bootstrap window queried");
            return Runtime.Word.GetHwnd();
        }
    }
    public class FakeCountCollection : IEnumerable {
        public int Count { get; private set; }
        public FakeCountCollection(int count) { Count = count; }
        public IEnumerator GetEnumerator() { return new object[0].GetEnumerator(); }
    }
    public class FakeRange { public string GetText() {
        Runtime.Fail("bootstrap_read");
        return Runtime.Scenario == "nonempty_bootstrap" ? "USER_TEXT\r" : "\r";
    } }
    // IEnumerable is essential: this reproduces PowerShell's collection-unrolling
    // semantics, including an empty Documents collection before opening anything.
    public class FakeDocuments : IEnumerable {
        public List<FakeDocument> Items = new List<FakeDocument>();
        public int? Count { get { return Runtime.CountDisconnected ? (int?)null : Items.Count; } }
        public IEnumerator GetEnumerator() { return Items.GetEnumerator(); }
        public FakeDocument Item(int index) { return Items[index - 1]; }
        public FakeDocument Open(object path, object confirm, object readOnly, object mru,
            object password, object templatePassword, object revert, object writePassword,
            object writeTemplatePassword, object format, object encoding, object visible) {
            Runtime.Record("open", "open_document");
            Runtime.Fail("open");
            if (!(bool)readOnly || (bool)mru || (bool)visible || (bool)revert)
                throw new Exception("Incorrect Open argument order");
            var document = new FakeDocument(this, (string)path);
            Items.Add(document);
            return document;
        }
    }
    public class FakeDocument {
        private FakeDocuments owner;
        public string FullName { get; private set; }
        public bool IsBootstrap { get; private set; }
        public bool Closed { get; private set; }
        public string Path { get { return IsBootstrap ? "" : "staged"; } }
        public FakeRange Content { get { return new FakeRange(); } }
        public bool Saved { get { return !Runtime.BootstrapChanged; } }
        public string WordOpenXML { get { return Runtime.BootstrapChanged || Runtime.Scenario == "header_bootstrap" ? "USER_TEXT" : "EMPTY_XML"; } }
        public FakeCountCollection Tables { get { return new FakeCountCollection(Runtime.Scenario == "table_bootstrap" ? 1 : 0); } }
        public FakeCountCollection Fields { get { return new FakeCountCollection(0); } }
        public FakeCountCollection Shapes { get { return new FakeCountCollection(0); } }
        public FakeCountCollection InlineShapes { get { return new FakeCountCollection(0); } }
        public FakeDocument(FakeDocuments owner, string path, bool bootstrap = false) { this.owner = owner; FullName = path; IsBootstrap = bootstrap; }
        public void Close(object save) {
            Runtime.Record(IsBootstrap ? "close_bootstrap" : "close", IsBootstrap ? "close_bootstrap_document" : "close_document");
            Runtime.Fail(IsBootstrap ? "close_bootstrap" : "close");
            owner.Items.Remove(this);
            Closed = true;
            // Native /w evidence: closing the final blank disconnects Count.
            // Preserve this behavior so tests cannot bless the old close/quit gap.
            if (IsBootstrap && owner.Items.Count == 0) Runtime.CountDisconnected = true;
        }
        public void ExportAsFixedFormat(object path, object format, object viewer, object quality,
            object range, object from, object to, object item, object props, object irm,
            object bookmarks, object tags, object bitmap, object iso) {
            Runtime.Record("export", "export_pdf");
            Runtime.Fail("export");
            if ((int)format != 17 || (bool)viewer || (int)quality != 0 || (int)range != 0 || !(bool)irm)
                throw new Exception("Incorrect full-document print export");
            if (Runtime.Scenario == "extra_document") owner.Items.Add(new FakeDocument(owner, "USER_DOCUMENT"));
            if (Runtime.Scenario == "pid_reuse") Runtime.Reused = true;
            if (Runtime.Scenario == "changed_bootstrap") Runtime.BootstrapChanged = true;
            if (Runtime.Scenario == "added_protected_view") Runtime.ProtectedViewAdded = true;
        }
    }
}
namespace LegalPdfWord {
    public static class NativeWindow {
        public static uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid) { pid = 789; return 1; }
        public static IntPtr[] FindDocumentWindows(int pid) { return new IntPtr[] { new IntPtr(123) }; }
        public static object GetNativeWordWindow(IntPtr hwnd, int expectedPid) {
            if (expectedPid != 789) throw new Exception("Wrong process");
            return new WordPdfTest.FakeWindow();
        }
        public static bool SameComIdentity(object first, object second) { return Object.ReferenceEquals(first, second); }
        public static bool IsEmptyBootstrapXml(string text) { return text == "EMPTY_XML"; }
    }
}
"""


def _run_fake_helper(tmp_path: Path, scenario: str, *, export: bool = True):
    powershell = shutil.which("powershell.exe")
    if powershell is None:
        pytest.skip("PowerShell unavailable")
    state_path = tmp_path / "fake-helper-state.json"
    # The real parent prewrites a starting journal, so the very first helper save
    # must atomically replace an existing destination (not only create a file).
    state_path.write_text(json.dumps({"status": "starting", "launch_attempted": True}), encoding="utf-8")
    helper = build_pdf_script(
        tmp_path / "João's staged source.docx" if export else None,
        tmp_path / "fresh output.pdf" if export else None,
        state_path=state_path,
        word_executable=tmp_path / "never-executable" / "WINWORD.EXE",
    )
    native_definition = re.search(r"    Add-Type[^\n]* -TypeDefinition @'.*?\n'@", helper, re.DOTALL)
    assert native_definition is not None
    helper = helper.replace(native_definition.group(0), "    # Native identity API replaced by the fake runtime.")
    helper = helper.replace("[Diagnostics.Process]", "[WordPdfTest.FakeProcess]")
    helper = helper.replace("[Runtime.InteropServices.Marshal]", "[WordPdfTest.FakeMarshal]")
    # A managed getter throwing COMException is specially wrapped by PowerShell's
    # property adapter. A method faithfully supplies the COM HRESULT to Invoke-Com.
    helper = helper.replace("$bootstrapWindow.Hwnd", "$bootstrapWindow.GetHwnd()")
    helper = helper.replace("$range.Text", "$range.GetText()")
    helper = helper.replace("[IO.File]::Exists($wordExecutable)", "$true")
    helper = helper.replace(
        "@(Get-Process -Name WINWORD -ErrorAction SilentlyContinue |\n        ForEach-Object { $_.Id })",
        "@(789)" if scenario == "preexisting" else "@()",
    )
    # Hard guards make an incomplete substitution fail before executing anything.
    for forbidden in ("-ComObject", "DllImport", "[Diagnostics.Process]", "Get-Process", "GetActiveObject"):
        assert forbidden not in helper
    quoted_state = str(state_path.resolve()).replace("'", "''")
    wrapped = (
        "$ErrorActionPreference = 'Stop'\n"
        "Add-Type -TypeDefinition @'\n" + _FAKE_RUNTIME + "\n'@\n"
        f"[WordPdfTest.Runtime]::Scenario = '{scenario}'\n"
        f"[WordPdfTest.Runtime]::StatePath = '{quoted_state}'\n" + helper
    )
    runner = "[Console]::InputEncoding = [Text.UTF8Encoding]::new($false); & ([scriptblock]::Create([Console]::In.ReadToEnd()))"
    result = subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand",
         base64.b64encode(runner.encode("utf-16-le")).decode("ascii")],
        input=wrapped, capture_output=True, text=True, encoding="utf-8", timeout=20, check=False,
    )
    assert state_path.exists(), result.stderr
    state = json.loads(state_path.read_text(encoding="utf-8"))
    events = [line.removeprefix("FAKE:") for line in result.stdout.splitlines() if line.startswith("FAKE:")]
    assert "PRIVATE_DOCUMENT_TEXT" not in result.stdout + result.stderr + json.dumps(state)
    return result, state, events


@pytest.mark.skipif(os.name != "nt", reason="PowerShell fake-runtime harness is Windows-only")
@pytest.mark.parametrize("export", [False, True])
def test_fake_word_success_preserves_empty_collection_and_confirms_cleanup(tmp_path: Path, export: bool) -> None:
    result, state, events = _run_fake_helper(tmp_path, "success", export=export)
    assert result.returncode == 0, (state, result.stderr)
    assert state["status"] == "succeeded"
    assert state["cleanup_status"] == "confirmed"
    assert state["ownership"] == "proven"
    assert state["word_identity_verified"] is True
    assert state["document_owned"] is False
    assert events.count("launch") == 1
    assert events.count("quit") == 1
    assert events.count("open") == int(export)
    assert events.count("close") == int(export)
    assert events.count("export") == int(export)
    assert events.count("release") >= (5 if export else 4)
    assert events.count("close_bootstrap") == 0
    observations = state["document_count_observations"]
    assert [entry["phase"] for entry in observations] == ["documents_count", "remaining_documents_count"]
    assert [entry["value"] for entry in observations] == [1, 1]
    assert all(entry["collection_type"] == "WordPdfTest.FakeDocuments" for entry in observations)
    assert all(entry["collection_is_array"] is False for entry in observations)
    assert all(entry["count_type"] == "System.Int32" for entry in observations)


@pytest.mark.skipif(os.name != "nt", reason="PowerShell fake-runtime harness is Windows-only")
@pytest.mark.parametrize("scenario", ["preexisting", "preexisting_document"])
def test_fake_word_rejects_reused_instance_without_mutation(tmp_path: Path, scenario: str) -> None:
    result, state, events = _run_fake_helper(tmp_path, scenario)
    assert result.returncode == 1
    assert state["failure_code"] == "ownership_unproven"
    assert state["ownership"] == "rejected"
    assert state["cleanup_status"] == "ambiguous"
    assert not {"visible", "security", "open", "export", "close", "quit"}.intersection(events)


@pytest.mark.skipif(os.name != "nt", reason="PowerShell fake-runtime harness is Windows-only")
@pytest.mark.parametrize(
    ("scenario", "phase", "cleanup", "closes", "quits"),
    [
        ("open_failure", "open_document", "confirmed", 0, 1),
        ("export_failure", "export_pdf", "confirmed", 1, 1),
        ("export_and_close_failure", "export_pdf", "ambiguous", 1, 0),
        ("close_failure", "close_document", "ambiguous", 1, 0),
        ("quit_failure", "quit_word", "ambiguous", 1, 1),
        ("extra_document", "remaining_documents_count", "ambiguous", 1, 0),
        ("pid_reuse", "cleanup_word_identity_process", "confirmed", 0, 0),
    ],
)
def test_fake_word_primary_failure_and_cleanup_are_independent(
    tmp_path: Path, scenario: str, phase: str, cleanup: str, closes: int, quits: int,
) -> None:
    result, state, events = _run_fake_helper(tmp_path, scenario)
    assert result.returncode == 1
    assert state["primary_failure_phase"] == phase
    assert state["cleanup_status"] == cleanup
    assert events.count("close") == closes
    assert events.count("quit") == quits
    assert events.count("open") == 1
    assert events.count("export") == (0 if scenario == "open_failure" else 1)
    if scenario.endswith("_failure"):
        assert state["primary_hresult"] == "0x80004005"
    if scenario == "export_and_close_failure":
        assert state["cleanup_hresult"] == "0x80004005"


@pytest.mark.skipif(os.name != "nt", reason="PowerShell fake-runtime harness is Windows-only")
def test_fake_word_retries_only_rejected_reads(tmp_path: Path) -> None:
    result, state, events = _run_fake_helper(tmp_path, "transient_read", export=False)
    assert result.returncode == 0, state
    assert events.count("launch") == 1
    assert events[:4] == ["launch", "hwnd", "hwnd", "hwnd"]


@pytest.mark.skipif(os.name != "nt", reason="PowerShell fake-runtime harness is Windows-only")
def test_fake_word_does_not_retry_unknown_read_failure(tmp_path: Path) -> None:
    result, state, events = _run_fake_helper(tmp_path, "permanent_read", export=False)
    assert result.returncode == 1
    assert state["primary_failure_phase"] == "capture_word_identity"
    assert state["primary_hresult"] == "0x80004005"
    assert state["cleanup_status"] == "ambiguous"
    assert events.count("launch") == 1
    assert events.count("hwnd") == 1
    assert "quit" not in events


@pytest.mark.skipif(os.name != "nt", reason="PowerShell fake-runtime harness is Windows-only")
def test_fake_word_launch_failure_has_durable_identity_free_quarantine(tmp_path: Path) -> None:
    result, state, events = _run_fake_helper(tmp_path, "launch_failure", export=False)
    assert result.returncode == 1
    assert state["launch_attempted"] is True
    assert state["helper_start_ticks"]
    assert state["word_identity_verified"] is False
    assert state["word_pid"] is None
    assert state["primary_failure_phase"] == "launch_word"
    assert state["cleanup_status"] == "ambiguous"
    assert events == ["launch"]


@pytest.mark.skipif(os.name != "nt", reason="PowerShell fake-runtime harness is Windows-only")
@pytest.mark.parametrize("scenario", [
    "nonempty_bootstrap", "table_bootstrap", "header_bootstrap", "protected_view",
    "bootstrap_read_failure",
])
def test_fake_bootstrap_rejects_user_content_before_settings(tmp_path: Path, scenario: str) -> None:
    result, state, events = _run_fake_helper(tmp_path, scenario)
    assert result.returncode == 1
    assert state["cleanup_status"] == "ambiguous"
    assert not {"visible", "security", "open", "export", "close", "close_bootstrap", "quit"}.intersection(events)
    if scenario == "bootstrap_read_failure":
        assert state["primary_failure_phase"] == "initial_bootstrap_text"
        assert state["primary_hresult"] == "0x80004005"
        assert "release" in events


@pytest.mark.skipif(os.name != "nt", reason="PowerShell fake-runtime harness is Windows-only")
@pytest.mark.parametrize("scenario", ["changed_bootstrap", "added_protected_view"])
def test_fake_cleanup_preserves_changed_bootstrap_or_protected_document(tmp_path: Path, scenario: str) -> None:
    result, state, events = _run_fake_helper(tmp_path, scenario)
    assert result.returncode == 1
    assert state["cleanup_status"] == "ambiguous"
    assert events.count("close") == 1  # Our unique staged target only.
    assert "close_bootstrap" not in events
    assert "quit" not in events


@pytest.mark.skipif(os.name != "nt", reason="PowerShell definition compiler is Windows-only")
def test_actual_native_definition_compiles_and_validates_only_story_content(tmp_path: Path) -> None:
    powershell = shutil.which("powershell.exe")
    if powershell is None:
        pytest.skip("PowerShell unavailable")
    declaration = re.search(r"    Add-Type[^\n]* -TypeDefinition @'.*?\n'@", _script(tmp_path), re.DOTALL)
    assert declaration is not None
    namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    prefix = "application/vnd.openxmlformats-officedocument.wordprocessingml."

    def part(name: str, kind: str, xml: str) -> str:
        return f'<pkg:part pkg:name="/word/{name}.xml" pkg:contentType="{prefix}{kind}+xml"><pkg:xmlData>{xml}</pkg:xmlData></pkg:part>'

    def package(body: str = "<w:p />", extra: str = "") -> str:
        main = part("document", "document.main", f'<w:document xmlns:w="{namespace}"><w:body>{body}</w:body></w:document>')
        return '<pkg:package xmlns:pkg="http://schemas.microsoft.com/office/2006/xmlPackage">' + main + extra + "</pkg:package>"

    styles = part("styles", "styles", f'<w:styles xmlns:w="{namespace}"><w:style><w:pPr><w:numPr /></w:pPr></w:style></w:styles>')
    header = part("header1", "header", f'<w:hdr xmlns:w="{namespace}"><w:p><w:r><w:t>Header content</w:t></w:r></w:p></w:hdr>')
    cases = [
        {"Name": "blank", "Xml": package(), "Expected": True},
        {"Name": "numbered_style_definition", "Xml": package(extra=styles), "Expected": True},
        {"Name": "header_text", "Xml": package(extra=header), "Expected": False},
        {"Name": "body_drawing", "Xml": package("<w:p><w:r><w:drawing /></w:r></w:p>"), "Expected": False},
        {"Name": "body_list", "Xml": package("<w:p><w:pPr><w:numPr /></w:pPr></w:p>"), "Expected": False},
    ]
    encoded_cases = base64.b64encode(json.dumps(cases).encode("utf-8")).decode("ascii")
    # Execute the exact production C# declaration and its pure XML method only.
    # No process/window enumeration, P/Invoke, COM activation, or Word API runs.
    code = "$ErrorActionPreference = 'Stop'\n$ProgressPreference = 'SilentlyContinue'\n" + declaration.group(0) + "\n"
    code += f"$cases = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded_cases}')) | ConvertFrom-Json\n"
    code += """
foreach ($case in $cases) {
    $actual = [LegalPdfWord.NativeWindow]::IsEmptyBootstrapXml($case.Xml)
    if ($actual -ne $case.Expected) { Write-Output ('FAILED:' + $case.Name); exit 1 }
}
Write-Output 'COMPILE_AND_XML_OK'
"""
    runner = "[Console]::InputEncoding = [Text.UTF8Encoding]::new($false); & ([scriptblock]::Create([Console]::In.ReadToEnd()))"
    result = subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand",
         base64.b64encode(runner.encode("utf-16-le")).decode("ascii")],
        input=code, capture_output=True, text=True, encoding="utf-8", timeout=20, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "COMPILE_AND_XML_OK"


@pytest.mark.skipif(os.name != "nt", reason="In-memory scripting COM collection is Windows-only")
def test_real_in_memory_com_collection_keeps_count_after_mutation(tmp_path: Path) -> None:
    powershell = shutil.which("powershell.exe")
    if powershell is None:
        pytest.skip("PowerShell unavailable")
    # Execute helper definitions only, then use an ephemeral Scripting.Dictionary.
    # This is an in-process Windows COM collection; no Word, window enumeration,
    # source documents, executable launch, or Office state is involved.
    prefix = _script(tmp_path).split("\ntry {\n    Save-State\n", 1)[0]
    assert "[Diagnostics.Process]::Start(" not in prefix
    code = prefix + r'''
$dictionary = $null
try {
    $dictionary = New-Object -ComObject Scripting.Dictionary
    $dictionary.Add('synthetic', 1)
    $captured = Invoke-Com 'dictionary_capture' { ,$dictionary } -RetryRead
    $before = Invoke-Com 'dictionary_before' { $captured.Count } -RetryRead
    $dictionary.RemoveAll()
    $after = Invoke-Com 'dictionary_after' { $captured.Count } -RetryRead
    $observation = @{
        captured_type = $captured.GetType().FullName
        captured_is_array = ($captured -is [array])
        before = $before
        after = $after
        original_after = $dictionary.Count
    }
    Write-Output ('COM_DICTIONARY_RESULT:' + ($observation | ConvertTo-Json -Compress))
} finally {
    if ($null -ne $dictionary) { $null = [Runtime.InteropServices.Marshal]::FinalReleaseComObject($dictionary) }
}
'''
    runner = "[Console]::InputEncoding = [Text.UTF8Encoding]::new($false); & ([scriptblock]::Create([Console]::In.ReadToEnd()))"
    result = subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand",
         base64.b64encode(runner.encode("utf-16-le")).decode("ascii")],
        input=code, capture_output=True, text=True, encoding="utf-8", timeout=20, check=False,
    )
    assert result.returncode == 0, result.stderr
    observation = json.loads(next(line.removeprefix("COM_DICTIONARY_RESULT:")
        for line in result.stdout.splitlines() if line.startswith("COM_DICTIONARY_RESULT:")))
    assert observation["before"] == 1, observation
    assert observation["original_after"] == 0, observation
    assert observation["after"] == 0, observation
    assert observation["captured_is_array"] is False, observation
