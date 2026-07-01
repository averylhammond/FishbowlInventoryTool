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
`FishbowlInvoiceTool`). When test infrastructure is added, document the commands here. A
planned follow-up is to stand up `pytest` and add `tests/InventoryAppFileIO_tests.py`
mirroring the sibling's `tests/InvoiceAppFileIO_tests.py` mocking conventions.

## Architecture

The application flow is: **entry point → controller → file I/O + entry data classes +
spreadsheet writer**.

- **`main.py`** — thin entry point. Constructs an `InventoryAppController` and calls
  `start_application()`. Contains no application logic.
- **`InventoryAppController`** (`source/InventoryAppController.py`) — the orchestrator.
  It owns the GUI and parsing flow and delegates all file I/O to `InventoryAppFileIO`.
  Responsibilities:
  - `__init__` constructs the `InventoryAppFileIO` collaborator and clears the results
    file (`reset_results_file()`) so each run starts with a fresh diagnostics log.
  - `start_application()` builds the PySimpleGUI window (file picker + inventory/turnover
    column checkboxes + Process button), wires the file I/O controller's `report_error`
    callback to the GUI output line, and runs the event loop. On "Process This
    Inventory" it parses the chosen inventory PDF (bailing gracefully if it can't be
    read), derives the output filename from the PDF name via regex (falling back to a
    generic name when the regex doesn't match), creates the workbook via the file I/O
    controller, then loops over every turnover PDF appending turnover columns and saves.
  - PDF parsing helpers: `process_inventory_file` / `process_inventory_page` and
    `process_turnover_file` / `process_turnover_page` source raw pages from
    `InventoryAppFileIO.read_pdf()` and convert table rows into `InventoryEntry` /
    `TurnoverEntry` objects.
  - `build_checkbox_dict()` snapshots the GUI checkbox state into a dict consumed by the
    spreadsheet writer to decide which columns to emit.
- **`InventoryAppFileIO`** (`source/InventoryAppFileIO.py`) — home of all file I/O. Reads
  inventory and turnover PDFs via `tabula.read_pdf` (`read_pdf()`), lists the turnover
  report PDFs as full `Path`s ready to read (`list_turnover_files()`), and owns the
  output spreadsheet lifecycle — opening (`create_workbook()`) and saving
  (`save_workbook()`) the `xlsxwriter` workbook. It also owns the results log at
  `logs/results.txt` — `reset_results_file()` clears it on startup and
  `write_to_results_file()` appends a line; the inventory/turnover processing output
  that the app once printed to the terminal via `logging` now flows through the latter
  (the `logging` dependency has been removed). Errors are **not** written there — they go
  only to the GUI output line via `report_error`. Directory and file paths come from
  `source/constants.py`. Every method wraps its I/O in `try/except`, returns a safe empty
  value (`[]`/`None`/`False`) on failure, and surfaces the error through an injected
  `report_error(title, message)` callback (a no-op by default until the controller wires
  it to the GUI), so missing/unreadable files never crash the app. The two results-file
  helpers swallow their own write failures silently. The in-memory cell writing still
  lives in `spreadsheetDriver.py`, which receives the already-open workbook.
- **`constants.py`** (`source/constants.py`) — relative `Path` constants for the input
  directories (`INVENTORY_DIR`, `TURNOVER_DIR`) and the diagnostics log (`LOGS_DIR`,
  `RESULTS_FILE`), resolved against the executable's CWD (mirrors the sibling invoice
  tool's `constants.py`).
- **`InventoryEntry`** (`source/InventoryEntry.py`) — plain data holder for one
  inventory row (part, description, uom, onHand, allocated, available, etc.).
  `populateInventoryEntry(list)` maps a split PDF row onto its fields (stripping
  whitespace/commas); `to_formatted_string()` returns a formatted-string dump that the
  controller writes to the results file. Tracks `rowWrittenTo` so turnover data can be
  matched back to the same spreadsheet row.
- **`TurnoverEntry`** (`source/TurnoverEntry.py`) — plain data holder for one turnover
  "Totals:" row (partDescription, unitsSold, avgQOH, avgTODays, TORate), with a parallel
  `populateTurnoverEntry()` / `to_formatted_string()` (the latter returns a formatted
  string dump).
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
- The commented-out `win32gui`/`win32con` block in `InventoryAppController` hides the
  Windows console for the packaged executable — uncomment only when building with
  PyInstaller.
- Keep comments concise: a comment should explain only what the immediately adjacent
  code does. Do not document the behavior of other objects, functions, or modules from
  within a comment — describe those where they are defined, not at the call site.

## Git Workflow (when working on a GitHub issue)

When work is tied to a specific GitHub issue, start from an up-to-date base branch:

- Check out the base branch (usually `main` unless another is specified) and pull
  (`git checkout main && git pull`) before branching, so work branches off the current
  tip rather than a stale local copy.
- Name the branch with the issue number so GitHub links it (e.g.
  `3-inventory-app-controller`): `git checkout -b <issue-number>-<short-description>`.
