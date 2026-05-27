; PanCalc Tools — Windows Installer
; Fully self-contained installer that includes all prerequisites
; Set MyAppVersion via the /D switch when compiling, e.g.:
;   iscc pancalc-tools.iss /DMyAppVersion=0.2.0

#define MyAppName "PanCalc Tools"
#define MyAppPublisher "Pan Devs"
#define MyAppPublisherURL "https://github.com/pan-devs"
#define MyAppURL "https://github.com/pan-devs/pancalc-tools"
#define MyAppExeName "pancalc-tools.exe"
#define GPG4WIN_FILE "gpg4win-4.2.0.exe"  ; default value, can be overridden by /DGPG4WIN_FILE=

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppPublisherURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppPublisher}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=..\LICENSE.md
OutputDir=..
OutputBaseFilename=PanCalc-Tools-Setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
SetupIconFile=favicon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
ChangesEnvironment=yes
DisableWelcomePage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "addtopath"; Description: "Add PanCalc Tools to your system &PATH (lets you run 'pcalc' from any terminal)"; GroupDescription: "Other tasks:"

[Files]
Source: "..\dist\pancalc-tools\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\pancalc-tools\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\ARCHITECTURE.md"; DestDir: "{app}"; Flags: ignoreversion

; Prerequisite installers (placed in temp directory during install)
Source: "installer\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: ignoreversion
Source: "installer\{#GPG4WIN_FILE}"; DestDir: "{tmp}"; Flags: ignoreversion

[Icons]
Name: "{group}\PanCalc Tools (CLI)"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Comment: "Command-line interface for managing calculator add-ins, converting files, and more"
Name: "{group}\PanCalc Tools (TUI)"; Filename: "{app}\{#MyAppExeName}"; Parameters: "tui"; WorkingDir: "{app}"; Comment: "Graphical terminal interface — easier for browsing and installing add-ins"
Name: "{group}\Documentation"; Filename: "{app}\README.md"; Comment: "Open the README documentation file"
Name: "{group}\Uninstall PanCalc Tools"; Filename: "{uninstallexe}"
Name: "{commondesktop}\PanCalc Tools"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon; Comment: "Launch PanCalc Tools"

[Registry]
Root: HKA; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; \
    ValueType: expandsz; ValueName: "PATH"; ValueData: "{olddata};{app}"; \
    Tasks: addtopath; Check: NeedsAddPath

[Run]
; Install VC++ Redistributable if needed (64-bit)
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; \
    StatusMsg: "Installing Microsoft Visual C++ Redistributable..."; \
    Flags: waituntilterminated runhidden; \
    Check: VCRedistNeedsInstall

; Install Gpg4win if needed  
Filename: "{tmp}\{#GPG4WIN_FILE}"; Parameters: "/S"; \
    StatusMsg: "Installing Gpg4win for add-in verification..."; \
    Flags: waituntilterminated runhidden; \
    Check: Gpg4winNeedsInstall

; Launch application after install
Filename: "{app}\{#MyAppExeName}"; Description: "Launch PanCalc Tools"; Flags: nowait postinstall skipifsilent unchecked

[Code]
function NeedsAddPath: Boolean;
var
  OrigPath: string;
  AppDir: string;
begin
  AppDir := ExpandConstant('{app}');
  if not RegQueryStringValue(HKA, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'PATH', OrigPath) then
  begin
    Result := True;
    Exit;
  end;
  Result := Pos(';' + UpperCase(AppDir) + ';', ';' + UpperCase(OrigPath) + ';') = 0;
end;

// Check if VC++ Redistributable needs to be installed
function VCRedistNeedsInstall: Boolean;
var
  RegVal: string;
begin
  // Check for VC++ 2015-2022 Redistributable (x64) - what pymupdf typically needs
  // We check for a specific version that's known to work
  if RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', RegVal) then
  begin
    // If installed, check version - we want at least 14.0
    Result := (StrToIntDef(RegVal, 0) < 14);
    Exit;
  end;
  
  // Alternative check: look for specific DLL in system32
  Result := not FileExists(ExpandConstant('{sys}\vcruntime140.dll')) and
            not FileExists(ExpandConstant('{sys}\vcruntime140_1.dll')) and
            not FileExists(ExpandConstant('{sys}\vcruntime140_2.dll'));
end;

// Check if Gpg4win needs to be installed
function Gpg4winNeedsInstall: Boolean;
var
  RegPath: string;
  ExePath: string;
  CmdResult: Integer;
begin
  // Check common Gpg4win installation paths
  ExePath := ExpandConstant('{pf}\Gpg4win\bin\gpg.exe');
  if not FileExists(ExePath) then
  begin
    ExePath := ExpandConstant('{pf}\GNU\GnuPG\bin\gpg.exe');
    if not FileExists(ExePath) then
    begin
      ExePath := ExpandConstant('{sf}\gpg\bin\gpg.exe');
      if not FileExists(ExePath) then
      begin
        // Try to find gpg in PATH
        if not (Exec(ExpandConstant('{cmd}'), '/c where gpg', '', SW_HIDE, ewWaitUntilTerminated, CmdResult)) then
        begin
          Result := True; // Assume not found if we can't run where command
          Exit;
        end;
        Result := (CmdResult <> 0); // Non-zero exit code means not found
        Exit;
      end;
    end;
  end;
  
  // If we found gpg.exe, check if it's recent enough
  Result := False; // Assume it's good enough if found
end;