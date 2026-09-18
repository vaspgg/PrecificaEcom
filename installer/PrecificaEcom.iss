#define MyAppName "PrecificaEcom"
#define MyAppVersion "0.19"
#define MyAppPublisher "PrecificaEcom"
#define MyAppExeName "PrecificaEcom.exe"

[Setup]
AppId={{C63A66A4-6F42-4F5A-A147-62F2B6E0C919}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\PrecificaEcom
DefaultGroupName=PrecificaEcom
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=PrecificaEcom-Setup
SetupIconFile=..\assets\PrecificaEcom.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes

[Files]
Source: "..\dist\PrecificaEcom.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\PrecificaEcom"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\PrecificaEcom"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir PrecificaEcom"; Flags: nowait postinstall skipifsilent
