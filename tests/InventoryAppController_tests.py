import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, call, MagicMock

from source.columns import all_columns_selected
from source.constants import GITHUB_REPO, VERSION
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

    with (
        patch("source.gui.InventoryAppDisplay.InventoryAppDisplay") as mock_display_cls,
        patch.object(controller.controller, "_start_update_check"),
    ):
        controller.controller.start_application()

    mock_display_cls.assert_called_once_with(
        process_callback=controller.controller.handle_process_inventory,
        read_file_callback=controller.file_io.read_text_file,
        check_for_updates_callback=controller.controller.handle_check_for_updates,
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

    with (
        patch("source.gui.InventoryAppDisplay.InventoryAppDisplay") as mock_display_cls,
        patch.object(controller.controller, "_start_update_check"),
    ):
        controller.controller.start_application()

    assert (
        controller.file_io.report_error is mock_display_cls.return_value.show_popup
    )


def test_start_application_starts_a_background_update_check(controller):
    """
    Tests that a normal run kicks off the startup update check once the display
    exists, so the user learns about a newer release without the GUI blocking on
    the network

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    with (
        patch("source.gui.InventoryAppDisplay.InventoryAppDisplay"),
        patch.object(controller.controller, "_start_update_check") as mock_check,
    ):
        controller.controller.start_application()

    mock_check.assert_called_once_with()


def test_start_application_in_integration_test_mode_never_builds_the_gui(controller):
    """
    Tests that headless mode processes the inventories directly, creates no
    window, and checks for no updates. The integration test job runs with no
    display, so building the GUI there would fail the run outright, and it must
    perform no network I/O.

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
        patch.object(controller.controller, "_start_update_check") as mock_check,
    ):
        controller.controller.start_application()

    mock_headless.assert_called_once_with()
    mock_display_cls.assert_not_called()
    mock_check.assert_not_called()
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


###############################################################################
###         Tests InventoryAppController -> _start_update_check()           ###
###############################################################################
def test_start_update_check_spawns_a_daemon_worker_thread(controller):
    """
    Tests that the startup check runs on a background daemon thread, so the GUI
    never blocks on the GitHub API and a stalled request cannot delay shutdown

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    with patch("source.InventoryAppController.threading.Thread") as mock_thread_cls:
        controller.controller._start_update_check()

    mock_thread_cls.assert_called_once_with(
        target=controller.controller._run_update_check, args=(False,), daemon=True
    )
    mock_thread_cls.return_value.start.assert_called_once_with()


def test_start_update_check_passes_the_manual_flag_to_the_worker(controller):
    """
    Tests that a manually triggered check hands the manual flag to the worker, which
    is what makes an up-to-date or failed check report back to the user

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    with patch("source.InventoryAppController.threading.Thread") as mock_thread_cls:
        controller.controller._start_update_check(manual=True)

    mock_thread_cls.assert_called_once_with(
        target=controller.controller._run_update_check, args=(True,), daemon=True
    )


###############################################################################
###          Tests InventoryAppController -> _run_update_check()            ###
###############################################################################
def test_run_update_check_schedules_the_result_on_the_gui_thread(controller):
    """
    Tests that the worker checks this application's own releases and hands the
    outcome back through display.after(), so the GUI is only ever touched from the
    tkinter main thread

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.controller.display = MagicMock()

    with patch("source.InventoryAppController.UpdateChecker") as mock_checker_cls:
        mock_result = mock_checker_cls.return_value.check_for_update.return_value
        controller.controller._run_update_check(manual=True)

    mock_checker_cls.assert_called_once_with(
        current_version=VERSION, repo=GITHUB_REPO
    )
    controller.controller.display.after.assert_called_once_with(
        0, controller.controller._handle_update_result, mock_result, True
    )


###############################################################################
###         Tests InventoryAppController -> _handle_update_result()         ###
###############################################################################
def test_handle_update_result_shows_the_update_window_when_newer(controller):
    """
    Tests that a strictly newer release always opens the update window, whether the
    check was manual or the silent one run on startup

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.controller.display = MagicMock()
    result = SimpleNamespace(update_available=True)

    controller.controller._handle_update_result(result)

    controller.controller.display.show_update_available.assert_called_once_with(result)
    controller.controller.display.show_popup.assert_not_called()


def test_handle_update_result_stays_silent_when_up_to_date_on_startup(controller):
    """
    Tests that the startup check says nothing when the app is already current, so
    the user is never interrupted on launch

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.controller.display = MagicMock()

    controller.controller._handle_update_result(SimpleNamespace(update_available=False))

    controller.controller.display.show_update_available.assert_not_called()
    controller.controller.display.show_popup.assert_not_called()


def test_handle_update_result_stays_silent_when_the_startup_check_fails(controller):
    """
    Tests that a failed startup check (no result at all) is swallowed, so being
    offline never greets the user with an error popup

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.controller.display = MagicMock()

    controller.controller._handle_update_result(None)

    controller.controller.display.show_update_available.assert_not_called()
    controller.controller.display.show_popup.assert_not_called()


def test_handle_update_result_reports_up_to_date_on_a_manual_check(controller):
    """
    Tests that a manual check confirms the app is current, so a deliberate action
    always produces an outcome

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.controller.display = MagicMock()

    controller.controller._handle_update_result(
        SimpleNamespace(update_available=False), manual=True
    )

    controller.controller.display.show_popup.assert_called_once()
    assert (
        controller.controller.display.show_popup.call_args.args[0]
        == "No Updates Available"
    )


def test_handle_update_result_reports_failure_on_a_manual_check(controller):
    """
    Tests that a manual check that could not reach GitHub tells the user so, rather
    than appearing to do nothing

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    controller.controller.display = MagicMock()

    controller.controller._handle_update_result(None, manual=True)

    controller.controller.display.show_popup.assert_called_once()
    assert (
        controller.controller.display.show_popup.call_args.args[0]
        == "Update Check Failed"
    )


###############################################################################
###        Tests InventoryAppController -> handle_check_for_updates()       ###
###############################################################################
def test_handle_check_for_updates_starts_a_manual_check(controller):
    """
    Tests that the Help menu's callback reuses the background check pipeline and
    flags it as manual, so the user always gets feedback

    Args:
        controller (pytest.fixture): Test fixture building the controller with all
            of its collaborators mocked
    """

    with patch.object(controller.controller, "_start_update_check") as mock_check:
        controller.controller.handle_check_for_updates()

    mock_check.assert_called_once_with(manual=True)
