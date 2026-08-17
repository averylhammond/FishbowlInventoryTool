import threading

from fishbowl_common import ArgumentProvider, SettingsRepository, UpdateChecker
from source.columns import all_columns_selected
from source.constants import GITHUB_REPO, SETTINGS_DB_PATH, VERSION
from source.InventoryAppFileIO import InventoryAppFileIO
from source.InventoryProcessor import InventoryProcessor


# InventoryAppController class to drive logic for processing inventory and
# turnover report PDFs.
class InventoryAppController:

    ###########################################################################
    ###                InventoryAppController -> __init__()                 ###
    ###########################################################################
    def __init__(self):
        """
        Initializes the InventoryAppController object.
        """

        # Create the file I/O controller
        self.file_io = InventoryAppFileIO()

        # Processor that does the parsing and spreadsheet writing, handed the same
        # file I/O controller so every read and write in the app goes through one object
        self.processor = InventoryProcessor(file_io=self.file_io)

        # Argument provider to check for integration test (headless) mode
        self.argument_provider = ArgumentProvider(
            description="Fishbowl inventory availability report generator"
        )

        # The GUI, constructed in start_application() rather than here so that a
        # headless run never builds a window it has no display for
        self.display = None

        # The persisted settings store, constructed alongside the GUI in
        # start_application() so that a headless run touches no database
        self.settings_repository = None

        # Start each run with a clean results file
        self.file_io.reset_results_file()

    ###########################################################################
    ###         InventoryAppController -> handle_process_inventory()        ###
    ###########################################################################
    def handle_process_inventory(
        self, inventory_pdf_path: str, checkbox_dict: dict
    ) -> bool:
        """
        Processes the inventory PDF the user chose in the GUI, routing status
        messages to the GUI's output box. Wired into the display as its process
        callback.

        Args:
            inventory_pdf_path (str): Path to the inventory availability PDF to process
            checkbox_dict (dict): Column-selection dict deciding which columns to emit

        Returns:
            bool: True if the spreadsheet was saved, False if any step failed
        """

        return self.processor.process_inventory(
            inventory_pdf_path, checkbox_dict, self.display.write_output
        )

    ###########################################################################
    ###           InventoryAppController -> handle_save_setting()           ###
    ###########################################################################
    def handle_save_setting(self, key: str, value: str):
        """
        Persists a single user setting so it is restored on the next launch. Wired
        into the display as its settings callback.

        Args:
            key (str): The setting's identifier (e.g. "theme", "font_family")
            value (str): The setting's value to store
        """

        self.settings_repository.save_setting(key=key, value=value)

    ###########################################################################
    ###           InventoryAppController -> run_integration_test()          ###
    ###########################################################################
    def run_integration_test(self):
        """
        Runs the application headless (no GUI): every inventory/turnover column is
        included and every inventory PDF in the inventory directory is processed. This
        lets a CI workflow generate the results file without any GUI interaction.
        """

        # Surface I/O failures to stdout since there is no GUI output line here
        self.file_io.report_error = lambda title, message: print(
            f"{title}: {message}"
        )

        # Include every column. The keys come from source/columns.py, the single
        # source of truth the GUI's checkbox grid is also built from.
        checkbox_dict = all_columns_selected()

        # Process every inventory PDF, routing status to stdout (not the results file)
        for path in self.file_io.list_inventory_files():
            self.processor.process_inventory(str(path), checkbox_dict, print)

    ###########################################################################
    ###            InventoryAppController -> start_application()            ###
    ###########################################################################
    def start_application(self):
        """
        Starts the application by building the GUI and running the tkinter main
        loop until the user exits.

        Note: In integration test mode the GUI is skipped entirely and every inventory
        PDF is processed headless instead.
        """

        # In integration test mode, process all inventories headless without a GUI
        if self.argument_provider.integration_test_mode:
            self.run_integration_test()
            return

        # Imported here, after the check above, rather than at module scope so a
        # headless run never loads tkinter. Keep it here: the integration test
        # runs on a machine with no display attached.
        from source.gui.InventoryAppDisplay import InventoryAppDisplay

        # Load the settings the user last chose so the GUI can start out of the box
        # the way they left it. Built here rather than in __init__ for the same
        # reason the GUI is: integration test mode must touch no database and leave
        # no data directory behind.
        self.settings_repository = SettingsRepository(db_path=SETTINGS_DB_PATH)
        saved_settings = self.settings_repository.get_all_settings()

        # Create the GUI, giving it the callback that processes a chosen inventory
        # and the settings to restore the user's last theme, font and column choices
        self.display = InventoryAppDisplay(
            process_callback=self.handle_process_inventory,
            read_file_callback=self.file_io.read_text_file,
            check_for_updates_callback=self.handle_check_for_updates,
            save_settings_callback=self.handle_save_setting,
            title="Automated Inventory Processor",
            window_resolution="700x700",
            settings=saved_settings,
        )

        # Wire the GUI's popup into the file I/O controller and the settings
        # repository so file and database failures reach the user without coupling
        # either of them to the GUI
        self.file_io.report_error = self.display.show_popup
        self.settings_repository.report_error = self.display.show_popup

        # Kick off a background check for a newer release before entering the GUI
        # loop. Confined to this branch so integration-test mode performs no
        # network I/O.
        self._start_update_check()

        self.display.mainloop()

    ###########################################################################
    ###           InventoryAppController -> _start_update_check()           ###
    ###########################################################################
    def _start_update_check(self, manual: bool = False):
        """
        Spawns a daemon thread that checks for a newer release.

        Running on a background thread keeps the GUI from blocking while waiting on
        the GitHub API, and the daemon flag ensures a slow or stalled request can
        never delay application shutdown.

        Args:
            manual (bool): True when the check was triggered manually from the Help
                menu (the user should always get feedback), False for the silent
                startup check.
        """

        threading.Thread(
            target=self._run_update_check, args=(manual,), daemon=True
        ).start()

    ###########################################################################
    ###            InventoryAppController -> _run_update_check()            ###
    ###########################################################################
    def _run_update_check(self, manual: bool = False):
        """
        Worker-thread body for an update check.

        Performs the (blocking, but silent-on-failure) update check off the GUI
        thread, then hands the result back to the tkinter main thread via
        display.after() so the GUI is only ever touched from the GUI thread.

        Args:
            manual (bool): Passed through to _handle_update_result so it knows
                whether to surface "up to date"/failure feedback.
        """

        result = UpdateChecker(
            current_version=VERSION, repo=GITHUB_REPO
        ).check_for_update()
        self.display.after(0, self._handle_update_result, result, manual)

    ###########################################################################
    ###           InventoryAppController -> _handle_update_result()         ###
    ###########################################################################
    def _handle_update_result(self, result, manual: bool = False):
        """
        Handles the outcome of an update check on the GUI thread.

        Always shows the update popup when a strictly newer release exists. For a
        manual check the user also gets feedback when no update is available
        (an info popup) or the check failed (an error popup), so a deliberate
        action always confirms an outcome. The startup check (manual=False) stays
        silent in those cases so the user is never interrupted on launch.

        Args:
            result (UpdateCheckResult | None): The comparison outcome from
                UpdateChecker.check_for_update(), or None if the check failed.
            manual (bool): True when the check was triggered manually from the Help
                menu, enabling the up-to-date/failure feedback.
        """

        if result and result.update_available:
            self.display.show_update_available(result)
        elif manual:
            if result is None:
                self.display.show_popup(
                    "Update Check Failed",
                    "Could not check for updates. Please check your internet "
                    "connection and try again.",
                )
            else:
                self.display.show_popup(
                    "No Updates Available",
                    f"You're running the latest version ({VERSION}).",
                )

    ###########################################################################
    ###          InventoryAppController -> handle_check_for_updates()       ###
    ###########################################################################
    def handle_check_for_updates(self):
        """
        Runs an on-demand update check, triggered by the Help menu's
        "Check for Updates" item. Reuses the background daemon-thread pipeline so
        the GUI never blocks on the network, and flags the check as manual so the
        user always gets feedback about the outcome.
        """

        self._start_update_check(manual=True)
