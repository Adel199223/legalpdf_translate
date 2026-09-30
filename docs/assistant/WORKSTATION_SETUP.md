# Windows development workstation setup

This recipe reproduces the tool versions used for LegalPDF development. The app's Python packages remain controlled by `.python-version`, `pyproject.toml`, `uv.lock` and `scripts/setup_python311_env.ps1`. The workstation checker never installs or repairs anything.

## Check an existing workstation

From the intended checkout:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_dev_workstation.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_dev_workstation.ps1 -ConfigurationOnly
```

The first command checks exact required tool versions and locates Python 3.11.9 through uv without downloading it. It returns exit 1 for a missing required tool, version mismatch or invalid tracked configuration. Git, Python, uv, Node, Dart and Windows PowerShell are required. GitHub CLI, ripgrep, PowerShell 7 and WinGet report advisory differences rather than preventing local development.

`-ConfigurationOnly` reads tracked files without executing tool commands. It checks the JSON-compatible YAML recipe's approved resources, module/package versions, identities and consistency with the Python/Node/Dart pins. It does not contact WinGet, validate live package availability or prove an installer succeeds. Use `-AsJson` with either command for a structured report.

For an existing SDK/interpreter that is not selected correctly by PATH:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_dev_workstation.ps1 -PythonExecutable 'C:\Python311\python.exe' -DartExecutable 'C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe'
```

Supply trusted existing executables; these example paths are not prerequisites. The checker selects an existing direct SDK binary before probing a discovered Dart batch wrapper, because Flutter's wrapper can bootstrap/update its SDK even for a version request. It does not bootstrap a missing SDK or use bare/global Python as a fallback.

## Recorded baseline

| Tool | Tested version | Setup authority |
|---|---|---|
| Python | 3.11.9 | `.python-version`; existing locked Python setup |
| uv | 0.12.20 | `pyproject.toml` exact required version |
| Node | 24.14.0 | `.node-version`; Windows CI installs this version |
| Dart | 3.11.0 | `.dart-version`; Windows/Linux tooling CI reads this version |
| Git for Windows | 2.54.0.windows.1 | WinGet package version 2.54.0 |
| GitHub CLI | 2.91.0 | Optional development helper |
| ripgrep | 15.1.0 | Optional development helper |
| PowerShell 7 | Standalone 7.6.1 observed | Optional shell; Codex's separate bundled 7.6.5 is an advisory difference |

`config/dev-workstation.json` records package mappings and validation metadata. `config/dev-workstation.winget` pins Git, uv, Node, Dart, GitHub CLI and ripgrep; it also pins the stable Microsoft.WinGet.DSC processor to 1.12.440. The .winget file uses JSON flow syntax, which is valid YAML and can be checked locally without an additional YAML library.

## Prepare a new Windows workstation

Actual installation is a separate, explicitly authorized operation. Start with Windows 11 x64, WinGet >=1.12.440 and PowerShell >=7.2 for the pinned configuration processor. The WinGet floor is a conservative project recipe choice corresponding to the pinned processor/client release; Microsoft's Configuration feature floor is 1.6.2631, and older combinations were not tested. The recipe does not install PowerShell, change OS settings or select installer scope/type; the published WinGetPackage resource does not support those settings.

If PowerShell 7 is missing, provision it separately with an explicit installer/scope choice before applying the recipe. The observed standalone 7.6.1 corresponds to [WinGet package version 7.6.1.0](https://github.com/microsoft/winget-pkgs/blob/master/manifests/m/Microsoft/PowerShell/7.6.1.0/Microsoft.PowerShell.installer.yaml); its MSI/MSIX options are deliberately outside the six-resource recipe.

1. Review the tracked recipe and check it with `-ConfigurationOnly`. On newer WinGet installations using the reduced App Installer package, `configure` can report that extended features are disabled. Its supported prerequisite is `winget configure --enable` (used alone), which requests the full App Installer package through the Microsoft Store. That operation can shut down its own process during the update; inspect its result and rerun validation from a fresh process rather than treating the shutdown alone as successful provisioning.
2. If installation has been authorized, use WinGet's online processor/catalog validation and then its interactive configuration application:

   ```powershell
   winget configure validate --file config/dev-workstation.winget
   winget configure --file config/dev-workstation.winget
   ```

   These commands are not the read-only checker. They can contact package/module sources, and application can install software and exact-version processors. An existing newer package can be uninstalled/reinstalled to reach the pinned version; inspect the current workstation first. Do not apply a stock Microsoft Windows Developer Configuration.

3. Install **Python 3.11.9** deliberately if it is missing. The [official Python 3.11.9 Windows installer](https://www.python.org/downloads/release/python-3119/) provides the exact version; generic latest-Python package installation is not this project's setup. Keep other Python versions separate.
4. Open a fresh shell so new tool locations are visible, rerun the workstation checker, then use the existing locked environment setup:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/setup_python311_env.ps1
   powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Quick
   ```

The locked setup does not download Python automatically, upgrade dependencies or rewrite the lock. A deliberate environment replacement remains a separate choice; the existing `-Recreate` backup/recovery safeguards are unchanged. Test reconstruction in an isolated checkout/environment before replacing one used by the live app.

## Windows and manual requirements

Microsoft Word desktop installation/license, browser installation, native Gmail registration/authentication and credentials are manual requirements, not part of this recipe. Word/Gmail operations need Windows and their own authorized testing scope. The app deliberately selects Windows PowerShell 5.1 for its native Word helper, even when PowerShell 7 is installed. Version-check success does not certify Word, Gmail, provider or browser readiness.

WSL, Docker, native Coreutils, Office, compiler toolchains and application credentials are absent from the recipe. Linux testing would need an explicit supported target, separate checkout/environment and relevant tests. The current browser server is local-only; a container does not turn it into an approved deployable service.

## Validation and limits

Run the workstation regressions with the project's Python, followed by the ordinary required development checks:

```powershell
.\.venv311\Scripts\python.exe -m pytest -q tests/test_dev_workstation.py tests/test_dev_workstation_ci.py tests/test_python_setup.py
powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1
powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full
```

This task validates recipe contracts, the downloaded official Microsoft JSON schema, existing tool versions and temporary fake-tool script behavior. The read-only checker itself uses local structural/pin checks; it does not download that schema. Online WinGet processor/catalog validation, installer execution and hosted CI are not established by these checks. Exact historical package versions were verified against official manifests on 2026-09-30; later availability must be rechecked rather than silently selecting latest.

If the existing Dart launcher reports `Unable to find AOT snapshot for dartdev`, retain that failure and use the established direct-Dart fallback. The workstation checker itself avoids Flutter bootstrap. See [VALIDATION.md](VALIDATION.md) for evidence rules and [EXTERNAL_SOURCE_REGISTRY.md](EXTERNAL_SOURCE_REGISTRY.md) for the verified package/resource/action sources.

Initial local delivery on 2026-09-30 passed all 64 focused setup cases, standard validation (249 tests), selected Full (1,389 executions including 191 formatting cases) and documentation/hygiene checks. Full has nine expected intake deselections; the known Dart AOT failures and successful fallback remain recorded. These initial results belong to the isolated workstation branch and do not establish hosted CI or canonical adoption. The user subsequently authorized both publication/merge and applying setup to this PC; [HANDOFF.md](HANDOFF.md) and the retained publication/application receipt own those separate outcomes and the final version-checking correction.

The corrected checker compares complete version tokens, including prerelease suffixes; its 51 workstation/CI cases pass, with the prior 22 Python recovery cases unchanged. Authorized online validation and application of all six recipe units succeeded on this PC, and the independent WinGet desired-state test confirmed every unit matches. Standalone Dart 3.11.0 was added alongside Flutter; five other package versions already matched. The exact 1.12.440 processor/client modules were provisioned. Python packages, lock/setup inputs and WSL/Docker service state were preserved. Required final local Full and hosted publication outcomes belong to the separate retained receipt, so installation success alone does not certify a merge.
