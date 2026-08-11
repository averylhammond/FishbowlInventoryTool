import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, call, MagicMock

from source.columns import all_columns_selected
from source.InventoryAppController import InventoryAppController
from source.InventoryEntry import InventoryEntry


###############################################################################
###                 InventoryAppController -> Test Fixture                  ###
###############################################################################
@pytest.fixture
def controller():
    """
    Builds an InventoryAppController with every collaborator replaced by a mock,
    so no PDF is read, no spreadsheet is written and no window is created.

    Note the display is NOT patched here: the controller imports it inside
    start_application(), so the name never exists at module scope and only the
    tests that reach the GUI branch patch it, at its definition site.

    Returns:
        types.SimpleNamespace: Holds the constructed controller (`controller`) and
            the mocked collaborator instances (`file_io`, `parser`, `arg_provider`)
    """

    with (
        patch("source.InventoryAppController.ArgumentProvider") as mock_arg_cls,
        patch("source.InventoryAppController.InventoryAppFileIO") as mock_file_io_cls,
        patch("source.InventoryAppController.PdfTableParser") as mock_parser_cls,
    ):

        mock_arg_provider = mock_arg_cls.return_value
        mock_arg_provider.integration_test_mode = False

        yield SimpleNamespace(
            controller=InventoryAppController(),
            file_io=mock_file_io_cls.return_value,
            parser=mock_parser_cls.return_value,
            arg_provider=mock_arg_provider,
            file_io_cls=mock_file_io_cls,
            parser_cls=mock_parser_cls,
            arg_provider_cls=mock_arg_cls,
        )


###############################################################################
###               Tests InventoryAppController -> __init__()                ###
###############################################################################
def test_init_constructs_the_collaborators(controller):
    """
    Tests that the controller builds the file I/O controller, the parser and the
    argument provider it delegates to

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.file_io_cls.assert_called_once_with()
    controller.parser_cls.assert_called_once_with()
    controller.arg_provider_cls.assert_called_once_with(
        description="Fishbowl inventory availability report generator"
    )


def test_init_clears_the_results_file(controller):
    """
    Tests that each run starts from an empty results file, so the diagnostics log
    only ever holds the current run's output

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.file_io.reset_results_file.assert_called_once_with()


def test_init_does_not_build_the_gui(controller):
    """
    Tests that constructing the controller creates no GUI. The integration test
    runs headless with no display attached, so the window must not be built until
    the GUI branch of start_application() is reached.

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    assert controller.controller.display is None


###############################################################################
###           Tests InventoryAppController -> start_application()           ###
###############################################################################
def test_start_application_builds_the_gui_and_runs_the_main_loop(controller):
    """
    Tests that a normal run creates the display with the application's title and
    resolution, hands it the processing callback, and enters the tkinter main loop

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    with patch(
        "source.gui.InventoryAppDisplay.InventoryAppDisplay"
    ) as mock_display_cls:
        controller.controller.start_application()

    mock_display_cls.assert_called_once_with(
        process_callback=controller.controller.handle_process_inventory,
        title="Automated Inventory Processor",
        window_resolution="700x700",
    )
    mock_display_cls.return_value.mainloop.assert_called_once_with()


def test_start_application_wires_the_gui_popup_into_file_io(controller):
    """
    Tests that file I/O failures surface to the user through the GUI's popup,
    which is what keeps the file I/O controller free of any GUI dependency

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    with patch(
        "source.gui.InventoryAppDisplay.InventoryAppDisplay"
    ) as mock_display_cls:
        controller.controller.start_application()

    assert (
        controller.file_io.report_error is mock_display_cls.return_value.show_popup
    )


def test_start_application_in_integration_test_mode_never_builds_the_gui(controller):
    """
    Tests that headless mode processes the inventories directly and creates no
    window. The integration test job runs with no display, so building the GUI
    there would fail the run outright.

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.arg_provider.integration_test_mode = True

    with (
        patch(
            "source.gui.InventoryAppDisplay.InventoryAppDisplay"
        ) as mock_display_cls,
        patch.object(controller.controller, "run_integration_test") as mock_headless,
    ):
        controller.controller.start_application()

    mock_headless.assert_called_once_with()
    mock_display_cls.assert_not_called()
    assert controller.controller.display is None


###############################################################################
###          Tests InventoryAppController -> run_integration_test()         ###
###############################################################################
def test_run_integration_test_processes_every_inventory_with_all_columns(controller):
    """
    Tests that the headless path includes every column and processes each
    inventory PDF the file I/O controller lists, routing status to stdout rather
    than the results file so the CI diff stays deterministic

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.file_io.list_inventory_files.return_value = [
        Path("InventoryAvailability/Inventory 01222024.pdf"),
        Path("InventoryAvailability/Inventory 02222024.pdf"),
    ]

    with patch.object(controller.controller, "process_inventory") as mock_process:
        controller.controller.run_integration_test()

    assert mock_process.call_args_list == [
        call(
            str(Path("InventoryAvailability/Inventory 01222024.pdf")),
            all_columns_selected(),
            print,
        ),
        call(
            str(Path("InventoryAvailability/Inventory 02222024.pdf")),
            all_columns_selected(),
            print,
        ),
    ]


def test_run_integration_test_routes_errors_away_from_the_default_reporter(controller):
    """
    Tests that file I/O failures are surfaced in headless mode, where there is no
    GUI popup to receive them

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.file_io.list_inventory_files.return_value = []

    with patch.object(controller.controller, "process_inventory"):
        controller.controller.run_integration_test()

    # A reporter was installed, and it is callable with a title and a message
    assert callable(controller.file_io.report_error)
    controller.file_io.report_error("File Error", "Could not read the file")


###############################################################################
###        Tests InventoryAppController -> handle_process_inventory()       ###
###############################################################################
def test_handle_process_inventory_routes_status_to_the_output_box(controller):
    """
    Tests that the GUI's process callback runs the shared processing routine with
    status directed at the display's output box, and hands back its result

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.controller.display = MagicMock()
    checkbox_dict = all_columns_selected()

    with patch.object(
        controller.controller, "process_inventory", return_value=True
    ) as mock_process:
        result = controller.controller.handle_process_inventory(
            "Inventory 01222024.pdf", checkbox_dict
        )

    mock_process.assert_called_once_with(
        "Inventory 01222024.pdf",
        checkbox_dict,
        controller.controller.display.write_output,
    )
    assert result is True


###############################################################################
###         Tests InventoryAppController -> process_inventory_file()        ###
###############################################################################
def test_process_inventory_file_parses_every_page_before_building_entries(controller):
    """
    Tests that each page is fed to the parser with the rows parsed so far, since a
    row's part or description can wrap from one page onto the next

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.file_io.read_pdf.return_value = ["page one", "page two"]

    # Each call returns the rows accumulated so far, as the real parser does
    controller.parser.parse_inventory_page.side_effect = [
        [["PART-A", "WIDGET", "ea", 1, 0, 0, 0, 1, 0, 0, 0]],
        [
            ["PART-A", "WIDGET", "ea", 1, 0, 0, 0, 1, 0, 0, 0],
            ["PART-B", "GADGET", "ea", 2, 0, 0, 0, 2, 0, 0, 0],
        ],
    ]

    inventory = controller.controller.process_inventory_file("Inventory.pdf")

    assert controller.parser.parse_inventory_page.call_args_list == [
        call("page one", []),
        call("page two", [["PART-A", "WIDGET", "ea", 1, 0, 0, 0, 1, 0, 0, 0]]),
    ]

    # One entry per parsed row, built in the parser's column order
    assert [entry.part for entry in inventory] == ["PART-A", "PART-B"]


def test_process_inventory_file_logs_the_bare_filename(controller):
    """
    Tests that the results file records the file's name rather than its path, so
    its contents do not vary with the platform or how the file was selected

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.file_io.read_pdf.return_value = ["page one"]
    controller.parser.parse_inventory_page.return_value = []

    controller.controller.process_inventory_file(
        "C:/Some/Absolute/Path/Inventory 01222024.pdf"
    )

    logged = [
        written.args[0]
        for written in controller.file_io.write_to_results_file.call_args_list
    ]
    assert "Processing inventory file: Inventory 01222024.pdf" in logged
    assert "Number of Pages in Inventory: 1" in logged


###############################################################################
###         Tests InventoryAppController -> process_turnover_file()         ###
###############################################################################
def test_process_turnover_file_writes_each_entry_to_the_results_file(controller):
    """
    Tests that every turnover entry parsed out of the report is recorded in the
    results file, which the integration test diffs against its canonical copy

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.file_io.read_pdf.return_value = ["page one"]
    controller.parser.parse_turnover_page.return_value = [
        ["PART-A", 10, 5.0, 2.0, 1.5],
        ["PART-B", 20, 6.0, 3.0, 2.5],
    ]

    turnover = controller.controller.process_turnover_file(Path("Turnover.pdf"))

    assert [entry.part_description for entry in turnover] == ["PART-A", "PART-B"]

    logged = [
        written.args[0]
        for written in controller.file_io.write_to_results_file.call_args_list
    ]
    for entry in turnover:
        assert entry.to_formatted_string() in logged


###############################################################################
###           Tests InventoryAppController -> process_inventory()           ###
###############################################################################
def test_process_inventory_writes_the_spreadsheet_and_reports_success(controller):
    """
    Tests the successful path end to end: the inventory is written to a new
    workbook, one turnover column group is appended per turnover report, the
    workbook is saved and the user is told it worked

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.file_io.list_turnover_files.return_value = [
        Path("TurnoverReports/January.pdf"),
        Path("TurnoverReports/February.pdf"),
    ]
    controller.file_io.save_workbook.return_value = True
    workbook = controller.file_io.create_workbook.return_value

    report_status = MagicMock()

    with (
        patch.object(
            controller.controller, "process_inventory_file", return_value=[InventoryEntry(part="PART-A")]
        ),
        patch.object(controller.controller, "process_turnover_file", return_value=[]),
        patch(
            "source.InventoryAppController.setupMainSpreadsheet", return_value=11
        ) as mock_setup_main,
        patch(
            "source.InventoryAppController.setupSpreadsheetTurnoverHeader"
        ) as mock_turnover_header,
        patch(
            "source.InventoryAppController.appendTurnoverToSpreadsheet"
        ) as mock_append,
    ):
        result = controller.controller.process_inventory(
            "Inventory 01222024.pdf", all_columns_selected(), report_status
        )

    assert result is True
    mock_setup_main.assert_called_once()

    # Each turnover report takes the next column, named after its own file
    assert [made.args[2] for made in mock_turnover_header.call_args_list] == [11, 12]
    assert [made.args[3] for made in mock_turnover_header.call_args_list] == [
        "January",
        "February",
    ]
    assert [made.args[3] for made in mock_append.call_args_list] == [11, 12]

    controller.file_io.save_workbook.assert_called_once_with(workbook)
    report_status.assert_called_with("Successfully processed Inventory Availability!")


def test_process_inventory_derives_the_output_name_from_the_pdf_name(controller):
    """
    Tests that the spreadsheet is named after the date in the inventory PDF's
    filename, which is how the user identifies the report

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.file_io.list_turnover_files.return_value = []
    controller.file_io.save_workbook.return_value = True

    with (
        patch.object(
            controller.controller, "process_inventory_file", return_value=[InventoryEntry(part="PART-A")]
        ),
        patch("source.InventoryAppController.setupMainSpreadsheet", return_value=11),
    ):
        controller.controller.process_inventory(
            "Inventory Availability 01222024.pdf", all_columns_selected(), MagicMock()
        )

    controller.file_io.create_workbook.assert_called_once_with("01222024")


def test_process_inventory_falls_back_to_a_generic_output_name(controller):
    """
    Tests that a PDF whose name carries no date still produces a report, rather
    than failing on the filename

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.file_io.list_turnover_files.return_value = []
    controller.file_io.save_workbook.return_value = True

    with (
        patch.object(
            controller.controller, "process_inventory_file", return_value=[InventoryEntry(part="PART-A")]
        ),
        patch("source.InventoryAppController.setupMainSpreadsheet", return_value=11),
    ):
        controller.controller.process_inventory(
            "Inventory Availability", all_columns_selected(), MagicMock()
        )

    controller.file_io.create_workbook.assert_called_once_with("InventoryReport")


def test_process_inventory_reports_and_returns_false_on_an_unreadable_pdf(controller):
    """
    Tests that an inventory PDF that could not be read stops the run before a
    workbook is created, and tells the user rather than failing silently

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    report_status = MagicMock()

    with patch.object(
        controller.controller, "process_inventory_file", return_value=[]
    ):
        result = controller.controller.process_inventory(
            "Inventory.pdf", all_columns_selected(), report_status
        )

    assert result is False
    controller.file_io.create_workbook.assert_not_called()
    report_status.assert_called_with(
        "Could not read the selected Inventory PDF. See log for details."
    )


def test_process_inventory_reports_and_returns_false_when_the_workbook_fails(
    controller,
):
    """
    Tests that a workbook the file I/O controller could not create stops the run
    before any column is written

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.file_io.create_workbook.return_value = None
    report_status = MagicMock()

    with (
        patch.object(
            controller.controller, "process_inventory_file", return_value=[InventoryEntry(part="PART-A")]
        ),
        patch("source.InventoryAppController.setupMainSpreadsheet") as mock_setup_main,
    ):
        result = controller.controller.process_inventory(
            "Inventory.pdf", all_columns_selected(), report_status
        )

    assert result is False
    mock_setup_main.assert_not_called()
    report_status.assert_called_with(
        "Could not create the output spreadsheet. See log for details."
    )


def test_process_inventory_reports_and_returns_false_when_the_save_fails(controller):
    """
    Tests that a workbook that could not be saved is reported as a failure, so the
    user does not believe a report was produced

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.file_io.list_turnover_files.return_value = []
    controller.file_io.save_workbook.return_value = False
    report_status = MagicMock()

    with (
        patch.object(
            controller.controller, "process_inventory_file", return_value=[InventoryEntry(part="PART-A")]
        ),
        patch("source.InventoryAppController.setupMainSpreadsheet", return_value=11),
    ):
        result = controller.controller.process_inventory(
            "Inventory.pdf", all_columns_selected(), report_status
        )

    assert result is False
    report_status.assert_called_with(
        "Could not save the output spreadsheet. See log for details."
    )
