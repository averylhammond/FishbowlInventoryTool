# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Keep this file current.** Whenever you change the application's architecture —
> add/remove/rename a class or module, move a responsibility between components, change
> how components are wired together, or alter the build/test/run workflow — update the
> relevant section of this file in the same change. Treat `CLAUDE.md` as part of the
> definition of done for any structural change, not an afterthought.

## Project Overview

A Python desktop app (tkinter) that parses Fishbowl-generated **Inventory
Availability** and **Turnover Report** PDFs and produces a formatted Excel (`.xlsx`)
report. The user picks an inventory availability PDF and checks which inventory and
turnover columns to include; the app parses the inventory PDF plus every turnover
report found in `TurnoverReports/`, matches turnover rows to inventory rows by part,
and writes a single styled worksheet named after the date in the inventory PDF's
filename.

This tool is being incrementally brought up to the architecture and engineering
standards of its sibling project `FishbowlInvoiceTool` (see that repo's `CLAUDE.md`
for the target end state). Expect ongoing refactors that split monolithic code into
focused, single-responsibility classes.

## Setup

- Submodule `automated-inventory-testing` provides sample inventory/turnover PDFs for
  development: `git submodule update --init`. This submodule is private (contains
  private company data) — never commit data sourced from it.
- `./scripts/copy_resources.sh` copies the submodule's `resources/` (e.g.
  `InventoryAvailability/`, `TurnoverReports/`) into the project root before running.
- Virtual env: `python -m venv venv`, then `source venv/Scripts/activate` (Windows) or
  `source venv/bin/activate` (Linux/Mac).
- Install deps: `pip install -r requirements/dev.txt` for development (pulls in
  `release.txt` plus `pytest`/`pytest-cov`); `requirements/release.txt` alone is what the
  shipped app needs. `release.txt` pulls `fishbowl-common` (import name
  `fishbowl_common`) from GitHub — the shared package providing `ArgumentProvider`,
  `SettingsRepository`, `UpdateChecker`, `UpdateCoordinator` and `PatchNotes`; see the
  sibling
  `FishbowlInvoiceTool` for the shared-package story. All four
  classes are application-agnostic and take every app-specific value by constructor
  injection, which is why `UpdateCoordinator` is handed `VERSION` and `GITHUB_REPO`, and
  `SettingsRepository` its `db_path`, rather than importing them. `SettingsRepository` and
  `UpdateCoordinator` are covered by their own tests in that package, so this repo tests
  only the wiring around them — `UpdateChecker` is not imported here at all, since the
  coordinator constructs it.
  The pin requests the **`[gui]` extra** (`fishbowl-common[gui] @ git+…@v1.3.0`), which
  adds the package's GUI half — the themed subwindows, the tooltip and the styling data
  this app shares with the sibling. The extra installs no additional requirements (its only
  dependency is tkinter, which ships with CPython); it marks intent, since the top-level
  `fishbowl_common` stays importable with no tkinter present.

## Common Commands

- Run the app (GUI): `python main.py`
- Run headless (no GUI): `python main.py --integration-test` — processes every PDF in
  `InventoryAvailability/` with all columns included and writes `logs/results.txt`. This
  is what CI runs to validate output without GUI interaction.
- Byte-compile sanity check:
  `python -m py_compile main.py source/*.py source/gui/*.py tests/*.py`
- Reproduce the integration test locally (after `./scripts/copy_resources.sh`):
  `python main.py --integration-test` then
  `diff logs/results.txt automated-inventory-testing/canonical_correct_results.txt`.
- Run all unit tests: `pytest tests/*` (from the repo root)
- Run a single test file: `pytest tests/InventoryAppFileIO_tests.py`
- Run a single test:
  `pytest tests/InventoryAppFileIO_tests.py::test_read_pdf_extracts_each_page_in_layout_mode`
- Run with coverage: `pytest --cov=./ --cov-report=term-missing tests/*`
- Package a release executable: `./scripts/package_release.sh` (no arguments). Builds via
  PyInstaller into `release/FishbowlInventoryTool/` and zips it. On Windows with Inno Setup
  installed, it additionally builds `release/FishbowlInventoryTool_Setup.exe` (via
  `scripts/installer.iss`); this step is skipped on Linux or when Inno Setup is absent.

### CI

Four workflows. Three of them — integration tests, unit tests and code coverage — run on
pull requests to `main` and on manual dispatch; the code-coverage one additionally runs on
pushes to `main`. The fourth, the release workflow, runs only on pushed `v*` tags.

`.github/workflows/integration-tests.yml`. On `ubuntu-latest` it installs `requirements/release.txt`,
stages the test PDFs with `scripts/copy_resources.sh`, runs the app headless, and fails
the check unless
`logs/results.txt` matches the submodule's `canonical_correct_results.txt`. Checking out
the private submodule needs the `CUSTOMER_DATA_PAT` repo secret. The diff is inlined in the
workflow; the submodule's `run_automated_tests.sh` is a local convenience script only and
is not invoked by CI. When the parser changes output intentionally, regenerate
`canonical_correct_results.txt` in the `automated-inventory-testing` repo and bump the
submodule pointer.

The job runs on Linux while the app ships as a Windows executable, which is only safe
because the results file is platform-independent by construction (see the results-file
convention below). The release workflow re-runs the same integration test on
`windows-latest`, so a Windows-specific regression is caught at release time — but not on
every PR. If one ever slips through to a release, add a `windows-latest` leg to a
`strategy.matrix` here.

`.github/workflows/unit-tests.yml` runs the unit tests. On `ubuntu-latest` it installs
`requirements/dev.txt` (`release.txt` plus `pytest`/`pytest-cov`) and runs `pytest tests/*`.
The glob is required because the test files use the `_tests.py` suffix, which pytest's
default discovery does not match. Unlike the integration job it checks out **without** the
submodule and needs no repo secret — unit tests mock all their I/O, so pulling the private
test data would only slow the job and tie it to `CUSTOMER_DATA_PAT`. Keep it that way: a
unit test that needs a real PDF belongs in the integration test instead. The GUI test files
do import `tkinter` at module scope, and no `python3-tk` system package is installed — none
is needed, because `actions/setup-python`'s CPython builds bundle `_tkinter` and its Tcl/Tk
libraries. No X display is needed either: the display tests patch `tk.Tk.__init__` and every
widget class, so a real window is never created. The sibling's identical job has been
running tkinter GUI tests on `ubuntu-latest` this way for months.

`.github/workflows/code-coverage.yml` runs the same unit tests under coverage
(`pytest --cov=./ --cov-report=xml --cov-fail-under=90 tests/*`) and uploads `coverage.xml`
to Codecov, which serves the README badge and posts the PR coverage comment. The upload step
is `if: always()` so the report still lands when the gate fails — that is when the comment is
most useful. It needs the `CODECOV_TOKEN` repo secret, and like the unit-test job it checks
out **without** the submodule. The extra `push: branches: [main]` trigger exists so Codecov
records a main-branch baseline for PR diffs; without it the badge never updates.

**Every measured module is at 100%**, so the 90% gate is headroom for an in-progress
refactor rather than a target to climb toward, and it matches the gate the sibling uses.
Keep it there: a new module landing untested should fail the check, not quietly lower the
average. Nothing is omitted for being untestable: the inert styling data that used to be
excluded now lives upstream in `fishbowl_common.gui` (see `.coveragerc`).

This workflow pins `actions/setup-python@v5` with pip caching while `unit-tests.yml` still
uses `@v4` and no cache — a deliberate mirror of the sibling's file rather than an oversight.
`.coveragerc` scopes what is measured (see the unit-testing section).

`.github/workflows/release.yml` publishes a release when a `v*` tag is pushed. On
`windows-latest` (see the release-packaging section below for why the platform is not
negotiable) it verifies the tag matches `VERSION` in `source/constants.py` — stripping the
`v` and failing with `::error::` on a mismatch, so a release can never ship an About box
that disagrees with the tag — checks that `PATCH_NOTES.md` carries a `## <VERSION>`
section, with the same `::error::` treatment, since a release whose notes never mention it
would ship silently and only surface when a customer updated into it — then runs the unit tests and the integration test, installs
Inno Setup via Chocolatey, runs `scripts/package_release.sh`, writes a `SHA256SUMS.txt`
over the built artifacts, and uploads `release/FishbowlInventoryTool.zip`,
`release/FishbowlInventoryTool_Setup.exe` and `release/SHA256SUMS.txt` to a
GitHub Release with `gh release create --generate-notes`. It checks out the submodule (for
`canonical_correct_results.txt`) and so needs `CUSTOMER_DATA_PAT`; the packaging itself
needs nothing from the submodule. Cutting a release is therefore: bump `VERSION`, add that version's section to
`PATCH_NOTES.md`, merge, then push a matching `vX.Y.Z` tag.

## Release Packaging

`scripts/package_release.sh` takes **no arguments** and produces everything a release
needs. It mirrors the sibling `FishbowlInvoiceTool`'s script — fresh venv, `pip install`
of `requirements/release.txt` plus PyInstaller (deliberately unpinned and deliberately not
in `requirements/`), then
`python -OO -m PyInstaller --onefile --noconsole --name AutoInventoryProc main.py`, then a
zip built with `shutil.make_archive` rather than `tar` so the artifact is a real
DEFLATE `.zip`. `-OO` strips docstrings and `__debug__`-gated code from the shipped
executable. Three divergences from the sibling, each load-bearing:

- **The release ships no sample data.** The sibling stages `Configs/` (and optionally
  `Invoices/`) out of its testing submodule; this app has no config files, so the payload
  is just the executable, `USER_GUIDE.txt` and `PATCH_NOTES.md` alongside **empty**
  `InventoryAvailability/` and `TurnoverReports/` folders. That is why the script takes no arguments and never
  touches `automated-inventory-testing` — packaging must not require access to a private
  repo.
- **The payload's input folders are created with `mkdir`, never copied from the repo
  root.** A release CI run stages real customer PDFs into the repo's
  `InventoryAvailability/` and `TurnoverReports/` to run the integration test *before*
  packaging, so a `cp` here would publish private data in the release zip. Do not
  "helpfully" copy them across.
- **`git clean -fdx`, not the sibling's `-fdxf`.** A single `-f` makes git skip nested
  repositories, leaving the submodule checkout intact; the sibling's second `-f` deletes it
  and then has to re-init it. Nothing here is packaged from the submodule, so there is
  nothing to re-init. This clean (and the venv deactivate above it) is guarded behind
  `IS_CI="${CI:-false}"` — in CI the tree is already clean and the clean would delete the
  staged test data.

`scripts/installer.iss` builds the optional double-click installer with Inno Setup, whose
`ISCC.exe` is Windows-only; the script probes `$ISCC`, then the default install path, then
`iscc` on `PATH`, and skips with a message when none is found — the zip is the guaranteed
artifact. The version reaches it as `//DAppVersion=` (a **double** slash, or Git Bash
path-mangles the argument) read from `source/constants.py`, keeping that the single source
of truth. The install is per-user (`PrivilegesRequired=lowest`, `{autopf}` resolving to
`%LOCALAPPDATA%\Programs`) because `constants.py` uses paths relative to the executable's
CWD — a Program Files install would leave the app unable to write its own `logs/`, `data/`
and `.xlsx` output. `InventoryAvailability/` and `TurnoverReports/` are `[Dirs]` entries
flagged `uninsneveruninstall` so a customer's PDFs survive upgrades and uninstalls; they
have no `[Files]` entries at all, since nothing ships inside them. `PATCH_NOTES.md` is a
`[Files]` entry flagged plain `ignoreversion` and deliberately **not**
`onlyifdoesntexist uninsneveruninstall`: those flags protect the customer's own data,
while this is app content that must be replaced on upgrade — a stale copy would have the
app announce an update by showing the previous release's notes. `data/` (the settings
database) is a `[Dirs]` entry too but deliberately **not** flagged `uninsneveruninstall`,
matching the sibling: it is this install's own state rather than the customer's data. An
upgrade preserves it regardless, because nothing in `[Files]` installs into that folder. The
`AppId` GUID is what
lets Inno upgrade an existing install in place — never change it, and never share it with
the sibling's.

### What the in-app updater needs from the release pipeline

Four things exist purely so "Update and Restart" works, and each of them was found by a
failed real upgrade in the sibling `FishbowlInvoiceTool` (issue #106, releases 4.1.0 through
4.1.5) rather than by reasoning. Treat all four as load-bearing:

- **`/RELAUNCH=1` is what brings the app back after a silent upgrade.** The interactive
  `[Run]` entry is flagged `skipifsilent`, so a `/VERYSILENT` install — which is how the
  updater invokes it — would otherwise finish with the application simply gone. A second
  `[Run]` entry gated on the `WantsRelaunch` `[Code]` function (`{param:relaunch|0} = '1'`)
  relaunches it, and only for that route: a hand-run silent install still springs no window
  open. Do not "simplify" this by dropping `skipifsilent` from the first entry.
- **`CloseApplications=force` is what makes the silent upgrade actually apply.** The running
  app launches the installer and exits, but Restart Manager scans a few hundred milliseconds
  later and asks the app to close by posting to its window — and a PyInstaller onefile build
  has two processes, the bootloader and its child, the bootloader owning no window. It never
  answers, Setup waits out its 30-second timeout, and because the updater passes
  `/SUPPRESSMSGBOXES` the resulting Abort/Retry/Ignore prompt defaults to **Abort**: the
  upgrade rolls back silently and the user is left on the old version with no error shown. No
  delay on the app's side fixes this, since there is no window to close — Setup has to
  terminate the process. Do not weaken this to plain `CloseApplications=yes`.
- **`InitializeSetup` clears the inherited `_PYI_*` variables before anything is relaunched.**
  The app is a PyInstaller onefile build, so its environment describes its extracted bundle;
  it launches the installer as a child process, which inherits those variables and would pass
  them to the relaunched app. Since PyInstaller 6.22.1 an app that starts with them set
  assumes it is a worker sub-process of a onefile parent and requires its parent process to be
  the same executable — it is Setup, so it refuses to start with "Security validation failure:
  parent process has different executable". An in-place upgrade keeps the same path, so
  nothing else tips it off. The `[Code]` section unsets `_PYI_ARCHIVE_FILE`,
  `_PYI_APPLICATION_HOME_DIR`, `_PYI_PARENT_PROCESS_LEVEL` and `_MEIPASS2` through a kernel32
  `SetEnvironmentVariableW` external, since Pascal Script cannot unset a variable itself. The
  deeper fix belongs upstream, in `fishbowl_common`'s `UpdateInstaller`, which should hand the
  installer a sanitized environment rather than its own; this one also covers users upgrading
  from an app version released before that lands. Note `package_release.sh` leaves PyInstaller
  unpinned, which is how that bootloader change landed mid-release-series in the sibling.
- **`release.yml` publishes `SHA256SUMS.txt`** alongside the zip and the installer, written
  with `sha256sum` from inside `release/` so the names in it are bare and match the asset names
  on the Release. The updater verifies the installer against it **before executing it**, so a
  release missing that asset offers only the manual download — which is the graceful
  degradation, not a failure. `SHA256SUMS.txt` is the name the shared `UpdateChecker` looks
  for (`DEFAULT_CHECKSUMS_NAME`); do not rename it. `INSTALLER_ASSET_PATTERN` in
  `source/constants.py` must likewise stay in step with the installer's `OutputBaseFilename`.

**Comments in `[Code]` must use `//`, never Pascal's `{ }` form.** Brace comments do not nest,
so the closing brace of a `{param:...}` constant written inside one ends the comment early and
the rest of it compiles as code — which cost the sibling a whole release.

The silent upgrade needs no UAC prompt, which is what makes the feature viable at all:
`PrivilegesRequired=lowest` with `{autopf}` resolving to `%LOCALAPPDATA%\Programs`, and the
stable `AppId` letting Inno upgrade in place without being told `/DIR`. Neither the executable
nor the installer is code-signed, so a manual download still draws a SmartScreen warning; that
matters more now that the app downloads and runs the installer itself, and an authenticode
certificate is tracked as follow-up work rather than being done here.

## Architecture

The application flow is: **entry point → controller → processor + GUI + file I/O + entry
data classes + spreadsheet writer**.

- **`main.py`** — thin entry point. Constructs an `InventoryAppController` and calls
  `start_application()`. Contains no application logic.
- **`InventoryAppController`** (`source/InventoryAppController.py`) — the wiring. It owns no
  parsing or spreadsheet logic itself, delegating the whole processing pipeline to
  `InventoryProcessor`, all file I/O to `InventoryAppFileIO` and everything visual to
  `InventoryAppDisplay`. Responsibilities:
  - `__init__` constructs the `InventoryAppFileIO` collaborator, constructs the
    `InventoryProcessor` and hands it that same file I/O instance (not a fresh one — the
    headless path reassigns `file_io.report_error`, which only reaches the object doing the
    reads if the two share one instance), constructs the shared `ArgumentProvider` (from the
    `fishbowl-common` package) to detect headless mode, sets `self.display = None`,
    `self.settings_repository = None` and `self.update_coordinator = None`, and clears the
    results file (`reset_results_file()`) so each run starts with a fresh diagnostics log.
    It deliberately builds none of the GUI, the settings repository or the update
    coordinator; see `start_application()` below.
  - `start_application()` first checks `argument_provider.integration_test_mode`: when set
    (via the `--integration-test` CLI flag) it skips the GUI entirely and calls
    `run_integration_test()`. Otherwise it constructs the shared `SettingsRepository` (from
    `fishbowl-common`) at `SETTINGS_DB_PATH` and reads `get_all_settings()`, then imports and
    constructs `InventoryAppDisplay`, passing `read_file_callback=self.file_io.read_text_file`
    so the display's View menu can populate its read-only file viewer,
    `check_for_updates_callback=self.handle_check_for_updates` for its Help menu,
    `save_settings_callback=self.handle_save_setting` and `settings=` the settings just read,
    wires both the file I/O controller's and the settings repository's `report_error`
    callbacks to the display's `show_popup`, starts the background update check, and enters
    `mainloop()`.
  - **The settings repository is built here, in the GUI branch, not in `__init__`** — the one
    deliberate divergence from the sibling, which builds its own in `__init__`. The
    integration test must perform no database I/O and leave no `data/` directory behind, the
    same reason the display itself is built here.
    `tests/InventoryAppController_tests.py` guards it with
    `mock_settings_cls.assert_not_called()`. Because `SettingsRepository.__init__` runs
    `initialize_database()` before any display exists, an error from that first call falls to
    the repository's no-op default reporter; only later reads and writes reach `show_popup`.
  - `handle_save_setting(key, value)` is the display's settings callback, forwarding to
    `settings_repository.save_setting()`. It is the display's only route to the database —
    the display itself never imports the repository.
  - **The patch notes.** `PatchNotes` from `fishbowl-common` reads `PATCH_NOTES_PATH`, the
    `## X.Y.Z` changelog packaged next to the executable, and returns the sections between
    two versions. The controller owns both halves of the feature the shared package cannot:
    - `show_patch_notes_if_updated(saved_settings)`, called from `start_application()`
      once the display exists, compares `SETTING_KEY_LAST_SEEN_VERSION` against `VERSION`
      with the shared `compare_versions()` and shows what changed only when the stored
      version is **older**. A fresh install (nothing stored), an ordinary relaunch and a
      downgrade all show nothing, and every one of the four cases stamps `VERSION` — so
      an update's notes appear once rather than on every launch after it. The first launch
      after upgrading *into* this feature shows nothing either, since a build that never
      wrote the key is indistinguishable from a fresh install.
    - **The window is opened through `display.after(0, ...)`, not inline**, and it must
      stay that way: `ThemedSubwindow._center_over_parent()` reads the parent's geometry,
      which is `1x1+0+0` until the root window has been mapped, so an inline call would
      put the window in the corner of the screen instead of over the app.
    - `handle_view_patch_notes()` is the display's Help-menu callback, showing every
      section up to `VERSION` (`notes_since(VERSION, None)`) — a user who dismissed the
      window after an update has no other way back to the notes, and without the menu item
      the feature is unreachable in a manual test without hand-editing the settings
      database. Unlike the silent startup check it reports when there is nothing to show,
      the same manual-versus-automatic split the update check makes.
    - Both the reader and the window are built **only** in the GUI branch, and
      `tests/InventoryAppController_tests.py` asserts `PatchNotes` is never constructed in
      integration-test mode.
  - **The update check** — `UpdateCoordinator` from `fishbowl-common` owns the whole
    feature: the `daemon=True` worker thread, the `UpdateChecker` call, the
    `display.after(0, ...)` hop back onto the GUI thread, and the decision to open the
    update window versus popping "No Updates Available" / "Update Check Failed" (the latter
    two only on a manual check, so a startup check never interrupts a launch just because
    the user is offline). The controller's whole share of it is two things:
    - `start_application()` constructs it with `current_version=VERSION`,
      `repo=GITHUB_REPO`, `display=self.display`, `asset_pattern=INSTALLER_ASSET_PATTERN`
      and calls `start()` for the silent startup check. It is built here rather than in
      `__init__` because it reports through the display, which does not exist until this
      branch.
    - `handle_check_for_updates()` is the display's Help-menu callback, calling
      `update_coordinator.start(manual=True)`. The display never touches the network itself.

    The coordinator is constructed **only** in `start_application()`'s GUI branch, after the
    `integration_test_mode` early return. Keep it there: a headless CI run must perform no
    network I/O, and `tests/InventoryAppController_tests.py` asserts the class is never
    called. The coordinator takes its display as a `typing.Protocol`, which is what lets it
    live in the headless half of `fishbowl_common` rather than `fishbowl_common.gui`; the
    display satisfies it through `after()`, `show_update_available()` and `show_popup()`.

    **In-app update ("Update and Restart").** `INSTALLER_ASSET_PATTERN` is the controller's
    only other contribution: it names this app's installer among a release's assets, which
    the shared package cannot know since each Fishbowl app names its own. Given that asset
    and a published `SHA256SUMS.txt`, the coordinator downloads the installer, verifies its
    digest, launches it silently detached and reports back — `show_update_available()`
    receives that flow as a second `start_install` argument and forwards it to `UpdateWindow`
    as `start_install_callback`. **The display's whole share of the feature is forwarding
    that callback**; it never downloads or executes anything itself. When the argument is
    `None` — no matching installer asset, no checksums asset, or a non-Windows platform — the
    window falls back to the browser-only "Exit and Update" it has always offered, which is
    also where a failed download lands. Both routes exit through the same
    `close_app_callback`, so the app leaves the same way whichever one is taken.
  - `handle_process_inventory(inventory_pdf_path, checkbox_dict)` — the callback handed to
    the display. It runs `self.processor.process_inventory()` with status routed to the
    display's output box, keeping the display's callback contract to two arguments.
  - `run_integration_test()` — the headless entry point. Routes `report_error` to stdout,
    takes an all-columns-checked `checkbox_dict` from `columns.all_columns_selected()`, and
    calls `self.processor.process_inventory()` for every PDF from
    `InventoryAppFileIO.list_inventory_files()`. Lets a CI workflow generate
    `logs/results.txt` with no GUI interaction.
- **`InventoryProcessor`** (`source/InventoryProcessor.py`) — the whole inventory-processing
  pipeline, mirroring `InvoiceProcessor` in the sibling `FishbowlInvoiceTool`. It takes the
  `InventoryAppFileIO` controller as its only constructor argument and builds its own
  `PdfTableParser`; it has no reference to the controller, the display or the argument
  provider, and user-facing status reaches the caller only through an injected callback.
  - `process_inventory(inventory_pdf_path, checkbox_dict, report_status)` — the shared
    per-file processing routine used by both the GUI and headless paths. It parses the
    inventory PDF (bailing gracefully if it can't be read), derives the output filename
    from the PDF name via regex (falling back to a generic name when the regex doesn't
    match), creates the workbook via the file I/O controller, then loops over every
    turnover PDF appending turnover columns and saves. Status strings go to the injected
    `report_status` callback (the GUI output line, or `print`/stdout in headless mode) —
    never to the results file — so the results log stays deterministic for CI diffing.
  - PDF parsing helpers: `process_inventory_file` and `process_turnover_file` source page
    text from `InventoryAppFileIO.read_pdf()`, delegate column parsing to
    `PdfTableParser`, and map the resulting rows onto `InventoryEntry` / `TurnoverEntry`
    objects. Every page is parsed before any entry is built, because a row's part or
    description can wrap from the bottom of one page onto the top of the next.
- **`source/gui/`** — the GUI subpackage. It holds exactly one class: this app's own
  `InventoryAppDisplay`. Every themed subwindow, the tooltip and the styling data it uses
  come from `fishbowl_common.gui` (see the bullet below), so this is the only module in the
  repo that imports tkinter directly.
  - **`InventoryAppDisplay`** (`source/gui/InventoryAppDisplay.py`) — a `tk.Tk` subclass
    that takes every dependency as a constructor argument (`process_callback`,
    `read_file_callback`, `check_for_updates_callback`, `save_settings_callback`, `title`,
    `window_resolution`, and the defaulted `theme`/`font_family`/`font_size`/`settings`) and
    never imports the controller. It owns the
    file picker, the two checkbox grids, the Process/Exit buttons, the `ScrolledText` output box,
    and a menu bar (File/View/Preferences/Help), and exposes `show_popup()`,
    `show_update_available()`, `show_patch_notes()`, `write_output()`, `clear_output()` and
    `get_selected_columns()`. `write_output()` calls
    `update_idletasks()` because processing runs on the GUI thread, so without it a status
    line would not paint until the work it announces had already finished.
    - **Settings restore happens in `__init__`, before `build_widgets()`**, so every widget is
      created already themed rather than restyled afterwards — and so no
      `save_settings_callback` fires during startup. The `theme`/`font_family`/`font_size`/
      `window_resolution` arguments are the *fallbacks* the restore resolves against, which is
      why they stay even though the controller now passes `settings`: the defaults live in one
      place and a missing or corrupt setting falls back to an injected value rather than a
      hardcoded one. Four helpers do the resolving — `THEME_BY_NAME.get()` inline for the
      theme, `_parse_font_size()` (`int()`, falling back on `TypeError`/`ValueError`),
      `_parse_geometry()` (accepts a value only if it matches `GEOMETRY_PATTERN`, since a
      corrupt string handed to `geometry()` would raise), and `_restore_column()` (one
      checkbox state per column).
    - The **menu bar** is built inline in `build_widgets()` (no separate `MenuBar` class,
      matching the sibling): **File** (Open/Clear/Exit — Exit calls `self.handle_exit`, not
      `self.quit`, to match the Exit button's own convention); **View** (Results Log opens
      `RESULTS_FILE` in a read-only `FileEditorWindow` via `_open_readonly_file_viewer()`,
      or a "File Not Found" popup if it doesn't exist yet; Inventories/Turnover Reports/
      Spreadsheets open a browse-only `filedialog.askopenfilename` rooted at
      `INVENTORY_DIR`/`TURNOVER_DIR`/`OUTPUT_DIR` and filtered to that folder's file type,
      reusing the same dialog mechanism as the top-level Browse button rather than shelling
      out to the OS's file explorer); **Preferences** (Theme/Font/Font Size submenus built by
      looping `ALL_THEMES`/`FONT_FAMILIES`/`FONT_SIZES`, each `command` a
      `lambda x=option: self.apply_x(x)` to avoid a late-binding closure bug); **Help**
      (About opens `AboutWindow` with `APP_NAME` and `VERSION` from `constants.py` — the
      shared window is application-agnostic and takes both by injection; Check for Updates just
      calls `check_for_updates_callback` — the display never touches the network itself, and
      the controller reports the outcome back through `show_update_available()`/`show_popup()`;
      What's New likewise just calls `view_patch_notes_callback`, and the controller hands the
      notes back through `show_patch_notes()`, so the display reads no file and holds no
      version of its own).
    - **`apply_theme()`** / **`apply_font_family()`** / **`apply_font_size()`** /
      **`_apply_font()`** apply a Preferences choice live by explicitly reconfiguring every
      widget the display owns, including every checkbutton in `column_checkbuttons` (the
      sibling has no checkbox grid, so this loop has no sibling analog). The first three
      persist the choice as their last statement; `_apply_font()` deliberately does not,
      since it runs for both font settings and would write two keys per change. Two of them
      also call **`_refresh_tooltips()`** so the hover tooltips follow the new styling:
      `apply_theme()` and `_apply_font()`, and only those two. `apply_font_family()` and
      `apply_font_size()` both route through `_apply_font()`, so a call there as well would
      restyle every tooltip twice per change.
    - **`handle_column_toggled(key)`** persists one column's checkbox state, wired as each
      checkbutton's `command` with the key captured as a default argument (the same
      late-binding guard the Preferences lambdas use). Tk runs `command` after updating the
      variable, so it reads the new state.
    - **`handle_exit()`** is the single way out of the application: it persists
      `winfo_geometry()` and then calls `destroy()`. The Exit button, File -> Exit, the
      window's close box (bound via `protocol("WM_DELETE_WINDOW", ...)` in `build_widgets()`)
      and `UpdateWindow`'s `close_app_callback` all route through it, so the geometry is saved
      whichever way the user leaves. Geometry is saved on exit rather than on `<Configure>` so
      a window drag does not write to the database on every frame.
  - **`fishbowl_common.gui`** — the shared GUI half of the `fishbowl-common` package, and
    the source of every themed window this app opens: `ThemedSubwindow` (a `tk.Toplevel`
    base that snapshots the active theme/font and centers over its parent), `MessageWindow`
    (the themed OK-button popup `show_popup()` builds), `AboutWindow`, `FileEditorWindow`,
    `UpdateWindow` and `Tooltip`, plus the styling data (`Theme`, `RED`, `ALL_THEMES`,
    `THEME_BY_NAME`, `FONT_FAMILIES`, `FONT_SIZES`, …). All of it is re-exported from that
    one name, so `InventoryAppDisplay` imports from `fishbowl_common.gui` rather than the
    individual modules. These lived in `source/gui/` until they were consolidated upstream;
    **do not re-add a local copy** — fix or extend them in `fishbowl-common` and bump the
    pin. Their unit tests live upstream in `fishbowl-common/tests/gui/` and deliberately
    have **no counterpart here**; this repo tests only its own display and the wiring
    around the shared classes.
    - It is a **separate import** from the top-level `fishbowl_common`, which stays
      tkinter-free so a headless run never loads tkinter. That split is what the `[gui]`
      extra in the `requirements/release.txt` pin marks.
    - `AboutWindow` takes both the name and the version it displays by injection, which is
      why `APP_NAME` lives in `source/constants.py` alongside `VERSION`.
    - `FileEditorWindow`'s `editable` flag toggles a Save button; this app only ever opens
      it with `editable=False`, since there are no editable config files here.
    - `PatchNotesWindow` shows what changed in the version now running: a heading naming
      the app and version, the notes in a read-only `ScrolledText`, and a Close button. It
      takes the notes as a **string**, not a path — they are frequently several releases'
      sections concatenated — which is why it is not a `FileEditorWindow(editable=False)`.
      The display's whole share of it is passing the current theme/font, exactly as
      `handle_about()` does.
    - `UpdateWindow` announces a newer release: its "Exit and Update" button
      `webbrowser.open()`s the release page, then closes the **whole application** after
      `CLOSE_DELAY_MS` (3s) via the injected `close_app_callback` — the display's
      `handle_exit`. The app must exit because Windows file-locks the running executable, so
      an installer that finds it open hangs trying to close it. When
      `start_install_callback` is supplied it additionally offers "Update and Restart" with a
      progress bar, driving the download itself and exiting through the same
      `close_app_callback` once the installer has started.
    - Unlike the sibling's display, this one puts **no `integration_test_mode` guard** on
      `show_update_available()` — it holds no argument provider and is never constructed
      headless, the same reason `show_popup()` has no guard either.
    - `Tooltip` binds `<Enter>`/`<Leave>`/`<ButtonPress>` on its target widget and shows a
      borderless `Toplevel` after `SHOW_DELAY_MS` (500ms), so a pointer merely crossing a
      widget never flashes a tip. **Those bindings use `add="+"`, which is load-bearing
      here in a way it is not in the sibling:** the column checkbuttons already carry their
      own `command`, and a binding without `add="+"` would replace it, silently breaking the
      checkbox that persists a column's state. Anyone changing `Tooltip` upstream must keep
      that flag.

      The display attaches its tooltips through **`_attach_tooltip(widget, text)`**, which
      tracks each one in `self.tooltips` — initialized in `__init__` **before** `build_widgets()`,
      since the grid builder attaches as it goes. Two groups get tooltips: the three action
      buttons, attached at the end of `build_widgets()` as the sibling does, and **every
      column checkbutton**, attached in `_build_checkbox_grid()` from that column's own
      `Column.tooltip`. The checkbox group has no sibling analog and is the reason the
      feature is worth more here than there — the checkbox labels are Fishbowl report jargon
      (`Not Available`, `Avg TO Days`, `TO Rate`). A column marked `always` has no
      checkbutton, so its tooltip text is never shown; it carries one anyway so the
      every-column-has-hover-text invariant survives an `always` flag being dropped later.
- **`columns.py`** (`source/columns.py`) — the single source of truth for the (column key,
  GUI label, section, hover text) record: a frozen `Column` dataclass plus `INVENTORY_COLUMNS`,
  `TURNOVER_COLUMNS`, `ALL_COLUMNS`, `COLUMN_KEYS` and `all_columns_selected()`. The tuple
  a `Column` lives in *is* its GUI section. It imports only `dataclasses`, which is what
  lets the headless path reach `all_columns_selected()` without loading tkinter.
- **`PdfTableParser`** (`source/PdfTableParser.py`) — turns one page of layout-extracted
  text into positional field lists, with no knowledge of the filesystem, `pypdf`, the
  entry classes, or the GUI. `parse_inventory_page(page, rows)` and
  `parse_turnover_page(page, rows)` each take the rows parsed so far and return them
  extended, so a row wrapped across a page boundary can be folded back into the row it
  continues. `align_to_columns()` assigns each numeric value to the column whose header
  right edge it lines up with, so a column the report leaves blank stays blank instead of
  shifting every later value one column left. `to_number()` then converts each numeric
  cell into the number it holds — dropping the thousands separators, `int` for a cell with
  no decimal point and `float` for one with, `None` for a blank — so the rows the entry
  classes are built from carry numbers rather than digit-strings, and the spreadsheet gets
  numeric cells Excel will sort and sum. A cell that is not a number (the numeric pattern
  also matches a stray `-`) is handed back unconverted rather than failing the report.
- **`InventoryAppFileIO`** (`source/InventoryAppFileIO.py`) — home of all file I/O. Reads
  inventory and turnover PDFs via `pypdf` (`read_pdf()`), returning one string of page
  text per page; `read_text_file()` reads a plain text file's full contents (used by the
  display's View menu to populate its read-only file viewer), lists the inventory
  availability PDFs (`list_inventory_files()`, used by headless mode) and the turnover
  report PDFs (`list_turnover_files()`) as full `Path`s ready to read, and owns the
  output spreadsheet lifecycle — opening (`create_workbook()`, which places the workbook
  under `OUTPUT_DIR`) and saving (`save_workbook()`) the `xlsxwriter` workbook. It also owns the results log at
  `logs/results.txt` — `reset_results_file()` **deletes** it on startup (rather than
  truncating it to empty) so a fresh app launch has no results file at all until
  something is actually processed, and `write_to_results_file()` (opening in append mode,
  which recreates the file) writes each line; the inventory/turnover processing output
  that the app once printed to the terminal via `logging` now flows through the latter
  (the `logging` dependency has been removed). The delete-not-truncate distinction is
  load-bearing: `InventoryAppDisplay.handle_results_log()` uses the file's *existence* to
  decide whether to open the viewer or show a "File Not Found" popup, and an empty-but-present
  file would open a blank viewer instead. Errors are **not** written there — they go
  only to the GUI output line via `report_error`. Directory and file paths come from
  `source/constants.py`. Every method wraps its I/O in `try/except`, returns a safe empty
  value (`[]`/`None`/`False`) on failure, and surfaces the error through an injected
  `report_error(title, message)` callback (a no-op by default until the controller wires
  it to the GUI), so missing/unreadable files never crash the app. The two results-file
  helpers swallow their own write failures silently. The in-memory cell writing still
  lives in `spreadsheetDriver.py`, which receives the already-open workbook.
- **`constants.py`** (`source/constants.py`) — `VERSION`, the current application version
  surfaced via Help -> About and compared against the latest release by the update check;
  `GITHUB_REPO`, the `"owner/name"` string naming the repo whose releases that check reads;
  `INSTALLER_ASSET_PATTERN`, the name of this app's installer asset on a release, injected
  into the coordinator so an update can be installed in place (keep it in step with
  `installer.iss`'s `OutputBaseFilename`);
  plus relative `Path` constants for the input directories
  (`INVENTORY_DIR`, `TURNOVER_DIR`), the generated spreadsheets (`OUTPUT_DIR`, the
  application root — shared by `create_workbook()` and the display's View -> Spreadsheets
  browser so the two cannot point at different folders), the diagnostics log (`LOGS_DIR`,
  `RESULTS_FILE`), the settings database (`DATA_DIR`, `SETTINGS_DB_PATH`) and the packaged
  patch notes (`PATCH_NOTES_PATH`),
  resolved against the executable's CWD (mirrors the sibling invoice tool's `constants.py`).
  It also holds the keys user settings are persisted under — `SETTING_KEY_THEME`,
  `SETTING_KEY_FONT_FAMILY`, `SETTING_KEY_FONT_SIZE`, `SETTING_KEY_GEOMETRY`,
  `SETTING_KEY_LAST_SEEN_VERSION` and the
  `SETTING_KEY_COLUMN_PREFIX` each column's key is appended to — shared between the display
  that reads/writes them and any other consumer so the two never drift apart.
- **`InventoryEntry`** (`source/InventoryEntry.py`) — `@dataclass` holding one inventory
  row (`part`, `description`, `uom`, `on_hand`, `allocated`, `available`, etc.). Every
  field is annotated and defaulted, so it both default-constructs and takes a parsed row
  positionally — the processor builds one with `InventoryEntry(*row)`, which is why the
  field order must match the parser's column order. The fields *are* the parsed row and
  nothing else: it holds no spreadsheet state, so where a row lands on the sheet cannot
  disagree with where the writer put it. Beyond the generated constructor its only method
  is `to_formatted_string()`, a formatted-string dump the processor writes to the results
  file.
- **`TurnoverEntry`** (`source/TurnoverEntry.py`) — the same shape for one turnover
  "Totals:" row (`part_description`, `units_sold`, `avg_qoh`, `avg_to_days`, `to_rate`).
  The three averages default to `None` because the report leaves them blank where a part's
  turnover is undefined.
- Both entry classes mirror `Invoice` in the sibling `FishbowlInvoiceTool`: a bare
  `@dataclass` (never `frozen` or `slots`, for parity with the sibling rather than
  because anything mutates them — nothing does), the field block wrapped in `# fmt:off` /
  `# fmt:on` with a trailing comment per field, and exactly two things in the class body.
  There is deliberately no `__post_init__` and no `populate*` method: converting the
  report's text into fields is `PdfTableParser`'s job.
- **`spreadsheetDriver.py`** (`source/spreadsheetDriver.py`) — all `xlsxwriter` output.
  Module-level functions (not a class) build the workbook: `setupMainSpreadsheet` writes
  the inventory header + rows; `setupSpreadsheetTurnoverHeader` /
  `appendTurnoverToSpreadsheet` add a turnover report's columns and match each
  `TurnoverEntry` to its `InventoryEntry` by part name, writing to the row that entry's
  position gives it. `setupSpreadsheetTurnoverHeader` **returns the first free column
  after the ones it filled**, and the caller assigns that value rather than advancing by a
  fixed amount — see the stride convention below. Helpers (`writeInventoryEntryToSpreadsheet`,
  `writeTurnoverEntryToSpreadsheet`, `formatTurnoverRow`) handle per-cell styling.

### Key conventions

- The dynamic-column scheme is checkbox-driven: every header/row writer walks the same
  `checkboxDict` keys in the same order, writing a column and incrementing the column
  index only when that box is checked. Inventory keys are plain (`"Part"`, `"OnHand"`);
  turnover keys are `t`-prefixed (`"tUnits Sold"`, `"tTO Rate"`). Keep the header writer
  and the row writer in lockstep — both must consult identical keys in identical order
  or columns and data will desync. **Those keys and their GUI labels live in
  `source/columns.py`**, and `InventoryAppDisplay` builds its checkbox grid by iterating
  the same tuples the writers walk, so the GUI cannot offer a column the spreadsheet does
  not know about or miss one it does. Add a column there, not in three places.
- **A turnover report is as many columns wide as the user checked, so the caller must
  never guess its stride.** `setupSpreadsheetTurnoverHeader` returns the first free
  column and `process_inventory()` assigns it (`nextCol = endCol`), exactly as
  `setupMainSpreadsheet` reports back where the inventory columns ended. It used to
  advance by `+= 1`, which silently overwrote all but the first column of every turnover
  report but the last — a data-loss bug invisible to CI, since the results file is built
  from the entry objects and never from the sheet. Whatever replaces these writers must
  keep reporting its true end column.
- **`get_selected_columns()` wraps every value in `bool()`, and that is load-bearing.**
  The spreadsheet writers test `if checkboxDict["Part"] == True`, which a `tk.BooleanVar`
  fails — the column would be silently dropped from the report rather than raising.
- **The settings table stores only text, so a persisted boolean is compared, never
  `bool()`-ed.** `SettingsRepository.get_all_settings()` hands back raw strings and
  `bool("False")` is `True`, so converting a stored column flag would silently check every
  box. `_restore_column()` compares against `str(True)` instead. The same applies in
  reverse: the font size is `str()`-ed on the way out and `int()`-ed on the way back.
- **An absent column setting means "never persisted", not "unchecked".** `_restore_column()`
  falls back to the column's own `always` default when the key is missing, so a column newly
  added to `source/columns.py` behaves like a first launch rather than arriving pre-unchecked.
  A column marked `always` is forced checked regardless of what is stored, since it has no
  checkbox the user could have unchecked it with.
- Turnover rows are matched to inventory rows by `part` vs. `partDescription` with all
  spaces removed; the matched entry's **position in the inventory list** is its row on the
  sheet. `setupMainSpreadsheet` writes one row per entry starting at `FIRST_DATA_ROW`
  regardless of which columns are checked, so `appendTurnoverToSpreadsheet` derives the
  row with `enumerate(inventory, start=FIRST_DATA_ROW)` rather than reading it back off
  the entry. **`FIRST_DATA_ROW` is the single definition of where data begins** — the
  inventory writer, the turnover pre-fill and the turnover join all measure from it, and
  row 0 is the header. The entry used to carry a `row_written_to` field instead, assigned
  from inside each checked column's branch; with no inventory column checked nothing
  assigned it and every turnover row overwrote the header (#55). Deriving the row removes
  the failure mode rather than guarding it, so do not reintroduce a stored row.
- **`extraction_mode="layout"` is mandatory in `read_pdf()`.** `pypdf`'s default mode
  discards the horizontal spacing the whole parser rests on, running adjacent columns
  together (`UOMOn`, `LABEL180 MINUTE DOOR LABEL`). Column offsets also drift by a
  character or two from page to page, so `PdfTableParser` re-derives them from each
  page's own header line rather than hardcoding them — and it slices `Part` off at the
  `Description` offset rather than splitting on the gap, since a part number can itself
  contain a run of spaces (`3/4"  BLANK HINGE`).
- `PdfTableParser.CONTINUATION_SEPARATOR` is the single knob for how the fragments of a
  part or description wrapped across several lines are rejoined. It is a space, matching
  how the report reads; set it to `""` to concatenate with nothing between.
- **`align_to_columns()` returns strings; `to_number()` runs after it, never inside it.**
  `parse_turnover_page` uses `if not any(values)` to spot a "Totals:" line whose part name
  wrapped onto the line above, and that check depends on blanks being `""` while real
  values are truthy *strings*. Convert any earlier and a legitimate all-zeros row becomes
  `[0, 0, 0, 0]`, which is falsy, so the parser would scrape values off the wrong line.
- **The entry classes' field names and their results-file labels are decoupled on
  purpose.** Fields are snake_case (`on_hand`, `part_description`), but
  `to_formatted_string()` prints the labels the report and the canonical results file use
  (`onHand:`, `partDescription:`). Renaming a field must not change its label, or the
  integration diff churns for no reason.
- **The results file is a CI fixture, not a log.** It is diffed against
  `canonical_correct_results.txt`, so its *content* must not vary by platform: log bare
  filenames rather than paths, and use explicitly-keyed sorts in
  `list_inventory_files`/`list_turnover_files` rather than relying on `Path` ordering
  (which is case-insensitive on Windows, case-sensitive on POSIX). Errors and user-facing
  status go to `report_error`/`report_status`, never here — they would make the diff depend
  on the environment. Line endings are the one thing that may differ: the file is written
  in text mode, so it is CRLF on Windows and LF on Linux, and git's `core.autocrlf`
  translation of the canonical file cancels this out on both. Do not "fix" that asymmetry
  in one place without the other.
- **`start_application()` imports `InventoryAppDisplay` inside the function, after the
  `integration_test_mode` early return, and it must stay that way.** This is not the
  stopgap the old PySimpleGUI import was: the integration-test job runs on `ubuntu-latest`
  with no display attached, so a headless run must never import tkinter or construct a
  window. That is also why the display is built here rather than in `__init__`, which is
  where the sibling builds its own — the sibling's integration job runs on Windows and can
  afford it. Do not "clean this up" into a module-scope import.
  `tests/InventoryAppController_tests.py` guards this with
  `mock_display_cls.assert_not_called()`.
- **GUI styling conventions, ported from the sibling.** Pure `tk`, zero `ttk`; a
  `###`-bordered banner above every method; a `# fmt:off` block of aligned
  `self.widget: tk.X | None = None` declarations in `__init__`, with `build_widgets()`
  called last; `pack` for the vertical page flow and `grid` inside frames. Buttons use one
  recipe — `bg=theme.button_bg, fg=theme.button_fg, activebackground=theme.accent,
  activeforeground=theme.fg_text, relief="flat", font=(family, size, "bold")` — with the
  Exit button set apart by `bg=theme.bg_entry, activebackground=RED`.
- **Checkbuttons need `selectcolor=theme.bg_entry` and `highlightthickness=0`.** This is
  the one styling recipe with no sibling precedent. Without them Tk paints the check box
  interior white and draws a light focus ring, both of which read as rendering artifacts
  against a dark `bg_main`. Their font is deliberately not bold: fifteen bold labels crowd
  the two grids.
- Keep comments concise: a comment should explain only what the immediately adjacent
  code does. Do not document the behavior of other objects, functions, or modules from
  within a comment — describe those where they are defined, not at the call site.

## Unit Testing

Unit tests live in `tests/` and run under `pytest`. Two reference implementations — mirror
them (and the sibling's `tests/` suite) rather than inventing new patterns:

- `tests/InventoryAppFileIO_tests.py` — a class with collaborators and I/O. Follow it for
  the mocking and error-path conventions below.
- `tests/PdfTableParser_tests.py` — a pure-logic class with no collaborators, so nothing
  is mocked and the fixture just constructs the object. Follow it for parser-style tests,
  including the synthetic-fixture rule below.
- `tests/InventoryEntry_tests.py` / `tests/TurnoverEntry_tests.py` — a dataclass, so there
  is no fixture at all: each test constructs the object it needs. Cover the defaults, a
  subset of keyword arguments, positional construction from a `PARSED_ROW` module constant
  shaped like the parser's output, and `to_formatted_string()` asserted against the
  report's labels rather than the field names.
- `tests/spreadsheetDriver_tests.py` — module-level functions writing through a mocked
  `xlsxwriter` workbook. Follow it for spreadsheet-writer tests: `workbook` and `worksheet`
  fixtures (`MagicMock(spec=xlsxwriter.Workbook)` / `spec=Worksheet)`, with
  `add_format.side_effect = lambda spec: dict(spec)` so each format is the spec dict it was
  built from and one format is distinguishable from another; `written_cells()` /
  `written_formats()` helpers reducing `worksheet.write.call_args_list` to
  `(row, col, value)` tuples and format dicts, so assertions read as column layout; a
  `checkboxes()` helper building the checkbox dict from a local `COLUMN_KEYS` tuple rather
  than importing the controller; and sibling functions in the same module patched at
  `source.spreadsheetDriver.<name>` so each test exercises one function. Real
  `InventoryEntry`/`TurnoverEntry` objects are used rather than mocks — they are inert data
  holders with no I/O — but each is given a distinct value per field so a column/data
  desync fails loudly instead of matching by coincidence.
- `tests/InventoryAppDisplay_tests.py` — a tkinter GUI class. The `display` fixture
  neutralizes `tk.Tk.__init__`, mocks the inherited Tk methods the display calls
  (title/geometry/resizable/configure/config/protocol/destroy/winfo_geometry), and
  replaces every widget class at its point of use
  (`patch("source.gui.InventoryAppDisplay.tk.Label", side_effect=_distinct_widget)`), so no
  real window is created and each widget attribute is a distinct assertable mock. It
  `yield`s a `SimpleNamespace` **from inside** the `with` block so the patches stay live for
  the whole test. Per-test constructor arguments come from indirect parametrization
  (`@pytest.mark.parametrize("display", [{"theme": FOREST}], indirect=True)`); persisted
  settings arrive the same way, as a `{"settings": {...}}` override.
  - **The inherited Tk methods are patched with one `patch.multiple(InventoryAppDisplay,
    title=DEFAULT, ...)`, not one `patch.object` each.** Python allows only twenty
    statically nested blocks, and a `with` item is one; eight separate `patch.object`
    calls would put this fixture within one item of the ceiling, where the next patch
    anyone adds raises `SyntaxError: too many statically nested blocks` at collection
    time. As written the block holds sixteen items, so there is room for four more —
    verify with a trial `compile()` before assuming a new patch fits. The mocks come back
    as a dict (`tk_methods["geometry"]`). Add new Tk-method patches inside that call.
    `PatchNotesWindow` brought the block to seventeen items, verified that way.
  - **`tk.StringVar` and `tk.BooleanVar` are patched with the `_FakeStringVar` /
    `_FakeBooleanVar` stubs, not bare `MagicMock`s.** A tkinter variable cannot be built
    without a default root window, so the real classes raise "Too early to create variable";
    and a `MagicMock` would defeat the assertions that `get_selected_columns()` returns real
    booleans, which is the property the spreadsheet writers depend on.
  - The menu bar's Preferences submenus are built from a `command=lambda x=option:
    self.apply_x(x)` per loop iteration (see the architecture section above); tests invoke
    each captured `command` directly (`made_call.kwargs["command"]()`) and assert the
    resulting state, which is what actually exercises the default-argument capture rather
    than just asserting the menu was built. The checkbutton `command`s are tested the same
    way, each resolved back to its column through the `variable` it was built with, so a
    late-binding regression fails rather than passing by coincidence.
  - **`Tooltip` is patched at `source.gui.InventoryAppDisplay.Tooltip`** with the same
    `_distinct_widget` side effect the widget classes use, so every attached tooltip is its
    own assertable mock, and exposed on the fixture namespace as `tooltip_cls`. The
    attachment tests read `call.kwargs["widget"]` / `["text"]`, so `_attach_tooltip()` must
    keep passing those by keyword. The per-column test resolves each checkbutton back
    through `column_checkbuttons[column.key]` before comparing text — a "every tooltip has
    some text" assertion would pass even with every tip attached to the wrong checkbox.
  - `save_settings_callback` is a bare `MagicMock()`; `SettingsRepository` is never imported
    here, since the display only ever reaches it through that callback. The three Preferences
    submenu tests invoke every `command` in a loop, so those tests absorb 4 + 10 + 14 writes
    into the same mock — assert with `assert_any_call` there, and reserve
    `assert_called_once_with` for the tests that exercise a single `apply_*` call.
- **There are no tests here for the shared GUI classes.** `ThemedSubwindow`,
  `MessageWindow`, `AboutWindow`, `FileEditorWindow`, `UpdateWindow` and `Tooltip` are
  covered upstream in `fishbowl-common/tests/gui/`; this repo tests only its own display
  and the wiring around them. Do not re-add a local test file for one — a gap in their
  coverage is a change to make in that repo.
- `tests/InventoryAppController_tests.py` — the wiring, with `ArgumentProvider`,
  `InventoryAppFileIO` and `InventoryProcessor` patched at
  `source.InventoryAppController.<name>` as usual. Because the processor is mocked there,
  the GUI and headless paths are asserted against `processor.process_inventory` directly
  rather than by patching a method onto the controller. **The display is the one exception
  to the patch-at-the-point-of-use rule:** `start_application()` imports it inside the
  function, so the name never exists at module scope and the target is its definition site,
  `patch("source.gui.InventoryAppDisplay.InventoryAppDisplay")`. A function-local
  `from X import Y` resolves `Y` as an attribute of module `X` at call time, which is why
  patching there works. Every test reaching `start_application()` must patch
  `source.InventoryAppController.UpdateCoordinator`, or a real daemon thread would call
  GitHub during the run; the threading and result-handling those tests used to cover
  directly are now `UpdateCoordinator`'s own tests upstream, and this repo asserts only that
  the coordinator is built with this app's `VERSION`/`GITHUB_REPO`/display and started.
  **`SettingsRepository` and `PatchNotes` are deliberately absent from the `controller`
  fixture** — both are built in `start_application()`, so only the tests reaching that method
  patch them (at `source.InventoryAppController.<name>`, the ordinary point of use). Every test
  that calls `start_application()` must patch both, or it opens a real SQLite database and
  leaves a `data/` directory in the working tree, breaking the "no new artifacts after a run"
  rule below. The patch-notes decision table is covered by calling
  `show_patch_notes_if_updated()` directly on a controller with its display, settings
  repository and reader replaced, one test per row.
- `tests/InventoryProcessor_tests.py` — a class whose collaborator is injected rather than
  constructed, so the file I/O controller is a `MagicMock(spec=InventoryAppFileIO)` handed to
  the constructor while the `PdfTableParser` the processor builds itself is patched at
  `source.InventoryProcessor.PdfTableParser`. The `spec=` is safe only because the processor
  never touches `report_error`, which is an instance attribute a spec'd mock would reject.
  The spreadsheet writers reach the module through `from source.spreadsheetDriver import *`,
  which makes `source.InventoryProcessor.setupMainSpreadsheet` (etc.) the point of use —
  never `source.spreadsheetDriver.<name>`. `process_inventory()` is tested with its own
  parsing helpers replaced via `patch.object` on the instance, so each test exercises one
  method.

### Test one object in isolation

Every unit test exercises exactly **one** class or function. Replace **all** collaborators
with mocks so a failure points unambiguously at the unit under test — never let a unit test
touch the real filesystem, a real PDF, or the GUI.

- **Construct the unit under test in a pytest fixture** (the `file_io` fixture) so each
  test starts from a clean, identically-configured object, with `report_error` injected as
  a bare `MagicMock()`. Every failure-path test ends with
  `file_io.report_error.assert_called_once()`; the title/message text is never asserted.
- **Patch module-level names at the point of use, not their definition site.**
  `InventoryAppFileIO` does `from source.constants import INVENTORY_DIR, RESULTS_FILE,
  TURNOVER_DIR`, so the patch targets are `source.InventoryAppFileIO.RESULTS_FILE` — never
  `source.constants.RESULTS_FILE`.
- **Patch `pypdf.PdfReader` and `xlsxwriter.Workbook`, never the whole module.** The
  methods under test catch `pypdf.errors.PdfReadError` and
  `xlsxwriter.exceptions.XlsxWriterException`; replacing the module object with a
  `MagicMock` makes those `except` clauses reference a non-exception and raise `TypeError`
  while handling the error.
- **Mock injected collaborators with `MagicMock(spec=Collaborator)`** so the mock only
  allows attributes the real class defines.
- **Name unasserted mock parameters with a leading underscore** (`_mock_file`) and reserve
  plain names (`mock_results_file`) for mocks you assert against.

### Follow the FIRST principles

- **Fast** — no real file, PDF, or GUI I/O; mock it. The whole run should stay under a
  second.
- **Independent** — no ordering dependencies or shared mutable state between tests.
- **Repeatable** — deterministic on every machine. Do not depend on the
  `automated-inventory-testing` submodule; that drives the *integration* test, not the
  unit tests. After a run, `git status` must show no new `logs/`, `data/`, `*.xlsx`, or
  `InventoryAvailability/` artifacts.
- **Self-validating** — each test asserts a clear pass/fail; never require reading
  `logs/results.txt` to judge the result.
- **Timely** — add or extend tests alongside any new branch or utility function, in the
  same change.

### Conventions

- Test files are named `<ClassName>_tests.py` (suffix, not the pytest-default `test_`
  prefix), which is why pytest is always invoked as `pytest tests/*` rather than relying on
  default discovery.
- Flat module-level `test_<method>_<behavior>` functions — no test classes. Error paths are
  suffixed `_reports_on_error` / `_reports_and_returns_<x>_on_error`.
- `tests/__init__.py`, `source/__init__.py` and `source/gui/__init__.py` are empty but
  **load-bearing**: with `tests/__init__.py` present, pytest's prepend import mode walks up
  past `tests/` and puts the repo root on `sys.path`, which is what makes
  `from source.InventoryAppFileIO import *` resolve. There is deliberately no `conftest.py`
  and no pytest config file.
- `.coveragerc` scopes measurement to `./source`, omitting `main.py`, `constants.py`,
  `tests/`, the virtualenv and the empty `__init__.py` files. Nothing else is omitted: the
  inert styling data that used to be excluded now lives upstream in `fishbowl_common.gui`.
- Group tests under the `###`-bordered banners used throughout the file, and give each test
  a docstring describing what it verifies with an `Args:` block documenting every
  mock/fixture parameter.
- **Sample page text is synthetic, never copied from the submodule.** The
  `automated-inventory-testing` reports are private company data, so a parser fixture
  reproduces the report's *geometry* — header offsets, column gaps, the wrapped `Avg. TO`
  label, the page footer — under invented part numbers and descriptions, at reduced column
  widths so the lines stay readable. Because those column positions are load-bearing, build
  a page by joining explicit line literals (`build_page()` in `PdfTableParser_tests.py`)
  rather than dedenting a triple-quoted block an editor could reflow.

## Git Workflow (when working on a GitHub issue)

When work is tied to a specific GitHub issue, start from an up-to-date base branch:

- Check out the base branch (usually `main` unless another is specified) and pull
  (`git checkout main && git pull`) before branching, so work branches off the current
  tip rather than a stale local copy.
- Name the branch with the issue number so GitHub links it (e.g.
  `3-inventory-app-controller`): `git checkout -b <issue-number>-<short-description>`.
