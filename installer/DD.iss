; Inno Setup script for the D&D Windows release.
#define MyAppName "D&D"
#define MyAppVersion "0.28.0"
#define MyAppPublisher "D&D"
#define MyAppExeName "DD.exe"

[Setup]
AppId={{D&D-CRM-2026}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\D&D
DefaultGroupName={#MyAppName}
OutputDir=output
OutputBaseFilename=D&D_Setup_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\desktop\dist\DD\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autodesktop}\D&D"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\D&D"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch D&D"; Flags: nowait postinstall skipifsilent
