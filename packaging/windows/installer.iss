; Inno Setup script for the Office Automation Platform Windows installer.
;
; Prerequisites:
;   1. Run `python scripts/build_windows.py` first to produce
;      dist\OfficeAutomationPlatform\OfficeAutomationPlatform.exe
;   2. Install Inno Setup (https://jrsoftware.org/isinfo.php)
;   3. Compile this script: iscc packaging\windows\installer.iss
;
; Output: dist\installer\OfficeAutomationPlatform-Setup-{#MyAppVersion}.exe
;
; This installer bundles the PyInstaller output plus config/ and alembic/
; (so `alembic upgrade head` and rule-engine YAML edits work post-install),
; creates a Start Menu shortcut, and does NOT silently create a database or
; admin account - the administrator must still follow docs/INSTALLATION.md
; to configure .env and run scripts/create_admin.py, which is deliberate:
; an installer should never auto-provision default credentials.

#define MyAppName "Office Automation Platform"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Legislative Council Office"
#define MyAppExeName "OfficeAutomationPlatform.exe"

[Setup]
AppId={{B6C1E4B4-0F1A-4E7A-9C3F-0FFICEAUTOMATION}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\OfficeAutomationPlatform
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist\installer
OutputBaseFilename=OfficeAutomationPlatform-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; Requires an administrator to install (writes to Program Files)
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\..\dist\OfficeAutomationPlatform\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\config\*"; DestDir: "{app}\config"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\alembic\*"; DestDir: "{app}\alembic"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\alembic.ini"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\.env.example"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\docs\INSTALLATION.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\..\docs\TROUBLESHOOTING.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\..\docs\user_manual.md"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Installation Guide"; Filename: "{app}\docs\INSTALLATION.md"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\docs\INSTALLATION.md"; Description: "View the installation guide (complete setup before first launch)"; Flags: postinstall shellexec skipifsilent unchecked
