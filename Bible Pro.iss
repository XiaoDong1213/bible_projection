; Bible Pro Inno Setup 7 installer
; Copyright © 2026 XiaoDong and JiangRTTTR

#define MyAppName "Bible Pro"
#define MyAppVersion "1.5.0"
#define MyAppPublisher "XiaoDong & JiangRTTTR"
#define MyAppExeName "Bible Pro.exe"
; Paths are relative to this .iss file (project root), so the script works on any machine.
#define MyAppSourceDir AddBackslash(SourcePath) + "dist\Bible Pro"
#define MyAppIcon AddBackslash(SourcePath) + "resources\icon.ico"
#define MyAppUserModelId "XiaoDong.BibleProjection"

[Setup]
AppId={{8B1BF115-C8D9-46A1-B711-01928676DCF0}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
OutputDir=dist_installer
OutputBaseFilename=Bible Pro_Setup
SetupIconFile={#MyAppIcon}
SolidCompression=yes
WizardStyle=modern dynamic

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:\Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Personal configuration files are never included in the installer.
; Existing user configuration is preserved during overwrite/upgrade installation.
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "config.ini,config.json,settings.ini,settings.json,history.ini,history.json"

[Icons]
; Read the icon directly from the installed EXE instead of referencing icon.ico.
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; IconIndex: 0; WorkingDir: "{app}"; AppUserModelID: "{#MyAppUserModelId}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; IconIndex: 0; WorkingDir: "{app}"; AppUserModelID: "{#MyAppUserModelId}"; Tasks: desktopicon

[Code]
procedure DeleteUserData;
var
  UserDataDir: string;
begin
  { Installed-version configuration is stored in %APPDATA%\bible_projection. }
  UserDataDir := ExpandConstant('{userappdata}\bible_projection');
  if DirExists(UserDataDir) then
    DelTree(UserDataDir, True, True, True);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  { Only a real uninstall removes user data. Overwrite/upgrade installation does not call this. }
  if CurUninstallStep = usUninstall then
  begin
    MsgBox('Bible Pro 将删除程序文件以及当前用户保存的配置、历史记录等数据。', mbInformation, MB_OK);
    DeleteUserData;
  end;
end;

[Run]
; Refresh the Windows shell icon cache after an overwrite installation.
Filename: "{sys}\ie4uinit.exe"; Parameters: "-show"; Flags: runhidden waituntilterminated skipifsilent
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent
