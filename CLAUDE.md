# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Keep this file current.** Whenever you change the application's architecture —
> add/remove/rename a class or module, move a responsibility between components, change
> how components are wired together, or alter the build/test/run workflow — update the
> relevant section of this file in the same change. Treat `CLAUDE.md` as part of the
> definition of done for any structural change, not an afterthought.

## Project Overview

A Python desktop app (PySimpleGUI) that parses Fishbowl-generated **Inventory
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
- **Java (JRE 8+) is required** — `tabula-py` shells out to a bundled Java jar to read
  PDF tables. The app/parsing will fail without a JRE on `PATH`.
- Virtual env: `python -m venv venv`, then `source venv/Scripts/activate` (Windows) or
  `source venv/bin/activate` (Linux/Mac).
- Install deps: `pip install -r requirements/release.txt`.

## Common Commands

- Run the app (GUI): `python main.py`
- Byte-compile sanity check: `python -m py_compile main.py source/*.py`

There is currently **no test suite, dev requirements file, or CI** in this repo (unlike
`FishbowlInvoiceTool`). When test infrastructure is added, document the commands here.

## Architecture

The application flow is: **entry point → controller → entry data classes + spreadsheet
writer**.

- **`main.py`** — thin entry point. Constructs an `InventoryAppController` and calls
  `start_application()`. Contains no application logic.
- **`InventoryAppController`** (`source/InventoryAppController.py`) — the orchestrator
  and current home of all application logic. Responsibilities:
  - `__init__` configures logging and resolves the `InventoryAvailability/` and
    `TurnoverReports/` directories (relative to the executable's CWD).
  - `start_application()` builds the PySimpleGUI window (file picker + inventory/turnover
    column checkboxes + Process button) and runs the event loop. On "Process This
    Inventory" it parses the chosen inventory PDF, derives the output filename from the
    PDF name via regex, builds the workbook, then loops over every PDF in
    `TurnoverReports/` appending turnover columns.
  - PDF parsing helpers: `process_inventory_file` / `process_inventory_page` and
    `process_turnover_file` / `process_turnover_page` read PDFs with `tabula.read_pdf`
    and convert table rows into `InventoryEntry` / `TurnoverEntry` objects.
  - `build_checkbox_dict()` snapshots the GUI checkbox state into a dict consumed by the
    spreadsheet writer to decide which columns to emit.
- **`InventoryEntry`** (`source/InventoryEntry.py`) — plain data holder for one
  inventory row (part, description, uom, onHand, allocated, available, etc.).
  `populateInventoryEntry(list)` maps a split PDF row onto its fields (stripping
  whitespace/commas); `dumpInventoryEntry()` is a `__debug__` logging helper. Tracks
  `rowWrittenTo` so turnover data can be matched back to the same spreadsheet row.
- **`TurnoverEntry`** (`source/TurnoverEntry.py`) — plain data holder for one turnover
  "Totals:" row (partDescription, unitsSold, avgQOH, avgTODays, TORate), with a parallel
  `populateTurnoverEntry()` / `dumpTurnoverEntry()`.
- **`spreadsheetDriver.py`** (`source/spreadsheetDriver.py`) — all `xlsxwriter` output.
  Module-level functions (not a class) build the workbook: `setupMainSpreadsheet` writes
  the inventory header + rows; `setupSpreadsheetTurnoverHeader` /
  `appendTurnoverToSpreadsheet` add a turnover report's columns and match each
  `TurnoverEntry` to its `InventoryEntry` by part name, writing to that entry's
  `rowWrittenTo`. Helpers (`writeInventoryEntryToSpreadsheet`,
  `writeTurnoverEntryToSpreadsheet`, `formatTurnoverRow`) handle per-cell styling.

### Key conventions

- The dynamic-column scheme is checkbox-driven: every header/row writer walks the same
  `checkboxDict` keys in the same order, writing a column and incrementing the column
  index only when that box is checked. Inventory keys are plain (`"Part"`, `"OnHand"`);
  turnover keys are `t`-prefixed (`"tUnits Sold"`, `"tTO Rate"`). Keep the header writer
  and the row writer in lockstep — both must consult identical keys in identical order
  or columns and data will desync.
- Turnover rows are matched to inventory rows by `part` vs. `partDescription` with all
  spaces removed; `InventoryEntry.rowWrittenTo` is the join key into the spreadsheet.
- `__debug__`-gated code (debug logging / entry dumps) is intended to be stripped in a
  PyInstaller release build (`python -O`), matching the sibling invoice tool's approach.
- The commented-out `win32gui`/`win32con` block in `InventoryAppController` hides the
  Windows console for the packaged executable — uncomment only when building with
  PyInstaller.

## Git Workflow (when working on a GitHub issue)

When work is tied to a specific GitHub issue, start from an up-to-date base branch:

- Check out the base branch (usually `main` unless another is specified) and pull
  (`git checkout main && git pull`) before branching, so work branches off the current
  tip rather than a stale local copy.
- Name the branch with the issue number so GitHub links it (e.g.
  `3-inventory-app-controller`): `git checkout -b <issue-number>-<short-description>`.
