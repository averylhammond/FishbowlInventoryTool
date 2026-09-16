---
paths:
  - "source/spreadsheetDriver.py"
  - "source/columns.py"
---

# Spreadsheet output and the column scheme

`spreadsheetDriver.py` is all `xlsxwriter` output — **module-level functions, not a class** —
receiving the already-open workbook from `InventoryAppFileIO`:

| Function | Does |
| --- | --- |
| `setupMainSpreadsheet` | The entry point for one inventory report: delegates the header to `setupSpreadsheetInventoryHeader` and each row to `writeInventoryEntryToSpreadsheet`, and reports back where the inventory columns ended |
| `setupSpreadsheetInventoryHeader` | Writes row 0 for the checked inventory columns |
| `writeInventoryEntryToSpreadsheet` | One inventory row's cells, per-cell styling included |
| `appendTurnoverToSpreadsheet` | One turnover report: its header, its pre-fill, and the join onto the inventory rows |
| `setupSpreadsheetTurnoverHeader` | Writes that report's headers and **returns the first free column after them** |
| `writeTurnoverEntryToSpreadsheet` | One turnover row's cells |
| `formatTurnoverRow` | Styles a turnover column *and* writes the literal `'N/A'` into every data row of it, so a part with no turnover row reads as missing rather than blank |
| `FIRST_DATA_ROW` | `= 1`, at the top of the module: the single definition of where data begins |

## The column scheme

The scheme is checkbox-driven: every header and row writer walks the same `checkboxDict` keys in
the same order, writing a column and incrementing the column index only when that box is checked.
Inventory keys are plain (`"Part"`, `"OnHand"`); turnover keys are `t`-prefixed (`"tUnits Sold"`,
`"tTO Rate"` — note `"tDescription"` has no space after the prefix). **Keep the header writer and
the row writer in lockstep** — both must consult identical keys in identical order or columns and
data will desync.

`source/columns.py` holds the `(key, label, always, tooltip)` record — a frozen `Column`
dataclass plus `INVENTORY_COLUMNS`, `TURNOVER_COLUMNS`, `ALL_COLUMNS`, `COLUMN_KEYS` and
`all_columns_selected()`. The tuple a `Column` lives in *is* its GUI section. It imports only
`dataclasses`, which is what lets the headless path reach `all_columns_selected()` without
loading tkinter.

**`columns.py` is the single source of truth for the GUI only — not for the spreadsheet.**
`InventoryAppDisplay` builds its checkbox grid by iterating `ALL_COLUMNS`, but
`spreadsheetDriver.py` does not import `source.columns` at all: all 16 keys are string literals
spread across four functions, and the header text is hardcoded a second time. So the two already
disagree on wording — the sheet says `"OnHand"`, `"NotAvailable"`, `"DropShip"`, `"OnOrder"` and
`"TO Description"` where `columns.py` labels read `"On Hand"`, `"Not Available"`, `"Drop Ship"`,
`"On Order"` and `"Description"`, and the four numeric turnover headers append the report's
filename, a concept `columns.py` cannot express.

**Adding a column therefore means editing `columns.py` *and* two functions in
`spreadsheetDriver.py`** (the header writer and the row writer for that section). A column added
only to `columns.py` gets a checkbox and a settings key and is then silently never written —
no error, no missing-key failure. **#57 rewrites these writers as a data-driven
`spreadsheet_writer.py` and makes `columns.py` the real single source of truth**; until it lands,
do not write guidance that assumes it already is. That rewrite touches every cell-writing path
here, so check it against the spreadsheet dump (`rules/ci.md`) rather than the results file: the
dump is the only thing in CI that sees the columns it produces.

## Rules that are easy to break

- **A turnover report is as many columns wide as the user checked, so the caller must never guess
  its stride.** `setupSpreadsheetTurnoverHeader` returns the first free column and
  `process_inventory()` assigns it (`nextCol = endCol`), exactly as `setupMainSpreadsheet` reports
  back where the inventory columns ended. It used to advance by `+= 1`, which silently overwrote
  all but the first column of every turnover report but the last (#53) — a data-loss bug the
  results file cannot see, since it is built from the entry objects and never from the sheet.
  **The spreadsheet dump added in #56 is what catches this class of bug now**: CI diffs a cell
  dump of the generated `.xlsx` against a canonical copy, so a column that moves or disappears
  fails the integration check. Whatever replaces these writers must keep reporting its true end
  column — and must leave that dump unchanged, or explain why the output legitimately differs.
- **Turnover rows are matched to inventory rows by `part` vs. `part_description`** with all
  spaces removed; the matched entry's **position in the inventory list** is its row on the sheet.
  `setupMainSpreadsheet` writes one row per entry starting at `FIRST_DATA_ROW` regardless of
  which columns are checked, so `appendTurnoverToSpreadsheet` derives the row with
  `enumerate(inventory, start=FIRST_DATA_ROW)` rather than reading it back off the entry. The
  inventory writer, the turnover pre-fill and the turnover join all measure from `FIRST_DATA_ROW`,
  and row 0 is the header. The entry used to carry a `row_written_to` field instead, assigned
  from inside each checked column's branch; with no inventory column checked nothing assigned it
  and every turnover row overwrote the header (#55). Deriving the row removes the failure mode
  rather than guarding it — **do not reintroduce a stored row.** The header row is row 0 of the
  spreadsheet dump, so a writer that lands on it now fails CI rather than shipping.
- **`get_selected_columns()` wraps every value in `bool()`, and that is load-bearing.** The
  writers test `if checkboxDict["Part"] == True`, which a `tk.BooleanVar` fails — the column
  would be silently dropped from the report rather than raising.
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
- `writeInventoryEntryToSpreadsheet` still annotates its `row` parameter as `str` and calls
  `int()` on it, fed by `str(row)` from `setupMainSpreadsheet`. That round trip is deliberate only
  in the sense that nobody has untangled it yet; #57 removes it. Do not add more of the same.
