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
; Fixed AppId so updates replace the same install (the auto-generated id is
; derived from name/version and would create a duplicate "Add or Remove
; Programs" entry on upgrade).
AppId={{368B5286-E697-47E4-96E6-44AA0DF5EB78}
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

; When the app is running (it holds the AppMutex below, e.g. during an in-app
; update or a manual reinstall), let the installer close just our exe instead
; of failing to overwrite it. Filtered so it never touches other programs.
CloseApplications=yes
CloseApplicationsFilter=pancalc-tools-gui.exe
AppMutex=PanCalcTools_Lock
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\dist\pancalc-tools-gui\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\pancalc-tools-gui\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\ARCHITECTURE.md"; DestDir: "{app}"; Flags: ignoreversion

; Prerequisite installers (placed in temp directory during install)
; NOTE: GnuPG is bundled INSIDE the app (dist\pancalc-tools\gpg) — not installed system-wide.
Source: "prereqs\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: ignoreversion
; A second copy lives inside {app}\redist so the uninstaller can run its
; /uninstall mode; it is deleted by the uninstaller after use.
Source: "prereqs\vc_redist.x64.exe"; DestDir: "{app}\redist"; Flags: ignoreversion uninsneveruninstall

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

[UninstallDelete]
; Force-remove anything the app created inside its own folder at runtime
; (logs etc.) that is not in the [Files] list and would otherwise stay behind.
; The user's %APPDATA%/%LOCALAPPDATA% cleanup runs from [Code] in the
; usUninstall step instead — it must target the ORIGINAL user's profile, not
; the elevated administrator one, so it is handled via ExecAsOriginalUser.
Type: filesandordirs; Name: "{app}"

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

// ── Optional removal at uninstall ─────────────────────────────────────
// The uninstaller asks what else to remove (with a "remove everything"
// master checkbox). The Visual C++ Redistributable is always offered but is
// NOT covered by the master box and is kept by default, because other
// programs may depend on it.
//
// Custom uninstall wizard pages are not supported, so we inject a page into
// UninstallProgressForm.InnerNotebook and run its modal loop (standard
// Inno Setup technique).
var
  RemoveConfigChecked: Boolean;
  RemoveCacheChecked: Boolean;
  RemoveVCChecked: Boolean;
  VCRemovalFailed: Boolean;
  UninstallCustomPage: TNewNotebookPage;
  UninstallCheckList: TNewCheckListBox;
  UninstallCustomButton: TNewButton;
  OriginalNotebookPage: TNewNotebookPage;
  MasterBox: TNewCheckBox;
  OriginalAppData: string;
  OriginalLocalAppData: string;

// "Remove everything" master: while checked, the settings/cache boxes stay
// checked and greyed out (non-interactive); when unchecked, they become plain
// independent checkboxes the user can tick one by one. The VC++ box is never
// touched by this handler.
procedure MasterBoxOnClick(Sender: TObject);
begin
  if MasterBox.Checked then
  begin
    UninstallCheckList.Checked[0] := True;
    UninstallCheckList.Checked[1] := True;
    UninstallCheckList.ItemEnabled[0] := False;
    UninstallCheckList.ItemEnabled[1] := False;
  end
  else
  begin
    UninstallCheckList.ItemEnabled[0] := True;
    UninstallCheckList.ItemEnabled[1] := True;
    UninstallCheckList.Checked[0] := False;
    UninstallCheckList.Checked[1] := False;
  end;
end;

// The uninstaller runs elevated (administrator token), so the
// {userappdata}/{localappdata} constants point at the ADMINISTRATOR's profile
// and not the real (possibly non-admin) user who started the uninstall —
// deleting those would leave the user's data behind. Resolve the actual
// user's %APPDATA%/%LOCALAPPDATA% by running a tiny helper as the original
// user and reading back its output (written under ProgramData, a location
// both tokens can access).
procedure CaptureOriginalUserDataPaths;
var
  ScriptPath, OutPath, BatContent, S: string;
  RC, P: Integer;
begin
  OriginalAppData := '';
  OriginalLocalAppData := '';
  CreateDir(ExpandConstant('{commonappdata}\pancalc'));
  ScriptPath := ExpandConstant('{commonappdata}\pancalc\get-pancalc-env.bat');
  OutPath := ExpandConstant('{commonappdata}\pancalc\pancalc_uninstall_env.txt');
  DeleteFile(OutPath);
  BatContent := '@echo off' + #13#10 +
                '>  "' + OutPath + '" echo %APPDATA%' + #13#10 +
                '>> "' + OutPath + '" echo %LOCALAPPDATA%' + #13#10 +
                'exit /b 0' + #13#10;
  if SaveStringToFile(ScriptPath, BatContent, False) then
  begin
    if ExecAsOriginalUser(ScriptPath, '', '', SW_HIDE, ewWaitUntilTerminated, RC)
       and FileExists(OutPath) and LoadStringFromFile(OutPath, S) then
    begin
      P := Pos(#13#10, S);
      if P > 0 then
      begin
        OriginalAppData := Trim(Copy(S, 1, P - 1));
        S := Copy(S, P + 2, Length(S));
        P := Pos(#13#10, S);
        if P > 0 then
          OriginalLocalAppData := Trim(Copy(S, 1, P - 1))
        else
          OriginalLocalAppData := Trim(S);
      end;
    end;
    DeleteFile(ScriptPath);
    DeleteFile(OutPath);
  end;
  // Fallback: behave like today if the capture failed for any reason.
  if OriginalAppData = '' then
    OriginalAppData := ExpandConstant('{userappdata}');
  if OriginalLocalAppData = '' then
    OriginalLocalAppData := ExpandConstant('{localappdata}');
end;

function InitializeUninstall: Boolean;
begin
  Result := True;
  // Defaults also cover silent (/VERYSILENT) uninstall where the page is
  // skipped: app + data + config removed, VC++ Redistributable kept.
  RemoveConfigChecked := True;
  RemoveCacheChecked := True;
  RemoveVCChecked := False;
  VCRemovalFailed := False;
  CaptureOriginalUserDataPaths;
end;

procedure CreateCustomUninstallPage;
var
  PageTitle, Note: TNewStaticText;
  CancelButton: TNewButton;
  ListWidth, ListHeight: Integer;
begin
  UninstallCustomPage := TNewNotebookPage.Create(UninstallProgressForm);
  UninstallCustomPage.Notebook := UninstallProgressForm.InnerNotebook;
  UninstallCustomPage.Parent := UninstallProgressForm.InnerNotebook;
  UninstallCustomPage.Align := alClient;

  PageTitle := TNewStaticText.Create(UninstallCustomPage);
  PageTitle.Parent := UninstallCustomPage;
  PageTitle.Left := ScaleX(12);
  PageTitle.Top := ScaleY(14);
  PageTitle.AutoSize := True;
  PageTitle.Caption := 'Choose what to remove:';

  ListWidth := UninstallProgressForm.InnerNotebook.ClientWidth - ScaleX(24);

  // TNewCheckListBox subitems are drawn on a single clipped line, so the
  // Visual C++ explanation lives here as a wrapping note instead.
  Note := TNewStaticText.Create(UninstallCustomPage);
  Note.Parent := UninstallCustomPage;
  Note.Left := ScaleX(12);
  Note.Top := PageTitle.Top + PageTitle.Height + ScaleY(6);
  Note.Width := ListWidth;
  Note.Height := ScaleY(42);
  Note.WordWrap := True;
  Note.AutoSize := False;
  Note.Caption := 'The "Remove everything" option keeps the Microsoft Visual C++ Redistributable because other programs may need it. Tick the last box only if you are sure you no longer need it.';

  MasterBox := TNewCheckBox.Create(UninstallCustomPage);
  MasterBox.Parent := UninstallCustomPage;
  MasterBox.Left := ScaleX(12);
  MasterBox.Top := Note.Top + Note.Height + ScaleY(6);
  MasterBox.Width := ListWidth;
  MasterBox.AutoSize := False;
  MasterBox.Caption := 'Remove everything installed by PanCalc Tools (recommended)';
  MasterBox.Checked := True;
  MasterBox.OnClick := @MasterBoxOnClick;

  ListHeight := UninstallProgressForm.InnerNotebook.ClientHeight - MasterBox.Top - MasterBox.Height - ScaleY(20);
  if ListHeight < ScaleY(120) then
    ListHeight := ScaleY(120);

  UninstallCheckList := TNewCheckListBox.Create(UninstallCustomPage);
  UninstallCheckList.Parent := UninstallCustomPage;
  UninstallCheckList.Left := ScaleX(12);
  UninstallCheckList.Top := MasterBox.Top + MasterBox.Height + ScaleY(6);
  UninstallCheckList.Width := ListWidth;
  UninstallCheckList.Height := ListHeight;

  // All boxes sit at the same level (siblings). A higher ALevel would make
  // each one a parent of the next, so checking one cascaded to all of them.
  // The first two boxes start checked but disabled (the master is checked by
  // default); MasterBoxOnClick toggles their state and enabledness.
  UninstallCheckList.AddCheckBox('Settings and configuration', '%APPDATA%\pancalc\pancalc',
      0, True, False, False, True, nil);
  UninstallCheckList.AddCheckBox('Data, cache, Local Library and GnuPG keys', '%LOCALAPPDATA%\pancalc\pancalc',
      0, True, False, False, True, nil);
  UninstallCheckList.AddCheckBox('Microsoft Visual C++ Redistributable 2015-2022 (x64)',
      '', 0, False, True, False, True, nil);

  // Add an "Uninstall" button next to the standard Cancel button and make
  // both break the modal loop (mrOK = proceed, mrCancel = abort).
  CancelButton := UninstallProgressForm.CancelButton;
  UninstallCustomButton := TNewButton.Create(UninstallProgressForm);
  UninstallCustomButton.Parent := UninstallProgressForm;
  UninstallCustomButton.Left := CancelButton.Left - CancelButton.Width - ScaleX(10);
  UninstallCustomButton.Top := CancelButton.Top;
  UninstallCustomButton.Width := CancelButton.Width;
  UninstallCustomButton.Height := CancelButton.Height;
  UninstallCustomButton.TabOrder := CancelButton.TabOrder;
  UninstallCustomButton.Caption := 'Uninstall';
  UninstallCustomButton.ModalResult := mrOK;
  UninstallProgressForm.CancelButton.TabOrder := UninstallCustomButton.TabOrder + 1;
end;

procedure InitializeUninstallProgressForm;
begin
  if UninstallSilent then
    Exit;

  OriginalNotebookPage := UninstallProgressForm.InnerNotebook.ActivePage;
  CreateCustomUninstallPage;
  UninstallProgressForm.InnerNotebook.ActivePage := UninstallCustomPage;
  UninstallProgressForm.ShowModal;

  // Read the choices, then restore the normal uninstall layout.
  RemoveConfigChecked := MasterBox.Checked or UninstallCheckList.Checked[0];
  RemoveCacheChecked := MasterBox.Checked or UninstallCheckList.Checked[1];
  RemoveVCChecked := UninstallCheckList.Checked[2];
  UninstallProgressForm.InnerNotebook.ActivePage := OriginalNotebookPage;
  UninstallCustomButton.Visible := False;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    // Target the REAL user's profile (captured pre-elevation), not the
    // administrator's, when the uninstaller runs elevated.
    if RemoveConfigChecked then
      DelTree(OriginalAppData + '\pancalc', True, True, True);
    if RemoveCacheChecked then
      DelTree(OriginalLocalAppData + '\pancalc', True, True, True);
    if RemoveVCChecked then
    begin
      if Exec(ExpandConstant('{app}\redist\vc_redist.x64.exe'),
              '/uninstall /quiet /norestart', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      begin
        if ResultCode <> 0 then
          VCRemovalFailed := True;
      end
      else
        VCRemovalFailed := True;
    end;
    // The redist copy was only needed for the step above.
    DelTree(ExpandConstant('{app}\redist'), True, True, True);
  end;
  if CurUninstallStep = usPostUninstall then
  begin
    if VCRemovalFailed then
      MsgBox('The Visual C++ Redistributable could not be uninstalled automatically.' #13#10
             'You can remove it later from "Apps & Features" (Microsoft Visual C++ 2015-2022 Redistributable (x64)).',
             mbInformation, MB_OK);
  end;
end;

