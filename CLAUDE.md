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
  pytest/pytest-cov and ruff). CI pins Python `3.11.9`, except the coverage job which floats on
  `3.11` (#66).

## Common Commands

- Run the app (GUI): `python main.py`
- Run the app headless (processes every PDF in `InventoryAvailability/` with all columns included
  and writes `logs/results.txt`, no GUI): `python main.py --integration-test`. `main.py` parses
  nothing itself — the flag is registered by the shared `ArgumentProvider`.
- Reproduce the integration check locally (after `./scripts/copy_resources.sh`):
  `python main.py --integration-test`, then **both** diffs —
  `diff logs/results.txt automated-inventory-testing/canonical_correct_results.txt` and
  `python scripts/dump_workbooks.py && diff logs/spreadsheet_dump.txt automated-inventory-testing/canonical_correct_spreadsheets.txt`
- Dump the generated workbooks on their own: `python scripts/dump_workbooks.py` (writes
  `logs/spreadsheet_dump.txt`; needs `openpyxl` from `requirements/dev.txt`)
- Run all unit tests: `pytest tests/`
- Run a single test file: `pytest tests/test_InventoryAppFileIO.py`
- Run a single test:
  `pytest tests/test_InventoryAppFileIO.py::test_read_pdf_extracts_each_page_in_layout_mode`
- Run with coverage: `pytest --cov=./ --cov-report=term-missing tests/` — the 90% gate is
  `fail_under` in `pyproject.toml`, so it applies locally too
- Lint: `ruff check .` (add `--fix` to apply the safe fixes, `--statistics` for a summary)
- Format: `ruff format .` (`--check` to verify without writing, as CI does)
- Byte-compile sanity check:
  `python -m py_compile main.py source/*.py source/gui/*.py tests/*.py scripts/*.py`
- Package a release: `./scripts/package_release.sh` (no arguments). Builds via PyInstaller into
  `release/FishbowlInventoryTool/` and zips it; on Windows with Inno Setup installed it also
  builds `release/FishbowlInventoryTool_Setup.exe`.

## CI

Five workflows in `.github/workflows/`: unit tests, code coverage, lint and integration tests on
`ubuntu-latest`, releases on `windows-latest`. Coverage is gated at **90%** by `fail_under` in
`pyproject.toml`, so the gate applies to a local `pytest --cov` exactly as it does in
`code-coverage.yml`. The lint job fails on any `ruff check` finding or any formatting
difference — the gate is the whole rule set, not a subset.

The integration check diffs **two** artifacts against canonical copies in the submodule, and any
change to parsing, layout or output formatting breaks it until the matching canonical file is
regenerated:

| Generated | Canonical | Covers |
| --- | --- | --- |
| `logs/results.txt` | `canonical_correct_results.txt` | The parser trace, built from the `InventoryEntry`/`TurnoverEntry` objects |
| `logs/spreadsheet_dump.txt` | `canonical_correct_spreadsheets.txt` | The generated `.xlsx` files themselves, dumped cell by cell |

The second exists because the first never touches the workbook, which is how three Priority-0
spreadsheet bugs shipped alongside a green diff and 100% line coverage (#53, #54, #55).
**Regenerating either canonical file is a commit in the private `automated-inventory-testing`
repo plus a submodule pointer bump here** — and capture it from a build you have reason to
trust, since a canonical file records whatever the app did, bug included. See
`.claude/rules/ci.md`.

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
| `source/columns.py` | The `(key, label, field, always, tooltip)` record for every selectable column, and `all_columns_selected()` |
| `source/spreadsheet_writer.py` | All `xlsxwriter` output: the `SpreadsheetWriter` class, built once around the open workbook |
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
- **`columns.py` is the single source of truth for the GUI *and* the spreadsheet.** Each
  `Column` carries the key the checkbox dict is read by, the label both the checkbox and the
  sheet header show, and the entry attribute the value is read from. Adding a column is one
  entry there plus the matching field on the entry dataclass — the writer needs no edit. See
  `.claude/rules/spreadsheet.md`.

## Key Conventions

- The dynamic-column scheme is checkbox-driven: `SpreadsheetWriter` filters a section's columns
  against `checkbox_dict` **once** and hands that same tuple to its header writer and its row
  writer, so the two cannot drift apart. **Keep it that way** — a writer that re-filters for
  itself is how a column and its data come to disagree.
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
  and `tests/` mirrors the module name. `N999` is ignored in `pyproject.toml` because of it;
  #92 renames them to `snake_case` and deletes that entry. Until it lands, follow the existing
  names rather than introducing a mixed convention. The exceptions are `columns.py`,
  `constants.py` and `spreadsheet_writer.py`, the last renamed by #57 because that module was
  rewritten wholesale — so #92 covers seven modules, not eight.
- **Every `def` under `source/` is fully annotated**, `-> None` included. `ANN` enforces that
  they are present, and is off for `tests/**`; the rest is on you. Container types are spelled
  out — `list[str]`, `dict[str, bool]`, `tuple[Column, ...]` — since a bare `list` tells a
  reader as little as no annotation at all. Use `X | None`, never `Optional[X]`. Where a union
  would be spelled out twice in one signature, name it once at module scope instead, as
  `PdfTableParser`'s `ParsedRow` does.
- **The annotation is the only place a type is written.** Under `source/`, an `Args:` entry is
  `name: description` and a `Returns:` block is the description alone, with no parenthesized or
  prefixed type repeating the signature. Under `tests/` the docstring type stays, since test
  parameters are deliberately unannotated — see `.claude/rules/tests.md`.
- **Import grouping and ordering are enforced, not remembered.** `ruff check --fix` applies them;
  `[tool.ruff.lint.isort]` in `pyproject.toml` is the statement of intent, including that
  `fishbowl_common` is third party — it installs from a pinned git tag — and never sits among the
  `source.*` imports.
- **Style is the linter's job.** Line length, quoting and spacing live in `[tool.ruff]`; run
  `ruff format` rather than matching the surrounding file by eye. Where a rule is suppressed, the
  reason sits beside it — in `pyproject.toml` for a policy, in a comment at the site for a
  one-off. A rationale comment must not begin with `# noqa`, or ruff reads it as a second
  directive and reports it unused via `RUF100`.
- **No banner comments above definitions.** `source/` and `tests/` carried a `###`-bordered
  banner above every method until they were removed for parity with the sibling, which had
  already dropped its own. A definition is introduced by its docstring; do not reintroduce a
  banner, section divider or repeated-name header above one.
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
| `rules/spreadsheet.md` | `spreadsheet_writer.py`, `columns.py` | `SpreadsheetWriter`, the column scheme, `FIRST_DATA_ROW`, the turnover stride and join |
| `rules/gui.md` | `source/gui/**` | The display, its menu bar, what comes from `fishbowl_common.gui`, theme/font reconfiguration, the styling recipes, the `after(0, …)` rule |
| `rules/shared-package.md` | `InventoryAppController.py`, `constants.py`, `requirements/**` | What each shared class takes by injection, construction order and headless gating, patch-notes logic, `constants.py`'s catalogue |
| `rules/tests.md` | `tests/**` | Per-file reference implementations, the `display` fixture, isolation rules, FIRST, conventions |
| `rules/ci.md` | `.github/workflows/**`, `requirements/**` | Workflow internals, the coverage gate, the two canonical fixtures and `dump_workbooks.py`, the two release gates, submodule handling |
| `rules/packaging.md` | `scripts/**` | `package_release.sh`, the load-bearing `installer.iss` details the in-app updater depends on, and which scripts are not packaging |
