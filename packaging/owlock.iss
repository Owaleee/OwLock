; Instalador do OwLock para Windows (Inno Setup 6).
; Gerado pelo workflow de release:  iscc /DAppVersion=1.0.0 packaging\owlock.iss
; Instala só para o usuário atual (não pede administrador), em %LOCALAPPDATA%\Programs\OwLock.
; O cofre (pasta .owlock no perfil do usuário) NUNCA é apagado pelo desinstalador.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{7B1E4C2A-5D0F-4E8B-9A61-0C3F2D8E4B57}
AppName=OwLock
AppVersion={#AppVersion}
AppVerName=OwLock {#AppVersion}
AppPublisher=Alexandre Queiroz
AppPublisherURL=https://github.com/Owaleee/OwLock
AppSupportURL=https://github.com/Owaleee/OwLock/issues
AppUpdatesURL=https://github.com/Owaleee/OwLock/releases
DefaultDirName={localappdata}\Programs\OwLock
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=OwLock-Setup
SetupIconFile=owlock.ico
UninstallDisplayIcon={app}\OwLock.exe
UninstallDisplayName=OwLock
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
LicenseFile=..\LICENSE
ShowLanguageDialog=no

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: "..\dist\OwLock.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\OwLock"; Filename: "{app}\OwLock.exe"; Comment: "Gerenciador de senhas local"
Name: "{userdesktop}\OwLock"; Filename: "{app}\OwLock.exe"; Tasks: desktopicon

[Registry]
; "Iniciar com o Windows" é ligado pelo próprio app (Ajustes); o desinstalador só remove o valor.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "OwLock"; Flags: uninsdeletevalue dontcreatekey

[Run]
Filename: "{app}\OwLock.exe"; Description: "Abrir o OwLock agora"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM OwLock.exe /F"; Flags: runhidden; RunOnceId: "FecharOwLock"

[Messages]
brazilianportuguese.FinishedLabel=O OwLock foi instalado.%n%nSeu cofre fica na pasta .owlock do seu usuário e não é apagado se você desinstalar o programa.

[Code]
// Antes de instalar ou atualizar: fecha o OwLock (ele pode estar escondido na bandeja).
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{cmd}'), '/C taskkill /IM OwLock.exe /F', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;
