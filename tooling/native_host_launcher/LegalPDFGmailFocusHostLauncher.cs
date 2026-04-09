using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            return RunAsync(args ?? Array.Empty<string>()).GetAwaiter().GetResult();
        }
        catch (Exception ex)
        {
            TryWriteLauncherLog(ex.ToString());
            return 1;
        }
    }

    private static async Task<int> RunAsync(string[] args)
    {
        string repoRoot = ResolveRepoRoot();
        if (string.IsNullOrWhiteSpace(repoRoot))
        {
            TryWriteLauncherLog("Could not resolve the LegalPDF repo root for the native host launcher.");
            return 1;
        }

        string pythonExecutable = ResolvePythonExecutable(repoRoot);
        if (string.IsNullOrWhiteSpace(pythonExecutable))
        {
            TryWriteLauncherLog("Could not resolve pythonw.exe or python.exe for the native host launcher.");
            return 1;
        }

        var startInfo = new ProcessStartInfo
        {
            FileName = pythonExecutable,
            Arguments = BuildArgumentString(args),
            WorkingDirectory = repoRoot,
            UseShellExecute = false,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };

        string srcRoot = Path.Combine(repoRoot, "src");
        string existingPythonPath = Environment.GetEnvironmentVariable("PYTHONPATH") ?? string.Empty;
        startInfo.EnvironmentVariables["PYTHONPATH"] = string.IsNullOrWhiteSpace(existingPythonPath)
            ? srcRoot
            : srcRoot + ";" + existingPythonPath;

        using (var process = new Process())
        {
            process.StartInfo = startInfo;
            process.EnableRaisingEvents = true;
            if (!process.Start())
            {
                TryWriteLauncherLog("Failed to start pythonw.exe for the native host launcher.");
                return 1;
            }

            using (Stream parentInput = Console.OpenStandardInput())
            using (Stream parentOutput = Console.OpenStandardOutput())
            {
                Task stdinTask = PumpInputAsync(parentInput, process);
                Task stdoutTask = PumpOutputAsync(process, parentOutput);
                Task stderrTask = DrainStandardErrorAsync(process);
                Task waitTask = Task.Run(() => process.WaitForExit());

                await Task.WhenAll(stdinTask, stdoutTask, stderrTask, waitTask).ConfigureAwait(false);
                return process.ExitCode;
            }
        }
    }

    private static async Task PumpInputAsync(Stream source, Process process)
    {
        try
        {
            await source.CopyToAsync(process.StandardInput.BaseStream).ConfigureAwait(false);
            await process.StandardInput.BaseStream.FlushAsync().ConfigureAwait(false);
        }
        catch
        {
            // The Python child may exit before the browser closes stdin.
        }
        finally
        {
            try
            {
                process.StandardInput.Close();
            }
            catch
            {
                // Best-effort close only.
            }
        }
    }

    private static async Task PumpOutputAsync(Process process, Stream destination)
    {
        try
        {
            await process.StandardOutput.BaseStream.CopyToAsync(destination).ConfigureAwait(false);
            await destination.FlushAsync().ConfigureAwait(false);
        }
        catch
        {
            // If the browser closes stdout early, the child will exit shortly after.
        }
    }

    private static async Task DrainStandardErrorAsync(Process process)
    {
        try
        {
            string stderr = await process.StandardError.ReadToEndAsync().ConfigureAwait(false);
            if (!string.IsNullOrWhiteSpace(stderr))
            {
                TryWriteLauncherLog(stderr.Trim());
            }
        }
        catch
        {
            // Do not fail the host if stderr collection fails.
        }
    }

    private static string BuildArgumentString(IEnumerable<string> args)
    {
        var allArgs = new List<string> { "-m", "legalpdf_translate.gmail_focus_host" };
        allArgs.AddRange(args ?? Enumerable.Empty<string>());
        return string.Join(" ", allArgs.Select(QuoteArgument));
    }

    private static string QuoteArgument(string value)
    {
        string text = value ?? string.Empty;
        if (text.Length == 0)
        {
            return "\"\"";
        }
        if (text.IndexOfAny(new[] { ' ', '\t', '\n', '\v', '"' }) < 0)
        {
            return text;
        }

        var builder = new StringBuilder();
        builder.Append('"');
        int backslashCount = 0;
        foreach (char ch in text)
        {
            if (ch == '\\')
            {
                backslashCount++;
                continue;
            }
            if (ch == '"')
            {
                builder.Append('\\', backslashCount * 2 + 1);
                builder.Append('"');
                backslashCount = 0;
                continue;
            }
            if (backslashCount > 0)
            {
                builder.Append('\\', backslashCount);
                backslashCount = 0;
            }
            builder.Append(ch);
        }
        if (backslashCount > 0)
        {
            builder.Append('\\', backslashCount * 2);
        }
        builder.Append('"');
        return builder.ToString();
    }

    private static string ResolveRepoRoot()
    {
        string fromEnv = Environment.GetEnvironmentVariable("LEGALPDF_REPO_ROOT") ?? string.Empty;
        if (!string.IsNullOrWhiteSpace(fromEnv) && LooksLikeRepoRoot(fromEnv))
        {
            return Path.GetFullPath(fromEnv);
        }

        string baseDir = AppDomain.CurrentDomain.BaseDirectory;
        DirectoryInfo current = new DirectoryInfo(baseDir);
        while (current != null)
        {
            if (LooksLikeRepoRoot(current.FullName))
            {
                return current.FullName;
            }
            current = current.Parent;
        }
        return string.Empty;
    }

    private static bool LooksLikeRepoRoot(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return false;
        }
        string marker = Path.Combine(path, "src", "legalpdf_translate", "gmail_focus_host.py");
        return File.Exists(marker);
    }

    private static string ResolvePythonExecutable(string repoRoot)
    {
        var candidates = new[]
        {
            Path.Combine(repoRoot, ".venv311", "Scripts", "pythonw.exe"),
            Path.Combine(repoRoot, ".venv", "Scripts", "pythonw.exe"),
            Path.Combine(repoRoot, ".venv311", "Scripts", "python.exe"),
            Path.Combine(repoRoot, ".venv", "Scripts", "python.exe"),
        };
        foreach (string candidate in candidates)
        {
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }
        return string.Empty;
    }

    private static void TryWriteLauncherLog(string message)
    {
        try
        {
            string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            if (string.IsNullOrWhiteSpace(appData))
            {
                return;
            }
            string logDir = Path.Combine(appData, "LegalPDFTranslate", "native_messaging");
            Directory.CreateDirectory(logDir);
            string logPath = Path.Combine(logDir, "LegalPDFGmailFocusHost.launcher.log");
            File.AppendAllText(
                logPath,
                "[" + DateTime.UtcNow.ToString("o") + "] " + (message ?? string.Empty) + Environment.NewLine,
                Encoding.UTF8
            );
        }
        catch
        {
            // Avoid surfacing secondary logging failures to the browser.
        }
    }
}
