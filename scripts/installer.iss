; ###########################################################################
; Inno Setup script for the Fishbowl Inventory Tool.
;
; Produces a per-user, no-UAC installer (FishbowlInventoryTool_Setup.exe) from
; the release payload that scripts/package_release.sh writes to
; release/FishbowlInventoryTool/. Designed so that UPGRADES replace the program
; files (exe + user guide) while PRESERVING any inventory availability and
; turnover report PDFs the customer has dropped into the input folders.
;
; The app (see source/constants.py) reads/writes logs/, data/,
; InventoryAvailability/ and TurnoverReports/ RELATIVE TO ITS OWN EXE, so it is
; installed per-user into a writable location ({localappdata}\Programs) rather
; than Program Files.
;
; Unlike the sibling FishbowlInvoiceTool's installer, no files ship inside the
; input folders -- the release payload creates them empty -- so they appear in
; [Dirs] only and there are no [Files] entries for them.
;
; Build (run from the repo root, after building the release payload):
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAppVersion=1.0.0 scripts\installer.iss
;
; AppVersion is passed in via /D so source/constants.py stays the single source
; of truth; the #ifndef below provides a fallback for a bare manual compile.
; ###########################################################################

#define AppName "Fishbowl Inventory Tool"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppExeName "AutoInventoryProc.exe"
#define Publisher "Hammond Software"

; Release payload produced by scripts/package_release.sh, relative to this .iss.
#define SourceRoot "..\release\FishbowlInventoryTool"

; Optional installer icon. No .ico ships in the repo yet, so reference it only
; if present; once scripts\assets\app.ico is added it is picked up automatically.
#define IconFile "assets\app.ico"
#define HaveIcon FileExists(AddBackslash(SourcePath) + IconFile)

[Setup]
; A stable AppId is what lets Inno recognize an existing install and upgrade it
; in place. Do NOT change this GUID across versions, and do NOT reuse the
; invoice tool's -- a shared AppId would make the two apps upgrade over one
; another.
AppId={{7C4E9A31-6B2D-4F87-A05C-3E1F8D6B2947}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#Publisher}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#Publisher}
VersionInfoDescription={#AppName} Setup

; Per-user install, no admin prompt. {autopf} under lowest privileges resolves
; to %LOCALAPPDATA%\Programs, which the app can freely write into at runtime.
PrivilegesRequired=lowest
DefaultDirName={autopf}\FishbowlInventoryTool
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

; Force close applications Restart Manager cannot shut down gracefully. This is
; what makes the in-app "Update and Restart" work: the running app launches this
; installer and then exits, but Restart Manager scans within a few hundred ms and
; asks the app to close by posting to its window. A PyInstaller onefile build has
; two processes -- the bootloader and its child -- and the bootloader owns no
; window, so it never answers. Setup then waits out its 30-second timeout, reports
; "Some applications could not be shut down", and because the updater passes
; /SUPPRESSMSGBOXES the Abort/Retry/Ignore prompt defaults to Abort: the upgrade
; silently rolls back and the user is left on the old version. Without a window to
; close, no delay on the app's side fixes this -- Setup has to terminate it.
CloseApplications=force

WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes

OutputDir=..\release
OutputBaseFilename=FishbowlInventoryTool_Setup
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
#if HaveIcon
SetupIconFile={#IconFile}
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Program files: always replaced on upgrade. These are the only files in the
; payload; the input folders ship empty and are handled in [Dirs] below.
Source: "{#SourceRoot}\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\USER_GUIDE.txt"; DestDir: "{app}"; Flags: ignoreversion
; Patch notes: ignoreversion like the rest of the program files, and deliberately
; NOT onlyifdoesntexist/uninsneveruninstall. Those flags exist to protect the
; customer's own data; this is app content that MUST be replaced on upgrade, or the
; app would announce an update by showing the previous release's notes.
Source: "{#SourceRoot}\PATCH_NOTES.md"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
; Guarantee the app's writable folders exist, and keep the ones holding the
; customer's own PDFs on uninstall. data/ holds the per-machine settings
; database, which is deliberately NOT kept: it is this install's own state, not
; the customer's data, and an upgrade preserves it anyway since nothing here
; installs into that folder.
Name: "{app}\logs"
Name: "{app}\data"
Name: "{app}\InventoryAvailability"; Flags: uninsneveruninstall
Name: "{app}\TurnoverReports"; Flags: uninsneveruninstall

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\User Guide"; Filename: "{app}\USER_GUIDE.txt"
Name: "{group}\What's New"; Filename: "{app}\PATCH_NOTES.md"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Interactive install: offer the usual "launch now" checkbox on the final page.
; skipifsilent keeps a scripted silent deployment from springing a window open.
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
; In-app update: the running application launches this installer silently and then
; exits so its executable can be replaced, so nothing above would bring it back.
; Gated on the /RELAUNCH=1 switch the updater passes (see WantsRelaunch below) so
; only that route relaunches, never a hand-run silent install.
Filename: "{app}\{#AppExeName}"; Flags: nowait; Check: WantsRelaunch

[Code]
// Clears one variable from Setup's own environment. Declared against the Win32
// API because Pascal Script has no built-in way to unset a variable; passing an
// empty value deletes it, which is what CMD's "set NAME=" does underneath.
function SetEnvVar(lpName: String; lpValue: String): Boolean;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';

// Drops the PyInstaller bootloader variables Setup inherited from the app that
// started it, so the relaunched app does not.
//
// The app is a PyInstaller onefile build, so its environment carries _PYI_*
// variables describing the extracted bundle. It launches this installer as a
// child process, which inherits them, and the [Run] relaunch above would pass
// them on again. Since PyInstaller 6.22.1 a starting app that sees them assumes
// it is a worker sub-process of a onefile parent and requires its parent process
// to be the same executable -- here it is Setup, so it refuses to start with
// "Security validation failure: parent process has different executable". An
// in-place upgrade keeps the same path, so nothing else tips it off.
//
// Called from InitializeSetup so it applies to everything Setup spawns.
procedure ClearInheritedPyInstallerEnv;
begin
  SetEnvVar('_PYI_ARCHIVE_FILE', '');
  SetEnvVar('_PYI_APPLICATION_HOME_DIR', '');
  SetEnvVar('_PYI_PARENT_PROCESS_LEVEL', '');
  SetEnvVar('_MEIPASS2', '');
end;

function InitializeSetup: Boolean;
begin
  ClearInheritedPyInstallerEnv;
  Result := True;
end;

// True when the installer was started by the application's own updater, which
// passes /RELAUNCH=1. The param constant below expands to the switch's value, or
// to 0 when it was not passed at all.
//
// These are // comments rather than Pascal's { } form deliberately: a brace
// comment does not nest, so the closing brace of a {param:...} constant written
// inside one ends the comment early and the rest of it is compiled as code.
function WantsRelaunch: Boolean;
begin
  Result := ExpandConstant('{param:relaunch|0}') = '1';
end;
