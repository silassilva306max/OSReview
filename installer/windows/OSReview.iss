; OSReview — INSTALADOR FINAL (independente de interpretes externos e sem download de runtime no cliente)
; Gerar apenas DEPOIS de compilar o projeto em Windows x64.
#define AppName "OSReview"
#define AppVersion "0.8.1"
#define AppExe "OSReview.exe"

[Setup]
AppId=OSReview.Diagnostics
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=OSReview (projeto independente)
DefaultDirName={localappdata}\Programs\OSReview
DefaultGroupName=OSReview
DisableDirPage=no
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
SetupIconFile=..\..\assets\osreview.ico
UninstallDisplayIcon={app}\{#AppExe}
OutputDir=..\..\release
OutputBaseFilename=OSReview-Setup-{#AppVersion}-Windows-x64-NAO-ASSINADO
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes
UsePreviousTasks=yes
SetupLogging=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked
Name: "autostart"; Description: "Iniciar OSReview ao entrar no Windows (usuário atual)"; GroupDescription: "Inicialização:"; Flags: unchecked

[Files]
; A pasta dist/OSReview é uma distribuição PyInstaller --onedir já compilada.
; Ela inclui Python e a ponte .NET 8 self-contained; NÃO copiar código-fonte nem .bat.
Source: "..\..\dist\OSReview\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\OSReview"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\OSReview"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir OSReview após instalar"; Flags: nowait postinstall skipifsilent unchecked

[Code]
function InitializeSetup(): Boolean;
begin
  Result := IsWin64;
  if not Result then
    MsgBox('OSReview requer Windows 10/11 x64.', mbCriticalError, MB_OK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  StartupValue: String;
begin
  if CurStep = ssPostInstall then
  begin
    StartupValue := '"' + ExpandConstant('{app}\{#AppExe}') + '"';
    if WizardIsTaskSelected('autostart') then
      RegWriteStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'OSReview', StartupValue)
    else
      RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'OSReview');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'OSReview');
end;
