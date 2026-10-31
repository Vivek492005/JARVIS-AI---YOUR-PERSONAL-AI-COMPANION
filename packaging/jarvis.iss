; JARVIS Inno Setup 6 script — produces JARVIS-Setup-vX.Y.Z.exe
;
; Build (after `pyinstaller packaging/jarvis.spec`):
;   iscc /DMyAppVersion=1.0.0 packaging\jarvis.iss
; The GitHub release workflow passes the version from the git tag.
;
; Design decisions (see plans/03-packaging-roadmap.md):
; - Installs to %LOCALAPPDATA%\JARVIS, no admin rights (fewer UAC prompts).
; - Unsigned v1: release notes document the SmartScreen "Unknown publisher"
;   warning (More info -> Run anyway). Revisit signing with revenue.

#define MyAppName "JARVIS"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "Vivek Bartwal"
#define MyAppURL "https://github.com/Vivek492005/JARVIS-AI---YOUR-PERSONAL-AI-COMPANION"

[Setup]
AppId={{A3F1B2C4-D5E6-4F7A-8B9C-0D1E2F3A4B5C}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\JARVIS
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist-installer
OutputBaseFilename=JARVIS-Setup-v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE
UninstallDisplayName={#MyAppName} v{#MyAppVersion}
; Fresh installs only — never silently overwrite a user's .env/notes
DirExistsWarning=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "autostart"; Description: "Start JARVIS with &Windows"; GroupDescription: "Startup:"

[Files]
Source: "..\dist\JARVIS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\JARVIS.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\JARVIS.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
  ValueName: "JARVIS"; ValueData: """{app}\JARVIS.exe"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\JARVIS.exe"; Description: "Launch {#MyAppName} now"; \
  Flags: nowait postinstall skipifsilent

[Code]
// On uninstall, ASK before touching user data — never silently delete
// notes, logs, or API keys.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{app}');
    if MsgBox('Delete your JARVIS data too (notes, logs, saved API keys)?',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      DeleteFile(DataDir + '\notes.txt');
      DeleteFile(DataDir + '\jarvis_audit.log');
      DeleteFile(DataDir + '\jarvis.log');
      DeleteFile(DataDir + '\.env');
    end;
  end;
end;
