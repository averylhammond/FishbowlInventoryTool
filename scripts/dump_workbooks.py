"""
Dumps every generated .xlsx into a deterministic text file so CI can diff the
spreadsheet the app actually produced, not just the results-file parser trace.

The results file is built from the InventoryEntry/TurnoverEntry objects and never
touches the workbook, so a spreadsheet-only bug (a turnover report written over
another's columns, a pre-fill that stops short of the last row) leaves it unchanged.
This dump closes that hole: one line per sheet row, each cell rendered as
<style code>:<value>, diffed against the canonical copy in the private
automated-inventory-testing submodule.

Test tooling, not application code: it is never imported by the app, openpyxl is
pinned in requirements/dev.txt only, and the output lands in the gitignored logs/
directory because it holds customer part data.

Usage (from the project root, after a headless run):
    python scripts/dump_workbooks.py
"""

import sys
from pathlib import Path

import openpyxl
from openpyxl.cell.cell import Cell
from openpyxl.worksheet.worksheet import Worksheet

# Directory the app writes its workbooks to, and where the dump is written. Kept as
# literals rather than imported from source/constants.py so this script stays
# independent of the application package it is checking.
WORKBOOK_DIR = Path()
DUMP_PATH = Path("logs") / "spreadsheet_dump.txt"

# The three formats SpreadsheetWriter builds, keyed by the (bold, font size, fill
# color) triple each produces, and the one-letter code each is dumped as. A cell whose
# styling matches none of them dumps as UNKNOWN_STYLE, so a formatting regression shows
# up as a diff rather than passing unnoticed.
STYLE_CODES = {
    (True, 16.0, "FFF0F0F0"): "H",  # Header row
    (False, 12.0, "FFF0F0F0"): "E",  # Even-numbered data row
    (False, 12.0, "FFE6F0FF"): "O",  # Odd-numbered data row
}
UNKNOWN_STYLE = "?"

# Rendered in place of a cell that is both empty and unstyled, so every row lines up
# column-for-column with every other row in the dump
EMPTY_CELL = "-"


def style_code(cell: Cell) -> str:
    """
    Classifies a cell's formatting into the one-letter code it is dumped as.

    Args:
        cell: The cell whose font and fill are inspected

    Returns:
        The matching code from STYLE_CODES, or UNKNOWN_STYLE if the cell carries a
        combination the spreadsheet writers are not known to produce
    """

    # openpyxl reports an unfilled cell's color as None; normalize it so an unstyled
    # cell is one lookup miss rather than a special case
    fill = cell.fill.fgColor.rgb if cell.fill is not None else None
    key = (bool(cell.font.bold), cell.font.size, fill if isinstance(fill, str) else None)

    return STYLE_CODES.get(key, UNKNOWN_STYLE)


def render_value(value: object) -> str:
    """
    Renders a cell's value into a form that is stable across platforms and safe to
    put in a pipe-separated line.

    Args:
        value: The value openpyxl read out of the cell

    Returns:
        The value as text, with the separator and any line breaks escaped
    """

    # repr() keeps an int distinguishable from a float of the same magnitude, which a
    # column of quantities would otherwise hide
    text = value if isinstance(value, str) else repr(value)

    return text.replace("\\", "\\\\").replace("|", r"\|").replace("\n", "\n")


def render_cell(cell: Cell) -> str:
    """
    Renders one cell as the "<style code>:<value>" pair the dump is made of.

    Args:
        cell: The cell to render

    Returns:
        The rendered pair, or EMPTY_CELL if the cell holds no value and no styling
    """

    code = style_code(cell)

    if cell.value is None:
        # A blank cell that still carries a format is worth dumping: that is exactly
        # what a turnover pre-fill looks like when it has lost its value
        return EMPTY_CELL if code == UNKNOWN_STYLE else f"{code}:"

    return f"{code}:{render_value(cell.value)}"


def dump_worksheet(worksheet: Worksheet) -> list[str]:
    """
    Dumps one worksheet as its dimensions followed by a line per row.

    Args:
        worksheet: The worksheet to dump

    Returns:
        The lines describing the sheet, without trailing newlines
    """

    lines = [f"dims: {worksheet.max_row} rows x {worksheet.max_column} cols"]

    # Row 0 of the sheet is openpyxl's row 1, and it holds the headers; label it so a
    # diff in the column layout is obvious at a glance
    for index, row in enumerate(
        worksheet.iter_rows(min_row=1, max_row=worksheet.max_row, max_col=worksheet.max_column)
    ):
        label = "hdr" if index == 0 else "row"
        cells = " | ".join(render_cell(cell) for cell in row)
        lines.append(f"{label} {index:>5} | {cells}")

    return lines


def dump_workbooks(workbook_dir: Path) -> list[str]:
    """
    Dumps every workbook in a directory, in filename order.

    Args:
        workbook_dir: The directory holding the generated .xlsx files

    Returns:
        The lines of the complete dump, without trailing newlines
    """

    lines = []

    # Sorted by name so the dump is in the same order on every platform, the same
    # reason the file listings in InventoryAppFileIO sort
    for path in sorted(workbook_dir.glob("*.xlsx"), key=lambda p: p.name):
        workbook = openpyxl.load_workbook(path)

        for worksheet in workbook.worksheets:
            lines.append(f"=== {path.name} ({worksheet.title}) ===")
            lines.extend(dump_worksheet(worksheet))

        workbook.close()

    return lines


def main() -> int:
    """
    Writes the dump of every generated workbook to DUMP_PATH.

    Returns:
        The process exit status: 0 on success, 1 if no workbook was found
    """

    lines = dump_workbooks(WORKBOOK_DIR)

    # An empty dump would diff clean against an empty fixture, turning a run that
    # produced nothing into a passing check
    if not lines:
        print(f"::error::No .xlsx files found in {WORKBOOK_DIR.resolve()}")
        return 1

    DUMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    DUMP_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Report the size, never the contents: this dump holds private customer data and
    # must not reach a CI log
    print(f"Wrote {len(lines)} lines to {DUMP_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
