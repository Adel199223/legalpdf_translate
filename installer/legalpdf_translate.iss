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

#define EdgeNativeHostName "com.legalpdf.gmail_focus"
#define EdgeExtensionOrigin "chrome-extension://afckgbhjkmojchdlinolkepffchlgpin/"

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

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Edge\NativeMessagingHosts\{#EdgeNativeHostName}"; \
  ValueType: string; ValueName: ""; ValueData: "{app}\native_messaging\{#EdgeNativeHostName}.edge.json"; \
  Flags: uninsdeletekey

[UninstallDelete]
Type: files; Name: "{app}\native_messaging\{#EdgeNativeHostName}.edge.json"
Type: dirifempty; Name: "{app}\native_messaging"

[Run]
Filename: "{app}\LegalPDFTranslate.exe"; Description: "Launch LegalPDF Translate"; Flags: nowait postinstall skipifsilent

[Code]
function JsonEscapePath(Value: string): string;
begin
  Result := StringChangeEx(Value, '\', '\\', True);
end;

function EdgeNativeHostManifestText(HostExePath: string): string;
begin
  Result :=
    '{' + #13#10 +
    '  "name": "{#EdgeNativeHostName}",' + #13#10 +
    '  "description": "LegalPDF Translate foreground activation host",' + #13#10 +
    '  "path": "' + JsonEscapePath(HostExePath) + '",' + #13#10 +
    '  "type": "stdio",' + #13#10 +
    '  "allowed_origins": [' + #13#10 +
    '    "{#EdgeExtensionOrigin}"' + #13#10 +
    '  ]' + #13#10 +
    '}' + #13#10;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  HostExePath: string;
  ManifestPath: string;
begin
  if CurStep <> ssPostInstall then
    exit;

  HostExePath := ExpandConstant('{app}\LegalPDFGmailFocusHost.exe');
  ManifestPath := ExpandConstant('{app}\native_messaging\{#EdgeNativeHostName}.edge.json');
  ForceDirectories(ExtractFileDir(ManifestPath));
  SaveStringToFile(ManifestPath, EdgeNativeHostManifestText(HostExePath), False);
end;
