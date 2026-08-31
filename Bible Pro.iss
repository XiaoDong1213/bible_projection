; Bible Pro Inno Setup 7 installer
; Copyright © 2026 XiaoDong

#define MyAppName "Bible Pro"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "XiaoDong"
#define MyAppExeName "Bible Pro.exe"
#define MyAppSourceDir "C:\Users\XiaoDong\Documents\GitHub\bible_projection\dist\Bible Pro"
#define MyAppIcon "C:\Users\XiaoDong\Documents\GitHub\bible_projection\icon.ico"

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
OutputBaseFilename=Bible Pro_Setup
SetupIconFile={#MyAppIcon}
SolidCompression=yes
WizardStyle=modern dynamic

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Personal configuration files are never included in the installer.
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "config.ini,config.json,settings.ini,settings.json,history.ini,history.json"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

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

procedure CurStepChanged(CurStep: TSetupStep);
begin
  { Always reset installed-version user data before copying files. }
  if CurStep = ssInstall then
    DeleteUserData;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    MsgBox('Bible Pro 将删除程序文件以及当前用户保存的配置、历史记录等数据。', mbInformation, MB_OK);
    DeleteUserData;
  end;
end;

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent
