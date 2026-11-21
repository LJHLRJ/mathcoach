; MathCoach Windows 安装器：按用户安装，不需要管理员权限
#define MyAppName "MathCoach"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppPublisher "MathCoach"
#define MyAppExeName "MathCoach.exe"

[Setup]
AppId={{7B2E4D3A-9C41-4F6E-8A52-3D1B7F0C5E21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\MathCoach
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
; OutputDir 按 ISCC 运行目录解析；CI 从仓库根目录运行
OutputDir=dist\installer
OutputBaseFilename=MathCoachSetup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableWelcomePage=yes
InfoBeforeFile=scripts\installer\install-before.txt
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\MathCoach.exe
SourceDir=..\..

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
ExitSetupMessage=Setup is not complete. If you exit now, any changes already made will be rolled back.%n%nYou may run Setup again at another time to complete the installation.%n%nExit Setup?

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Start MathCoach when Windows starts"; GroupDescription: "Startup options:"; Flags: unchecked

[Files]
Source: "dist\MathCoach\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{userprograms}\{#MyAppName}"; Filename: "{app}\MathCoach.exe"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\MathCoach.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "MathCoach"; ValueData: """{app}\MathCoach.exe"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\MathCoach.exe"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
