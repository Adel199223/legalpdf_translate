; Inno Setup script for LegalPDF Translate
; Requires: Inno Setup 6+  (https://jrsoftware.org/isinfo.php)
; Build:    ISCC.exe installer\legalpdf_translate.iss

[Setup]
AppId={{B8F3C2A1-7D4E-4F5A-9C6B-1E2D3F4A5B6C}
; ^^^ stable GUID — do NOT change between versions (enables clean upgrades)
AppName=LegalPDF Translate
AppVersion=0.1.0
; ^^^ bump this when src/legalpdf_translate/__init__.py __version__ changes
AppPublisher=LegalPDF Translate
DefaultDirName={localappdata}\Programs\LegalPDF Translate
DefaultGroupName=LegalPDF Translate
PrivilegesRequired=lowest
OutputDir=..\installer_output
OutputBaseFilename=Setup_LegalPDFTranslate_0.1.0
SetupIconFile=..\resources\icons\LegalPDFTranslate.ico
UninstallDisplayIcon={app}\LegalPDFTranslate.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a Desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\legalpdf_translate\*"; DestDir: "{app}"; \
  Excludes: "*.env,*.log,*.pdb,*.pyc,__pycache__,run_events*.jsonl,run_summary*.json,run_state*.json,run_report*.md,analyze_report*.json,*.docx"; \
  Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\LegalPDF Translate"; Filename: "{app}\LegalPDFTranslate.exe"
Name: "{group}\Uninstall LegalPDF Translate"; Filename: "{uninstallexe}"
Name: "{userdesktop}\LegalPDF Translate"; Filename: "{app}\LegalPDFTranslate.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\LegalPDFTranslate.exe"; Description: "Launch LegalPDF Translate"; Flags: nowait postinstall skipifsilent
