"""C# fragment for a direct, initially hidden Word process with retained identity.

Compiled inside the guarded PowerShell helper, never executed on Python import.
STARTUPINFO supplies SW_HIDE without the .NET Framework shell-launch dependency.
Owning a launch handle alone is not permission to attach to COM, open or quit Word.
"""

DIRECT_PROCESS_CS = r'''
    // No shell, executable discovery, child adoption, or process termination.
    // Keep the original process handle until disposal, including on rejection.
    public sealed class DirectProcess : IDisposable {
        private readonly Microsoft.Win32.SafeHandles.SafeProcessHandle handle;
        private DirectProcess(Microsoft.Win32.SafeHandles.SafeProcessHandle value) { handle = value; }

        public static DirectProcess StartHidden(string executable) {
            if (String.IsNullOrWhiteSpace(executable) || executable.IndexOf('"') >= 0 ||
                executable.IndexOf('\0') >= 0 || !Path.IsPathRooted(executable) ||
                !String.Equals(Path.GetFullPath(executable), executable, StringComparison.OrdinalIgnoreCase))
                throw new ArgumentException("Invalid absolute executable path");
            var startup = new DirectProcessNative.StartupInfo();
            startup.cb = Marshal.SizeOf(typeof(DirectProcessNative.StartupInfo));
            startup.dwFlags = 0x00000001; // STARTF_USESHOWWINDOW
            startup.wShowWindow = 0; // SW_HIDE, including GUI startup
            var command = new StringBuilder("\"" + executable + "\" /w");
            DirectProcessNative.ProcessInformation created;
            // Non-null application name avoids space/path search ambiguity.
            // No inherited handles, alternate token, desktop or environment.
            if (!DirectProcessNative.CreateProcessW(executable, command, IntPtr.Zero, IntPtr.Zero,
                false, 0x08000000, IntPtr.Zero, Path.GetDirectoryName(executable), ref startup, out created))
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            // CREATE_NO_WINDOW concerns consoles; SW_HIDE above handles GUI startup.
            Microsoft.Win32.SafeHandles.SafeProcessHandle owned = null;
            try {
                owned = new Microsoft.Win32.SafeHandles.SafeProcessHandle(created.hProcess, true);
                if (owned.IsInvalid) throw new InvalidOperationException("Invalid process handle");
                var process = new DirectProcess(owned);
                if (process.Id != checked((int)created.dwProcessId))
                    throw new InvalidOperationException("Process handle identity mismatch");
                owned = null; // ownership transfers to the returned wrapper
                return process;
            } finally {
                if (created.hThread != IntPtr.Zero) DirectProcessNative.CloseHandle(created.hThread);
                if (owned != null) owned.Dispose();
            }
        }

        public int Id {
            get {
                uint value = DirectProcessNative.GetProcessId(handle);
                if (value == 0) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
                return checked((int)value);
            }
        }
        public bool HasExited { get { return WaitForExit(0); } }
        public bool WaitForExit(int milliseconds) {
            if (milliseconds < 0) throw new ArgumentOutOfRangeException("milliseconds");
            uint result = DirectProcessNative.WaitForSingleObject(handle, checked((uint)milliseconds));
            if (result == 0) return true; // WAIT_OBJECT_0
            if (result == 258) return false; // WAIT_TIMEOUT
            throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
        }
        public DateTime StartTime {
            get {
                long created, exited, kernel, user;
                if (!DirectProcessNative.GetProcessTimes(handle, out created, out exited, out kernel, out user))
                    throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
                return DateTime.FromFileTimeUtc(created);
            }
        }
        public int SessionId {
            get {
                // Session lookup takes a PID. Bracket it with retained-handle
                // liveness checks so an exited/recycled PID cannot supply identity.
                if (HasExited) throw new InvalidOperationException("Process exited");
                uint session;
                if (!DirectProcessNative.ProcessIdToSessionId(checked((uint)Id), out session))
                    throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
                if (HasExited) throw new InvalidOperationException("Process exited");
                return checked((int)session);
            }
        }
        private string ImagePath {
            get {
                var buffer = new StringBuilder(32768);
                uint size = checked((uint)buffer.Capacity);
                if (!DirectProcessNative.QueryFullProcessImageNameW(handle, 0, buffer, ref size))
                    throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
                if (size == 0 || size >= buffer.Capacity) throw new InvalidOperationException("Invalid image path");
                return buffer.ToString();
            }
        }
        public string ProcessName { get { return Path.GetFileNameWithoutExtension(ImagePath); } }
        public DirectProcessModule MainModule { get { return new DirectProcessModule(ImagePath); } }
        public void Refresh() {
            // All identity properties query the original handle afresh.
            if (handle.IsClosed) throw new ObjectDisposedException("DirectProcess");
        }
        public void Dispose() { handle.Dispose(); }
    }
    public sealed class DirectProcessModule {
        public string FileName { get; private set; }
        internal DirectProcessModule(string value) { FileName = value; }
    }
    internal static class DirectProcessNative {
        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        internal struct StartupInfo {
            internal int cb;
            internal IntPtr lpReserved, lpDesktop, lpTitle;
            internal uint dwX, dwY, dwXSize, dwYSize, dwXCountChars, dwYCountChars;
            internal uint dwFillAttribute, dwFlags;
            internal ushort wShowWindow, cbReserved2;
            internal IntPtr lpReserved2, hStdInput, hStdOutput, hStdError;
        }
        [StructLayout(LayoutKind.Sequential)]
        internal struct ProcessInformation {
            internal IntPtr hProcess, hThread;
            internal uint dwProcessId, dwThreadId;
        }
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        internal static extern bool CreateProcessW(string application, StringBuilder command,
            IntPtr processAttributes, IntPtr threadAttributes, [MarshalAs(UnmanagedType.Bool)] bool inheritHandles,
            uint flags, IntPtr environment, string directory, ref StartupInfo startup, out ProcessInformation created);
        [DllImport("kernel32.dll", ExactSpelling = true, SetLastError = true)]
        internal static extern uint GetProcessId(Microsoft.Win32.SafeHandles.SafeProcessHandle process);
        [DllImport("kernel32.dll", ExactSpelling = true, SetLastError = true)]
        internal static extern uint WaitForSingleObject(Microsoft.Win32.SafeHandles.SafeProcessHandle process, uint milliseconds);
        [DllImport("kernel32.dll", ExactSpelling = true, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        internal static extern bool GetProcessTimes(Microsoft.Win32.SafeHandles.SafeProcessHandle process,
            out long created, out long exited, out long kernel, out long user);
        [DllImport("kernel32.dll", ExactSpelling = true, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        internal static extern bool ProcessIdToSessionId(uint pid, out uint session);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        internal static extern bool QueryFullProcessImageNameW(Microsoft.Win32.SafeHandles.SafeProcessHandle process,
            uint flags, StringBuilder path, ref uint size);
        [DllImport("kernel32.dll", ExactSpelling = true, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        internal static extern bool CloseHandle(IntPtr handle);
    }
'''
