; PanCalc Tools — Windows Installer
; Fully self-contained installer that includes all prerequisites
; Set MyAppVersion via the /D switch when compiling, e.g.:
;   iscc pancalc-tools.iss /DMyAppVersion=0.2.2

#define MyAppName "PanCalc Tools"
#define MyAppPublisher "Pan Devs"
#define MyAppPublisherURL "https://github.com/pan-devs"
#define MyAppURL "https://github.com/pan-devs/pancalc-tools"
#define MyAppExeName "pancalc-tools-gui.exe"

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

[Files]
Source: "..\dist\pancalc-tools\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\pancalc-tools\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\ARCHITECTURE.md"; DestDir: "{app}"; Flags: ignoreversion

; Prerequisite installers (placed in temp directory during install)
; NOTE: GnuPG is bundled INSIDE the app (dist\pancalc-tools\gpg) — not installed system-wide.
Source: "prereqs\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: ignoreversion

[Icons]
Name: "{group}\PanCalc Tools"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Comment: "Graphical user interface for managing calculator add-ins, converting files, and more"
Name: "{group}\Documentation"; Filename: "{app}\README.md"; Comment: "Open the README documentation file"
Name: "{group}\Uninstall PanCalc Tools"; Filename: "{uninstallexe}"
Name: "{commondesktop}\PanCalc Tools"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon; Comment: "Launch PanCalc Tools GUI"

[Run]
; Install VC++ Redistributable if needed (64-bit)
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; \
    StatusMsg: "Installing Microsoft Visual C++ Redistributable..."; \
    Flags: waituntilterminated runhidden; \
    Check: VCRedistNeedsInstall

; Launch the GUI after install
Filename: "{app}\{#MyAppExeName}"; Description: "Launch PanCalc Tools"; Flags: nowait postinstall skipifsilent unchecked

[Code]
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

