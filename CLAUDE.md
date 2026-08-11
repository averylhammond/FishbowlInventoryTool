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
- Virtual env: `python -m venv venv`, then `source venv/Scripts/activate` (Windows) or
  `source venv/bin/activate` (Linux/Mac).
- Install deps: `pip install -r requirements/dev.txt` for development (pulls in
  `release.txt` plus `pytest`/`pytest-cov`); `requirements/release.txt` alone is what the
  shipped app needs. `release.txt` pulls `fishbowl-common` (import name
  `fishbowl_common`) from GitHub — the shared package providing `ArgumentProvider`; see
  the sibling `FishbowlInvoiceTool` for the shared-package story.

## Common Commands

- Run the app (GUI): `python main.py`
- Run headless (no GUI): `python main.py --integration-test` — processes every PDF in
  `InventoryAvailability/` with all columns included and writes `logs/results.txt`. This
  is what CI runs to validate output without GUI interaction.
- Byte-compile sanity check: `python -m py_compile main.py source/*.py tests/*.py`
- Reproduce the integration test locally (after `./scripts/copy_resources.sh`):
  `python main.py --integration-test` then
  `diff logs/results.txt automated-inventory-testing/canonical_correct_results.txt`.
- Run all unit tests: `pytest tests/*` (from the repo root)
- Run a single test file: `pytest tests/InventoryAppFileIO_tests.py`
- Run a single test:
  `pytest tests/InventoryAppFileIO_tests.py::test_read_pdf_extracts_each_page_in_layout_mode`
- Run with coverage: `pytest --cov=./ --cov-report=term-missing tests/*`

### CI

Three workflows, all of which run on pull requests to `main` and on manual dispatch. The
code-coverage one additionally runs on pushes to `main`.

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
convention below). Nothing enforces that continuously — if a Windows-specific regression
ever slips through, add a `windows-latest` leg to a `strategy.matrix`.

`.github/workflows/unit-tests.yml` runs the unit tests. On `ubuntu-latest` it installs
`requirements/dev.txt` (`release.txt` plus `pytest`/`pytest-cov`) and runs `pytest tests/*`.
The glob is required because the test files use the `_tests.py` suffix, which pytest's
default discovery does not match. Unlike the integration job it checks out **without** the
submodule and needs no repo secret — unit tests mock all their I/O, so pulling the private
test data would only slow the job and tie it to `CUSTOMER_DATA_PAT`. Keep it that way: a
unit test that needs a real PDF belongs in the integration test instead. The job installs
`PySimpleGUI` transitively but never imports it (the controller imports it locally inside
`start_application()`), so no `python3-tk` system package is installed; a future test that
imports a GUI module at module scope would need one added.

`.github/workflows/code-coverage.yml` runs the same unit tests under coverage
(`pytest --cov=./ --cov-report=xml --cov-fail-under=75 tests/*`) and uploads `coverage.xml`
to Codecov, which serves the README badge and posts the PR coverage comment. The upload step
is `if: always()` so the report still lands when the gate fails — that is when the comment is
most useful. It needs the `CODECOV_TOKEN` repo secret, and like the unit-test job it checks
out **without** the submodule. The extra `push: branches: [main]` trigger exists so Codecov
records a main-branch baseline for PR diffs; without it the badge never updates.

**The 75% gate is a temporary floor, not the target.** Measured coverage is 79%
(`InventoryAppFileIO`, `PdfTableParser`, `InventoryEntry`, `TurnoverEntry` and
`spreadsheetDriver` at 100%, `InventoryAppController` at 0%), so 75 leaves a little
headroom for in-progress refactors. Ratchet it upward as `InventoryAppController` gains
tests; 80–90% is the goal, matching the sibling.

This workflow pins `actions/setup-python@v5` with pip caching while `unit-tests.yml` still
uses `@v4` and no cache — a deliberate mirror of the sibling's file rather than an oversight.
`.coveragerc` scopes what is measured (see the unit-testing section).

## Architecture

The application flow is: **entry point → controller → file I/O + entry data classes +
spreadsheet writer**.

- **`main.py`** — thin entry point. Constructs an `InventoryAppController` and calls
  `start_application()`. Contains no application logic.
- **`InventoryAppController`** (`source/InventoryAppController.py`) — the orchestrator.
  It owns the GUI and parsing flow and delegates all file I/O to `InventoryAppFileIO`.
  Responsibilities:
  - `__init__` constructs the `InventoryAppFileIO` collaborator, constructs the shared
    `ArgumentProvider` (from the `fishbowl-common` package) to detect headless mode, and
    clears the results file (`reset_results_file()`) so each run starts with a fresh
    diagnostics log.
  - `start_application()` first checks `argument_provider.integration_test_mode`: when set
    (via the `--integration-test` CLI flag) it skips the GUI entirely and calls
    `run_integration_test()`. Otherwise it builds the PySimpleGUI window (file picker +
    inventory/turnover column checkboxes + Process button), wires the file I/O
    controller's `report_error` callback to the GUI output line, and runs the event loop.
    On "Process This Inventory" it delegates to `process_inventory()`.
  - `process_inventory(inventory_pdf_path, checkbox_dict, report_status)` — the shared
    per-file processing routine used by both the GUI and headless paths. It parses the
    inventory PDF (bailing gracefully if it can't be read), derives the output filename
    from the PDF name via regex (falling back to a generic name when the regex doesn't
    match), creates the workbook via the file I/O controller, then loops over every
    turnover PDF appending turnover columns and saves. Status strings go to the injected
    `report_status` callback (the GUI output line, or `print`/stdout in headless mode) —
    never to the results file — so the results log stays deterministic for CI diffing.
  - `run_integration_test()` — the headless entry point. Routes `report_error` to stdout,
    builds an all-columns-checked `checkbox_dict` (reusing `build_checkbox_dict` with a
    `defaultdict(lambda: True)` so the column keys stay defined in one place), and calls
    `process_inventory()` for every PDF from `InventoryAppFileIO.list_inventory_files()`.
    Lets a CI workflow generate `logs/results.txt` with no GUI interaction.
  - PDF parsing helpers: `process_inventory_file` and `process_turnover_file` source page
    text from `InventoryAppFileIO.read_pdf()`, delegate column parsing to
    `PdfTableParser`, and map the resulting rows onto `InventoryEntry` / `TurnoverEntry`
    objects. Every page is parsed before any entry is built, because a row's part or
    description can wrap from the bottom of one page onto the top of the next.
  - `build_checkbox_dict()` snapshots the GUI checkbox state into a dict consumed by the
    spreadsheet writer to decide which columns to emit.
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
  text per page, lists the inventory
  availability PDFs (`list_inventory_files()`, used by headless mode) and the turnover
  report PDFs (`list_turnover_files()`) as full `Path`s ready to read, and owns the
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
- **`InventoryEntry`** (`source/InventoryEntry.py`) — `@dataclass` holding one inventory
  row (`part`, `description`, `uom`, `on_hand`, `allocated`, `available`, etc.). Every
  field is annotated and defaulted, so it both default-constructs and takes a parsed row
  positionally — the controller builds one with `InventoryEntry(*row)`, which is why the
  field order must match the parser's column order and `row_written_to` must stay last.
  Beyond the generated constructor its only method is `to_formatted_string()`, a
  formatted-string dump the controller writes to the results file. Tracks
  `row_written_to` so turnover data can be matched back to the same spreadsheet row.
- **`TurnoverEntry`** (`source/TurnoverEntry.py`) — the same shape for one turnover
  "Totals:" row (`part_description`, `units_sold`, `avg_qoh`, `avg_to_days`, `to_rate`).
  The three averages default to `None` because the report leaves them blank where a part's
  turnover is undefined.
- Both entry classes mirror `Invoice` in the sibling `FishbowlInvoiceTool`: a bare
  `@dataclass` (never `frozen` or `slots` — `spreadsheetDriver` assigns `row_written_to`),
  the field block wrapped in `# fmt:off` / `# fmt:on` with a trailing comment per field,
  and exactly two things in the class body. There is deliberately no `__post_init__` and no
  `populate*` method: converting the report's text into fields is `PdfTableParser`'s job.
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
- `start_application()` imports `PySimpleGUI` locally rather than at module scope, so a
  headless run never loads tkinter. This is a stopgap — when the GUI is extracted into its
  own class the controller should stop importing GUI modules entirely and the local import
  should go.
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
  unit tests. After a run, `git status` must show no new `logs/`, `*.xlsx`, or
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
- `tests/__init__.py` and `source/__init__.py` are empty but **load-bearing**: with
  `tests/__init__.py` present, pytest's prepend import mode walks up past `tests/` and puts
  the repo root on `sys.path`, which is what makes `from source.InventoryAppFileIO import
  *` resolve. There is deliberately no `conftest.py` and no pytest config file.
- `.coveragerc` scopes measurement to `./source`, omitting `main.py`, `constants.py`,
  `tests/`, and the virtualenv.
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
