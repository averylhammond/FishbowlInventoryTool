---
paths:
  - "source/InventoryProcessor.py"
  - "source/PdfTableParser.py"
  - "source/InventoryAppFileIO.py"
  - "source/InventoryEntry.py"
  - "source/TurnoverEntry.py"
---

# Inventory parsing and file I/O

The pipeline is: `InventoryAppFileIO.read_pdf()` hands page text to `PdfTableParser`, which
returns positional field lists; `InventoryProcessor` maps those onto `InventoryEntry` /
`TurnoverEntry` objects, writes each entry's `to_formatted_string()` into the results file, and
drives `spreadsheetDriver` (see `rules/spreadsheet.md`) to produce the `.xlsx`.

## `InventoryProcessor`

The whole inventory-processing pipeline, mirroring `InvoiceProcessor` in the sibling. It takes
the `InventoryAppFileIO` controller as its only constructor argument and builds its own
`PdfTableParser`; it has no reference to the controller, the display or the argument provider,
and user-facing status reaches the caller only through an injected callback.

- `process_inventory(inventory_pdf_path, checkbox_dict, report_status)` — the shared per-file
  routine used by both the GUI and headless paths. It parses the inventory PDF (bailing
  gracefully if it cannot be read), derives the output filename from the PDF name via regex
  (falling back to a generic name when the regex does not match), creates the workbook via the
  file I/O controller, then loops over every turnover PDF appending turnover columns, and saves.
  Status strings go to the injected `report_status` callback (the GUI output line, or
  `print`/stdout in headless mode) — **never** to the results file, so the results log stays
  deterministic for CI diffing.
- `process_inventory_file` and `process_turnover_file` source page text from
  `InventoryAppFileIO.read_pdf()`, delegate column parsing to `PdfTableParser`, and map the
  resulting rows onto the entry classes. **Every page is parsed before any entry is built**,
  because a row's part or description can wrap from the bottom of one page onto the top of the
  next.
- It imports `spreadsheetDriver` with `from source.spreadsheetDriver import *` — the one wildcard
  import left under `source/`, and why it calls `setupMainSpreadsheet` unqualified. Ruff would
  flag it (`F403`/`F405`) once the linter lands (#65); prefer explicit imports for anything new.

## `PdfTableParser`

Turns one page of layout-extracted text into positional field lists, with no knowledge of the
filesystem, `pypdf`, the entry classes or the GUI. `parse_inventory_page(page, rows)` and
`parse_turnover_page(page, rows)` each take the rows parsed so far and return them extended, so a
row wrapped across a page boundary can be folded back into the row it continues.

- `align_to_columns()` assigns each numeric value to the column whose header right edge it lines
  up with, so a column the report leaves blank stays blank instead of shifting every later value
  one column left.
- `to_number()` then converts each numeric cell into the number it holds — dropping thousands
  separators, `int` for a cell with no decimal point and `float` for one with, `None` for a blank
  — so the rows the entry classes are built from carry numbers rather than digit-strings and the
  spreadsheet gets numeric cells Excel will sort and sum. A cell that is not a number (the
  numeric pattern also matches a stray `-`) is handed back unconverted rather than failing the
  report.
- `CONTINUATION_SEPARATOR` and `ParsedRow` are **module-level** names, not attributes of the
  class. `CONTINUATION_SEPARATOR` is the single knob for how the fragments of a part or
  description wrapped across several lines are rejoined; it is a space, matching how the report
  reads. Set it to `""` to concatenate with nothing between.

Two ordering rules hold this together:

- **`extraction_mode="layout"` is mandatory in `read_pdf()`.** `pypdf`'s default mode discards
  the horizontal spacing the whole parser rests on, running adjacent columns together (`UOMOn`,
  `LABEL180 MINUTE DOOR LABEL`). Column offsets also drift by a character or two from page to
  page, so the parser re-derives them from each page's own header line rather than hardcoding
  them — and it slices `Part` off at the `Description` offset rather than splitting on the gap,
  since a part number can itself contain a run of spaces (`3/4"  BLANK HINGE`).
- **`align_to_columns()` returns strings; `to_number()` runs after it, never inside it.**
  `parse_turnover_page` uses `if not any(values)` to spot a "Totals:" line whose part name
  wrapped onto the line above, and that check depends on blanks being `""` while real values are
  truthy *strings*. Convert any earlier and a legitimate all-zeros row becomes `[0, 0, 0, 0]`,
  which is falsy, so the parser would scrape values off the wrong line.

## `InventoryAppFileIO`

Home of **all** file I/O. Directory and file paths come from `source/constants.py`.

- `read_pdf()` reads an inventory or turnover PDF via `pypdf`, returning one string of page text
  per page; `read_text_file()` reads a plain text file's full contents (used by the display's View
  menu to populate its read-only file viewer).
- `list_inventory_files()` (used by headless mode) and `list_turnover_files()` return full
  `Path`s ready to read.
- It owns the output spreadsheet lifecycle: `create_workbook()` places the workbook under
  `OUTPUT_DIR`, `save_workbook()` saves it. The in-memory cell writing lives in
  `spreadsheetDriver.py`, which receives the already-open workbook.
- It owns the results log at `logs/results.txt`. `reset_results_file()` **deletes** it on startup
  rather than truncating it, and `write_to_results_file()` (append mode, which recreates the
  file) writes each line. The delete-not-truncate distinction is load-bearing:
  `InventoryAppDisplay.handle_results_log()` uses the file's *existence* to decide whether to
  open the viewer or show a "File Not Found" popup, and an empty-but-present file would open a
  blank viewer instead.

**Error reporting contract.** Every method wraps its I/O in `try/except`, returns a safe empty
value (`[]`/`None`/`False`) on failure, and surfaces the error through an injected
`report_error(title, message)` callback — a no-op by default until the controller wires it to the
GUI — so a missing or unreadable file never crashes the app. **That includes the two results-file
helpers:** `reset_results_file()` and `write_to_results_file()` both report on `OSError` like
everything else here. Errors are never written *into* the results file; they go only to
`report_error`.

## The entry classes

- **`InventoryEntry`** — `@dataclass` holding one inventory row (`part`, `description`, `uom`,
  `on_hand`, `allocated`, `available`, …). Every field is annotated and defaulted, so it both
  default-constructs and takes a parsed row positionally — the processor builds one with
  `InventoryEntry(*row)`, which is why **the field order must match the parser's column order**.
  The fields *are* the parsed row and nothing else: it holds no spreadsheet state, so where a row
  lands on the sheet cannot disagree with where the writer put it (#55 removed the stored row —
  see `rules/spreadsheet.md`). Beyond the generated constructor its only method is
  `to_formatted_string()`.
- **`TurnoverEntry`** — the same shape for one turnover "Totals:" row (`part_description`,
  `units_sold`, `avg_qoh`, `avg_to_days`, `to_rate`). The three averages default to `None`
  because the report leaves them blank where a part's turnover is undefined.
- Both mirror `Invoice` in the sibling: a bare `@dataclass` (never `frozen` or `slots`, for
  parity rather than because anything mutates them — nothing does), the field block wrapped in
  `# fmt:off` / `# fmt:on` with a trailing comment per field, and exactly two things in the class
  body. There is deliberately no `__post_init__` and no `populate*` method: converting the
  report's text into fields is `PdfTableParser`'s job.
- **Field names and results-file labels are decoupled on purpose.** Fields are snake_case
  (`on_hand`, `part_description`) while `to_formatted_string()` prints the labels the report and
  the canonical results file use (`onHand:`, `partDescription:`). Renaming a field must not
  change its label, or the integration diff churns for no reason.

## The results file is a CI fixture, not a log

It is diffed against the submodule's `canonical_correct_results.txt`, so its *content* must not
vary by platform: log bare filenames rather than paths, and use explicitly-keyed sorts in
`list_inventory_files`/`list_turnover_files` rather than relying on `Path` ordering (which is
case-insensitive on Windows, case-sensitive on POSIX). Errors and user-facing status go to
`report_error`/`report_status`, never here — they would make the diff depend on the environment.

Line endings are the one thing that may differ: the file is written in text mode, so it is CRLF
on Windows and LF on Linux, and git's `core.autocrlf` translation of the canonical file cancels
this out on both. Do not "fix" that asymmetry in one place without the other.
