; ─────────────────────────────────────────────────────────────────────────────
;  Atlas SEO — Inno Setup Installer Script
;  Builds: AtlasSetup.exe
; ─────────────────────────────────────────────────────────────────────────────

#define MyAppName      "Atlas SEO"
#define MyAppVersion   "2.0.0"
#define MyAppPublisher "Atlas SEO"
#define MyAppURL       "https://atlasseo.app"
#define MyAppExeName   "atlas-launch.bat"
#define SourceDir      "D:\Atlas\atlas"
#define InstallerDir   "D:\Atlas\atlas\installer"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; Install to user's local AppData — no admin needed, launcher can write files freely
DefaultDirName={localappdata}\Atlas SEO
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Output
OutputDir={#InstallerDir}\output
OutputBaseFilename=AtlasSetup
SetupIconFile={#InstallerDir}\atlas.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; No admin required — installs per-user
PrivilegesRequired=lowest
; Minimum Windows 10
MinVersion=10.0.17763
; Uninstall
UninstallDisplayIcon={app}\atlas.ico
UninstallDisplayName={#MyAppName} {#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Desktop icon ON by default
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; ── Core config ────────────────────────────────────────────────────────────
Source: "{#SourceDir}\docker-compose.yml";              DestDir: "{app}"; Flags: ignoreversion
Source: "{#InstallerDir}\atlas-launch.bat";             DestDir: "{app}"; Flags: ignoreversion
Source: "{#InstallerDir}\atlas-stop.bat";               DestDir: "{app}"; Flags: ignoreversion
Source: "{#InstallerDir}\atlas.ico";                    DestDir: "{app}"; Flags: ignoreversion
Source: "{#InstallerDir}\resources\default.env";        DestDir: "{app}"; Flags: ignoreversion

; ── Ollama entrypoint ───────────────────────────────────────────────────────
Source: "{#SourceDir}\ollama\entrypoint.sh";  DestDir: "{app}\ollama"; Flags: ignoreversion

; ── Backend source ──────────────────────────────────────────────────────────
Source: "{#SourceDir}\backend\*"; DestDir: "{app}\backend"; \
    Flags: ignoreversion recursesubdirs createallsubdirs; \
    Excludes: "__pycache__,*.pyc,*.pyo,.env,venv,.venv,*.egg-info"

; ── Frontend source ─────────────────────────────────────────────────────────
Source: "{#SourceDir}\frontend\*"; DestDir: "{app}\frontend"; \
    Flags: ignoreversion recursesubdirs createallsubdirs; \
    Excludes: "node_modules,.next,.env.local,*.log"

[Icons]
; Start Menu
Name: "{group}\Atlas SEO";         Filename: "{app}\atlas-launch.bat"; IconFilename: "{app}\atlas.ico"; WorkingDir: "{app}"
Name: "{group}\Stop Atlas SEO";    Filename: "{app}\atlas-stop.bat";   IconFilename: "{app}\atlas.ico"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; Desktop shortcut (on by default)
Name: "{autodesktop}\Atlas SEO";   Filename: "{app}\atlas-launch.bat"; IconFilename: "{app}\atlas.ico"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; After install, check Docker
Filename: "powershell.exe"; \
    Parameters: "-NoProfile -Command ""if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {{ [System.Windows.Forms.MessageBox]::Show('Docker Desktop is required to run Atlas SEO. Please install it from https://www.docker.com/products/docker-desktop/', 'Docker Required', 'OK', 'Warning') }}"""; \
    Flags: runhidden; Description: "Checking Docker Desktop"; StatusMsg: "Checking system requirements..."

; Launch Atlas after install — checked by default
Filename: "{app}\atlas-launch.bat"; \
    Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
    Flags: nowait postinstall; WorkingDir: "{app}"

[UninstallRun]
; Stop containers before uninstall
Filename: "cmd.exe"; \
    Parameters: "/c cd /d ""{app}"" && docker compose down"; \
    Flags: runhidden; RunOnceId: "StopContainers"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.atlas-built"
Type: filesandordirs; Name: "{app}\.env"
Type: filesandordirs; Name: "{app}"

[Code]
// ─── Pre-install: check Docker is installed ──────────────────────────────────
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  if not Exec('cmd.exe', '/c where docker >nul 2>&1', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
  begin
    if MsgBox('Docker Desktop is required to run Atlas SEO.' + #13#10 + #13#10 +
              'Docker Desktop provides the container engine that powers Atlas.' + #13#10 +
              'Would you like to open the Docker Desktop download page?',
              mbInformation, MB_YESNO) = IDYES then
    begin
      ShellExec('open', 'https://www.docker.com/products/docker-desktop/', '', '', SW_SHOW, ewNoWait, ResultCode);
    end;
    // Still allow install — Docker might just not be on PATH yet
  end;
end;
