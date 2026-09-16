---
paths:
  - "source/spreadsheet_writer.py"
  - "source/columns.py"
---

# Spreadsheet output and the column scheme

`spreadsheet_writer.py` is all `xlsxwriter` output. `SpreadsheetWriter` is constructed **once per
workbook** by `InventoryProcessor`, around the already-open workbook from `InventoryAppFileIO`:

| Member | Does |
| --- | --- |
| `__init__` | Opens the single worksheet the report occupies and builds the three cell formats, so nothing downstream looks the sheet up by name or rebuilds a format |
| `write_inventory` | The inventory section: the header row, then one row per entry, **returning the first free column** |
| `append_turnover_report` | One turnover report end to end — its headers, its pre-fill, and the join onto the inventory rows — **returning the first free column after it** |
| `_checked_columns` | Filters a section's columns against the checkbox dict, once per call |
| `_write_header` | Writes one section's header row, appending `suffix` to every title |
| `_write_entry_row` | One entry's cells across a section, `getattr(entry, column.field)` per cell |
| `_prefill` | Writes `MISSING_TURNOVER_VALUE` into every data row of a report's columns, so a part with no turnover row reads as missing rather than blank |
| `_row_format` | The even/odd banding choice, in one place for every section |
| `_match_key` | Normalizes a part name for the join: every space removed |
| `HEADER_ROW` / `FIRST_DATA_ROW` | `0` and `1`, at the top of the module: the single definition of where the header sits and where data begins |

## The column scheme

The scheme is checkbox-driven, and **lockstep is structural, not a convention**: each public
method calls `_checked_columns()` once and hands that same tuple to `_write_header` and to
`_write_entry_row`. Neither re-filters, so a column and its data cannot drift apart. The width a
section reports back is `len()` of that tuple — which is also why an empty inventory still
reports the width its headers occupy rather than column 0. **Do not add a writer that filters for
itself.**

Inventory keys are plain (`"Part"`, `"OnHand"`); turnover keys are `t`-prefixed (`"tUnits Sold"`,
`"tTO Rate"` — note `"tDescription"` has no space after the prefix).

`source/columns.py` holds the `(key, label, field, always, tooltip)` record — a frozen `Column`
dataclass plus `INVENTORY_COLUMNS`, `TURNOVER_COLUMNS`, `ALL_COLUMNS`, `COLUMN_KEYS` and
`all_columns_selected()`. The tuple a `Column` lives in *is* its GUI section. It imports only
`dataclasses`, which is what lets the headless path reach `all_columns_selected()` without
loading tkinter — **keep it that way**; the check that each `field` resolves therefore lives in
`tests/test_columns.py`, not here.

**`columns.py` is the single source of truth for the GUI *and* the spreadsheet.** `label` is both
the checkbox text and the sheet header; `field` names the attribute on `InventoryEntry` /
`TurnoverEntry` the value is read from. **Adding a column is one entry in `columns.py` plus the
matching field on the entry dataclass** — `spreadsheet_writer.py` needs no edit at all, and a
column whose `field` does not resolve fails in `test_columns.py` rather than as an
`AttributeError` partway through writing a report.

Two historical notes, so an old report or an old fixture is still recognizable:

- Until #57 the writers hardcoded all 16 keys *and* a second set of header strings, so the sheet
  read `"OnHand"`, `"NotAvailable"`, `"DropShip"`, `"OnOrder"` and `"TO Description"` where
  `columns.py` read `"On Hand"`, `"Not Available"`, `"Drop Ship"`, `"On Order"` and
  `"Description"`. The labels won; the canonical spreadsheet fixture was regenerated with them.
- `field` is a literal, not something derived from `key`. Fifteen of the sixteen would survive a
  computed rule, but `"tDescription"` maps to `part_description`. **Do not "simplify" it into a
  `key.removeprefix("t")` helper.**

The four numeric turnover headers append the report's filename, which `_write_header`'s `suffix`
parameter carries for the whole section rather than a branch per column. Under #57 the
description column takes that suffix too, so two reports side by side no longer share a title.

## Rules that are easy to break

- **A turnover report is as many columns wide as the user checked, so the caller must never guess
  its stride.** `append_turnover_report()` returns the first free column and `process_inventory()`
  assigns it (`next_col = writer.append_turnover_report(...)`), exactly as `write_inventory()`
  reports back where the inventory columns ended. It used to advance by `+= 1`, which silently
  overwrote all but the first column of every turnover report but the last (#53) — a data-loss
  bug the results file cannot see, since it is built from the entry objects and never from the
  sheet. The header and the append were also two separate calls threading the same index, so the
  caller could hand them different columns; #57 collapsed them into one call, which makes that
  mistake unrepresentable rather than merely fixed. **The spreadsheet dump added in #56 is what
  catches this class of bug now**: CI diffs a cell dump of the generated `.xlsx` against a
  canonical copy, so a column that moves or disappears fails the integration check. Anything that
  replaces these writers must keep reporting its true end column — and must leave that dump
  unchanged, or explain why the output legitimately differs.
- **Turnover rows are matched to inventory rows by `part` vs. `part_description`** with all
  spaces removed (`_match_key`); the matched entry's **position in the inventory list** is its row
  on the sheet. `write_inventory()` writes one row per entry starting at `FIRST_DATA_ROW`
  regardless of which columns are checked, so `append_turnover_report()` derives the row with
  `enumerate(inventory, start=FIRST_DATA_ROW)` rather than reading it back off the entry. The
  entry used to carry a `row_written_to` field instead, assigned from inside each checked column's
  branch; with no inventory column checked nothing assigned it and every turnover row overwrote
  the header (#55). Deriving the row removes the failure mode rather than guarding it — **do not
  reintroduce a stored row.** The header row is row 0 of the spreadsheet dump, so a writer that
  lands on it now fails CI rather than shipping.
- **The join index maps a part to a *list* of rows, not to one row.** The nested loop it replaced
  had no `break`, so a part the inventory lists twice received the turnover data on both of its
  rows. A `dict[str, int]` would be faster to write and would silently drop one of them. The index
  is also rebuilt per report rather than cached from `write_inventory()`, so
  `append_turnover_report()` does not depend on the order the two were called in.
- **The three formats are built once, in `__init__`.** `add_format()` inside a loop is what the
  module before #57 did, leaving roughly 1,200 duplicate `Format` objects in a 600-row report.
  `scripts/dump_workbooks.py` keys its style codes on the `(bold, font size, fill)` triple these
  three produce, so changing a format spec means changing `STYLE_CODES` with it — or every cell
  dumps as `?` and the integration check fails wholesale.
- **`get_selected_columns()` wraps every value in `bool()`.** The writers only test truthiness
  now, so this is no longer what stands between a `tk.BooleanVar` and a dropped column; it matters
  because the dict is typed `dict[str, bool]` and the settings layer round-trips it through
  `str()`.
- **The settings table stores only text, so a persisted boolean is compared, never `bool()`-ed.**
  `SettingsRepository.get_all_settings()` hands back raw strings and `bool("False")` is `True`, so
  converting a stored column flag would silently check every box. `_restore_column()` compares
  against `str(True)` instead. The same applies in reverse: the font size is `str()`-ed on the way
  out and `int()`-ed on the way back.
- **An absent column setting means "never persisted", not "unchecked".** `_restore_column()` falls
  back to the column's own `always` default when the key is missing, so a column newly added to
  `columns.py` behaves like a first launch rather than arriving pre-unchecked. A column marked
  `always` is forced checked regardless of what is stored, since it has no checkbox the user could
  have unchecked it with.
