# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

> **Keep the guidance current.** Whenever you change the architecture — add/remove/rename a class
> or module, move a responsibility between this repo and `fishbowl-common`, change a public
> signature, or alter the build/test/release workflow — update **this file or the matching
> `.claude/rules/` file** in the same change. Treat that as part of the definition of done for any
> structural change, not an afterthought.

## Project Overview

A Python/tkinter desktop app that parses Fishbowl-generated **Inventory Availability** and
**Turnover Report** PDFs and produces a formatted Excel (`.xlsx`) report. The user picks an
inventory availability PDF and checks which inventory and turnover columns to include; the app
parses that PDF plus every turnover report in `TurnoverReports/`, matches turnover rows to
inventory rows by part, and writes a single styled worksheet named after the date in the
inventory PDF's filename.

It is one of two Fishbowl desktop tools. The sibling is
[FishbowlInvoiceTool](https://github.com/averylhammond/FishbowlInvoiceTool); the shared
infrastructure and GUI package both depend on is
[fishbowl-common](https://github.com/averylhammond/fishbowl-common). This tool is being
incrementally brought up to the sibling's architecture and engineering standards — see that
repo's `CLAUDE.md` for the target end state — so expect ongoing refactors, and expect the
guidance here to name the open issue behind anything that has not caught up yet.

## Setup

- Submodule `automated-inventory-testing` provides sample inventory/turnover PDFs for development
  and integration testing: `git submodule update --init`
- **This submodule repo is private since it contains sensitive customer data. Never commit
  information obtained from it, and never echo its contents into a CI log.**
- `./scripts/copy_resources.sh` copies the submodule's `resources/` (`InventoryAvailability/`,
  `TurnoverReports/`) into the project root (required before running the app or the integration
  test locally).
- Virtual env: `python -m venv venv`, then `source venv/Scripts/activate` (Windows) or
  `source venv/bin/activate` (Linux/Mac).
- Install deps: `pip install -r requirements/dev.txt` (pulls in `release.txt` plus
  pytest/pytest-cov). CI pins Python `3.11.9`, except the coverage job which floats on `3.11`
  (#66).

## Common Commands

- Run the app (GUI): `python main.py`
- Run the app headless (processes every PDF in `InventoryAvailability/` with all columns included
  and writes `logs/results.txt`, no GUI): `python main.py --integration-test`. `main.py` parses
  nothing itself — the flag is registered by the shared `ArgumentProvider`.
- Reproduce the integration check locally (after `./scripts/copy_resources.sh`):
  `python main.py --integration-test` then
  `diff logs/results.txt automated-inventory-testing/canonical_correct_results.txt`
- Run all unit tests: `pytest tests/`
- Run a single test file: `pytest tests/test_InventoryAppFileIO.py`
- Run a single test:
  `pytest tests/test_InventoryAppFileIO.py::test_read_pdf_extracts_each_page_in_layout_mode`
- Run with coverage: `pytest --cov=./ --cov-report=term-missing tests/` — the 90% gate is
  `fail_under` in `pyproject.toml`, so it applies locally too
- Byte-compile sanity check:
  `python -m py_compile main.py source/*.py source/gui/*.py tests/*.py`
- Package a release: `./scripts/package_release.sh` (no arguments). Builds via PyInstaller into
  `release/FishbowlInventoryTool/` and zips it; on Windows with Inno Setup installed it also
  builds `release/FishbowlInventoryTool_Setup.exe`.

There is **no lint or format command yet** — ruff is not configured in this repo (#65). That is
parity work tracked against the sibling; `pyproject.toml` is already here to hold the config.

## CI

Four workflows in `.github/workflows/`: unit tests, code coverage and integration tests on
`ubuntu-latest`, releases on `windows-latest`. Coverage is gated at **90%** by `fail_under` in
`pyproject.toml`, so the gate applies to a local `pytest --cov` exactly as it does in
`code-coverage.yml`. The integration check diffs `logs/results.txt` against the submodule's
`canonical_correct_results.txt`, so any change to parsing or output formatting breaks it until
that canonical file is updated.

Pushing a `v*` tag runs the release workflow, which refuses the tag unless it matches
`constants.VERSION` **and** `PATCH_NOTES.md` has a matching `## <VERSION>` section. **Cutting a
release is: bump `VERSION`, add that version's `PATCH_NOTES.md` section, merge, then push a
matching `vX.Y.Z` tag.** Details in `.claude/rules/ci.md`.

## Architecture

`InventoryAppController` constructs and wires everything. Each module owns exactly one concern:

| Module | Owns |
| --- | --- |
| `main.py` | Thin entry point: constructs the controller and calls `start_application()`. No application logic, no argument parsing |
| `source/InventoryAppController.py` | Entry-point glue: builds the collaborators, gates the GUI half behind the headless check, owns `handle_process_inventory()` and `run_integration_test()`, and the patch-notes feature |
| `source/InventoryAppFileIO.py` | All file I/O: inventory/turnover PDFs via pypdf (one string per page), text files for the View menu, listing input files, the workbook lifecycle, and the `logs/` results file |
| `source/InventoryProcessor.py` | The processing pipeline: parse one inventory PDF, build the entries, drive the spreadsheet writers, append every turnover report |
| `source/PdfTableParser.py` | Parsing only: layout-extracted page text → positional field lists (`align_to_columns`, `to_number`) |
| `source/InventoryEntry.py` / `source/TurnoverEntry.py` | Plain data holders for one parsed row, plus `to_formatted_string()` |
| `source/columns.py` | The `(key, label, always, tooltip)` record for every selectable column, and `all_columns_selected()` |
| `source/spreadsheetDriver.py` | All `xlsxwriter` output: module-level header, row and format writers |
| `source/constants.py` | Paths, `APP_NAME`/`VERSION`/`GITHUB_REPO`/`INSTALLER_ASSET_PATTERN`, setting keys |
| `source/gui/InventoryAppDisplay.py` | The `tk.Tk` root: main window, the two checkbox grids and the File/View/Preferences/Help menu bar |

**Everything else is `fishbowl-common`, taken as a pinned git tag.** From the headless half:
`ArgumentProvider`, `SettingsRepository`, `UpdateCoordinator`, `PatchNotes`, `compare_versions()`.
From `fishbowl_common.gui`: `ThemedSubwindow`, `MessageWindow`, `AboutWindow`, `FileEditorWindow`,
`PatchNotesWindow`, `UpdateWindow`, `Tooltip`, and the theme/font data. Those two imports are
deliberately separate — the top-level package stays tkinter-free so a headless run never loads
tkinter, which is what the `[gui]` extra in the pin marks.

The shared classes are application-agnostic and take every app-specific value by constructor
injection. **They lived in `source/gui/` until they were consolidated upstream; do not re-add a
local copy** — fix or extend them in `fishbowl-common` and bump the pin. Their tests live upstream
too, and deliberately have no counterpart here.

Three responsibilities worth knowing before touching them:

- **`UpdateCoordinator` owns the whole update feature** — the background check, the download,
  digest verification, and the silent in-place install. The display's entire share of it is
  forwarding a callback; it never downloads or executes anything.
- **The GUI collaborators are built inside `start_application()`, not `__init__`** — the display,
  the settings repository, the update coordinator and the patch-notes reader. That is the one
  deliberate divergence from the sibling, which builds its own in `__init__`: the integration
  test must import no tkinter, perform no database I/O, leave no `data/` directory behind and
  make no network call, and this placement gets all four structurally. **Do not "fix" it.**
- **`columns.py` is the single source of truth for the GUI, not for the spreadsheet.**
  `spreadsheetDriver.py` hardcodes all 16 keys and its own header text, so adding a column there
  too is part of adding a column. #57 is what makes it one source; see
  `.claude/rules/spreadsheet.md`.

## Key Conventions

- The dynamic-column scheme is checkbox-driven: every header and row writer walks the same
  `checkboxDict` keys in the same order, writing a column and advancing the column index only
  when that box is checked. **Keep the header writer and the row writer in lockstep.**
- `__debug__`-gated code is stripped from the release build, which compiles with **`python -OO`**
  per `scripts/package_release.sh`.
- Prefer extending behavior through a `columns.py` entry, or new theme/font data upstream, over
  adding `if/elif` branches to existing parsing and display methods.
- Pass a class only the narrow dependencies it needs — `InventoryProcessor` takes the
  `InventoryAppFileIO` controller and builds its own parser; the display takes callbacks, never
  the controller. Avoid god objects in constructors.
- New logic goes in the class that owns that concern, not bolted onto `InventoryAppController`. If
  a method is doing two distinct jobs (parsing *and* formatting), split it.
- **Modules are `PascalCase` today** (`source/InventoryAppFileIO.py`), matching the class inside,
  and `tests/` mirrors the module name. #92 renames them to `snake_case` and enables ruff's
  `N999`; until it lands, follow the existing names rather than introducing a mixed convention.
- **Every `def` under `source/` is fully annotated**, `-> None` included, and container types are
  spelled out — `list[str]`, `dict[str, bool]`, `tuple[Column, ...]` — since a bare `list` tells a
  reader as little as no annotation at all. Use `X | None`, never `Optional[X]`. Where a union
  would be spelled out twice in one signature, name it once at module scope instead, as
  `PdfTableParser`'s `ParsedRow` does.
- **The annotation is the only place a type is written.** Under `source/`, an `Args:` entry is
  `name: description` and a `Returns:` block is the description alone, with no parenthesized or
  prefixed type repeating the signature. Under `tests/` the docstring type stays, since test
  parameters are deliberately unannotated — see `.claude/rules/tests.md`.
- **Imports are grouped standard library, third party, first party**, one blank line between
  groups and each group sorted case-insensitively. `fishbowl_common` is third party — it installs
  from a pinned git tag — so it never sits among the `source.*` imports. This is what ruff's isort
  defaults produce, so adopting the linter (#65) will reorder nothing.
- A `###`-bordered banner sits above every method, in `source/` and `tests/` alike. The sibling
  has since dropped its banners; this repo has not, so match what the file already does.
- Keep comments concise: a comment should explain only what the immediately adjacent code does.
  Do not document the behavior of other objects, functions or modules from within a comment —
  describe those where they are defined, not at the call site.

## Git Workflow (when working on a GitHub issue)

When the work is tied to a specific GitHub issue, always do the following before making changes:

- **Start from an up-to-date base branch.** Check out the base branch (usually `main` unless
  another is given) and pull (`git checkout main && git pull`) before creating the new branch, so
  work branches off the current tip rather than a stale local copy.
- **Name the branch so it links to the issue in GitHub.** Include the issue number (e.g.
  `72-claude-md-overhaul`), then branch off the freshly pulled base
  (`git checkout -b <issue-number>-<short-description>`).
- Merge through a PR, with a subject line ending `(closes #N)`.
- **A change to a public signature in `fishbowl-common` is not one PR but three**: the package
  first, then this repo's pin, then `FishbowlInvoiceTool`.

## Where the rest of the guidance lives

Detail that only matters for part of the codebase lives in `.claude/rules/`, loaded when a
matching file is opened. Put new detail in the matching rule file rather than growing this one.

| File | Loads when you touch | Carries |
| --- | --- | --- |
| `rules/inventory-processing.md` | `InventoryProcessor.py`, `PdfTableParser.py`, `InventoryAppFileIO.py`, the two entry classes | The parse pipeline, layout mode, the error-reporting contract, the results file as a CI fixture |
| `rules/spreadsheet.md` | `spreadsheetDriver.py`, `columns.py` | The writers, the column scheme, `FIRST_DATA_ROW`, the turnover stride and join |
| `rules/gui.md` | `source/gui/**` | The display, its menu bar, what comes from `fishbowl_common.gui`, theme/font reconfiguration, the styling recipes, the `after(0, …)` rule |
| `rules/shared-package.md` | `InventoryAppController.py`, `constants.py`, `requirements/**` | What each shared class takes by injection, construction order and headless gating, patch-notes logic, `constants.py`'s catalogue |
| `rules/tests.md` | `tests/**` | Per-file reference implementations, the `display` fixture, isolation rules, FIRST, conventions |
| `rules/ci.md` | `.github/workflows/**` | Workflow internals, the coverage gate, the two release gates, submodule handling |
| `rules/packaging.md` | `scripts/**` | `package_release.sh`, and the load-bearing `installer.iss` details the in-app updater depends on |
