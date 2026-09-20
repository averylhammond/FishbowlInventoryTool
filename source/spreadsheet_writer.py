import xlsxwriter

from source.columns import INVENTORY_COLUMNS, TURNOVER_COLUMNS, Column
from source.InventoryEntry import InventoryEntry
from source.TurnoverEntry import TurnoverEntry

# Row 0 of the worksheet holds the column headers, so the inventory data starts on
# the row below it. Every writer that addresses a data row measures from here.
HEADER_ROW = 0
FIRST_DATA_ROW = 1

# Written into every data row of a turnover column before that report's own rows are
# joined on, so a part the report never mentions reads as missing rather than blank
MISSING_TURNOVER_VALUE = "N/A"

# The three formats every cell carries, built once per workbook in __init__. #F0F0F0
# is a light gray and #E6F0FF a light blue; the module this replaced had the two
# labelled the other way around in all three of its copies.
HEADER_FORMAT = {
    "valign": "vcenter",
    "align": "center",
    "bold": True,
    "font_size": 16,
    "bg_color": "#F0F0F0",  # Light gray
    "border": 1,
}
EVEN_ROW_FORMAT = {
    "valign": "vcenter",
    "font_size": 12,
    "bg_color": "#F0F0F0",  # Light gray
    "border": 1,
}
ODD_ROW_FORMAT = {
    "valign": "vcenter",
    "font_size": 12,
    "bg_color": "#E6F0FF",  # Light blue
    "border": 1,
}


def _match_key(part: str) -> str:
    """
    Normalizes a part name into the form the two reports are matched on, since the
    same part is spaced differently on each

    Args:
        part: The part name as one of the two reports spells it

    Returns:
        The name with every space removed
    """

    return part.replace(" ", "")


# SpreadsheetWriter writes one workbook's single worksheet: the header row, the
# inventory rows, and one block of columns per turnover report. Every writer walks
# the column tuples in source/columns.py, so a column added there is emitted here
# without this module being touched.
class SpreadsheetWriter:

    def __init__(self, workbook: xlsxwriter.Workbook) -> None:
        """
        Initializes the SpreadsheetWriter object, opening the single worksheet the
        report occupies and building the three cell formats it uses

        Args:
            workbook: The already-open workbook to write into, created by
                InventoryAppFileIO
        """

        # The workbook every write lands in, and the one worksheet it holds. Opened
        # here so no writer has to look the sheet back up by name.
        self.workbook = workbook
        self.worksheet = workbook.add_worksheet()

        # Built once per workbook rather than per row: a Format is an immutable
        # style, so one object serves every cell that carries it
        self.header_format = workbook.add_format(HEADER_FORMAT)
        self.even_format = workbook.add_format(EVEN_ROW_FORMAT)
        self.odd_format = workbook.add_format(ODD_ROW_FORMAT)

    def write_inventory(
        self, inventory: list[InventoryEntry], checkbox_dict: dict[str, bool]
    ) -> int:
        """
        Writes the inventory section: a header for every checked inventory column,
        then one row per entry below it

        Args:
            inventory: The inventory entries to write, one row each in list order
            checkbox_dict: Column selection deciding which columns are emitted

        Returns:
            The first free column after the inventory section, where the first
            turnover report starts
        """

        columns = self._checked_columns(INVENTORY_COLUMNS, checkbox_dict)

        self._write_header(columns, 0)

        # An entry's position in the list is the row it occupies, which is what the
        # turnover join measures from too
        for row, entry in enumerate(inventory, start=FIRST_DATA_ROW):
            self._write_entry_row(row, 0, columns, entry)

        # Taken from the columns the header was written from, not from the last row
        # written, so an empty inventory still reports the width the headers occupy
        return len(columns)

    def append_turnover_report(
        self,
        turnover: list[TurnoverEntry],
        inventory: list[InventoryEntry],
        start_col: int,
        checkbox_dict: dict[str, bool],
        report: str,
    ) -> int:
        """
        Appends one turnover report's columns to the right of everything already
        written: its headers, its placeholder pre-fill, and its rows joined onto the
        inventory rows the same parts already occupy

        Args:
            turnover: The turnover entries read out of this report
            inventory: The inventory entries, whose list order is their row order
            start_col: The first free column, where this report's columns begin
            checkbox_dict: Column selection deciding which columns are emitted
            report: The report's name, appended to each of its column headers

        Returns:
            The first free column after this report, where the next one starts
        """

        columns = self._checked_columns(TURNOVER_COLUMNS, checkbox_dict)

        self._write_header(columns, start_col, suffix=f" {report}")
        self._prefill(columns, start_col, len(inventory))

        # A part may occupy more than one inventory row and each of them takes this
        # report's data, so the index holds every row a part was written to. Built
        # here rather than carried over from write_inventory, which would make this
        # method depend on the order the two were called in.
        rows_by_part: dict[str, list[int]] = {}
        for row, entry in enumerate(inventory, start=FIRST_DATA_ROW):
            rows_by_part.setdefault(_match_key(entry.part), []).append(row)

        # Overwrites the placeholder on the rows this report does mention, leaving
        # the rest reading as missing
        for entry in turnover:
            for row in rows_by_part.get(_match_key(entry.part_description), []):
                self._write_entry_row(row, start_col, columns, entry)

        return start_col + len(columns)

    def _checked_columns(
        self, columns: tuple[Column, ...], checkbox_dict: dict[str, bool]
    ) -> tuple[Column, ...]:
        """
        Filters one section's columns down to the ones the user checked, in
        spreadsheet order. The header writer and the row writer are then handed the
        same tuple, which is what keeps them in step.

        Args:
            columns: A section's columns, in the order the spreadsheet emits them
            checkbox_dict: Column selection deciding which columns are emitted

        Returns:
            The checked columns, in the same order
        """

        return tuple(column for column in columns if checkbox_dict[column.key])

    def _write_header(
        self, columns: tuple[Column, ...], start_col: int, suffix: str = ""
    ) -> None:
        """
        Writes the header row for one section. The inventory section takes no
        suffix; a turnover report takes its own name, since several reports sit side
        by side under otherwise identical titles.

        Args:
            columns: The checked columns this section emits, in order
            start_col: The column this section's first header is written to
            suffix: Text appended to every header in this section
        """

        for col, column in enumerate(columns, start=start_col):
            self.worksheet.write(
                HEADER_ROW, col, f"{column.label}{suffix}", self.header_format
            )

    def _write_entry_row(
        self,
        row: int,
        start_col: int,
        columns: tuple[Column, ...],
        entry: InventoryEntry | TurnoverEntry,
    ) -> None:
        """
        Writes one entry's cells across a section's columns, reading each value off
        the entry by the attribute its column names

        Args:
            row: The worksheet row this entry occupies
            start_col: The column this section's first cell is written to
            columns: The checked columns this section emits, in order
            entry: The inventory or turnover entry to read the values from
        """

        row_format = self._row_format(row)

        for col, column in enumerate(columns, start=start_col):
            self.worksheet.write(row, col, getattr(entry, column.field), row_format)

    def _prefill(
        self, columns: tuple[Column, ...], start_col: int, row_count: int
    ) -> None:
        """
        Fills every data row of a turnover report's columns with the placeholder,
        before the report's own rows are written over the ones it mentions

        Args:
            columns: The checked columns this report emits, in order
            start_col: The column this report's first cell is written to
            row_count: How many data rows the inventory occupies
        """

        for row in range(FIRST_DATA_ROW, FIRST_DATA_ROW + row_count):
            row_format = self._row_format(row)

            for col in range(start_col, start_col + len(columns)):
                self.worksheet.write(row, col, MISSING_TURNOVER_VALUE, row_format)

    def _row_format(self, row: int) -> xlsxwriter.format.Format:
        """
        Picks the fill one data row carries, so the banding that makes a wide report
        readable holds across every section of the sheet

        Args:
            row: The worksheet row the cells are written to

        Returns:
            The format that row's cells are written with
        """

        return self.even_format if row % 2 == 0 else self.odd_format
