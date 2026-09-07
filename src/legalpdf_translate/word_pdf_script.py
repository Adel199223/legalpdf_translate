"""Build the isolated, fail-closed Word PDF helper (never execute it here).

The caller owns a cross-process lock, a unique staged DOCX/PDF pair, and the
state file's private directory. A durable journal survives helper timeouts.
COM activation alone is deliberately *not* accepted as process ownership.
"""

from __future__ import annotations

from pathlib import Path


def _literal(path: Path) -> str:
    return "'" + str(path.expanduser().resolve()).replace("'", "''") + "'"


def build_pdf_script(
    docx_path: Path | None,
    pdf_path: Path | None,
    *,
    state_path: Path,
    word_executable: Path | None = None,
) -> str:
    """Return a PowerShell helper; ``None`` paths mean launch-only preflight.

    No paths, document text, or raw exception messages enter the JSON journal.
    The parent must bound the helper's lifetime and quarantine uncertain cleanup;
    this script never terminates a Word process or retries a mutating COM call.
    """
    if (docx_path is None) != (pdf_path is None):
        raise ValueError("DOCX and PDF paths must be supplied together")
    return (
        "$ErrorActionPreference = 'Stop'\n"
        "$ProgressPreference = 'SilentlyContinue'\n"
        f"$statePath = {_literal(state_path)}\n"
        f"$mode = {'export' if docx_path is not None else 'preflight'!r}\n"
        f"$target = {_literal(docx_path) if docx_path is not None else '$null'}\n"
        f"$pdfPath = {_literal(pdf_path) if pdf_path is not None else '$null'}\n"
        f"$wordExecutable = {_literal(word_executable) if word_executable is not None else chr(39) + chr(39)}\n"
        + _SCRIPT
    )


_SCRIPT = r'''
$helperProcess = [Diagnostics.Process]::GetCurrentProcess()
$helperSessionId = $helperProcess.SessionId
$state = [ordered]@{
    schema_version = 1
    mode = $mode
    status = 'running'
    phase = 'initialize'
    primary_failure_phase = ''
    primary_hresult = ''
    failure_code = ''
    helper_pid = $PID
    helper_start_ticks = $helperProcess.StartTime.ToUniversalTime().Ticks.ToString()
    helper_session_id = $helperSessionId
    launch_attempted = $false
    word_pid = $null
    word_start_ticks = $null
    word_identity_verified = $false
    process_identity_verified = $false
    ownership = 'unknown'
    document_owned = $false
    bootstrap_owned = $false
    cleanup_status = 'not_started'
    cleanup_phase = ''
    cleanup_hresult = ''
    document_count_observations = @()
}
$word = $null
$documents = $null
$doc = $null
$bootstrapWindow = $null
$bootstrapDoc = $null
$bootstrapXml = $null
$bootstrapSaved = $null
$wordProcess = $null
$operationSucceeded = $false
$cleanupMode = $false
$failureCode = ''
$launchStartedTicks = 0L
$preExistingWordPids = @()

function Save-State {
    # Replace a fully flushed sibling, never expose half a JSON document.
    $temporaryPath = $statePath + '.' + $PID + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($state | ConvertTo-Json -Compress -Depth 4))
    $stream = $null
    try {
        $stream = [IO.FileStream]::new($temporaryPath, [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write, [IO.FileShare]::None)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
        $stream.Dispose()
        $stream = $null
        if ([IO.File]::Exists($statePath)) {
            # PowerShell casts ordinary $null to an empty string for a string
            # parameter, which File.Replace rejects as an invalid backup path.
            [IO.File]::Replace($temporaryPath, $statePath, [NullString]::Value)
        } else {
            [IO.File]::Move($temporaryPath, $statePath)
        }
    } finally {
        if ($null -ne $stream) { $stream.Dispose() }
        if ([IO.File]::Exists($temporaryPath)) { [IO.File]::Delete($temporaryPath) }
    }
}

function Set-Phase {
    param([string]$Phase)
    $state.phase = $Phase
    if ($cleanupMode) { $state.cleanup_phase = $Phase }
    Save-State
    Write-Output ('LEGALPDF_WORD_PHASE:' + $Phase) | Out-Host
}

function Record-DocumentCount {
    param([string]$Phase, $Collection, $Count)
    # Type/count metadata only: never stringify a COM object, document, or a
    # surprising returned value. This distinguishes wrappers and null shutdown
    # results from an actual nonzero document count without relaxing the guard.
    $collectionType = ''
    $countType = ''
    $numericCount = $null
    $arrayLength = $null
    if ($null -ne $Collection) { $collectionType = $Collection.GetType().FullName }
    if ($null -ne $Count) { $countType = $Count.GetType().FullName }
    if ($Count -is [int] -or $Count -is [long] -or $Count -is [uint32]) { $numericCount = $Count }
    if ($Count -is [array]) { $arrayLength = $Count.Length }
    $state.document_count_observations += [ordered]@{
        phase = $Phase
        collection_type = $collectionType
        collection_is_array = ($Collection -is [array])
        count_type = $countType
        count_is_null = ($null -eq $Count)
        count_array_length = $arrayLength
        value = $numericCount
    }
    Save-State
}

function Get-HResult {
    param($Record)
    $exception = $Record.Exception
    $last = $exception
    while ($null -ne $exception) {
        $last = $exception
        if ($exception -is [Runtime.InteropServices.COMException]) { break }
        $exception = $exception.InnerException
    }
    if ($null -eq $last) { return '' }
    return '0x' + ([int]$last.HResult).ToString('X8')
}

function Fail-Safe {
    param([string]$Code)
    $script:failureCode = $Code
    $exception = [InvalidOperationException]::new($Code)
    $record = [Management.Automation.ErrorRecord]::new(
        $exception, $Code, [Management.Automation.ErrorCategory]::InvalidOperation, $null)
    Set-PrimaryFailure $record
    throw $exception
}

function Set-PrimaryFailure {
    param($Record)
    if (-not $state.primary_failure_phase) {
        $state.primary_failure_phase = $state.phase
        $state.primary_hresult = Get-HResult $Record
        $state.failure_code = $script:failureCode
        if (-not $state.failure_code) {
            $state.failure_code = switch ($state.primary_hresult) {
                '0x80040154' { 'word_unavailable'; break }
                '0x80080005' { 'com_launch_failed'; break }
                default { 'export_failed' }
            }
        }
    }
    $state.status = 'failed'
}

function Invoke-Com {
    param([string]$Phase, [scriptblock]$Action, [switch]$RetryRead)
    # Rejected read-only calls alone may be replayed. Never retry launch, open,
    # export, settings, close or quit: a failed return does not prove no mutation.
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        Set-Phase $Phase
        try {
            # Preserve COM collection objects; do not enumerate Documents into
            # its items (an empty collection would otherwise become null).
            return ,(& $Action)
        } catch {
            $hresult = Get-HResult $_
            if (-not $RetryRead -or $attempt -ge 3 -or
                @('0x80010001', '0x8001010A') -notcontains $hresult) {
                Set-PrimaryFailure $_
                throw
            }
            Start-Sleep -Milliseconds 150
        }
    }
}

function Assert-StartedProcess {
    param([string]$Phase)
    Set-Phase $Phase
    if ($null -eq $wordProcess -or -not $state.process_identity_verified) {
        Fail-Safe 'ownership_unproven'
    }
    $wordProcess.Refresh()
    if ($wordProcess.HasExited -or $wordProcess.Id -ne $state.word_pid -or
        $wordProcess.ProcessName -ine 'WINWORD' -or
        $wordProcess.SessionId -ne $helperSessionId -or
        $wordProcess.StartTime.ToUniversalTime().Ticks.ToString() -ne $state.word_start_ticks -or
        -not [string]::Equals($wordProcess.MainModule.FileName, $wordExecutable, [StringComparison]::OrdinalIgnoreCase)) {
        Fail-Safe 'ownership_unproven'
    }
}

function Assert-OwnedProcess {
    param([string]$Phase)
    if ($state.ownership -ne 'proven' -or -not $state.word_identity_verified) {
        Fail-Safe 'ownership_unproven'
    }
    Assert-StartedProcess ($Phase + '_process')
    # Word exposes Window.Hwnd, not Application.Hwnd. Keep the unchanged blank
    # anchor alive until scoped Quit; closing /w's final document can disconnect
    # the automation model before Documents.Count or Quit can be called.
    $currentHwnd = Invoke-Com $Phase { $bootstrapWindow.Hwnd } -RetryRead
    [uint32]$currentPid = 0
    $threadId = [LegalPdfWord.NativeWindow]::GetWindowThreadProcessId(
        [IntPtr]$currentHwnd, [ref]$currentPid)
    if ($threadId -eq 0 -or $currentPid -ne $state.word_pid) { Fail-Safe 'ownership_unproven' }
}

function Release-Reference {
    param($Reference, [string]$Phase)
    if ($null -ne $Reference -and [Runtime.InteropServices.Marshal]::IsComObject($Reference)) {
        Set-Phase $Phase
        $null = [Runtime.InteropServices.Marshal]::FinalReleaseComObject($Reference)
    }
}

function Assert-NoProtectedView {
    param([string]$Phase)
    $protectedWindows = $null
    try {
        $protectedWindows = Invoke-Com ($Phase + '_collection') { ,$word.ProtectedViewWindows } -RetryRead
        $protectedCount = Invoke-Com $Phase { $protectedWindows.Count } -RetryRead
        if ($protectedCount -ne 0) { Fail-Safe 'ownership_unproven' }
    } catch { Set-PrimaryFailure $_; throw }
    finally { Release-Reference $protectedWindows ($Phase + '_release') }
}

function Read-BootstrapEvidence {
    param([string]$Phase)
    $path = Invoke-Com ($Phase + '_path') { $bootstrapDoc.Path } -RetryRead
    if ($path -ne '') { Fail-Safe 'bootstrap_changed' }
    $range = $null
    try {
        $range = Invoke-Com ($Phase + '_content') { $bootstrapDoc.Content } -RetryRead
        $body = Invoke-Com ($Phase + '_text') { $range.Text } -RetryRead
        if ($body -cne "`r") { Fail-Safe 'bootstrap_changed' }
    } catch { Set-PrimaryFailure $_; throw }
    finally { Release-Reference $range ($Phase + '_content_release') }
    foreach ($property in @('Tables', 'Fields', 'Shapes', 'InlineShapes')) {
        $collection = $null
        try {
            $collection = Invoke-Com ($Phase + '_' + $property.ToLowerInvariant()) { ,$bootstrapDoc.$property } -RetryRead
            $count = Invoke-Com ($Phase + '_' + $property.ToLowerInvariant() + '_count') { $collection.Count } -RetryRead
            if ($count -ne 0) { Fail-Safe 'bootstrap_changed' }
        } catch { Set-PrimaryFailure $_; throw }
        finally { Release-Reference $collection ($Phase + '_collection_release') }
    }
    $xml = Invoke-Com ($Phase + '_xml') { $bootstrapDoc.WordOpenXML } -RetryRead
    if (-not [LegalPdfWord.NativeWindow]::IsEmptyBootstrapXml($xml)) { Fail-Safe 'bootstrap_changed' }
    $saved = Invoke-Com ($Phase + '_saved') { $bootstrapDoc.Saved } -RetryRead
    # Saved is only Word's dirty flag. Empty Path, exact content, other stories,
    # and object identity establish a never-saved blank; never set Saved=true.
    return [pscustomobject]@{ Xml = $xml; Saved = $saved }
}

function Assert-BootstrapUnchanged {
    param([string]$Phase)
    Assert-OwnedProcess ($Phase + '_identity')
    Assert-NoProtectedView ($Phase + '_protected_view')
    $count = Invoke-Com ($Phase + '_documents_count') { $documents.Count } -RetryRead
    if ($count -ne 1 -or -not $state.bootstrap_owned) { Fail-Safe 'bootstrap_changed' }
    $onlyDoc = $null
    try {
        $onlyDoc = Invoke-Com ($Phase + '_only_document') { $documents.Item(1) } -RetryRead
        if (-not [LegalPdfWord.NativeWindow]::SameComIdentity($onlyDoc, $bootstrapDoc)) {
            Fail-Safe 'bootstrap_changed'
        }
    } finally {
        # The same RCW can be returned twice. ReleaseComObject balances the extra
        # acquisition; FinalRelease here would disconnect our bootstrap anchor.
        if ($null -ne $onlyDoc -and [Runtime.InteropServices.Marshal]::IsComObject($onlyDoc)) {
            Set-Phase ($Phase + '_only_document_release')
            $null = [Runtime.InteropServices.Marshal]::ReleaseComObject($onlyDoc)
        }
    }
    $evidence = Read-BootstrapEvidence $Phase
    if ($evidence.Xml -cne $bootstrapXml -or $evidence.Saved -ne $bootstrapSaved) {
        Fail-Safe 'bootstrap_changed'
    }
}

function Assert-StagedDocument {
    param([string]$Phase)
    Assert-OwnedProcess ($Phase + '_process')
    if ($null -eq $doc -or -not $state.document_owned) { Fail-Safe 'document_ownership_unproven' }
    $actualPath = Invoke-Com $Phase { $doc.FullName } -RetryRead
    if (-not [string]::Equals($actualPath, $target, [StringComparison]::OrdinalIgnoreCase)) {
        Fail-Safe 'document_ownership_unproven'
    }
}

function Test-OwnedProcessExited {
    if (-not $state.process_identity_verified) { return $false }
    $remainingProcess = $null
    try {
        $remainingProcess = [Diagnostics.Process]::GetProcessById([int]$state.word_pid)
        if ($remainingProcess.StartTime.ToUniversalTime().Ticks.ToString() -ne $state.word_start_ticks) {
            # PID reuse proves the recorded original has exited; touch neither.
            return $true
        }
        return $remainingProcess.WaitForExit(2000)
    } catch [ArgumentException] {
        return $true
    } catch {
        return $false
    } finally {
        if ($null -ne $remainingProcess) { $remainingProcess.Dispose() }
    }
}

try {
    Save-State
    Write-Output 'LEGALPDF_WORD_HELPER_OWNER:app_owned'
    Write-Output ('LEGALPDF_WORD_HELPER_PID:' + $PID)
    Set-Phase 'load_native_identity'
    Add-Type -ReferencedAssemblies 'System.Xml.dll', 'System.Core.dll' -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Xml;
namespace LegalPdfWord {
    public static class NativeWindow {
        [DllImport("user32.dll", SetLastError = true)]
        public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
        private delegate bool EnumWindowCallback(IntPtr hwnd, IntPtr parameter);
        [DllImport("user32.dll")]
        private static extern bool EnumWindows(EnumWindowCallback callback, IntPtr parameter);
        [DllImport("user32.dll")]
        private static extern bool EnumChildWindows(IntPtr parent, EnumWindowCallback callback, IntPtr parameter);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        private static extern int GetClassName(IntPtr hwnd, StringBuilder name, int capacity);
        [DllImport("oleacc.dll")]
        private static extern int AccessibleObjectFromWindow(IntPtr hwnd, uint objectId,
            ref Guid interfaceId, [MarshalAs(UnmanagedType.Interface)] out object nativeObject);

        public static IntPtr[] FindDocumentWindows(int processId) {
            var matches = new List<IntPtr>();
            EnumWindows(delegate(IntPtr top, IntPtr ignored) {
                uint topPid;
                GetWindowThreadProcessId(top, out topPid);
                if (topPid != processId) return true;
                EnumChildWindows(top, delegate(IntPtr child, IntPtr unused) {
                    uint childPid;
                    GetWindowThreadProcessId(child, out childPid);
                    if (childPid != processId) return true;
                    var name = new StringBuilder(256);
                    if (GetClassName(child, name, name.Capacity) > 0 &&
                        String.Equals(name.ToString(), "_WwG", StringComparison.Ordinal)) matches.Add(child);
                    return true;
                }, IntPtr.Zero);
                return true;
            }, IntPtr.Zero);
            return matches.ToArray();
        }

        public static object GetNativeWordWindow(IntPtr hwnd, int expectedPid) {
            // Microsoft documents OBJID_NATIVEOM on Word's _WwG window as
            // returning Word.Window. No COM activation or running-object lookup.
            var dispatchId = new Guid("00020400-0000-0000-C000-000000000046");
            uint ownerPid;
            if (GetWindowThreadProcessId(hwnd, out ownerPid) == 0 || ownerPid != expectedPid)
                throw new COMException("Word window ownership changed", unchecked((int)0x80004005));
            object window;
            int result = AccessibleObjectFromWindow(hwnd, 0xFFFFFFF0, ref dispatchId, out window);
            if (result < 0) throw new COMException("Word window binding unavailable", result);
            if (window == null) throw new COMException("Word window binding unavailable", unchecked((int)0x80004005));
            return window;
        }

        public static bool SameComIdentity(object first, object second) {
            IntPtr firstUnknown = IntPtr.Zero;
            IntPtr secondUnknown = IntPtr.Zero;
            try {
                firstUnknown = Marshal.GetIUnknownForObject(first);
                secondUnknown = Marshal.GetIUnknownForObject(second);
                return firstUnknown == secondUnknown;
            } finally {
                if (firstUnknown != IntPtr.Zero) Marshal.Release(firstUnknown);
                if (secondUnknown != IntPtr.Zero) Marshal.Release(secondUnknown);
            }
        }

        public static bool IsEmptyBootstrapXml(string text) {
            if (String.IsNullOrEmpty(text)) return false;
            var settings = new XmlReaderSettings { DtdProcessing = DtdProcessing.Prohibit, XmlResolver = null };
            var document = new XmlDocument { XmlResolver = null };
            using (var reader = XmlReader.Create(new StringReader(text), settings)) document.Load(reader);
            var storyTypes = new HashSet<string>(StringComparer.Ordinal) {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"
            };
            bool mainFound = false;
            var namespaces = new XmlNamespaceManager(document.NameTable);
            namespaces.AddNamespace("pkg", "http://schemas.microsoft.com/office/2006/xmlPackage");
            foreach (XmlElement part in document.SelectNodes("//pkg:part", namespaces)) {
                string contentType = part.GetAttribute("contentType", namespaces.LookupNamespace("pkg"));
                if (!storyTypes.Contains(contentType)) continue;
                if (contentType.EndsWith(".document.main+xml", StringComparison.Ordinal)) mainFound = true;
                // Style/numbering definitions can contain w:numPr in a truly
                // blank document. Inspect document/story parts, not definitions.
                foreach (XmlNode node in part.SelectNodes(".//*")) {
                if (node.NamespaceURI != "http://schemas.openxmlformats.org/wordprocessingml/2006/main" &&
                    node.NamespaceURI != "http://purl.oclc.org/ooxml/wordprocessingml/main") continue;
                switch (node.LocalName) {
                    case "t": case "instrText": case "delText":
                        if (node.InnerText.Length != 0) return false;
                        break;
                    case "tbl": case "drawing": case "pict": case "object":
                    case "fldSimple": case "fldChar": case "sdt": case "numPr":
                        return false;
                }
                }
            }
            return mainFound;
        }
    }
}
'@
    if ([string]::IsNullOrWhiteSpace($wordExecutable) -or -not [IO.File]::Exists($wordExecutable)) {
        Fail-Safe 'word_unavailable'
    }
    Set-Phase 'inventory_word_processes'
    $preExistingWordPids = @(Get-Process -Name WINWORD -ErrorAction SilentlyContinue |
        ForEach-Object { $_.Id })
    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $wordExecutable
    $startInfo.Arguments = '/w'
    # Framework PowerShell only honors WindowStyle when UseShellExecute=true.
    # /w is the single documented switch for a new Word instance + blank document.
    $startInfo.UseShellExecute = $true
    $startInfo.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
    $launchStartedTicks = [DateTime]::UtcNow.Ticks
    $state.launch_attempted = $true
    Set-Phase 'launch_word'
    $wordProcess = [Diagnostics.Process]::Start($startInfo)
    if ($null -eq $wordProcess) { Fail-Safe 'ownership_unproven' }
    $state.word_pid = $wordProcess.Id
    $state.word_start_ticks = $wordProcess.StartTime.ToUniversalTime().Ticks.ToString()
    Save-State
    $wordProcess.Refresh()
    if ($wordProcess.HasExited -or $preExistingWordPids -contains $wordProcess.Id -or
        $wordProcess.SessionId -ne $helperSessionId -or
        $wordProcess.ProcessName -ine 'WINWORD' -or
        $wordProcess.StartTime.ToUniversalTime().Ticks -lt $launchStartedTicks -or
        -not [string]::Equals($wordProcess.MainModule.FileName, $wordExecutable, [StringComparison]::OrdinalIgnoreCase)) {
        $state.ownership = 'rejected'
        Fail-Safe 'ownership_unproven'
    }
    $state.process_identity_verified = $true
    Save-State
    for ($bindingAttempt = 0; $bindingAttempt -lt 40; $bindingAttempt++) {
        Assert-StartedProcess 'find_word_window'
        $handles = @([LegalPdfWord.NativeWindow]::FindDocumentWindows([int]$state.word_pid))
        if ($handles.Count -gt 0) {
            $bootstrapWindow = Invoke-Com 'capture_word_window' {
                [LegalPdfWord.NativeWindow]::GetNativeWordWindow($handles[0], [int]$state.word_pid)
            } -RetryRead
            break
        }
        Start-Sleep -Milliseconds 100
    }
    if ($null -eq $bootstrapWindow) { Fail-Safe 'word_window_unavailable' }
    $hwnd = Invoke-Com 'capture_word_identity' { $bootstrapWindow.Hwnd } -RetryRead
    [uint32]$boundPid = 0
    $boundThread = [LegalPdfWord.NativeWindow]::GetWindowThreadProcessId([IntPtr]$hwnd, [ref]$boundPid)
    if ($boundThread -eq 0 -or $boundPid -ne $state.word_pid) { Fail-Safe 'ownership_unproven' }
    $state.word_identity_verified = $true
    Save-State
    $word = Invoke-Com 'get_word_application' { $bootstrapWindow.Application } -RetryRead
    $documents = Invoke-Com 'get_documents' { ,$word.Documents } -RetryRead
    $initialDocumentCount = Invoke-Com 'documents_count' { $documents.Count } -RetryRead
    Record-DocumentCount 'documents_count' $documents $initialDocumentCount
    if ($initialDocumentCount -ne 1) {
        $state.ownership = 'rejected'
        Fail-Safe 'ownership_unproven'
    }
    Assert-NoProtectedView 'initial_protected_view'
    $bootstrapDoc = Invoke-Com 'get_bootstrap_document' { $bootstrapWindow.Document } -RetryRead
    $initialEvidence = Read-BootstrapEvidence 'initial_bootstrap'
    $bootstrapXml = $initialEvidence.Xml
    $bootstrapSaved = $initialEvidence.Saved
    $state.bootstrap_owned = $true
    $state.ownership = 'proven'
    Save-State
    Assert-BootstrapUnchanged 'verify_initial_bootstrap'
    if ($mode -eq 'export') {
        Assert-BootstrapUnchanged 'verify_before_hidden'
        Invoke-Com 'set_hidden' { $word.Visible = $false }
        Assert-BootstrapUnchanged 'verify_before_security'
        Invoke-Com 'disable_automation_macros' { $word.AutomationSecurity = 3 }
        Assert-BootstrapUnchanged 'verify_before_open'
        $missing = [Type]::Missing
        # ReadOnly=true, AddToRecentFiles=false, Visible=false; no activation,
        # repair, password, encoding or security prompt suppression.
        # Microsoft VBA and current PIA docs disagree on optional positions
        # 13-16 (OpenConflictDocument versus XMLTransform). Their first twelve
        # agree. Omit the disputed default tail: do not request a transform,
        # repair, direction override, or encoding-dialog bypass.
        # https://learn.microsoft.com/en-us/dotnet/api/microsoft.office.interop.word.documents.open
        $doc = Invoke-Com 'open_document' {
            $documents.Open(
                $target, $false, $true, $false, $missing, $missing, $false,
                $missing, $missing, $missing, $missing, $false)
        }
        if ($null -eq $doc) { Fail-Safe 'document_ownership_unproven' }
        # The private unique staged path cannot alias a user-open source target.
        $actualOpenedPath = Invoke-Com 'verify_opened_document' { $doc.FullName } -RetryRead
        if (-not [string]::Equals($actualOpenedPath, $target, [StringComparison]::OrdinalIgnoreCase)) {
            Fail-Safe 'document_ownership_unproven'
        }
        $state.document_owned = $true
        Save-State
        Assert-StagedDocument 'export_document_identity'
        # PDF, no viewer, print quality, all pages, document content;
        # IncludeDocProps=true, KeepIRM=true (retain labels/protection).
        # Omit optional FixedFormatExtClassPtr: it is an alternate-renderer
        # add-in pointer, not a required missing-value placeholder for Word PDF.
        Invoke-Com 'export_pdf' {
            $doc.ExportAsFixedFormat(
                $pdfPath, 17, $false, 0, 0, 1, 1, 0, $true, $true,
                0, $true, $true, $false)
        }
        Set-Phase 'export_complete'
    }
    $operationSucceeded = $true
} catch {
    Set-PrimaryFailure $_
    try { Save-State } catch { }
} finally {
    $cleanupMode = $true
    $state.cleanup_status = 'in_progress'
    try {
        Save-State
        if ($state.ownership -eq 'proven') {
            Assert-OwnedProcess 'cleanup_word_identity'
            if ($null -ne $doc) {
                Assert-StagedDocument 'cleanup_document_identity'
                Invoke-Com 'close_document' { $doc.Close(0) }
                $state.document_owned = $false
                Save-State
            }
            Assert-StartedProcess 'cleanup_quit_identity'
            $remainingCount = Invoke-Com 'remaining_documents_count' { $documents.Count } -RetryRead
            Record-DocumentCount 'remaining_documents_count' $documents $remainingCount
            if ($remainingCount -ne 1) { Fail-Safe 'cleanup_ambiguous' }
            # Exactly our original, unchanged, never-saved blank may remain.
            # This also checks its live window/process and ProtectedView.Count=0;
            # it does not permit an arbitrary nonzero document count.
            Assert-BootstrapUnchanged 'cleanup_bootstrap'
            Invoke-Com 'quit_word' { $word.Quit(0) }
        } elseif ($state.launch_attempted) {
            Fail-Safe 'cleanup_ambiguous'
        }
    } catch {
        $state.cleanup_status = 'ambiguous'
        $state.cleanup_hresult = Get-HResult $_
        Set-PrimaryFailure $_
        try { Save-State } catch { }
    } finally {
        # Releasing our references is not permission to close or kill a process.
        foreach ($reference in @($doc, $bootstrapDoc, $bootstrapWindow, $documents, $word)) {
            if ($null -ne $reference -and [Runtime.InteropServices.Marshal]::IsComObject($reference)) {
                try {
                    Set-Phase 'release_com_reference'
                    $null = [Runtime.InteropServices.Marshal]::FinalReleaseComObject($reference)
                } catch {
                    $state.cleanup_hresult = Get-HResult $_
                    $state.cleanup_status = 'ambiguous'
                    Set-PrimaryFailure $_
                }
            }
        }
        $doc = $null
        $bootstrapDoc = $null
        $bootstrapWindow = $null
        $documents = $null
        $word = $null
        try {
            Set-Phase 'confirm_word_exit'
            if (-not $state.launch_attempted -or
                ($state.process_identity_verified -and (Test-OwnedProcessExited))) {
                $state.cleanup_status = 'confirmed'
                $state.bootstrap_owned = $false
                $state.document_owned = $false
            } else {
                $state.cleanup_status = 'ambiguous'
                if (-not $state.primary_failure_phase) { Fail-Safe 'cleanup_ambiguous' }
            }
        } catch {
            $state.cleanup_status = 'ambiguous'
            Set-PrimaryFailure $_
        }
        if ($null -ne $wordProcess) { $wordProcess.Dispose() }
        $helperProcess.Dispose()
        if ($operationSucceeded -and $state.cleanup_status -eq 'confirmed' -and
            -not $state.primary_failure_phase) {
            $state.status = 'succeeded'
            $state.phase = 'complete'
        } else { $state.status = 'failed' }
        try { Save-State } catch { $state.status = 'failed' }
    }
}
if ($state.status -eq 'succeeded' -and $state.cleanup_status -eq 'confirmed') {
    Write-Output 'OK'
    exit 0
}
Write-Output 'WORD_PDF_HELPER_FAILED'
exit 1
'''
