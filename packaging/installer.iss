#define AppName "Astro Laboratory"
#define AppVersion "0.9.0"
#define AppExe "AstroLaboratory.exe"
#if !FileExists("..\dist\AstroLaboratory\_internal\static\index.html")
  #error Missing packaged static/index.html. Run build_windows.bat before compiling this installer.
#endif
[Setup]
AppId={{4C164BDC-01C0-4A3D-BE43-57CFC401F320}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\AstroLaboratory
UsePreviousAppDir=no
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=AstroLaboratory-{#AppVersion}-Windows-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
CloseApplications=yes

[Files]
Source: "..\dist\AstroLaboratory\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Include the interface explicitly, including when the resource directory is hidden.
Source: "..\dist\AstroLaboratory\_internal\static\index.html"; DestDir: "{app}\_internal\static"; Flags: ignoreversion

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
