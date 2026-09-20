from unittest.mock import MagicMock

import pytest
import xlsxwriter
from xlsxwriter.worksheet import Worksheet

from source.columns import COLUMN_KEYS
from source.InventoryEntry import InventoryEntry
from source.spreadsheet_writer import FIRST_DATA_ROW, SpreadsheetWriter
from source.TurnoverEntry import TurnoverEntry


def checkboxes(overrides: dict = None, default: bool = True) -> dict:
    """
    Builds the checkbox state dictionary the writer reads, with every column
    checked unless a test says otherwise. The keys come from source/columns.py,
    which the writer now walks itself; the layout assertions below stay written as
    literal cells, so a reordering there fails them rather than following along.

    Args:
        overrides (dict): The keys to set against the default, e.g. {"UOM": False}
        default (bool): The state every key not named in overrides takes

    Returns:
        dict: A checkbox state dictionary covering every column key
    """

    state = dict.fromkeys(COLUMN_KEYS, default)
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


def final_cells(worksheet: MagicMock) -> dict:
    """
    Reduces the writes to what the saved sheet would hold, with a later write to a
    cell replacing an earlier one. A turnover report writes each of its columns
    twice, as a placeholder and then as the data that lands on top of it, so the
    call list alone does not say what the user sees.

    Args:
        worksheet (unittest.mock.MagicMock): The worksheet the writes were recorded on

    Returns:
        dict: The value each written (row, column) ends up holding
    """

    return {(write.args[0], write.args[1]): write.args[2] for write in worksheet.write.call_args_list}


def cells_in_row(worksheet: MagicMock, row: int) -> list:
    """
    Reads one row of the saved sheet back, left to right.

    Args:
        worksheet (unittest.mock.MagicMock): The worksheet the writes were recorded on
        row (int): The row to read

    Returns:
        list: One (column, value) tuple per written cell in that row, in column order
    """

    cells = final_cells(worksheet)
    return sorted((col, value) for (written_row, col), value in cells.items() if written_row == row)


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
    Test fixture to set up the workbook the writer is built around. Formats are
    handed back as the specification dictionary they were requested with, since a
    bare mock would return one identical object for every call and no test could
    tell two formats apart. add_worksheet() is stubbed because the writer opens the
    worksheet in its constructor.

    Args:
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    workbook = MagicMock(spec=xlsxwriter.Workbook)
    workbook.add_format.side_effect = lambda spec: dict(spec)
    workbook.add_worksheet.return_value = worksheet

    return workbook


@pytest.fixture
def writer(workbook):
    """
    Test fixture to set up the unit under test, wrapped around the mocked workbook.

    Args:
        workbook (pytest.fixture): Test fixture to create the workbook
    """

    return SpreadsheetWriter(workbook)


def test_init_opens_one_worksheet_and_builds_each_format_once(workbook, writer):
    """
    Tests that the writer opens the single worksheet the report occupies and builds
    its three cell formats up front, so no writer has to look the sheet back up by
    name or rebuild a format to write a cell.

    Args:
        workbook (pytest.fixture): Test fixture to create the workbook
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
    """

    workbook.add_worksheet.assert_called_once_with()
    assert workbook.add_format.call_count == 3
    assert writer.header_format["bold"] is True
    assert writer.even_format["bg_color"] == "#F0F0F0"
    assert writer.odd_format["bg_color"] == "#E6F0FF"


def test_write_inventory_titles_every_checked_column(writer, worksheet):
    """
    Tests that every inventory column is titled in the header row, in the order the
    row writer walks the same columns.

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The user leaves every inventory column checked
    writer.write_inventory([], checkboxes())

    # Each column is titled in declaration order, starting at the first column
    assert written_cells(worksheet) == [
        (0, 0, "Part"),
        (0, 1, "Description"),
        (0, 2, "UOM"),
        (0, 3, "On Hand"),
        (0, 4, "Allocated"),
        (0, 5, "Not Available"),
        (0, 6, "Drop Ship"),
        (0, 7, "Available"),
        (0, 8, "On Order"),
        (0, 9, "Committed"),
        (0, 10, "Short"),
    ]


def test_write_inventory_skips_unchecked_columns(writer, worksheet):
    """
    Tests that an unchecked column is left out entirely rather than written as a
    blank, and that the columns after it close the gap instead of holding their
    original position. The header and the data row are checked together, since they
    are written from the same filtered tuple and must not drift apart.

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The user clears two columns from the middle of the report
    writer.write_inventory([build_inventory_entry()], checkboxes({"UOM": False, "DropShip": False}))

    # The remaining columns stay contiguous, each shifting left past the gap
    assert cells_in_row(worksheet, 0) == [
        (0, "Part"),
        (1, "Description"),
        (2, "On Hand"),
        (3, "Allocated"),
        (4, "Not Available"),
        (5, "Available"),
        (6, "On Order"),
        (7, "Committed"),
        (8, "Short"),
    ]

    # The entry's fields land under the titles they belong to
    assert cells_in_row(worksheet, FIRST_DATA_ROW) == [
        (0, "PART-A"),
        (1, "WIDGET ONE"),
        (2, 100),
        (3, 5),
        (4, 1),
        (5, 95),
        (6, 20),
        (7, 7),
        (8, 3),
    ]


def test_write_inventory_writes_nothing_when_nothing_is_checked(writer, worksheet):
    """
    Tests that a sheet is left empty when the user checks no inventory column at
    all, rather than falling back to writing some default set

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # No column is checked
    next_col = writer.write_inventory([build_inventory_entry()], checkboxes(default=False))

    # Not a single cell is written, and no column is claimed
    worksheet.write.assert_not_called()
    assert next_col == 0


def test_write_inventory_styles_the_header_row(writer, worksheet):
    """
    Tests that the header titles are written in the bold, centered, larger format
    that separates them from the data rows beneath

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The header row is written
    writer.write_inventory([], checkboxes())

    # Every title carries the same bold, centered header format
    header_format = written_formats(worksheet)[0]
    assert header_format["bold"] is True
    assert header_format["align"] == "center"
    assert header_format["font_size"] == 16
    assert all(cell_format == header_format for cell_format in written_formats(worksheet))


def test_write_inventory_writes_every_field_of_each_entry(writer, worksheet):
    """
    Tests that each field of an entry is written across its row in the column its
    title was written to, read off the entry by the attribute its column names

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # One entry is written below the header with every column checked
    writer.write_inventory([build_inventory_entry()], checkboxes())

    # Every field lands in the column its title was written to
    assert cells_in_row(worksheet, FIRST_DATA_ROW) == [
        (0, "PART-A"),
        (1, "WIDGET ONE"),
        (2, "ea"),
        (3, 100),
        (4, 5),
        (5, 1),
        (6, 2),
        (7, 95),
        (8, 20),
        (9, 7),
        (10, 3),
    ]


def test_write_inventory_writes_one_row_per_entry_below_the_header(writer, worksheet):
    """
    Tests that the entries are written one per row starting below the header, in
    list order, since an entry's position in the list is the row the turnover join
    later looks it up by

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # Three parsed inventory entries are written, with one column checked
    inventory = [
        build_inventory_entry("PART-A"),
        build_inventory_entry("PART-B"),
        build_inventory_entry("PART-C"),
    ]
    writer.write_inventory(inventory, checkboxes({"Part": True}, default=False))

    # The header takes row zero and the entries follow it in order
    assert written_cells(worksheet) == [
        (0, 0, "Part"),
        (1, 0, "PART-A"),
        (2, 0, "PART-B"),
        (3, 0, "PART-C"),
    ]


def test_write_inventory_alternates_the_row_fill_colors(writer, worksheet):
    """
    Tests that consecutive entries are given different fills, so the bands of the
    report line up across the whole sheet

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # Two consecutive rows are written with a single column checked
    writer.write_inventory(
        [build_inventory_entry("PART-A"), build_inventory_entry("PART-B")],
        checkboxes({"Part": True}, default=False),
    )

    # The header aside, the odd row and the even row carry the alternating fills
    formats = written_formats(worksheet)
    assert formats[1]["bg_color"] == "#E6F0FF"
    assert formats[2]["bg_color"] == "#F0F0F0"


# The whole inventory group, a middle-sized selection, and a single column - the
# inventory is as wide as the user checked, so the caller cannot assume a width.
@pytest.mark.parametrize(
    "unchecked, width",
    [
        ({}, 11),
        ({"UOM": False, "DropShip": False}, 9),
        ({key: False for key in COLUMN_KEYS if key not in ("Part", "Short")}, 2),
    ],
)
def test_write_inventory_returns_the_first_free_column(unchecked, width, writer, worksheet):
    """
    Tests that the column reported back is the one past the last inventory column,
    which is where the caller starts appending the first turnover report

    Args:
        unchecked (dict): The inventory columns the user left out of the report
        width (int): The number of columns the remaining selection occupies
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The inventory is written with part of the report unchecked
    next_col = writer.write_inventory([build_inventory_entry()], checkboxes(unchecked))

    # The columns run contiguously from zero, and the value handed back is the
    # first one past them
    assert [col for col, _value in cells_in_row(worksheet, 0)] == list(range(width))
    assert next_col == width


def test_write_inventory_reports_its_width_for_an_empty_inventory(writer, worksheet):
    """
    Tests that an inventory PDF that yielded no entries still produces a titled
    worksheet and reports the width those titles occupy. Reporting the first column
    as free instead would start the first turnover report at column zero, writing
    its headers straight over the inventory titles.

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The inventory came back empty
    next_col = writer.write_inventory([], checkboxes())

    # The header is still written, no data row is, and the width is still reported
    assert len(cells_in_row(worksheet, 0)) == 11
    assert cells_in_row(worksheet, FIRST_DATA_ROW) == []
    assert next_col == 11


def test_write_inventory_reuses_the_cached_formats(workbook, writer):
    """
    Tests that no format is built while the rows are written, however many rows
    there are. The module this replaced built a format inside each row writer, so a
    report of a few hundred parts left hundreds of duplicate formats in the file.

    Args:
        workbook (pytest.fixture): Test fixture to create the workbook
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
    """

    # A report long enough that a per-row format would be obvious
    inventory = [build_inventory_entry(f"PART-{index}") for index in range(50)]
    writer.write_inventory(inventory, checkboxes())

    # Only the three built in the constructor
    assert workbook.add_format.call_count == 3


def test_append_turnover_report_labels_each_column_with_the_report(writer, worksheet):
    """
    Tests that each turnover column is titled from the first free column onward,
    naming the report each column came from so several turnover reports can sit side
    by side in one sheet

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # A turnover report is appended after the eleven inventory columns
    writer.append_turnover_report([], [], 11, checkboxes(), "Turnover_Jan2024")

    # Each column is titled with the report it holds, except the shared description
    assert cells_in_row(worksheet, 0) == [
        (11, "Description Turnover_Jan2024"),
        (12, "Units Sold Turnover_Jan2024"),
        (13, "Avg QOH Turnover_Jan2024"),
        (14, "Avg TO Days Turnover_Jan2024"),
        (15, "TO Rate Turnover_Jan2024"),
    ]


def test_append_turnover_report_skips_unchecked_columns(writer, worksheet):
    """
    Tests that an unchecked turnover column is left out and the columns after it
    close the gap, both in the header and in the data written beneath it

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The user wants only the numbers, and not the average quantity on hand
    writer.append_turnover_report(
        [build_turnover_entry()],
        [build_inventory_entry()],
        11,
        checkboxes({"tDescription": False, "tAvg QOH": False}),
        "Turnover_Jan2024",
    )

    # The remaining columns stay contiguous from the first free column
    assert cells_in_row(worksheet, 0) == [
        (11, "Units Sold Turnover_Jan2024"),
        (12, "Avg TO Days Turnover_Jan2024"),
        (13, "TO Rate Turnover_Jan2024"),
    ]

    # The entry's fields land under the titles they belong to
    assert cells_in_row(worksheet, FIRST_DATA_ROW) == [
        (11, 42),
        (12, 30),
        (13, 1.25),
    ]


def test_append_turnover_report_writes_every_checked_field(writer, worksheet):
    """
    Tests that each field of a turnover entry is written from the report's first
    column rightward, in the order the header titled them

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # A turnover entry is written onto the row its inventory part occupies
    writer.append_turnover_report([build_turnover_entry()], [build_inventory_entry()], 11, checkboxes(), "Q1")

    # Every field lands in the column its title was written to
    assert cells_in_row(worksheet, FIRST_DATA_ROW) == [
        (11, "PART-A"),
        (12, 42),
        (13, 7.5),
        (14, 30),
        (15, 1.25),
    ]


def test_append_turnover_report_writes_an_undefined_average_as_a_blank(writer, worksheet):
    """
    Tests that the averages the report left blank reach the sheet as blanks rather
    than as zeros, since a part with no turnover has no average rather than an
    average of nothing

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The report gave this part a unit count but no averages
    writer.append_turnover_report(
        [TurnoverEntry("PART-A", 0)],
        [build_inventory_entry()],
        11,
        checkboxes(),
        "Q1",
    )

    # The three averages are written as empty cells
    assert cells_in_row(worksheet, FIRST_DATA_ROW) == [
        (11, "PART-A"),
        (12, 0),
        (13, None),
        (14, None),
        (15, None),
    ]


# An empty report, a single row, the row count the pre-fill was once hardcoded to,
# and a report longer than that count - the case the hardcoded limit truncated.
@pytest.mark.parametrize("row_count", [0, 1, 618, 622])
def test_append_turnover_report_prefills_every_data_row(row_count, writer, worksheet):
    """
    Tests that every turnover column is pre-filled with a placeholder in every data
    row of the report, however long that report is, so a part the turnover report
    never mentions reads as N/A rather than as an empty cell. The header row is left
    alone for the column title.

    Args:
        row_count (int): The number of inventory data rows the report holds
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # A report whose turnover file mentions none of its parts
    inventory = [build_inventory_entry(f"PART-{index}") for index in range(row_count)]
    writer.append_turnover_report([], inventory, 11, checkboxes(), "Q1-2024")

    # Every row below the header holds the placeholder, down to the last one
    cells = final_cells(worksheet)
    assert [cells[(row, 11)] for row in range(FIRST_DATA_ROW, FIRST_DATA_ROW + row_count)] == ["N/A"] * row_count

    # And the pre-fill stops there rather than running past the last entry
    assert (FIRST_DATA_ROW + row_count, 11) not in cells


def test_append_turnover_report_prefills_every_column_it_titles(writer, worksheet):
    """
    Tests that each column the report titles is pre-filled, not just the first, so a
    part missing from the turnover report is not left with a run of blank cells to
    the right of its placeholder

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # A report whose turnover file mentions none of its two parts
    inventory = [build_inventory_entry("PART-A"), build_inventory_entry("PART-B")]
    writer.append_turnover_report([], inventory, 11, checkboxes(), "Q1-2024")

    # Both data rows read as missing across all five of the report's columns
    for row in (FIRST_DATA_ROW, FIRST_DATA_ROW + 1):
        assert cells_in_row(worksheet, row) == [(col, "N/A") for col in range(11, 16)]


def test_append_turnover_report_alternates_the_prefill_fill_colors(writer, worksheet):
    """
    Tests that the placeholder column keeps the banding of the rows it sits beside,
    so a wide report stays readable across the columns a turnover file never filled

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # Two data rows are pre-filled with a single turnover column checked
    inventory = [build_inventory_entry("PART-A"), build_inventory_entry("PART-B")]
    writer.append_turnover_report([], inventory, 11, checkboxes({"tDescription": True}, default=False), "Q1")

    # The header aside, the odd row and the even row carry the alternating fills
    formats = written_formats(worksheet)
    assert formats[1]["bg_color"] == "#E6F0FF"
    assert formats[2]["bg_color"] == "#F0F0F0"


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
def test_append_turnover_report_returns_the_first_free_column(unchecked, width, writer, worksheet):
    """
    Tests that a report reports back the column after the last one it filled,
    however many turnover columns the user checked. The caller has no other way to
    know how wide a report turned out to be, and a report is between one and five
    columns wide.

    Args:
        unchecked (dict): The turnover columns the user left out of this report
        width (int): The number of columns the remaining selection occupies
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # A turnover report is appended after the eleven inventory columns
    next_col = writer.append_turnover_report([], [], 11, checkboxes(unchecked), "Turnover_Jan2024")

    # The columns run contiguously from the first free one, and the value handed
    # back is the next one along
    assert [col for col, _value in cells_in_row(worksheet, 0)] == list(range(11, 11 + width))
    assert next_col == 11 + width


def test_append_turnover_report_places_two_reports_side_by_side(writer, worksheet):
    """
    Tests that threading one report's returned column into the next lays the two
    reports out side by side rather than the second overwriting the first. A caller
    advancing by a fixed column instead would leave the first report with only its
    leftmost column.

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The second report starts wherever the first one reported that it ended
    next_col = writer.append_turnover_report([], [], 11, checkboxes(), "Turnover_Q3-2023")
    writer.append_turnover_report([], [], next_col, checkboxes(), "Turnover_Q1-2024")

    # Both reports keep a complete set of columns, and none is written to twice
    assert cells_in_row(worksheet, 0) == [
        (11, "Description Turnover_Q3-2023"),
        (12, "Units Sold Turnover_Q3-2023"),
        (13, "Avg QOH Turnover_Q3-2023"),
        (14, "Avg TO Days Turnover_Q3-2023"),
        (15, "TO Rate Turnover_Q3-2023"),
        (16, "Description Turnover_Q1-2024"),
        (17, "Units Sold Turnover_Q1-2024"),
        (18, "Avg QOH Turnover_Q1-2024"),
        (19, "Avg TO Days Turnover_Q1-2024"),
        (20, "TO Rate Turnover_Q1-2024"),
    ]


def test_append_turnover_report_returns_its_starting_column_when_nothing_is_checked(writer, worksheet):
    """
    Tests that a report with no turnover column checked leaves the cursor where it
    found it, so the columns after it are not pushed across by an empty report

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The user wants the inventory columns only
    next_col = writer.append_turnover_report(
        [build_turnover_entry()],
        [build_inventory_entry()],
        11,
        checkboxes({key: False for key in COLUMN_KEYS if key[0] == "t"}),
        "Turnover_Jan2024",
    )

    assert written_cells(worksheet) == []
    assert next_col == 11


def test_append_turnover_report_writes_each_entry_to_its_matching_inventory_row(writer, worksheet):
    """
    Tests that each turnover entry is looked up by part and written to the row that
    part already occupies, rather than to the row it holds in the turnover report,
    since the two reports list their parts in their own order

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # Two parts occupy the first two data rows, and the turnover report lists them
    # the other way around
    inventory = [build_inventory_entry("PART-A"), build_inventory_entry("PART-B")]
    turnover = [build_turnover_entry("PART-B"), build_turnover_entry("PART-A")]

    writer.append_turnover_report(
        turnover,
        inventory,
        11,
        checkboxes({"tDescription": True}, default=False),
        "Q1",
    )

    # Each entry follows its part to that part's row, in the same free column
    assert cells_in_row(worksheet, FIRST_DATA_ROW) == [(11, "PART-A")]
    assert cells_in_row(worksheet, FIRST_DATA_ROW + 1) == [(11, "PART-B")]


def test_append_turnover_report_matches_parts_ignoring_spaces(writer, worksheet):
    """
    Tests that parts are matched with their spaces removed, since the same part is
    spaced differently in the two reports and would otherwise never match

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The inventory report spaces the part out, the turnover report runs it together
    inventory = [build_inventory_entry('3/4"  BLANK HINGE')]
    turnover = [build_turnover_entry('3/4"BLANKHINGE')]

    writer.append_turnover_report(
        turnover,
        inventory,
        11,
        checkboxes({"tUnits Sold": True}, default=False),
        "Q1",
    )

    # The part is recognized and its turnover data lands on its row
    assert cells_in_row(worksheet, FIRST_DATA_ROW) == [(11, 42)]


def test_append_turnover_report_writes_a_repeated_part_to_every_row_it_occupies(writer, worksheet):
    """
    Tests that a part the inventory lists twice gets this report's data on both of
    its rows. The join is an index rather than a scan of the whole inventory per
    entry, and an index holding one row per part would quietly drop the second.

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The same part appears on two inventory rows, with another part between them
    inventory = [
        build_inventory_entry("PART-A"),
        build_inventory_entry("PART-B"),
        build_inventory_entry("PART-A"),
    ]
    turnover = [build_turnover_entry("PART-A")]

    writer.append_turnover_report(
        turnover,
        inventory,
        11,
        checkboxes({"tUnits Sold": True}, default=False),
        "Q1",
    )

    # Both of the part's rows carry the data, and the row between them does not
    assert cells_in_row(worksheet, FIRST_DATA_ROW) == [(11, 42)]
    assert cells_in_row(worksheet, FIRST_DATA_ROW + 1) == [(11, "N/A")]
    assert cells_in_row(worksheet, FIRST_DATA_ROW + 2) == [(11, 42)]


def test_append_turnover_report_leaves_an_unmatched_part_reading_as_missing(writer, worksheet):
    """
    Tests that a part the turnover report sold but the inventory report never listed
    is dropped, since there is no row to write it to, and that the inventory rows it
    did not match keep their placeholder rather than being blanked

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # The turnover report names a part the inventory report does not
    inventory = [build_inventory_entry("PART-A")]
    turnover = [build_turnover_entry("PART-Z")]

    writer.append_turnover_report(
        turnover,
        inventory,
        11,
        checkboxes({"tUnits Sold": True}, default=False),
        "Q1",
    )

    # The only data row still reads as missing
    assert cells_in_row(worksheet, FIRST_DATA_ROW) == [(11, "N/A")]


def test_append_turnover_report_never_writes_over_the_header_row(writer, worksheet):
    """
    Tests that turnover data lands below the header however few inventory columns
    the user checked. The bug this guards lived in the handoff between the writers:
    the row an entry occupied used to be recorded only from inside a checked
    column's branch, so an inventory with every column unchecked left every entry
    claiming row zero and the turnover data overwrote the headers.

    Args:
        writer (pytest.fixture): Test fixture to create the spreadsheet writer
        worksheet (pytest.fixture): Test fixture to create the worksheet
    """

    # Not one inventory column is checked, so no inventory cell is ever written
    checkbox_dict = checkboxes({key: False for key in COLUMN_KEYS if key[0] != "t"})
    inventory = [build_inventory_entry("PART-A"), build_inventory_entry("PART-B")]
    turnover = [build_turnover_entry("PART-A"), build_turnover_entry("PART-B")]

    next_col = writer.write_inventory(inventory, checkbox_dict)
    writer.append_turnover_report(turnover, inventory, next_col, checkbox_dict, "Q1-2024")

    # Row zero still holds nothing but the turnover headers
    assert cells_in_row(worksheet, 0) == [
        (0, "Description Q1-2024"),
        (1, "Units Sold Q1-2024"),
        (2, "Avg QOH Q1-2024"),
        (3, "Avg TO Days Q1-2024"),
        (4, "TO Rate Q1-2024"),
    ]

    # Each part's turnover data sits on the data row that part occupies
    assert final_cells(worksheet)[(FIRST_DATA_ROW, 0)] == "PART-A"
    assert final_cells(worksheet)[(FIRST_DATA_ROW + 1, 0)] == "PART-B"
