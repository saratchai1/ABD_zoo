#define MyAppName "PDF Drawing Tool"
#define MyAppVersion "2.5.1"
#define MyAppExeName "PDF Drawing Tool.exe"

[Setup]
AppId={{6A37C39E-0A1E-4A0C-8D0B-7F01D6E43F22}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\PDF Drawing Tool
DefaultGroupName=PDF Drawing Tool
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=installer_output
OutputBaseFilename=PDF_Drawing_Tool_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: checkedonce

[Files]
; V2.5.1 keeps the V2.5 Dark CAD presentation and the V2.4.2 PDF engine,
; while replacing the cramped toolbar with a responsive two-row layout.
Source: "dist\PDF Drawing Tool\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\PDF Drawing Tool"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\PDF Drawing Tool"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch PDF Drawing Tool"; Flags: nowait postinstall skipifsilent
