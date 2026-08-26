import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, call, MagicMock

from source.columns import all_columns_selected
from source.InventoryAppFileIO import InventoryAppFileIO
from source.InventoryProcessor import InventoryProcessor
from source.InventoryEntry import InventoryEntry


###############################################################################
###                  InventoryProcessor -> Test Fixture                     ###
###############################################################################
@pytest.fixture
def processor():
    """
    Builds an InventoryProcessor with its injected file I/O controller mocked and
    the parser it builds itself replaced, so no PDF is read and no spreadsheet is
    written.

    Returns:
        types.SimpleNamespace: Holds the constructed processor (`processor`), the
            mocked file I/O controller (`file_io`) and the mocked parser (`parser`,
            with its patched class as `parser_cls`)
    """

    with patch("source.InventoryProcessor.PdfTableParser") as mock_parser_cls:

        mock_file_io = MagicMock(spec=InventoryAppFileIO)

        yield SimpleNamespace(
            processor=InventoryProcessor(file_io=mock_file_io),
            file_io=mock_file_io,
            parser=mock_parser_cls.return_value,
            parser_cls=mock_parser_cls,
        )


###############################################################################
###                 Tests InventoryProcessor -> __init__()                  ###
###############################################################################
def test_init_holds_the_injected_file_io_and_builds_the_parser(processor):
    """
    Tests that the processor works through the file I/O controller it was handed
    rather than one of its own, and builds the parser it delegates page text to

    Args:
        processor (pytest.fixture): Test fixture building the processor with its
            file I/O controller and parser mocked
    """

    assert processor.processor.file_io is processor.file_io

    processor.parser_cls.assert_called_once_with()
    assert processor.processor.parser is processor.parser


###############################################################################
###           Tests InventoryProcessor -> process_inventory_file()          ###
###############################################################################
def test_process_inventory_file_parses_every_page_before_building_entries(processor):
    """
    Tests that each page is fed to the parser with the rows parsed so far, since a
    row's part or description can wrap from one page onto the next

    Args:
        processor (pytest.fixture): Test fixture building the processor with its
            file I/O controller and parser mocked
    """

    processor.file_io.read_pdf.return_value = ["page one", "page two"]

    # Each call returns the rows accumulated so far, as the real parser does
    processor.parser.parse_inventory_page.side_effect = [
        [["PART-A", "WIDGET", "ea", 1, 0, 0, 0, 1, 0, 0, 0]],
        [
            ["PART-A", "WIDGET", "ea", 1, 0, 0, 0, 1, 0, 0, 0],
            ["PART-B", "GADGET", "ea", 2, 0, 0, 0, 2, 0, 0, 0],
        ],
    ]

    inventory = processor.processor.process_inventory_file("Inventory.pdf")

    assert processor.parser.parse_inventory_page.call_args_list == [
        call("page one", []),
        call("page two", [["PART-A", "WIDGET", "ea", 1, 0, 0, 0, 1, 0, 0, 0]]),
    ]

    # One entry per parsed row, built in the parser's column order
    assert [entry.part for entry in inventory] == ["PART-A", "PART-B"]


def test_process_inventory_file_logs_the_bare_filename(processor):
    """
    Tests that the results file records the file's name rather than its path, so
    its contents do not vary with the platform or how the file was selected

    Args:
        processor (pytest.fixture): Test fixture building the processor with its
            file I/O controller and parser mocked
    """

    processor.file_io.read_pdf.return_value = ["page one"]
    processor.parser.parse_inventory_page.return_value = []

    processor.processor.process_inventory_file(
        "C:/Some/Absolute/Path/Inventory 01222024.pdf"
    )

    logged = [
        written.args[0]
        for written in processor.file_io.write_to_results_file.call_args_list
    ]
    assert "Processing inventory file: Inventory 01222024.pdf" in logged
    assert "Number of Pages in Inventory: 1" in logged


###############################################################################
###            Tests InventoryProcessor -> process_turnover_file()          ###
###############################################################################
def test_process_turnover_file_writes_each_entry_to_the_results_file(processor):
    """
    Tests that every turnover entry parsed out of the report is recorded in the
    results file, which the integration test diffs against its canonical copy

    Args:
        processor (pytest.fixture): Test fixture building the processor with its
            file I/O controller and parser mocked
    """

    processor.file_io.read_pdf.return_value = ["page one"]
    processor.parser.parse_turnover_page.return_value = [
        ["PART-A", 10, 5.0, 2.0, 1.5],
        ["PART-B", 20, 6.0, 3.0, 2.5],
    ]

    turnover = processor.processor.process_turnover_file(Path("Turnover.pdf"))

    assert [entry.part_description for entry in turnover] == ["PART-A", "PART-B"]

    logged = [
        written.args[0]
        for written in processor.file_io.write_to_results_file.call_args_list
    ]
    for entry in turnover:
        assert entry.to_formatted_string() in logged


###############################################################################
###              Tests InventoryProcessor -> process_inventory()            ###
###############################################################################
def test_process_inventory_writes_the_spreadsheet_and_reports_success(processor):
    """
    Tests the successful path end to end: the inventory is written to a new
    workbook, one turnover column group is appended per turnover report, the
    workbook is saved and the user is told it worked

    Args:
        processor (pytest.fixture): Test fixture building the processor with its
            file I/O controller and parser mocked
    """

    processor.file_io.list_turnover_files.return_value = [
        Path("TurnoverReports/January.pdf"),
        Path("TurnoverReports/February.pdf"),
    ]
    processor.file_io.save_workbook.return_value = True
    workbook = processor.file_io.create_workbook.return_value

    report_status = MagicMock()

    with (
        patch.object(
            processor.processor, "process_inventory_file", return_value=[InventoryEntry(part="PART-A")]
        ),
        patch.object(processor.processor, "process_turnover_file", return_value=[]),
        patch(
            "source.InventoryProcessor.setupMainSpreadsheet", return_value=11
        ) as mock_setup_main,
        patch(
            "source.InventoryProcessor.setupSpreadsheetTurnoverHeader",
            side_effect=[16, 21],
        ) as mock_turnover_header,
        patch(
            "source.InventoryProcessor.appendTurnoverToSpreadsheet"
        ) as mock_append,
    ):
        result = processor.processor.process_inventory(
            "Inventory 01222024.pdf", all_columns_selected(), report_status
        )

    assert result is True
    mock_setup_main.assert_called_once()

    # Each turnover report starts where the one before it reported that it ended,
    # and is named after its own file
    assert [made.args[2] for made in mock_turnover_header.call_args_list] == [11, 16]
    assert [made.args[3] for made in mock_turnover_header.call_args_list] == [
        "January",
        "February",
    ]
    assert [made.args[3] for made in mock_append.call_args_list] == [11, 16]

    processor.file_io.save_workbook.assert_called_once_with(workbook)
    report_status.assert_called_with("Successfully processed Inventory Availability!")


# A report is between one and five columns wide, depending on which turnover
# columns the user checked, so no fixed stride can be correct for all of them.
@pytest.mark.parametrize("width", [1, 3, 5])
def test_process_inventory_starts_each_turnover_report_after_the_last(
    width, processor
):
    """
    Tests that each turnover report is written starting at the column the previous
    report reported as free, so several reports sit side by side instead of the
    later ones overwriting the earlier ones' columns

    Args:
        width (int): The number of columns each turnover report occupies
        processor (pytest.fixture): Test fixture building the processor with its
            file I/O controller and parser mocked
    """

    processor.file_io.list_turnover_files.return_value = [
        Path("TurnoverReports/January.pdf"),
        Path("TurnoverReports/February.pdf"),
        Path("TurnoverReports/March.pdf"),
    ]
    processor.file_io.save_workbook.return_value = True

    with (
        patch.object(
            processor.processor,
            "process_inventory_file",
            return_value=[InventoryEntry(part="PART-A")],
        ),
        patch.object(processor.processor, "process_turnover_file", return_value=[]),
        patch("source.InventoryProcessor.setupMainSpreadsheet", return_value=11),
        patch(
            "source.InventoryProcessor.setupSpreadsheetTurnoverHeader",
            # Stands in for the real writer, which fills one column per checked
            # turnover column and reports back the first free one
            side_effect=lambda workbook, checkboxes, col, name, rows: col + width,
        ) as mock_turnover_header,
        patch(
            "source.InventoryProcessor.appendTurnoverToSpreadsheet"
        ) as mock_append,
    ):
        processor.processor.process_inventory(
            "Inventory 01222024.pdf", all_columns_selected(), MagicMock()
        )

    # No report starts inside the columns of the one before it, and the data is
    # appended to the same columns their headers were written to
    expected = [11, 11 + width, 11 + 2 * width]
    assert [made.args[2] for made in mock_turnover_header.call_args_list] == expected
    assert [made.args[3] for made in mock_append.call_args_list] == expected


def test_process_inventory_sizes_the_turnover_columns_to_the_inventory(processor):
    """
    Tests that the turnover header is told how many inventory rows the report
    holds, so the placeholder pre-fill reaches the last row of a report of any
    length rather than stopping at a fixed row

    Args:
        processor (pytest.fixture): Test fixture building the processor with its
            file I/O controller and parser mocked
    """

    processor.file_io.list_turnover_files.return_value = [
        Path("TurnoverReports/January.pdf")
    ]
    processor.file_io.save_workbook.return_value = True

    # An inventory long enough that a hardcoded row limit would be visible
    inventory = [InventoryEntry(part=f"PART-{index}") for index in range(700)]

    with (
        patch.object(
            processor.processor, "process_inventory_file", return_value=inventory
        ),
        patch.object(processor.processor, "process_turnover_file", return_value=[]),
        patch("source.InventoryProcessor.setupMainSpreadsheet", return_value=11),
        patch(
            "source.InventoryProcessor.setupSpreadsheetTurnoverHeader"
        ) as mock_turnover_header,
        patch("source.InventoryProcessor.appendTurnoverToSpreadsheet"),
    ):
        processor.processor.process_inventory(
            "Inventory 01222024.pdf", all_columns_selected(), MagicMock()
        )

    # The row count handed over is the number of rows actually written
    mock_turnover_header.assert_called_once()
    assert mock_turnover_header.call_args.args[4] == len(inventory)


def test_process_inventory_derives_the_output_name_from_the_pdf_name(processor):
    """
    Tests that the spreadsheet is named after the date in the inventory PDF's
    filename, which is how the user identifies the report

    Args:
        processor (pytest.fixture): Test fixture building the processor with its
            file I/O controller and parser mocked
    """

    processor.file_io.list_turnover_files.return_value = []
    processor.file_io.save_workbook.return_value = True

    with (
        patch.object(
            processor.processor, "process_inventory_file", return_value=[InventoryEntry(part="PART-A")]
        ),
        patch("source.InventoryProcessor.setupMainSpreadsheet", return_value=11),
    ):
        processor.processor.process_inventory(
            "Inventory Availability 01222024.pdf", all_columns_selected(), MagicMock()
        )

    processor.file_io.create_workbook.assert_called_once_with("01222024")


def test_process_inventory_falls_back_to_a_generic_output_name(processor):
    """
    Tests that a PDF whose name carries no date still produces a report, rather
    than failing on the filename

    Args:
        processor (pytest.fixture): Test fixture building the processor with its
            file I/O controller and parser mocked
    """

    processor.file_io.list_turnover_files.return_value = []
    processor.file_io.save_workbook.return_value = True

    with (
        patch.object(
            processor.processor, "process_inventory_file", return_value=[InventoryEntry(part="PART-A")]
        ),
        patch("source.InventoryProcessor.setupMainSpreadsheet", return_value=11),
    ):
        processor.processor.process_inventory(
            "Inventory Availability", all_columns_selected(), MagicMock()
        )

    processor.file_io.create_workbook.assert_called_once_with("InventoryReport")


def test_process_inventory_reports_and_returns_false_on_an_unreadable_pdf(processor):
    """
    Tests that an inventory PDF that could not be read stops the run before a
    workbook is created, and tells the user rather than failing silently

    Args:
        processor (pytest.fixture): Test fixture building the processor with its
            file I/O controller and parser mocked
    """

    report_status = MagicMock()

    with patch.object(
        processor.processor, "process_inventory_file", return_value=[]
    ):
        result = processor.processor.process_inventory(
            "Inventory.pdf", all_columns_selected(), report_status
        )

    assert result is False
    processor.file_io.create_workbook.assert_not_called()
    report_status.assert_called_with(
        "Could not read the selected Inventory PDF. See log for details."
    )


def test_process_inventory_reports_and_returns_false_when_the_workbook_fails(
    processor,
):
    """
    Tests that a workbook the file I/O controller could not create stops the run
    before any column is written

    Args:
        processor (pytest.fixture): Test fixture building the processor with its
            file I/O controller and parser mocked
    """

    processor.file_io.create_workbook.return_value = None
    report_status = MagicMock()

    with (
        patch.object(
            processor.processor, "process_inventory_file", return_value=[InventoryEntry(part="PART-A")]
        ),
        patch("source.InventoryProcessor.setupMainSpreadsheet") as mock_setup_main,
    ):
        result = processor.processor.process_inventory(
            "Inventory.pdf", all_columns_selected(), report_status
        )

    assert result is False
    mock_setup_main.assert_not_called()
    report_status.assert_called_with(
        "Could not create the output spreadsheet. See log for details."
    )


def test_process_inventory_reports_and_returns_false_when_the_save_fails(processor):
    """
    Tests that a workbook that could not be saved is reported as a failure, so the
    user does not believe a report was produced

    Args:
        processor (pytest.fixture): Test fixture building the processor with its
            file I/O controller and parser mocked
    """

    processor.file_io.list_turnover_files.return_value = []
    processor.file_io.save_workbook.return_value = False
    report_status = MagicMock()

    with (
        patch.object(
            processor.processor, "process_inventory_file", return_value=[InventoryEntry(part="PART-A")]
        ),
        patch("source.InventoryProcessor.setupMainSpreadsheet", return_value=11),
    ):
        result = processor.processor.process_inventory(
            "Inventory.pdf", all_columns_selected(), report_status
        )

    assert result is False
    report_status.assert_called_with(
        "Could not save the output spreadsheet. See log for details."
    )
