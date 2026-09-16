---
paths:
  - "scripts/**"
---

# Release packaging and the installer

Not everything in `scripts/` is packaging. **`scripts/dump_workbooks.py` is integration-test
tooling** — it dumps the generated `.xlsx` files so CI can diff the spreadsheet itself, needs
`openpyxl` from `requirements/dev.txt`, and is no part of the release build. It is documented in
`rules/ci.md`; `copy_resources.sh` likewise stages test data rather than building anything.

`scripts/package_release.sh` builds the payload; `scripts/installer.iss` turns it into
`FishbowlInventoryTool_Setup.exe` with Inno Setup, and `.github/workflows/release.yml` publishes
both when a `v*` tag is pushed (see `rules/ci.md` for the workflow side).

`package_release.sh` takes **no arguments** and produces everything a release needs. It mirrors
the sibling `FishbowlInvoiceTool`'s script — fresh venv, `pip install` of
`requirements/release.txt` plus PyInstaller (deliberately unpinned and deliberately not in
`requirements/`), then
`python -OO -m PyInstaller --onefile --noconsole --name AutoInventoryProc main.py`, then a zip
built with `shutil.make_archive` rather than `tar` so the artifact is a real DEFLATE `.zip`.
`-OO` strips docstrings and `__debug__`-gated code from the shipped executable. The venv
deactivate and the `git clean -fdx` above the build are guarded behind `IS_CI="${CI:-false}"` —
in CI the tree is already clean and the clean would delete the staged test data.

Two divergences from the sibling, both load-bearing:

- **The release ships no sample data.** The sibling stages `Configs/` (and optionally
  `Invoices/`) out of its testing submodule; this app has no config files, so the payload is just
  the executable, `USER_GUIDE.txt` and `PATCH_NOTES.md` alongside **empty**
  `InventoryAvailability/` and `TurnoverReports/` folders. That is why the script takes no
  arguments and never touches `automated-inventory-testing` — packaging must not require access
  to a private repo, and there is no submodule re-init fallback here for the same reason.
- **The payload's input folders are created with `mkdir`, never copied from the repo root.** A
  release CI run stages real customer PDFs into the repo's `InventoryAvailability/` and
  `TurnoverReports/` to run the integration test *before* packaging, so a `cp` here would publish
  private data in the release zip. Do not "helpfully" copy them across.

The `git clean` is **not** a divergence: both repos use a single `-f` on purpose, since git skips
a registered submodule either way and a second `-f` only widens what can be deleted for no gain.

`installer.iss` builds the optional double-click installer with Inno Setup, whose `ISCC.exe` is
Windows-only; the script probes `$ISCC`, then the default install path, then `iscc` on `PATH`, and
skips with a message when none is found — the zip is the guaranteed artifact. The version reaches
it as `//DAppVersion=` (a **double** slash, or Git Bash path-mangles the argument) read from
`source/constants.py`, keeping that the single source of truth.

The install is per-user (`PrivilegesRequired=lowest`, `{autopf}` resolving to
`%LOCALAPPDATA%\Programs`) because `constants.py` uses paths relative to the executable's CWD — a
Program Files install would leave the app unable to write its own `logs/`, `data/` and `.xlsx`
output. `InventoryAvailability/` and `TurnoverReports/` are `[Dirs]` entries flagged
`uninsneveruninstall` so a customer's PDFs survive upgrades and uninstalls; they have no
`[Files]` entries at all, since nothing ships inside them. `PATCH_NOTES.md` is a `[Files]` entry
flagged plain `ignoreversion` and deliberately **not** `onlyifdoesntexist uninsneveruninstall`:
those flags protect the customer's own data, while this is app content that must be replaced on
upgrade — a stale copy would have the app announce an update by showing the previous release's
notes. `data/` (the settings database) is a `[Dirs]` entry too but deliberately **not** flagged
`uninsneveruninstall`, matching the sibling: it is this install's own state rather than the
customer's data. An upgrade preserves it regardless, because nothing in `[Files]` installs into
that folder. The `AppId` GUID is what lets Inno upgrade an existing install in place — never
change it, and never share it with the sibling's.

## What the in-app updater needs from the release pipeline

Four things exist purely so "Update and Restart" works, and each of them was found by a failed
real upgrade in the sibling `FishbowlInvoiceTool` (its issue #106, releases 4.1.0 through 4.1.5)
rather than by reasoning. Treat all four as load-bearing:

- **`/RELAUNCH=1` is what brings the app back after a silent upgrade.** The interactive `[Run]`
  entry is flagged `skipifsilent`, so a `/VERYSILENT` install — which is how the updater invokes
  it — would otherwise finish with the application simply gone. A second `[Run]` entry gated on
  the `WantsRelaunch` `[Code]` function (`{param:relaunch|0} = '1'`) relaunches it, and only for
  that route: a hand-run silent install still springs no window open. Do not "simplify" this by
  dropping `skipifsilent` from the first entry.
- **`CloseApplications=force` is what makes the silent upgrade actually apply.** The running app
  launches the installer and exits, but Restart Manager scans a few hundred milliseconds later
  and asks the app to close by posting to its window — and a PyInstaller onefile build has two
  processes, the bootloader and its child, the bootloader owning no window. It never answers,
  Setup waits out its 30-second timeout, and because the updater passes `/SUPPRESSMSGBOXES` the
  resulting Abort/Retry/Ignore prompt defaults to **Abort**: the upgrade rolls back silently and
  the user is left on the old version with no error shown. No delay on the app's side fixes this,
  since there is no window to close — Setup has to terminate the process. Do not weaken this to
  plain `CloseApplications=yes`.
- **`InitializeSetup` clears the inherited `_PYI_*` variables before anything is relaunched.**
  The app is a PyInstaller onefile build, so its environment describes its extracted bundle; it
  launches the installer as a child process, which inherits those variables and would pass them
  to the relaunched app. Since PyInstaller 6.22.1 an app that starts with them set assumes it is
  a worker sub-process of a onefile parent and requires its parent process to be the same
  executable — it is Setup, so it refuses to start with "Security validation failure: parent
  process has different executable". An in-place upgrade keeps the same path, so nothing else
  tips it off. The `[Code]` section unsets `_PYI_ARCHIVE_FILE`, `_PYI_APPLICATION_HOME_DIR`,
  `_PYI_PARENT_PROCESS_LEVEL` and `_MEIPASS2` through a kernel32 `SetEnvironmentVariableW`
  external, since Pascal Script cannot unset a variable itself. The deeper fix belongs upstream,
  in `fishbowl_common`'s `UpdateInstaller`, which should hand the installer a sanitized
  environment rather than its own; this one also covers users upgrading from an app version
  released before that lands. Note `package_release.sh` leaves PyInstaller unpinned, which is how
  that bootloader change landed mid-release-series in the sibling.
- **`release.yml` publishes `SHA256SUMS.txt`** alongside the zip and the installer, written with
  `sha256sum` from inside `release/` so the names in it are bare and match the asset names on the
  Release. The updater verifies the installer against it **before executing it**, so a release
  missing that asset offers only the manual download — which is the graceful degradation, not a
  failure. `SHA256SUMS.txt` is the name the shared `UpdateChecker` looks for
  (`DEFAULT_CHECKSUMS_NAME`); do not rename it. `INSTALLER_ASSET_PATTERN` in `source/constants.py`
  must likewise stay in step with the installer's `OutputBaseFilename`.

**Comments in `[Code]` must use `//`, never Pascal's `{ }` form.** Brace comments do not nest, so
the closing brace of a `{param:...}` constant written inside one ends the comment early and the
rest of it compiles as code — which cost the sibling a whole release.

The silent upgrade needs no UAC prompt, which is what makes the feature viable at all:
`PrivilegesRequired=lowest` with `{autopf}` resolving to `%LOCALAPPDATA%\Programs`, and the stable
`AppId` letting Inno upgrade in place without being told `/DIR`. Neither the executable nor the
installer is code-signed, so a manual download still draws a SmartScreen warning; that matters
more now that the app downloads and runs the installer itself, and an authenticode certificate is
tracked as follow-up work rather than being done here.
