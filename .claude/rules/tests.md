---
paths:
  - "tests/**"
---

# Unit testing conventions

Unit tests live in `tests/`, one `tests/test_<module_name>.py` per module under `source/` — the
mirror is the *module*, not a class, which is why `test_columns.py` (module-level code, no
class) sits alongside the class files. That name matches pytest's
default `python_files` pattern, so a bare `pytest` collects the whole suite and the workflows
invoke it as `pytest tests/` with no glob.

`tests/__init__.py`, `source/__init__.py` and `source/gui/__init__.py` are empty but
**load-bearing**: with `tests/__init__.py` present, pytest's prepend import mode walks up past
`tests/` and puts the repo root on `sys.path`, which is what makes
`from source.inventory_app_file_io import InventoryAppFileIO` resolve. There is deliberately no
`conftest.py`; pytest and coverage configuration lives in `pyproject.toml`, whose
`[tool.coverage.run]` scopes measurement to `./source`, omitting `main.py`, `constants.py`,
`tests/`, the virtualenv and the empty `__init__.py` files; nothing else is omitted, since the
inert styling data that used to be excluded now lives upstream in `fishbowl_common.gui`. Its
`fail_under = 90` is the gate CI relies on — see `rules/ci.md`.

## The per-file reference implementations

Mirror these (and the sibling's `tests/` suite) rather than inventing new patterns:

- **`tests/test_inventory_app_file_io.py`** — a class with collaborators and I/O. Follow it for the
  mocking and error-path conventions below.
- **`tests/test_pdf_table_parser.py`** — pure logic with no collaborators, so nothing is mocked and
  the fixture just constructs the object. Follow it for parser-style tests, including the
  synthetic-fixture rule below.
- **`tests/test_inventory_entry.py` / `tests/test_turnover_entry.py`** — dataclasses, so there is no
  fixture at all: each test constructs the object it needs. Cover the defaults, a subset of
  keyword arguments, positional construction from a `PARSED_ROW` module constant shaped like the
  parser's output, and `to_formatted_string()` asserted against the report's labels rather than
  the field names.
- **`tests/test_columns.py`** — plain module data, so again no fixture: it asserts the shape of
  `Column`, that `INVENTORY_COLUMNS`/`TURNOVER_COLUMNS` compose `ALL_COLUMNS` in spreadsheet
  order, that `COLUMN_KEYS` matches, and that `all_columns_selected()` maps every key to `True`.
  Keep it in step with `source/columns.py` whenever a column is added — it is the only test that
  notices a key or an `always` flag changing.
- **`tests/test_spreadsheet_writer.py`** — a class driven end to end through a mocked
  `xlsxwriter` workbook. Follow it for spreadsheet-writer tests: `worksheet` and `workbook`
  fixtures (`MagicMock(spec=Worksheet)` / `spec=xlsxwriter.Workbook`), with
  `add_format.side_effect = lambda spec: dict(spec)` so each format is the spec dict it was built
  from and one format is distinguishable from another, and `add_worksheet` stubbed because
  `SpreadsheetWriter.__init__` opens the sheet; then a `writer` fixture wrapping the writer
  around it. `written_cells()` gives `(row, col, value)` tuples in write order, while
  `final_cells()` / `cells_in_row()` give what the *saved* sheet would hold — a turnover report
  writes each column twice, as a placeholder and then as the data landing on top of it, so the
  call list alone does not say what the user sees. **Nothing is patched**: the writer's own
  methods are exercised together, which is what lets a test assert an unmatched part still reads
  `N/A`. `checkboxes()` builds the checkbox dict from the imported `source.columns.COLUMN_KEYS`,
  but every layout assertion stays a literal `(row, col, value)` tuple — those are what fail when
  a column moves. Real `InventoryEntry`/`TurnoverEntry` objects are used rather than mocks — they
  are inert data holders with no I/O — but each is given a distinct value per field so a
  column/data desync fails loudly instead of matching by coincidence.
- **`tests/test_inventory_processor.py`** — a class whose collaborator is injected rather than
  constructed, so the file I/O controller is a `MagicMock(spec=InventoryAppFileIO)` handed to the
  constructor while the `PdfTableParser` the processor builds itself is patched at
  `source.inventory_processor.PdfTableParser`. The `spec=` is safe only because the processor never
  touches `report_error`, which is an instance attribute a spec'd mock would reject. The
  spreadsheet writer is imported by name, so `source.inventory_processor.SpreadsheetWriter` is
  the point of use; a test drives the mocked class's `return_value` to stand in for the writer
  the processor builds. `process_inventory()` is tested with its own parsing helpers
  replaced via `patch.object` on the instance, so each test exercises one method.
- **`tests/test_inventory_app_controller.py`** — the wiring, with `ArgumentProvider`,
  `InventoryAppFileIO` and `InventoryProcessor` patched at `source.inventory_app_controller.<name>`
  as usual. Because the processor is mocked there, the GUI and headless paths are asserted against
  `processor.process_inventory` directly rather than by patching a method onto the controller.
  **The display is the one exception to the patch-at-the-point-of-use rule:**
  `start_application()` imports it inside the function, so the name never exists at module scope
  and the target is its definition site,
  `patch("source.gui.inventory_app_display.InventoryAppDisplay")`. A function-local
  `from X import Y` resolves `Y` as an attribute of module `X` at call time, which is why patching
  there works. Every test reaching `start_application()` must patch
  `source.inventory_app_controller.UpdateCoordinator`, or a real daemon thread would call GitHub
  during the run; this repo asserts only that the coordinator is built with this app's
  `VERSION`/`GITHUB_REPO`/display and started. **`SettingsRepository` and `PatchNotes` are
  deliberately absent from the `controller` fixture** — both are built in `start_application()`,
  so only the tests reaching that method patch them (at the ordinary point of use). Every test
  that calls it must patch both, or it opens a real SQLite database and leaves a `data/`
  directory in the working tree, breaking the "no new artifacts after a run" rule below. The
  patch-notes decision table is covered by calling `show_patch_notes_if_updated()` directly on a
  controller with its display, settings repository and reader replaced, one test per row.
- **`tests/test_inventory_app_display.py`** — a tkinter GUI class; see the next section.

**There are no tests here for anything owned by `fishbowl-common`.** `ThemedSubwindow`,
`MessageWindow`, `AboutWindow`, `FileEditorWindow`, `PatchNotesWindow`, `UpdateWindow`, `Tooltip`,
`UpdateCoordinator`, `SettingsRepository` and `PatchNotes` are covered upstream in
`fishbowl-common/tests/`; this repo tests only its own classes and the wiring around the shared
ones — that a coordinator was constructed with the right arguments, that a callback is forwarded
— never the shared behavior itself. Do not re-add a local test file for one; a gap in their
coverage is a change to make in that repo.

## The `display` fixture

It neutralizes `tk.Tk.__init__`, mocks the inherited Tk methods the display calls
(title/geometry/resizable/configure/config/protocol/destroy/winfo_geometry), and replaces every
widget class at its point of use
(`patch("source.gui.inventory_app_display.tk.Label", side_effect=_distinct_widget)`), so no real
window is created and each widget attribute is a distinct assertable mock. It `yield`s a
`SimpleNamespace` **from inside** the `with` block so the patches stay live for the whole test.
Per-test constructor arguments come from indirect parametrization
(`@pytest.mark.parametrize("display", [{"theme": FOREST}], indirect=True)`); persisted settings
arrive the same way, as a `{"settings": {...}}` override.

- **The inherited Tk methods are patched with one `patch.multiple(InventoryAppDisplay,
  title=DEFAULT, …)`, not one `patch.object` each.** Python allows only twenty statically nested
  blocks, and a `with` item is one. The block currently holds **17 items**, so there is room for
  three more — verify with a trial `compile()` before assuming a new patch fits, and expect
  `SyntaxError: too many statically nested blocks` at collection time if it does not. Expanding
  that one `patch.multiple` into its eight `patch.object` equivalents would take the block to 24
  items, i.e. straight past the ceiling — which is the whole reason it is written this way. The
  mocks come back as a dict (`tk_methods["geometry"]`); add new Tk-method patches inside that
  call.
- **`tk.StringVar` and `tk.BooleanVar` are patched with the `_FakeStringVar` / `_FakeBooleanVar`
  stubs, not bare `MagicMock`s.** A tkinter variable cannot be built without a default root
  window, so the real classes raise "Too early to create variable"; and a `MagicMock` would
  defeat the assertions that `get_selected_columns()` returns real booleans, which is the property
  the spreadsheet writers depend on.
- The menu bar's Preferences submenus are built from a `command=lambda x=option: self.apply_x(x)`
  per loop iteration, so tests invoke each captured `command` directly
  (`made_call.kwargs["command"]()`) and assert the resulting state — that actually exercises the
  default-argument capture rather than just asserting the menu was built. The checkbutton
  `command`s are tested the same way, each resolved back to its column through the `variable` it
  was built with, so a late-binding regression fails rather than passing by coincidence.
- **`Tooltip` is patched at `source.gui.inventory_app_display.Tooltip`** with the same
  `_distinct_widget` side effect the widget classes use, so every attached tooltip is its own
  assertable mock, exposed on the fixture namespace as `tooltip_cls`. The attachment tests read
  `call.kwargs["widget"]` / `["text"]`, so `_attach_tooltip()` must keep passing those by keyword.
  The per-column test resolves each checkbutton back through `column_checkbuttons[column.key]`
  before comparing text — an "every tooltip has some text" assertion would pass even with every
  tip attached to the wrong checkbox.
- `save_settings_callback` is a bare `MagicMock()`; `SettingsRepository` is never imported here,
  since the display only ever reaches it through that callback. The three Preferences submenu
  tests invoke every `command` in a loop, so those tests absorb 4 + 10 + 14 writes into the same
  mock — assert with `assert_any_call` there, and reserve `assert_called_once_with` for the tests
  that exercise a single `apply_*` call.

## Test one object in isolation

Every unit test exercises exactly **one** class or function. Replace **all** collaborators with
mocks so a failure points unambiguously at the unit under test — never let a unit test touch the
real filesystem, a real PDF, or the GUI.

- **Construct the unit under test in a pytest fixture** (the `file_io` fixture) so each test
  starts from a clean, identically-configured object, with `report_error` injected as a bare
  `MagicMock()`. Every failure-path test ends with `file_io.report_error.assert_called_once()`;
  the title/message text is never asserted.
- **Patch module-level names at the point of use, not their definition site.**
  `InventoryAppFileIO` does `from source.constants import INVENTORY_DIR, RESULTS_FILE,
  TURNOVER_DIR`, so the patch target is `source.inventory_app_file_io.RESULTS_FILE` — never
  `source.constants.RESULTS_FILE`.
- **Patch `pypdf.PdfReader` and `xlsxwriter.Workbook`, never the whole module.** The methods under
  test catch `pypdf.errors.PdfReadError` and `xlsxwriter.exceptions.XlsxWriterException`;
  replacing the module object with a `MagicMock` makes those `except` clauses reference a
  non-exception and raise `TypeError` while handling the error.
- **Mock injected collaborators with `MagicMock(spec=Collaborator)`** so the mock only allows
  attributes the real class defines.
- **Name unasserted mock parameters with a leading underscore** (`_mock_file`) and reserve plain
  names (`mock_results_file`) for mocks you assert against. `ARG001` catches the ones you
  forget, since ruff treats a leading underscore as the marker for a deliberately unused
  argument, and `ARG005` does the same for a stand-in lambda's parameters.

## Follow the FIRST principles

- **Fast** — no real file, PDF, or GUI I/O; mock it. The whole run should stay under a second.
- **Independent** — no ordering dependencies or shared mutable state between tests.
- **Repeatable** — deterministic on every machine. Do not depend on the
  `automated-inventory-testing` submodule; that drives the *integration* test, not the unit tests.
  After a run, `git status` must show no new `logs/`, `data/`, `*.xlsx` or
  `InventoryAvailability/` artifacts.
- **Self-validating** — each test asserts a clear pass/fail; never require reading
  `logs/results.txt` to judge the result.
- **Timely** — add or extend tests alongside any new branch or utility function, in the same
  change.

## Conventions

- Flat module-level `test_<method>_<behavior>` functions — no test classes. Error paths are
  suffixed `_reports_on_error` / `_reports_and_returns_<x>_on_error`.
- **Import the names under test explicitly — never `from <module> import *`.** A wildcard import
  binds whatever the module happens to export, so a name deleted or renamed in `source/` fails at
  the point of *use*, in one test, rather than at import, in every test that file holds — which
  makes a rename far harder to trace. `F403`/`F405` enforce it. Import lists are sorted and
  parenthesized across lines once they no longer fit on one — `ruff check --fix` does that for
  you, so run it rather than arranging them by hand. There is no star import left under
  `source/` either — #57 removed the last one, in `InventoryProcessor`.
- **`test_pdf_table_parser.py`'s synthetic page fixtures carry `# noqa: E501`.** Their column
  offsets are what `align_to_columns()` is tested against, so the eleven over-length lines
  cannot be split or wrapped to satisfy the 120-column limit.
- **A loop pairing a fixture against a captured `call_args_list` uses `zip(..., strict=True)`**,
  so a length mismatch fails the test rather than silently truncating to the shorter side —
  which is the regression those tests exist to catch.
- **One fixture convention: build the unit under test in a pytest fixture**, and give a test that
  needs a differently-constructed object its arguments through indirect parametrization rather
  than a `_build_window(...)`-style helper function. The helper form left this repo with the
  shared subwindow classes; do not reintroduce it. The exception is a module with no object to
  build: `test_inventory_entry.py`, `test_turnover_entry.py` and `test_columns.py` have no fixture
  at all.
- Keep the tests for one method together and in the order the methods appear in the module —
  the grouping the `###`-bordered banners used to mark before they were removed — and give
  each test a docstring describing what it verifies with an `Args:` block documenting every
  mock/fixture parameter.
- **`tests/` is deliberately unannotated, so the docstring type stays here.** Every `def` under
  `source/` is annotated and its docstring carries no types; test functions and fixtures take no
  annotations, which makes the docstring the only place a fixture's or mock's type is recorded —
  `file_io (pytest.fixture)`, `mock_show_popup (unittest.mock.MagicMock)`,
  `Returns: unittest.mock.call:`. Keep both halves of that split as they are. This is why
  `per-file-ignores` turns `ANN` off for `tests/**`, alongside `PLR2004`: an assertion's
  expected value belongs as a literal at the assertion, and hoisting `== 18` into a named
  constant hides the number the test exists to pin.
- **Sample page text is synthetic, never copied from the submodule.** The
  `automated-inventory-testing` reports are private company data, so a parser fixture reproduces
  the report's *geometry* — header offsets, column gaps, the wrapped `Avg. TO` label, the page
  footer — under invented part numbers and descriptions, at reduced column widths so the lines
  stay readable. Because those column positions are load-bearing, build a page by joining
  explicit line literals (`build_page()` in `test_pdf_table_parser.py`) rather than dedenting a
  triple-quoted block an editor could reflow.
