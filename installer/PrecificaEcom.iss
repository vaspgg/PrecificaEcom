#define MyAppName "Nalvi"
#define MyAppVersion "0.19"
#define MyAppPublisher "Nalvi"
#define MyAppExeName "Nalvi.exe"

[Setup]
AppId={{C63A66A4-6F42-4F5A-A147-62F2B6E0C919}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Nalvi
DefaultGroupName=Nalvi
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=Nalvi-Setup
SetupIconFile=..\assets\Nalvi.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes

[Files]
Source: "..\dist\Nalvi.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Nalvi"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Nalvi"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir Nalvi"; Flags: nowait postinstall skipifsilent
