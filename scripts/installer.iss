; ###########################################################################
; Inno Setup script for the Fishbowl Inventory Tool.
;
; Produces a per-user, no-UAC installer (FishbowlInventoryTool_Setup.exe) from
; the release payload that scripts/package_release.sh writes to
; release/FishbowlInventoryTool/. Designed so that UPGRADES replace the program
; files (exe + user guide) while PRESERVING any inventory availability and
; turnover report PDFs the customer has dropped into the input folders.
;
; The app (see source/constants.py) reads/writes logs/, InventoryAvailability/
; and TurnoverReports/ RELATIVE TO ITS OWN EXE, so it is installed per-user into
; a writable location ({localappdata}\Programs) rather than Program Files.
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

[Dirs]
; Guarantee the app's writable folders exist, and keep the ones holding the
; customer's own PDFs on uninstall.
Name: "{app}\logs"
Name: "{app}\InventoryAvailability"; Flags: uninsneveruninstall
Name: "{app}\TurnoverReports"; Flags: uninsneveruninstall

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\User Guide"; Filename: "{app}\USER_GUIDE.txt"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
