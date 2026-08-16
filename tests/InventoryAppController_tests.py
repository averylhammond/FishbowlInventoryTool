import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, call, MagicMock

from source.columns import all_columns_selected
from source.InventoryAppController import InventoryAppController


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
            the mocked collaborator instances (`file_io`, `processor`, `arg_provider`)
    """

    with (
        patch("source.InventoryAppController.ArgumentProvider") as mock_arg_cls,
        patch("source.InventoryAppController.InventoryAppFileIO") as mock_file_io_cls,
        patch("source.InventoryAppController.InventoryProcessor") as mock_processor_cls,
    ):

        mock_arg_provider = mock_arg_cls.return_value
        mock_arg_provider.integration_test_mode = False

        yield SimpleNamespace(
            controller=InventoryAppController(),
            file_io=mock_file_io_cls.return_value,
            processor=mock_processor_cls.return_value,
            arg_provider=mock_arg_provider,
            file_io_cls=mock_file_io_cls,
            processor_cls=mock_processor_cls,
            arg_provider_cls=mock_arg_cls,
        )


###############################################################################
###               Tests InventoryAppController -> __init__()                ###
###############################################################################
def test_init_constructs_the_collaborators(controller):
    """
    Tests that the controller builds the file I/O controller, the processor it
    hands that same file I/O controller to, and the argument provider

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.file_io_cls.assert_called_once_with()
    controller.processor_cls.assert_called_once_with(file_io=controller.file_io)
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
        read_file_callback=controller.file_io.read_text_file,
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
    Tests that the headless path includes every column and hands the processor
    each inventory PDF the file I/O controller lists, routing status to stdout
    rather than the results file so the CI diff stays deterministic

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.file_io.list_inventory_files.return_value = [
        Path("InventoryAvailability/Inventory 01222024.pdf"),
        Path("InventoryAvailability/Inventory 02222024.pdf"),
    ]

    controller.controller.run_integration_test()

    assert controller.processor.process_inventory.call_args_list == [
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

    controller.controller.run_integration_test()

    # A reporter was installed, and it is callable with a title and a message
    assert callable(controller.file_io.report_error)
    controller.file_io.report_error("File Error", "Could not read the file")


###############################################################################
###        Tests InventoryAppController -> handle_process_inventory()       ###
###############################################################################
def test_handle_process_inventory_routes_status_to_the_output_box(controller):
    """
    Tests that the GUI's process callback runs the processor with status directed
    at the display's output box, and hands back its result

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.controller.display = MagicMock()
    controller.processor.process_inventory.return_value = True
    checkbox_dict = all_columns_selected()

    result = controller.controller.handle_process_inventory(
        "Inventory 01222024.pdf", checkbox_dict
    )

    controller.processor.process_inventory.assert_called_once_with(
        "Inventory 01222024.pdf",
        checkbox_dict,
        controller.controller.display.write_output,
    )
    assert result is True
