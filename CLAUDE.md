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
  `fishbowl_common`) from GitHub — the shared package providing `ArgumentProvider`; see
  the sibling `FishbowlInvoiceTool` for the shared-package story.

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
average. `source/gui/color_theme.py` and `source/gui/font_settings.py` are omitted from
measurement (see `.coveragerc`) because they are inert data with no behavior to test.

This workflow pins `actions/setup-python@v5` with pip caching while `unit-tests.yml` still
uses `@v4` and no cache — a deliberate mirror of the sibling's file rather than an oversight.
`.coveragerc` scopes what is measured (see the unit-testing section).

## Architecture

The application flow is: **entry point → controller → GUI + file I/O + entry data classes +
spreadsheet writer**.

- **`main.py`** — thin entry point. Constructs an `InventoryAppController` and calls
  `start_application()`. Contains no application logic.
- **`InventoryAppController`** (`source/InventoryAppController.py`) — the orchestrator.
  It wires the components together and owns the parsing flow, delegating all file I/O to
  `InventoryAppFileIO` and everything visual to `InventoryAppDisplay`. Responsibilities:
  - `__init__` constructs the `InventoryAppFileIO` collaborator, constructs the shared
    `ArgumentProvider` (from the `fishbowl-common` package) to detect headless mode, sets
    `self.display = None`, and clears the results file (`reset_results_file()`) so each run
    starts with a fresh diagnostics log. It deliberately does **not** build the GUI; see
    `start_application()` below.
  - `start_application()` first checks `argument_provider.integration_test_mode`: when set
    (via the `--integration-test` CLI flag) it skips the GUI entirely and calls
    `run_integration_test()`. Otherwise it imports and constructs `InventoryAppDisplay`,
    passing `read_file_callback=self.file_io.read_text_file` so the display's View menu can
    populate its read-only file viewer, wires the file I/O controller's `report_error`
    callback to the display's `show_popup`, and enters `mainloop()`.
  - `handle_process_inventory(inventory_pdf_path, checkbox_dict)` — the callback handed to
    the display. It runs `process_inventory()` with status routed to the display's output
    box, keeping the display's callback contract to two arguments.
  - `process_inventory(inventory_pdf_path, checkbox_dict, report_status)` — the shared
    per-file processing routine used by both the GUI and headless paths. It parses the
    inventory PDF (bailing gracefully if it can't be read), derives the output filename
    from the PDF name via regex (falling back to a generic name when the regex doesn't
    match), creates the workbook via the file I/O controller, then loops over every
    turnover PDF appending turnover columns and saves. Status strings go to the injected
    `report_status` callback (the GUI output line, or `print`/stdout in headless mode) —
    never to the results file — so the results log stays deterministic for CI diffing.
  - `run_integration_test()` — the headless entry point. Routes `report_error` to stdout,
    takes an all-columns-checked `checkbox_dict` from `columns.all_columns_selected()`, and
    calls `process_inventory()` for every PDF from
    `InventoryAppFileIO.list_inventory_files()`. Lets a CI workflow generate
    `logs/results.txt` with no GUI interaction.
  - PDF parsing helpers: `process_inventory_file` and `process_turnover_file` source page
    text from `InventoryAppFileIO.read_pdf()`, delegate column parsing to
    `PdfTableParser`, and map the resulting rows onto `InventoryEntry` / `TurnoverEntry`
    objects. Every page is parsed before any entry is built, because a row's part or
    description can wrap from the bottom of one page onto the top of the next.
- **`source/gui/`** — the GUI subpackage, the only place tkinter appears.
  - **`InventoryAppDisplay`** (`source/gui/InventoryAppDisplay.py`) — a `tk.Tk` subclass
    that takes every dependency as a constructor argument (`process_callback`,
    `read_file_callback`, `title`, `window_resolution`, and the defaulted
    `theme`/`font_family`/`font_size`) and never imports the controller. It owns the file
    picker, the two checkbox grids, the Process/Exit buttons, the `ScrolledText` output box,
    and a menu bar (File/View/Preferences/Help), and exposes `show_popup()`, `write_output()`,
    `clear_output()` and `get_selected_columns()`. `write_output()` calls
    `update_idletasks()` because processing runs on the GUI thread, so without it a status
    line would not paint until the work it announces had already finished.
    - The **menu bar** is built inline in `build_widgets()` (no separate `MenuBar` class,
      matching the sibling): **File** (Open/Clear/Exit — Exit calls `self.destroy`, not
      `self.quit`, to match the Exit button's own convention); **View** (Results Log opens
      `RESULTS_FILE` in a read-only `FileEditorWindow` via `_open_readonly_file_viewer()`,
      or a "File Not Found" popup if it doesn't exist yet; Inventories/Turnover Reports open
      a browse-only `filedialog.askopenfilename` rooted at `INVENTORY_DIR`/`TURNOVER_DIR`,
      reusing the same dialog mechanism as the top-level Browse button rather than shelling
      out to the OS's file explorer); **Preferences** (Theme/Font/Font Size submenus built by
      looping `ALL_THEMES`/`FONT_FAMILIES`/`FONT_SIZES`, each `command` a
      `lambda x=option: self.apply_x(x)` to avoid a late-binding closure bug); **Help**
      (About opens `AboutWindow` with `VERSION` from `constants.py`).
    - **`apply_theme()`** / **`apply_font_family()`** / **`apply_font_size()`** /
      **`_apply_font()`** apply a Preferences choice live by explicitly reconfiguring every
      widget the display owns, including every checkbutton in `column_checkbuttons` (the
      sibling has no checkbox grid, so this loop has no sibling analog). These do **not**
      persist the choice or refresh tooltips — settings persistence
      (`SettingsRepository`) and `Tooltip` are tracked separately and not yet built; when
      they land, slot the persistence call and a `_refresh_tooltips()` call into these same
      four methods rather than restructuring them.
  - **`ThemedSubwindow`** / **`MessageWindow`** / **`AboutWindow`** / **`FileEditorWindow`**
    — ported verbatim from the sibling: `ThemedSubwindow` is a `tk.Toplevel` base that
    snapshots the active theme/font and centers over its parent; `MessageWindow` is the
    themed OK-button popup `show_popup()` builds; `AboutWindow` shows the app name (hardcoded
    as "Fishbowl Inventory Tool", since the sibling has no reusable app-name constant either)
    and `VERSION`; `FileEditorWindow` shows a file's text in a monospace box, with an
    `editable` flag toggling a Save button — this app only ever opens it with
    `editable=False` (there are no editable config files here), but the class itself needed
    no adaptation.
  - **`color_theme.py`** / **`font_settings.py`** — inert styling data shared with the
    sibling. Keep them byte-identical to that repo's copies so the two apps stay visually
    consistent; they are omitted from coverage for the same reason.
  - **Deliberately absent**, each a follow-up: `SettingsRepository` settings persistence
    (theme/font/column selections reset to defaults on restart until this lands) and
    `Tooltip`. Only `DARK` ships as the default today, but `ALL_THEMES` is already offered
    in the Preferences menu, and the theme is a constructor argument rather than a
    hardcoded value, so persistence needs no surgery on the display.
- **`columns.py`** (`source/columns.py`) — the single source of truth for the (column key,
  GUI label, section) triple: a frozen `Column` dataclass plus `INVENTORY_COLUMNS`,
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
  output spreadsheet lifecycle — opening (`create_workbook()`) and saving
  (`save_workbook()`) the `xlsxwriter` workbook. It also owns the results log at
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
  surfaced via Help -> About, plus relative `Path` constants for the input directories
  (`INVENTORY_DIR`, `TURNOVER_DIR`) and the diagnostics log (`LOGS_DIR`, `RESULTS_FILE`),
  resolved against the executable's CWD (mirrors the sibling invoice tool's `constants.py`).
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
  or columns and data will desync. **Those keys and their GUI labels live in
  `source/columns.py`**, and `InventoryAppDisplay` builds its checkbox grid by iterating
  the same tuples the writers walk, so the GUI cannot offer a column the spreadsheet does
  not know about or miss one it does. Add a column there, not in three places.
- **`get_selected_columns()` wraps every value in `bool()`, and that is load-bearing.**
  The spreadsheet writers test `if checkboxDict["Part"] == True`, which a `tk.BooleanVar`
  fails — the column would be silently dropped from the report rather than raising.
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
  neutralizes `tk.Tk.__init__`, mocks the inherited Tk methods the constructor calls
  (`patch.object(InventoryAppDisplay, "title"/"geometry"/"resizable"/"configure")`), and
  replaces every widget class at its point of use
  (`patch("source.gui.InventoryAppDisplay.tk.Label", side_effect=_distinct_widget)`), so no
  real window is created and each widget attribute is a distinct assertable mock. It
  `yield`s a `SimpleNamespace` **from inside** the `with` block so the patches stay live for
  the whole test. Per-test constructor arguments come from indirect parametrization
  (`@pytest.mark.parametrize("display", [{"theme": FOREST}], indirect=True)`).
  - **`tk.StringVar` and `tk.BooleanVar` are patched with the `_FakeStringVar` /
    `_FakeBooleanVar` stubs, not bare `MagicMock`s.** A tkinter variable cannot be built
    without a default root window, so the real classes raise "Too early to create variable";
    and a `MagicMock` would defeat the assertions that `get_selected_columns()` returns real
    booleans, which is the property the spreadsheet writers depend on.
  - The menu bar's Preferences submenus are built from a `command=lambda x=option:
    self.apply_x(x)` per loop iteration (see the architecture section above); tests invoke
    each captured `command` directly (`made_call.kwargs["command"]()`) and assert the
    resulting state, which is what actually exercises the default-argument capture rather
    than just asserting the menu was built.
- `tests/AboutWindow_tests.py` / `tests/FileEditorWindow_tests.py` — themed subwindows,
  following `tests/MessageWindow_tests.py`'s pattern exactly: a `_build_window()` helper
  neutralizing `tk.Toplevel.__init__` and `title`/`configure`/`_center_over_parent`, with
  every widget class patched at its point of use.
- `tests/InventoryAppController_tests.py` — the orchestrator, with `ArgumentProvider`,
  `InventoryAppFileIO` and `PdfTableParser` patched at `source.InventoryAppController.<name>`
  as usual. **The display is the one exception to the patch-at-the-point-of-use rule:**
  `start_application()` imports it inside the function, so the name never exists at module
  scope and the target is its definition site,
  `patch("source.gui.InventoryAppDisplay.InventoryAppDisplay")`. A function-local
  `from X import Y` resolves `Y` as an attribute of module `X` at call time, which is why
  patching there works.

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
- `tests/__init__.py`, `source/__init__.py` and `source/gui/__init__.py` are empty but
  **load-bearing**: with `tests/__init__.py` present, pytest's prepend import mode walks up
  past `tests/` and puts the repo root on `sys.path`, which is what makes
  `from source.InventoryAppFileIO import *` resolve. There is deliberately no `conftest.py`
  and no pytest config file.
- `.coveragerc` scopes measurement to `./source`, omitting `main.py`, `constants.py`,
  `tests/`, the virtualenv, and the two inert GUI data modules (`source/gui/color_theme.py`,
  `source/gui/font_settings.py`).
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
