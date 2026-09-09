"""Direct launch contracts: compile native declarations, execute only managed fakes.

No test invokes a real process-launch P/Invoke or disposes a synthetic IntPtr with
the framework's SafeProcessHandle. The fake seam is asserted before execution.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess

import pytest

from legalpdf_translate.word_process_start import DIRECT_PROCESS_CS


_USINGS = """
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
"""


def _powershell(code: str) -> str:
    executable = shutil.which("powershell.exe")
    if os.name != "nt" or executable is None:
        pytest.skip("Windows PowerShell C# compiler unavailable")
    runner = (
        "[Console]::InputEncoding = [Text.UTF8Encoding]::new($false); "
        "& ([scriptblock]::Create([Console]::In.ReadToEnd()))"
    )
    result = subprocess.run(
        [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand",
         base64.b64encode(runner.encode("utf-16-le")).decode("ascii")],
        input="$ErrorActionPreference = 'Stop'\n" + code,
        capture_output=True, text=True, encoding="utf-8", timeout=30, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return result.stdout.strip()


def test_exact_direct_process_fragment_compiles_without_invocation() -> None:
    # Add-Type only: none of the real fragment's methods or constructors run.
    declaration = _USINGS + "\nnamespace CompileOnly {\n" + DIRECT_PROCESS_CS + "\n}"
    script = "Add-Type -TypeDefinition @'\n" + declaration + "\n'@\n'COMPILE_ONLY_OK'\n"
    assert "::StartHidden" not in script
    assert _powershell(script) == "COMPILE_ONLY_OK"


_FAKE_NATIVE_METHODS = r'''
        internal static int Creates, ThreadCloses, ProcessDisposals, SessionQueries;
        internal static bool CreateOk, TimesOk, SessionOk, ImageOk, CloseOk;
        internal static IntPtr ProcessHandle, ThreadHandle;
        internal static uint CreatedPid, CurrentPid, Session, ImageSize;
        internal static string Application, Command, Directory, Image;
        internal static IntPtr ProcessAttributes, ThreadAttributes, Environment;
        internal static bool InheritHandles;
        internal static uint Flags;
        internal static StartupInfo Startup;
        internal static long CreatedTime;
        internal static Queue<uint> WaitResults;
        internal static List<uint> WaitMilliseconds;
        internal static List<string> HandleQueries;
        internal static FakeSafeProcessHandle OriginalHandle;

        internal static void Reset() {
            Creates = ThreadCloses = ProcessDisposals = SessionQueries = 0;
            CreateOk = TimesOk = SessionOk = ImageOk = CloseOk = true;
            ProcessHandle = new IntPtr(101); ThreadHandle = new IntPtr(202);
            CreatedPid = CurrentPid = 321; Session = 7; ImageSize = uint.MaxValue;
            Application = Command = Directory = null;
            Image = @"C:\Synthetic João\WINWORD.EXE";
            CreatedTime = new DateTime(2026, 9, 9, 1, 2, 3, DateTimeKind.Utc).ToFileTimeUtc();
            WaitResults = new Queue<uint>(); WaitMilliseconds = new List<uint>();
            HandleQueries = new List<string>(); OriginalHandle = null;
        }
        private static void Check(FakeSafeProcessHandle process, string operation) {
            if (process.IsClosed) throw new ObjectDisposedException("fake process");
            if (process.Value != ProcessHandle) throw new Exception("Handle changed");
            if (OriginalHandle == null) OriginalHandle = process;
            if (!Object.ReferenceEquals(OriginalHandle, process)) throw new Exception("Handle reopened");
            HandleQueries.Add(operation);
        }
        internal static bool CreateProcessW(string application, StringBuilder command,
            IntPtr processAttributes, IntPtr threadAttributes, bool inheritHandles,
            uint flags, IntPtr environment, string directory, ref StartupInfo startup,
            out ProcessInformation created) {
            Creates++; Application = application; Command = command.ToString();
            ProcessAttributes = processAttributes; ThreadAttributes = threadAttributes;
            InheritHandles = inheritHandles; Flags = flags; Environment = environment;
            Directory = directory; Startup = startup;
            created = new ProcessInformation();
            if (CreateOk) {
                created.hProcess = ProcessHandle; created.hThread = ThreadHandle;
                created.dwProcessId = CreatedPid; created.dwThreadId = 654;
            }
            return CreateOk;
        }
        internal static uint GetProcessId(FakeSafeProcessHandle process) {
            Check(process, "id"); return CurrentPid;
        }
        internal static uint WaitForSingleObject(FakeSafeProcessHandle process, uint milliseconds) {
            Check(process, "wait"); WaitMilliseconds.Add(milliseconds);
            return WaitResults.Count == 0 ? 258u : WaitResults.Dequeue();
        }
        internal static bool GetProcessTimes(FakeSafeProcessHandle process,
            out long created, out long exited, out long kernel, out long user) {
            Check(process, "time"); created = CreatedTime; exited = kernel = user = 0;
            return TimesOk;
        }
        internal static bool ProcessIdToSessionId(uint pid, out uint session) {
            SessionQueries++;
            if (pid != CurrentPid) throw new Exception("Session PID differs from retained handle");
            session = Session; return SessionOk;
        }
        internal static bool QueryFullProcessImageNameW(FakeSafeProcessHandle process,
            uint flags, StringBuilder path, ref uint size) {
            Check(process, "image");
            if (flags != 0 || size != 32768 || path.Capacity != 32768)
                throw new Exception("Wrong image query contract");
            path.Append(Image);
            size = ImageSize == uint.MaxValue ? (uint)Image.Length : ImageSize;
            return ImageOk;
        }
        internal static bool CloseHandle(IntPtr handle) {
            if (handle != ThreadHandle) throw new Exception("Closed non-thread handle");
            ThreadCloses++; return CloseOk;
        }
    }

    public sealed class FakeSafeProcessHandle : IDisposable {
        internal readonly IntPtr Value;
        public bool IsClosed { get; private set; }
        public bool IsInvalid { get { return Value == IntPtr.Zero || Value == new IntPtr(-1); } }
        public FakeSafeProcessHandle(IntPtr value, bool owns) {
            if (!owns) throw new Exception("Launch handle ownership lost");
            Value = value;
        }
        public void Dispose() {
            if (IsClosed) return;
            IsClosed = true; DirectProcessNative.ProcessDisposals++;
        }
    }
'''


_PROBE = r'''
    public static class Probe {
        private const string Exe = @"C:\Synthetic João\WINWORD.EXE";
        private static void Must(bool value, string message) {
            if (!value) throw new Exception(message);
        }
        private static void Throws<T>(Action action) where T : Exception {
            try { action(); } catch (T) { return; }
            throw new Exception("Expected " + typeof(T).Name);
        }
        public static string Run(string scenario) {
            DirectProcessNative.Reset();
            if (scenario.StartsWith("invalid_") && !scenario.EndsWith("_handle")) {
                string value = Exe;
                switch (scenario) {
                    case "invalid_null": value = null; break;
                    case "invalid_empty": value = ""; break;
                    case "invalid_whitespace": value = "  "; break;
                    case "invalid_relative": value = "WINWORD.EXE"; break;
                    case "invalid_quote": value = "C:\\Synthetic \\\"\\WINWORD.EXE"; break;
                    case "invalid_nul": value = "C:\\Synthetic\0\\WINWORD.EXE"; break;
                    case "invalid_dotdot": value = @"C:\Synthetic\..\WINWORD.EXE"; break;
                    case "invalid_drive_relative": value = @"C:WINWORD.EXE"; break;
                    default: throw new Exception("Unknown invalid case");
                }
                Throws<ArgumentException>(() => DirectProcess.StartHidden(value));
                Must(DirectProcessNative.Creates == 0, "Invalid path reached native launch");
                Must(DirectProcessNative.ThreadCloses == 0 && DirectProcessNative.ProcessDisposals == 0,
                    "Invalid path created/disposed handles");
                return "OK";
            }
            if (scenario == "creation_failure") {
                DirectProcessNative.CreateOk = false;
                Throws<System.ComponentModel.Win32Exception>(() => DirectProcess.StartHidden(Exe));
                Must(DirectProcessNative.Creates == 1, "Launch retried");
                Must(DirectProcessNative.ThreadCloses == 0 && DirectProcessNative.ProcessDisposals == 0,
                    "Failed creation invented ownership");
                return "OK";
            }
            if (scenario == "wrong_pid" || scenario == "zero_pid" || scenario == "overflow_pid" ||
                scenario == "invalid_zero_handle" || scenario == "invalid_minus_one_handle") {
                if (scenario == "wrong_pid") DirectProcessNative.CurrentPid = 999;
                if (scenario == "zero_pid") DirectProcessNative.CurrentPid = 0;
                if (scenario == "overflow_pid") DirectProcessNative.CreatedPid = uint.MaxValue;
                if (scenario == "invalid_zero_handle") DirectProcessNative.ProcessHandle = IntPtr.Zero;
                if (scenario == "invalid_minus_one_handle") DirectProcessNative.ProcessHandle = new IntPtr(-1);
                if (scenario == "zero_pid")
                    Throws<System.ComponentModel.Win32Exception>(() => DirectProcess.StartHidden(Exe));
                else if (scenario == "overflow_pid")
                    Throws<OverflowException>(() => DirectProcess.StartHidden(Exe));
                else Throws<InvalidOperationException>(() => DirectProcess.StartHidden(Exe));
                Must(DirectProcessNative.ThreadCloses == 1 && DirectProcessNative.ProcessDisposals == 1,
                    "Rejected launch leaked owned handles");
                return "OK";
            }
            if (scenario == "zero_thread") DirectProcessNative.ThreadHandle = IntPtr.Zero;
            if (scenario == "thread_close_failure") DirectProcessNative.CloseOk = false;
            DirectProcess process = DirectProcess.StartHidden(Exe);
            try {
                Must(DirectProcessNative.Creates == 1, "Launch retried");
                Must(DirectProcessNative.ProcessDisposals == 0, "Process disposed before ownership transfer");
                Must(DirectProcessNative.ThreadCloses == (scenario == "zero_thread" ? 0 : 1),
                    "Thread handle not released exactly once");
                if (scenario == "launch_contract") {
                    Must(DirectProcessNative.Application == Exe, "Application path changed");
                    Must(DirectProcessNative.Command == "\"" + Exe + "\" /w", "Wrong Unicode quoted command");
                    Must(DirectProcessNative.Directory == @"C:\Synthetic João", "Wrong working directory");
                    Must(DirectProcessNative.ProcessAttributes == IntPtr.Zero &&
                        DirectProcessNative.ThreadAttributes == IntPtr.Zero &&
                        DirectProcessNative.Environment == IntPtr.Zero && !DirectProcessNative.InheritHandles,
                        "Unexpected inherited resources/environment");
                    Must(DirectProcessNative.Flags == 0x08000000, "Wrong process creation flags");
                    var startup = DirectProcessNative.Startup;
                    Must(startup.cb == Marshal.SizeOf(typeof(DirectProcessNative.StartupInfo)), "Wrong startup size");
                    Must(startup.dwFlags == 1 && startup.wShowWindow == 0, "GUI not initially hidden");
                    Must(startup.lpDesktop == IntPtr.Zero && startup.lpTitle == IntPtr.Zero &&
                        startup.lpReserved == IntPtr.Zero && startup.lpReserved2 == IntPtr.Zero &&
                        startup.cbReserved2 == 0 && startup.hStdInput == IntPtr.Zero &&
                        startup.hStdOutput == IntPtr.Zero && startup.hStdError == IntPtr.Zero,
                        "Alternate desktop/title/standard handles supplied");
                } else if (scenario == "identity") {
                    Must(process.Id == 321 && process.SessionId == 7, "Wrong process/session identity");
                    Must(process.StartTime == DateTime.FromFileTimeUtc(DirectProcessNative.CreatedTime) &&
                        process.StartTime.Kind == DateTimeKind.Utc, "Wrong creation identity");
                    Must(process.ProcessName == "WINWORD" && process.MainModule.FileName == Exe,
                        "Image identity not retained");
                    process.Refresh();
                    Must(DirectProcessNative.HandleQueries.Contains("id") &&
                        DirectProcessNative.HandleQueries.Contains("time") &&
                        DirectProcessNative.HandleQueries.Contains("image"), "Identity cached instead of queried");
                    Must(DirectProcessNative.WaitMilliseconds.Count == 2 &&
                        DirectProcessNative.WaitMilliseconds.TrueForAll(x => x == 0), "Session liveness not bracketed");
                } else if (scenario == "wait_bounded") {
                    Must(!process.WaitForExit(123) && !process.WaitForExit(int.MaxValue), "Timeout misread");
                    Must(DirectProcessNative.WaitMilliseconds[0] == 123 &&
                        DirectProcessNative.WaitMilliseconds[1] == int.MaxValue, "Wait changed/infinite");
                } else if (scenario == "wait_negative") {
                    Throws<ArgumentOutOfRangeException>(() => process.WaitForExit(-1));
                    Must(DirectProcessNative.WaitMilliseconds.Count == 0, "Negative wait reached native API");
                } else if (scenario == "wait_exited") {
                    DirectProcessNative.WaitResults.Enqueue(0);
                    Must(process.HasExited && DirectProcessNative.WaitMilliseconds[0] == 0, "Exited probe incorrect");
                } else if (scenario == "wait_query_failure" || scenario == "wait_unexpected") {
                    DirectProcessNative.WaitResults.Enqueue(scenario == "wait_query_failure" ? uint.MaxValue : 128u);
                    Throws<System.ComponentModel.Win32Exception>(() => process.WaitForExit(25));
                } else if (scenario == "session_already_exited" || scenario == "session_pid_race") {
                    if (scenario == "session_pid_race") DirectProcessNative.WaitResults.Enqueue(258);
                    DirectProcessNative.WaitResults.Enqueue(0);
                    Throws<InvalidOperationException>(() => { int ignored = process.SessionId; });
                    Must(DirectProcessNative.SessionQueries == (scenario == "session_pid_race" ? 1 : 0),
                        "Session PID race not rejected around query");
                } else if (scenario == "session_query_failure") {
                    DirectProcessNative.SessionOk = false;
                    Throws<System.ComponentModel.Win32Exception>(() => { int ignored = process.SessionId; });
                } else if (scenario == "session_overflow") {
                    DirectProcessNative.Session = uint.MaxValue;
                    Throws<OverflowException>(() => { int ignored = process.SessionId; });
                } else if (scenario == "id_query_failure") {
                    DirectProcessNative.CurrentPid = 0;
                    Throws<System.ComponentModel.Win32Exception>(() => { int ignored = process.Id; });
                } else if (scenario == "time_query_failure") {
                    DirectProcessNative.TimesOk = false;
                    Throws<System.ComponentModel.Win32Exception>(() => { DateTime ignored = process.StartTime; });
                } else if (scenario == "image_query_failure") {
                    DirectProcessNative.ImageOk = false;
                    Throws<System.ComponentModel.Win32Exception>(() => { string ignored = process.ProcessName; });
                    Throws<System.ComponentModel.Win32Exception>(() => { var ignored = process.MainModule; });
                } else if (scenario == "image_empty" || scenario == "image_truncated") {
                    DirectProcessNative.ImageSize = scenario == "image_empty" ? 0u : 32768u;
                    Throws<InvalidOperationException>(() => { string ignored = process.ProcessName; });
                    Throws<InvalidOperationException>(() => { var ignored = process.MainModule; });
                } else if (scenario == "dispose") {
                    process.Dispose(); process.Dispose();
                    Throws<ObjectDisposedException>(() => process.Refresh());
                    Throws<ObjectDisposedException>(() => { int ignored = process.Id; });
                } else if (scenario != "zero_thread" && scenario != "thread_close_failure") {
                    throw new Exception("Unknown scenario");
                }
            } finally { process.Dispose(); }
            Must(DirectProcessNative.ProcessDisposals == 1, "Retained process handle not disposed exactly once");
            return "OK";
        }
    }
'''


_SCENARIOS = [
    "launch_contract", "identity", "creation_failure", "wrong_pid", "zero_pid", "overflow_pid",
    "invalid_zero_handle", "invalid_minus_one_handle", "zero_thread", "thread_close_failure",
    "wait_bounded", "wait_negative", "wait_exited", "wait_query_failure", "wait_unexpected",
    "session_already_exited", "session_pid_race", "session_query_failure", "session_overflow",
    "id_query_failure", "time_query_failure", "image_query_failure", "image_empty", "image_truncated",
    "dispose", "invalid_null", "invalid_empty", "invalid_whitespace", "invalid_relative",
    "invalid_quote", "invalid_nul", "invalid_dotdot", "invalid_drive_relative",
]


def _fake_declaration() -> str:
    marker = '        [DllImport("kernel32.dll",'
    assert DIRECT_PROCESS_CS.count("[DllImport(") == 7, "Review the native seam before updating tests"
    prefix, separator, _ = DIRECT_PROCESS_CS.partition(marker)
    assert separator and prefix.count("internal static class DirectProcessNative") == 1
    # Keep the actual wrapper and both ABI structs, replace every extern below.
    managed = (prefix + _FAKE_NATIVE_METHODS + _PROBE).replace(
        "Microsoft.Win32.SafeHandles.SafeProcessHandle", "FakeSafeProcessHandle"
    )
    declaration = _USINGS + "\nnamespace ManagedOnly {\n" + managed + "\n}"
    for forbidden in ("DllImport", " extern ", "kernel32", "Microsoft.Win32.SafeHandles",
                      "System.Diagnostics", "Process.Start(", "GetActiveObject", "ComObject"):
        assert forbidden not in declaration, f"Unsafe fake test seam: {forbidden}"
    assert "class FakeSafeProcessHandle : IDisposable" in declaration
    assert "internal static bool CreateProcessW(" in declaration
    return declaration


@pytest.fixture(scope="module")
def managed_results() -> dict[str, str]:
    declaration = _fake_declaration()  # Hard safety assertions precede any invocation.
    encoded_cases = base64.b64encode(json.dumps(_SCENARIOS).encode("utf-8")).decode("ascii")
    code = "Add-Type -TypeDefinition @'\n" + declaration + "\n'@\n"
    code += (
        "$cases = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"
        + encoded_cases + "')) | ConvertFrom-Json\n"
        "$results = @{}\n"
        "foreach ($case in $cases) { $results[$case] = [ManagedOnly.Probe]::Run($case) }\n"
        "$results | ConvertTo-Json -Compress\n"
    )
    return json.loads(_powershell(code))


@pytest.mark.parametrize("scenario", _SCENARIOS)
def test_direct_process_uses_only_fake_native_api(managed_results: dict[str, str], scenario: str) -> None:
    assert managed_results[scenario] == "OK"
