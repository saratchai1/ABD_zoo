#define MyAppName "PDF Drawing Tool"
#define MyAppVersion "2.6.0"
#define MyAppExeName "PDF Drawing Tool.exe"

[Setup]
AppId={{6A37C39E-0A1E-4A0C-8D0B-7F01D6E43F22}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
; Important: the user's existing desktop shortcut points to C:\PDF Drawing Tool\PDF Drawing Tool.exe.
; Install V2.6.0 to that exact legacy location so the shortcut cannot silently launch an older build.
DefaultDirName={sd}\PDF Drawing Tool
UsePreviousAppDir=no
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

[InstallDelete]
; Remove only old application binaries before copying the verified build.
Type: files; Name: "{app}\PDF Drawing Tool.exe"
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; V2.6.0: verified per-page title-block cell detection. The sheet-number center is
; recalculated from the actual current-page grid and stale coordinates are never reused.
Source: "dist\PDF Drawing Tool\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\PDF Drawing Tool"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\PDF Drawing Tool"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch PDF Drawing Tool V2.6.0"; Flags: nowait postinstall skipifsilent
