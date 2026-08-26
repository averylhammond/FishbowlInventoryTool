import pytest
import xlsxwriter
from xlsxwriter.worksheet import Worksheet
from unittest.mock import patch, call, MagicMock

from source.spreadsheetDriver import *
from source.InventoryEntry import InventoryEntry
from source.TurnoverEntry import TurnoverEntry


###############################################################################
###                    spreadsheetDriver -> Test Fixtures                   ###
###############################################################################
# Every checkbox key the spreadsheet writers consult, in the order they walk them.
# The canonical list lives in source/columns.py; it is duplicated here rather than
# imported so that a reordering there fails this file's layout assertions loudly
# instead of silently following along. The test at the bottom of this file is what
# keeps the two provably identical.
# Note the irregular turnover keys: "tDescription" has no space, the rest do.
COLUMN_KEYS = (
    "Part",
    "Description",
    "UOM",
    "OnHand",
    "Allocated",
    "NotAvailable",
    "DropShip",
    "Available",
    "OnOrder",
    "Committed",
    "Short",
    "tDescription",
    "tUnits Sold",
    "tAvg QOH",
    "tAvg TO Days",
    "tTO Rate",
)


def checkboxes(overrides: dict = None, default: bool = True) -> dict:
    """
    Builds the checkbox state dictionary the writers read, with every column
    checked unless a test says otherwise.

    Args:
        overrides (dict): The keys to set against the default, e.g. {"UOM": False}
        default (bool): The state every key not named in overrides takes

    Returns:
        dict: A checkbox state dictionary covering every column key
    """

    state = {key: default for key in COLUMN_KEYS}
    state.update(overrides or {})
    return state


def build_inventory_entry(part: str = "PART-A") -> InventoryEntry:
    """
    Builds a fully populated inventory entry. Every quantity differs from every
    other, so a column that drifts out of step with its data shows up as a wrong
    value rather than passing by coincidence.

    Args:
        part (str): The part number, which is also what turnover rows match on

    Returns:
        InventoryEntry: An entry with a distinct value in each field
    """

    return InventoryEntry(part, "WIDGET ONE", "ea", 100, 5, 1, 2, 95, 20, 7, 3)


def build_turnover_entry(part_description: str = "PART-A") -> TurnoverEntry:
    """
    Builds a fully populated turnover entry, with a distinct value in each field
    for the same reason as the inventory entry above.

    Args:
        part_description (str): The part the entry is matched to an inventory row by

    Returns:
        TurnoverEntry: An entry with a distinct value in each field
    """

    return TurnoverEntry(part_description, 42, 7.5, 30, 1.25)


def written_cells(worksheet: MagicMock) -> list:
    """
    Reduces the cells written to the worksheet to the position and value of each,
    dropping the format so a test can assert on the layout alone.

    Args:
        worksheet (unittest.mock.MagicMock): The worksheet the writes were recorded on

    Returns:
        list: One (row, column, value) tuple per cell, in the order written
    """

    return [tuple(write.args[:3]) for write in worksheet.write.call_args_list]


def written_formats(worksheet: MagicMock) -> list:
    """
    Reads back the format each cell was written with. The workbook fixture hands
    out every format as the specification dictionary it was built from, so these
    are the styling options themselves.

    Args:
        worksheet (unittest.mock.MagicMock): The worksheet the writes were recorded on

    Returns:
        list: One format specification dictionary per cell, in the order written
    """

    return [write.args[3] for write in worksheet.write.call_args_list]


@pytest.fixture
def worksheet():
    """
    Test fixture to set up the worksheet that cells are written to. It is a mock so
    a test can read back the exact cells that were written without ever creating a
    real .xlsx file.
    """

    return MagicMock(spec=Worksheet)


@pytest.fixture
def workbook(worksheet):
    """
    Test fixture to set up the workbook that formats are built from and the
    worksheet is looked up through. Formats are handed back as the specification
    dictionary they were requested with, since a bare mock would return one
    identical object for every call and no test could tell two formats apart.

    Args:
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    workbook = MagicMock(spec=xlsxwriter.Workbook)
    workbook.add_format.side_effect = lambda spec: dict(spec)
    workbook.get_worksheet_by_name.return_value = worksheet
    workbook.add_worksheet.return_value = worksheet

    return workbook


###############################################################################
###              Tests spreadsheetDriver -> formatTurnoverRow()             ###
###############################################################################
# An empty report, a single row, the row count the pre-fill was once hardcoded to,
# and a report longer than that count - the case the hardcoded limit truncated.
@pytest.mark.parametrize("row_count", [0, 1, 618, 622])
def test_format_turnover_row_fills_every_data_row_with_not_available(
    row_count, workbook, worksheet
):
    """
    Tests that formatTurnoverRow() pre-fills the column with a placeholder in every
    data row of the report it was given, however long that report is, so a part the
    turnover report never mentions reads as N/A rather than as an empty cell. The
    header row is left alone for the column title.

    Args:
        row_count (int): The number of inventory data rows the report holds
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # A turnover column is prepared before any turnover data is written to it
    formatTurnoverRow(workbook, 3, row_count)

    # Every row below the header holds the placeholder, down to the last one
    workbook.get_worksheet_by_name.assert_called_once_with("Sheet1")
    assert written_cells(worksheet) == [
        (row, 3, "N/A") for row in range(1, row_count + 1)
    ]


def test_format_turnover_row_alternates_the_row_fill_colors(workbook, worksheet):
    """
    Tests that formatTurnoverRow() gives odd and even rows different fills, so the
    placeholder column keeps the banding that makes a wide report readable.

    Args:
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # A turnover column is prepared
    formatTurnoverRow(workbook, 3, 4)

    # The first two rows written carry the two alternating fills
    formats = written_formats(worksheet)
    assert formats[0]["bg_color"] == "#E6F0FF"
    assert formats[1]["bg_color"] == "#F0F0F0"


###############################################################################
###       Tests spreadsheetDriver -> setupSpreadsheetInventoryHeader()      ###
###############################################################################
def test_setup_spreadsheet_inventory_header_writes_every_checked_column(
    workbook, worksheet
):
    """
    Tests that setupSpreadsheetInventoryHeader() titles every inventory column in
    the header row, in the order the row writer walks the same checkbox keys.

    Args:
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The user leaves every inventory column checked
    setupSpreadsheetInventoryHeader(workbook, worksheet, checkboxes())

    # Each column is titled in declaration order, starting at the first column
    assert written_cells(worksheet) == [
        (0, 0, "Part"),
        (0, 1, "Description"),
        (0, 2, "UOM"),
        (0, 3, "OnHand"),
        (0, 4, "Allocated"),
        (0, 5, "NotAvailable"),
        (0, 6, "DropShip"),
        (0, 7, "Available"),
        (0, 8, "OnOrder"),
        (0, 9, "Committed"),
        (0, 10, "Short"),
    ]


def test_setup_spreadsheet_inventory_header_skips_unchecked_columns(
    workbook, worksheet
):
    """
    Tests that an unchecked column is left out entirely rather than written as a
    blank, and that the columns after it close the gap instead of holding their
    original position.

    Args:
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The user clears two columns from the middle of the report
    setupSpreadsheetInventoryHeader(
        workbook, worksheet, checkboxes({"UOM": False, "DropShip": False})
    )

    # The remaining columns stay contiguous, each shifting left past the gap
    assert written_cells(worksheet) == [
        (0, 0, "Part"),
        (0, 1, "Description"),
        (0, 2, "OnHand"),
        (0, 3, "Allocated"),
        (0, 4, "NotAvailable"),
        (0, 5, "Available"),
        (0, 6, "OnOrder"),
        (0, 7, "Committed"),
        (0, 8, "Short"),
    ]


def test_setup_spreadsheet_inventory_header_writes_nothing_when_nothing_is_checked(
    workbook, worksheet
):
    """
    Tests that a header row is left empty when the user checks no columns at all,
    rather than falling back to writing some default set.

    Args:
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # No column is checked
    setupSpreadsheetInventoryHeader(workbook, worksheet, checkboxes(default=False))

    # Not a single header cell is written
    worksheet.write.assert_not_called()


def test_setup_spreadsheet_inventory_header_styles_the_header_row(
    workbook, worksheet
):
    """
    Tests that the header titles are written in the bold, centered, larger format
    that separates them from the data rows beneath.

    Args:
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The header row is written
    setupSpreadsheetInventoryHeader(workbook, worksheet, checkboxes())

    # Every title carries the same bold, centered header format
    header_format = written_formats(worksheet)[0]
    assert header_format["bold"] is True
    assert header_format["align"] == "center"
    assert header_format["font_size"] == 16
    assert all(
        cell_format == header_format for cell_format in written_formats(worksheet)
    )


###############################################################################
###       Tests spreadsheetDriver -> setupSpreadsheetTurnoverHeader()       ###
###############################################################################
@patch("source.spreadsheetDriver.formatTurnoverRow")
def test_setup_spreadsheet_turnover_header_labels_each_column_with_the_filename(
    _mock_format_row, workbook, worksheet
):
    """
    Tests that setupSpreadsheetTurnoverHeader() titles each turnover column from the
    first free column onward, naming the report each column came from so several
    turnover reports can sit side by side in one sheet.

    Args:
        _mock_format_row (unittest.mock.MagicMock): Mocks the placeholder pre-fill
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # A turnover report is appended after the eleven inventory columns
    setupSpreadsheetTurnoverHeader(
        workbook, checkboxes(), 11, "Turnover_Jan2024", 300
    )

    # Each column is titled with the report it holds, except the shared description
    workbook.get_worksheet_by_name.assert_called_once_with("Sheet1")
    assert written_cells(worksheet) == [
        (0, 11, "TO Description"),
        (0, 12, "Units Sold Turnover_Jan2024"),
        (0, 13, "Avg QOH Turnover_Jan2024"),
        (0, 14, "Avg TO Days Turnover_Jan2024"),
        (0, 15, "TO Rate Turnover_Jan2024"),
    ]


@patch("source.spreadsheetDriver.formatTurnoverRow")
def test_setup_spreadsheet_turnover_header_skips_unchecked_columns(
    _mock_format_row, workbook, worksheet
):
    """
    Tests that an unchecked turnover column is left out and the columns after it
    close the gap, matching how the turnover row writer walks the same keys.

    Args:
        _mock_format_row (unittest.mock.MagicMock): Mocks the placeholder pre-fill
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The user wants only the numbers, and not the average quantity on hand
    setupSpreadsheetTurnoverHeader(
        workbook,
        checkboxes({"tDescription": False, "tAvg QOH": False}),
        11,
        "Turnover_Jan2024",
        300,
    )

    # The remaining columns stay contiguous from the first free column
    assert written_cells(worksheet) == [
        (0, 11, "Units Sold Turnover_Jan2024"),
        (0, 12, "Avg TO Days Turnover_Jan2024"),
        (0, 13, "TO Rate Turnover_Jan2024"),
    ]


@patch("source.spreadsheetDriver.formatTurnoverRow")
def test_setup_spreadsheet_turnover_header_prefills_each_column_written(
    mock_format_row, workbook, worksheet
):
    """
    Tests that every turnover column it titles is also pre-filled with placeholders,
    so a part missing from the turnover report is not left as a run of blank cells.

    Args:
        mock_format_row (unittest.mock.MagicMock): Mocks the placeholder pre-fill
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # A turnover report is appended after the eleven inventory columns
    setupSpreadsheetTurnoverHeader(
        workbook, checkboxes(), 11, "Turnover_Jan2024", 300
    )

    # Each of the five columns is pre-filled down the whole report as it is titled
    assert mock_format_row.call_args_list == [
        call(workbook, 11, 300),
        call(workbook, 12, 300),
        call(workbook, 13, 300),
        call(workbook, 14, 300),
        call(workbook, 15, 300),
    ]


# The whole turnover group, a middle-sized selection, and a single column - the
# width of a report is whatever the user checked, so the caller cannot assume one.
@pytest.mark.parametrize(
    "unchecked, width",
    [
        ({}, 5),
        ({"tDescription": False, "tAvg QOH": False}, 3),
        (
            {
                "tDescription": False,
                "tUnits Sold": False,
                "tAvg QOH": False,
                "tAvg TO Days": False,
            },
            1,
        ),
    ],
)
@patch("source.spreadsheetDriver.formatTurnoverRow")
def test_setup_spreadsheet_turnover_header_returns_the_first_free_column(
    _mock_format_row, unchecked, width, workbook, worksheet
):
    """
    Tests that setupSpreadsheetTurnoverHeader() reports back the column after the
    last one it filled, however many turnover columns the user checked. The caller
    has no other way to know how wide a report turned out to be, and a report is
    between one and five columns wide.

    Args:
        _mock_format_row (unittest.mock.MagicMock): Mocks the placeholder pre-fill
        unchecked (dict): The turnover columns the user left out of this report
        width (int): The number of columns the remaining selection occupies
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # A turnover report is appended after the eleven inventory columns
    next_col = setupSpreadsheetTurnoverHeader(
        workbook, checkboxes(unchecked), 11, "Turnover_Jan2024", 300
    )

    # The columns run contiguously from the first free one, and the value handed
    # back is the next one along
    assert [cell[1] for cell in written_cells(worksheet)] == list(range(11, 11 + width))
    assert next_col == 11 + width


@patch("source.spreadsheetDriver.formatTurnoverRow")
def test_setup_spreadsheet_turnover_header_places_two_reports_side_by_side(
    _mock_format_row, workbook, worksheet
):
    """
    Tests that threading one report's returned column into the next lays the two
    reports out side by side rather than the second overwriting the first. A caller
    advancing by a fixed column instead would leave the first report with only its
    leftmost column and two "TO Description" titles in the header row.

    Args:
        _mock_format_row (unittest.mock.MagicMock): Mocks the placeholder pre-fill
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The second report starts wherever the first one reported that it ended
    next_col = setupSpreadsheetTurnoverHeader(
        workbook, checkboxes(), 11, "Turnover_Q3-2023", 300
    )
    setupSpreadsheetTurnoverHeader(
        workbook, checkboxes(), next_col, "Turnover_Q1-2024", 300
    )

    # Both reports keep a complete set of columns, and none is written to twice
    assert written_cells(worksheet) == [
        (0, 11, "TO Description"),
        (0, 12, "Units Sold Turnover_Q3-2023"),
        (0, 13, "Avg QOH Turnover_Q3-2023"),
        (0, 14, "Avg TO Days Turnover_Q3-2023"),
        (0, 15, "TO Rate Turnover_Q3-2023"),
        (0, 16, "TO Description"),
        (0, 17, "Units Sold Turnover_Q1-2024"),
        (0, 18, "Avg QOH Turnover_Q1-2024"),
        (0, 19, "Avg TO Days Turnover_Q1-2024"),
        (0, 20, "TO Rate Turnover_Q1-2024"),
    ]


@patch("source.spreadsheetDriver.formatTurnoverRow")
def test_setup_spreadsheet_turnover_header_returns_its_starting_column_when_nothing_is_checked(
    _mock_format_row, workbook, worksheet
):
    """
    Tests that a report with no turnover column checked leaves the cursor where it
    found it, so the columns after it are not pushed across by an empty report

    Args:
        _mock_format_row (unittest.mock.MagicMock): Mocks the placeholder pre-fill
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The user wants the inventory columns only
    next_col = setupSpreadsheetTurnoverHeader(
        workbook,
        checkboxes(
            {
                "tDescription": False,
                "tUnits Sold": False,
                "tAvg QOH": False,
                "tAvg TO Days": False,
                "tTO Rate": False,
            }
        ),
        11,
        "Turnover_Jan2024",
        300,
    )

    assert written_cells(worksheet) == []
    assert next_col == 11


###############################################################################
###      Tests spreadsheetDriver -> writeInventoryEntryToSpreadsheet()      ###
###############################################################################
def test_write_inventory_entry_writes_every_checked_field(workbook, worksheet):
    """
    Tests that writeInventoryEntryToSpreadsheet() writes each field of the entry
    across its row in the same order the header writer titled the columns, and
    reports back the first column left free for turnover data.

    Args:
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # An entry is written to the first data row with every column checked
    next_col = writeInventoryEntryToSpreadsheet(
        workbook, worksheet, "1", build_inventory_entry(), checkboxes()
    )

    # Every field lands in the column its title was written to
    assert written_cells(worksheet) == [
        (1, 0, "PART-A"),
        (1, 1, "WIDGET ONE"),
        (1, 2, "ea"),
        (1, 3, 100),
        (1, 4, 5),
        (1, 5, 1),
        (1, 6, 2),
        (1, 7, 95),
        (1, 8, 20),
        (1, 9, 7),
        (1, 10, 3),
    ]

    # The eleven inventory columns leave column eleven free
    assert next_col == 11


def test_write_inventory_entry_skips_unchecked_fields(workbook, worksheet):
    """
    Tests that the fields of an unchecked column are left out and the fields after
    it close the gap, so the row stays in step with the header.

    Args:
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The same two columns the header writer test cleared are cleared here
    next_col = writeInventoryEntryToSpreadsheet(
        workbook,
        worksheet,
        "1",
        build_inventory_entry(),
        checkboxes({"UOM": False, "DropShip": False}),
    )

    # The remaining fields stay contiguous, each shifting left past the gap
    assert written_cells(worksheet) == [
        (1, 0, "PART-A"),
        (1, 1, "WIDGET ONE"),
        (1, 2, 100),
        (1, 3, 5),
        (1, 4, 1),
        (1, 5, 95),
        (1, 6, 20),
        (1, 7, 7),
        (1, 8, 3),
    ]

    # Two fewer columns leaves the next free column two lower
    assert next_col == 9


def test_write_inventory_entry_accepts_the_row_number_as_a_string(
    workbook, worksheet
):
    """
    Tests that a row number arriving as a string is converted before use, since the
    caller counts rows as strings and a string row would land the entry in the wrong
    place.

    Args:
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The row number is handed over the way setupMainSpreadsheet supplies it
    writeInventoryEntryToSpreadsheet(
        workbook, worksheet, "7", build_inventory_entry(), checkboxes()
    )

    # Every cell is addressed by the row as a number
    assert all(row == 7 for row, _col, _value in written_cells(worksheet))


def test_write_inventory_entry_writes_nothing_when_nothing_is_checked(
    workbook, worksheet
):
    """
    Tests that an entry with no checked columns writes no cells and reports the
    first column as still free.

    Args:
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # No column is checked
    next_col = writeInventoryEntryToSpreadsheet(
        workbook, worksheet, "1", build_inventory_entry(), checkboxes(default=False)
    )

    # Nothing is written, and no column is claimed
    worksheet.write.assert_not_called()
    assert next_col == 0


def test_write_inventory_entry_alternates_the_row_fill_colors(workbook, worksheet):
    """
    Tests that consecutive entries are given different fills, so the bands of the
    report line up across the whole sheet.

    Args:
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # Two consecutive rows are written with a single column checked
    single_column = checkboxes({"Part": True}, default=False)
    writeInventoryEntryToSpreadsheet(
        workbook, worksheet, "2", build_inventory_entry(), single_column
    )
    writeInventoryEntryToSpreadsheet(
        workbook, worksheet, "3", build_inventory_entry(), single_column
    )

    # The even row and the odd row carry the two alternating fills
    assert written_formats(worksheet)[0]["bg_color"] == "#F0F0F0"
    assert written_formats(worksheet)[1]["bg_color"] == "#E6F0FF"


###############################################################################
###       Tests spreadsheetDriver -> writeTurnoverEntryToSpreadsheet()      ###
###############################################################################
def test_write_turnover_entry_writes_every_checked_field(workbook, worksheet):
    """
    Tests that writeTurnoverEntryToSpreadsheet() writes each field of the entry from
    the given column rightward, in the order the turnover header writer titled them.

    Args:
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # A turnover entry is written onto the row its inventory part occupies
    writeTurnoverEntryToSpreadsheet(
        workbook, worksheet, 4, 11, build_turnover_entry(), checkboxes()
    )

    # Every field lands in the column its title was written to
    assert written_cells(worksheet) == [
        (4, 11, "PART-A"),
        (4, 12, 42),
        (4, 13, 7.5),
        (4, 14, 30),
        (4, 15, 1.25),
    ]


def test_write_turnover_entry_skips_unchecked_fields(workbook, worksheet):
    """
    Tests that the fields of an unchecked turnover column are left out and the
    fields after it close the gap, so the row stays in step with the header.

    Args:
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The same two columns the turnover header writer test cleared are cleared here
    writeTurnoverEntryToSpreadsheet(
        workbook,
        worksheet,
        4,
        11,
        build_turnover_entry(),
        checkboxes({"tDescription": False, "tAvg QOH": False}),
    )

    # The remaining fields stay contiguous from the column given
    assert written_cells(worksheet) == [
        (4, 11, 42),
        (4, 12, 30),
        (4, 13, 1.25),
    ]


def test_write_turnover_entry_writes_an_undefined_average_as_a_blank(
    workbook, worksheet
):
    """
    Tests that the averages the report left blank reach the sheet as blanks rather
    than as zeros, since a part with no turnover has no average rather than an
    average of nothing.

    Args:
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The report gave this part a unit count but no averages
    writeTurnoverEntryToSpreadsheet(
        workbook, worksheet, 4, 11, TurnoverEntry("PART-A", 0), checkboxes()
    )

    # The three averages are written as empty cells
    assert written_cells(worksheet) == [
        (4, 11, "PART-A"),
        (4, 12, 0),
        (4, 13, None),
        (4, 14, None),
        (4, 15, None),
    ]


def test_write_turnover_entry_alternates_the_row_fill_colors(workbook, worksheet):
    """
    Tests that a turnover row picks its fill from the row it sits on, so its banding
    continues the banding of the inventory columns to its left.

    Args:
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # Two consecutive rows are written with a single turnover column checked
    single_column = checkboxes({"tDescription": True}, default=False)
    writeTurnoverEntryToSpreadsheet(
        workbook, worksheet, 4, 11, build_turnover_entry(), single_column
    )
    writeTurnoverEntryToSpreadsheet(
        workbook, worksheet, 5, 11, build_turnover_entry(), single_column
    )

    # The even row and the odd row carry the two alternating fills
    assert written_formats(worksheet)[0]["bg_color"] == "#F0F0F0"
    assert written_formats(worksheet)[1]["bg_color"] == "#E6F0FF"


###############################################################################
###            Tests spreadsheetDriver -> setupMainSpreadsheet()            ###
###############################################################################
@patch("source.spreadsheetDriver.writeInventoryEntryToSpreadsheet")
@patch("source.spreadsheetDriver.setupSpreadsheetInventoryHeader")
def test_setup_main_spreadsheet_writes_the_header_then_one_row_per_entry(
    mock_header, mock_write_entry, workbook, worksheet
):
    """
    Tests that setupMainSpreadsheet() opens a worksheet, titles it, and then writes
    the inventory one entry per row starting below the header.

    Args:
        mock_header (unittest.mock.MagicMock): Mocks the inventory header writer
        mock_write_entry (unittest.mock.MagicMock): Mocks the inventory row writer
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # Three parsed inventory entries are written to a fresh workbook
    inventory = [
        build_inventory_entry("PART-A"),
        build_inventory_entry("PART-B"),
        build_inventory_entry("PART-C"),
    ]
    checkbox_dict = checkboxes()
    setupMainSpreadsheet(workbook, inventory, checkbox_dict)

    # The header takes row zero and the entries follow it in order
    workbook.add_worksheet.assert_called_once_with()
    mock_header.assert_called_once_with(workbook, worksheet, checkbox_dict)
    assert mock_write_entry.call_args_list == [
        call(workbook, worksheet, "1", inventory[0], checkbox_dict),
        call(workbook, worksheet, "2", inventory[1], checkbox_dict),
        call(workbook, worksheet, "3", inventory[2], checkbox_dict),
    ]


@patch("source.spreadsheetDriver.writeInventoryEntryToSpreadsheet")
@patch("source.spreadsheetDriver.setupSpreadsheetInventoryHeader")
def test_setup_main_spreadsheet_returns_the_next_free_column(
    _mock_header, mock_write_entry, workbook
):
    """
    Tests that the column reported back is the one the last row left free, which is
    where the caller starts appending the first turnover report.

    Args:
        _mock_header (unittest.mock.MagicMock): Mocks the inventory header writer
        mock_write_entry (unittest.mock.MagicMock): Mocks the inventory row writer
        workbook (pytest.fixture): Test fixture to create the workbook
    """

    # Every row reports the same eleven inventory columns back
    mock_write_entry.return_value = 11
    next_col = setupMainSpreadsheet(
        workbook, [build_inventory_entry(), build_inventory_entry()], checkboxes()
    )

    # The turnover columns start where the inventory columns ended
    assert next_col == 11


@patch("source.spreadsheetDriver.writeInventoryEntryToSpreadsheet")
@patch("source.spreadsheetDriver.setupSpreadsheetInventoryHeader")
def test_setup_main_spreadsheet_still_writes_a_header_for_an_empty_inventory(
    mock_header, mock_write_entry, workbook, worksheet
):
    """
    Tests that an inventory PDF that yielded no entries still produces a titled
    worksheet, and reports the first column as free since no row claimed any.

    Args:
        mock_header (unittest.mock.MagicMock): Mocks the inventory header writer
        mock_write_entry (unittest.mock.MagicMock): Mocks the inventory row writer
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The inventory came back empty
    checkbox_dict = checkboxes()
    next_col = setupMainSpreadsheet(workbook, [], checkbox_dict)

    # The header is still written, and no row is
    mock_header.assert_called_once_with(workbook, worksheet, checkbox_dict)
    mock_write_entry.assert_not_called()
    assert next_col == 0


###############################################################################
###         Tests spreadsheetDriver -> appendTurnoverToSpreadsheet()        ###
###############################################################################
@patch("source.spreadsheetDriver.writeTurnoverEntryToSpreadsheet")
def test_append_turnover_writes_each_entry_to_its_matching_inventory_row(
    mock_write_entry, workbook, worksheet
):
    """
    Tests that appendTurnoverToSpreadsheet() looks each turnover entry up by part and
    writes it to the row that part already occupies, rather than to the row it holds
    in the turnover report, since the two reports list their parts in their own order.

    Args:
        mock_write_entry (unittest.mock.MagicMock): Mocks the turnover row writer
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # Two parts occupy the first two data rows, and the turnover report lists them
    # the other way around
    inventory = [build_inventory_entry("PART-A"), build_inventory_entry("PART-B")]
    turnover = [build_turnover_entry("PART-B"), build_turnover_entry("PART-A")]

    checkbox_dict = checkboxes()
    appendTurnoverToSpreadsheet(workbook, turnover, inventory, 11, checkbox_dict)

    # Each entry follows its part to that part's row, in the same free column
    workbook.get_worksheet_by_name.assert_called_once_with("Sheet1")
    assert mock_write_entry.call_args_list == [
        call(workbook, worksheet, 2, 11, turnover[0], checkbox_dict),
        call(workbook, worksheet, 1, 11, turnover[1], checkbox_dict),
    ]


@patch("source.spreadsheetDriver.writeTurnoverEntryToSpreadsheet")
def test_append_turnover_matches_parts_ignoring_spaces(
    mock_write_entry, workbook, worksheet
):
    """
    Tests that parts are matched with their spaces removed, since the same part is
    spaced differently in the two reports and would otherwise never match.

    Args:
        mock_write_entry (unittest.mock.MagicMock): Mocks the turnover row writer
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The inventory report spaces the part out, the turnover report runs it together
    inventory = [build_inventory_entry('3/4"  BLANK HINGE')]
    turnover = [build_turnover_entry('3/4"BLANKHINGE')]

    checkbox_dict = checkboxes()
    appendTurnoverToSpreadsheet(workbook, turnover, inventory, 11, checkbox_dict)

    # The part is recognized and its turnover data lands on its row
    mock_write_entry.assert_called_once_with(
        workbook, worksheet, FIRST_DATA_ROW, 11, turnover[0], checkbox_dict
    )


@patch("source.spreadsheetDriver.writeTurnoverEntryToSpreadsheet")
def test_append_turnover_skips_an_entry_with_no_matching_part(
    mock_write_entry, workbook
):
    """
    Tests that a part the turnover report sold but the inventory report never listed
    is dropped, since there is no row to write it to.

    Args:
        mock_write_entry (unittest.mock.MagicMock): Mocks the turnover row writer
        workbook (pytest.fixture): Test fixture to create the workbook
    """

    # The turnover report names a part the inventory report does not
    inventory = [build_inventory_entry("PART-A")]
    turnover = [build_turnover_entry("PART-Z")]

    appendTurnoverToSpreadsheet(workbook, turnover, inventory, 11, checkboxes())

    # Nothing is written for the unmatched part
    mock_write_entry.assert_not_called()


def test_append_turnover_never_writes_over_the_header_row(workbook, worksheet):
    """
    Tests that turnover data lands below the header however few inventory columns the
    user checked. This test drives the real writers rather than mocking them, since
    the bug it guards lived in the handoff between them: the row an entry occupied
    used to be recorded only from inside a checked column's branch, so an inventory
    with every column unchecked left every entry claiming row zero and the turnover
    data overwrote the headers.

    Args:
        workbook (pytest.fixture): Test fixture to create the workbook
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # Not one inventory column is checked, so no inventory cell is ever written
    checkbox_dict = checkboxes({key: False for key in COLUMN_KEYS if key[0] != "t"})
    inventory = [build_inventory_entry("PART-A"), build_inventory_entry("PART-B")]
    turnover = [build_turnover_entry("PART-A"), build_turnover_entry("PART-B")]

    next_col = setupMainSpreadsheet(workbook, inventory, checkbox_dict)
    setupSpreadsheetTurnoverHeader(
        workbook, checkbox_dict, next_col, "Q1-2024", len(inventory)
    )
    appendTurnoverToSpreadsheet(workbook, turnover, inventory, next_col, checkbox_dict)

    # Row zero still holds nothing but the turnover headers
    assert [
        (col, value) for row, col, value in written_cells(worksheet) if row == 0
    ] == [
        (0, "TO Description"),
        (1, "Units Sold Q1-2024"),
        (2, "Avg QOH Q1-2024"),
        (3, "Avg TO Days Q1-2024"),
        (4, "TO Rate Q1-2024"),
    ]

    # Each part's turnover data sits on the data row that part occupies
    assert (FIRST_DATA_ROW, 0, "PART-A") in written_cells(worksheet)
    assert (FIRST_DATA_ROW + 1, 0, "PART-B") in written_cells(worksheet)


###############################################################################
###                spreadsheetDriver -> Tests Column Key Sync                ###
###############################################################################
def test_column_keys_match_the_canonical_column_list():
    """
    Tests that this file's local COLUMN_KEYS, which every layout assertion above
    is written against, is still identical to the canonical list in
    source/columns.py. The duplication is deliberate, so a reordering fails the
    assertions above rather than silently following along; this test is what makes
    the two provably agree.
    """

    from source.columns import COLUMN_KEYS as CANONICAL_COLUMN_KEYS

    assert COLUMN_KEYS == CANONICAL_COLUMN_KEYS
