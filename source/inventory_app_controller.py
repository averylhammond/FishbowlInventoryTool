import threading
import traceback
from collections.abc import Callable
from typing import TYPE_CHECKING

from fishbowl_common import (
    ArgumentProvider,
    PatchNotes,
    SettingsRepository,
    UpdateCoordinator,
    compare_versions,
)

from source.columns import all_columns_selected
from source.constants import (
    APP_NAME,
    GITHUB_REPO,
    INSTALLER_ASSET_PATTERN,
    PATCH_NOTES_PATH,
    SETTING_KEY_LAST_SEEN_VERSION,
    SETTINGS_DB_PATH,
    VERSION,
)
from source.inventory_app_file_io import InventoryAppFileIO
from source.inventory_processor import InventoryProcessor

# Imported for the display attribute's annotation only. A runtime import here
# would load tkinter on a headless run, which start_application() goes out of
# its way to avoid.
if TYPE_CHECKING:
    from source.gui.inventory_app_display import InventoryAppDisplay


# InventoryAppController class to drive logic for processing inventory and
# turnover report PDFs.
class InventoryAppController:
    def __init__(self) -> None:
        """
        Initializes the InventoryAppController object.
        """

        # Create the file I/O controller
        self.file_io = InventoryAppFileIO()

        # Processor that does the parsing and spreadsheet writing, handed the same
        # file I/O controller so every read and write in the app goes through one object
        self.processor = InventoryProcessor(file_io=self.file_io)

        # Argument provider to check for integration test (headless) mode
        self.argument_provider = ArgumentProvider(description="Fishbowl inventory availability report generator")

        # The GUI, constructed in start_application() rather than here so that a
        # headless run never builds a window it has no display for
        self.display: InventoryAppDisplay | None = None

        # The persisted settings store, constructed alongside the GUI in
        # start_application() so that a headless run touches no database
        self.settings_repository: SettingsRepository | None = None

        # The update coordinator, constructed alongside the GUI in
        # start_application() since it reports its outcome through the display
        self.update_coordinator: UpdateCoordinator | None = None

        # The patch notes reader, constructed alongside the GUI in
        # start_application() since its notes are only ever shown in a window
        self.patch_notes: PatchNotes | None = None

        # Start each run with a clean results file
        self.file_io.reset_results_file()

    def handle_check_for_updates(self) -> None:
        """
        Runs an on-demand update check, triggered by the Help menu's
        "Check for Updates" item. Wired into the display as its update callback,
        which is the display's only route to the network.
        """

        self.update_coordinator.start(manual=True)

    def handle_view_patch_notes(self) -> None:
        """
        Shows the patch notes on demand, triggered by the Help menu's "What's New"
        item. Every version up to the running one is shown, newest first, since a
        user who has already been shown an update's notes has no other way back to
        them. Wired into the display as its patch notes callback.
        """

        notes = self.patch_notes.notes_since(VERSION, None)

        # Unlike the startup check below, a request the user made explicitly is
        # answered even when there is nothing to show
        if notes:
            self.display.show_patch_notes(APP_NAME, VERSION, notes)
        else:
            self.display.show_popup(
                title="No Patch Notes",
                message=f"No patch notes found at: {PATCH_NOTES_PATH}.",
            )

    def show_patch_notes_if_updated(self, saved_settings: dict[str, str]) -> None:
        """
        Shows the user what changed when this launch is the first one after an
        update, and records the running version either way.

        Nothing is shown on a fresh install (no version was ever stored), on an
        ordinary relaunch, or after a downgrade: in none of those cases did an
        update just happen. The very first launch after upgrading into this
        feature shows nothing either, since a user coming from a build that never
        wrote the setting is indistinguishable from a first-time user.

        Args:
            saved_settings: The settings persisted by the last run, holding the
                version that run was on
        """

        last_seen_version = saved_settings.get(SETTING_KEY_LAST_SEEN_VERSION)

        # Record the running version before deciding anything, so an update's
        # notes are shown once rather than on every launch that follows it
        self.handle_save_setting(SETTING_KEY_LAST_SEEN_VERSION, VERSION)

        if not last_seen_version or compare_versions(last_seen_version, VERSION) >= 0:
            return

        # Every version the user skipped, not just the one they landed on
        notes = self.patch_notes.notes_since(VERSION, last_seen_version)
        if not notes:
            return

        # Open the window once the main loop is running rather than inline: the
        # shared window centers itself over this one, whose geometry is not known
        # until the root window has been mapped
        self.display.after(0, self.display.show_patch_notes, APP_NAME, VERSION, notes)

    def handle_process_inventory(self, inventory_pdf_path: str, checkbox_dict: dict[str, bool]) -> None:
        """
        Processes the inventory PDF the user chose in the GUI on a background
        thread, routing status messages to the GUI's output box. Wired into the
        display as its process callback.

        Args:
            inventory_pdf_path: Path to the inventory availability PDF to process
            checkbox_dict: Column-selection dict deciding which columns to emit
        """

        self._start_processing(
            lambda report_status: self.processor.process_inventory(inventory_pdf_path, checkbox_dict, report_status)
        )

    def handle_process_all_inventories(self, checkbox_dict: dict[str, bool]) -> None:
        """
        Processes every inventory PDF in the inventory directory on a background
        thread, routing status messages to the GUI's output box. Wired into the
        display as its process-all callback.

        Args:
            checkbox_dict: Column-selection dict deciding which columns to emit
        """

        self._start_processing(
            lambda report_status: self.processor.process_all_inventories(checkbox_dict, report_status)
        )

    def _start_processing(self, work: Callable[[Callable[[str], None]], bool]) -> None:
        """
        Locks the GUI's process buttons and spawns a daemon thread to run a
        processing job.

        Running on a background thread keeps the window responsive while PDFs are
        parsed and spreadsheets written. Daemon, so exiting mid-run does not hang
        the application waiting on it.

        Args:
            work: The processing job, called with the status callback to report
                through
        """

        # Locked here, on the GUI thread, so a second click cannot start an
        # overlapping run before the worker gets going
        self.display.set_processing(True)
        threading.Thread(target=self._run_processing, args=(work,), daemon=True).start()

    def _run_processing(self, work: Callable[[Callable[[str], None]], bool]) -> None:
        """
        Worker-thread body for a processing job.

        Every status line and the final unlock are handed back to the GUI thread
        via display.after() so the toolkit is only ever touched from the thread
        that owns it.

        Args:
            work: The processing job, called with the status callback to report
                through
        """

        try:
            work(lambda message: self.display.after(0, self.display.write_output, message))
        except Exception:  # noqa: BLE001
            # The release build has no console, so an uncaught error here would
            # vanish without a trace; log it and tell the user rather than stop
            # silently
            self.file_io.write_to_results_file(traceback.format_exc())
            self.display.after(0, self.display.write_output, "Processing failed unexpectedly. See log for details.")
        finally:
            # Unlocked whatever happened, or a failed run would leave the buttons
            # disabled for the rest of the session
            self.display.after(0, self.display.set_processing, False)

    def handle_save_setting(self, key: str, value: str) -> None:
        """
        Persists a single user setting so it is restored on the next launch. Wired
        into the display as its settings callback.

        Args:
            key: The setting's identifier (e.g. "theme", "font_family")
            value: The setting's value to store
        """

        self.settings_repository.save_setting(key=key, value=value)

    def run_integration_test(self) -> None:
        """
        Runs the application headless (no GUI): every inventory/turnover column is
        included and every inventory PDF in the inventory directory is processed. This
        lets a CI workflow generate the results file without any GUI interaction.
        """

        # Surface I/O failures to stdout since there is no GUI output line here
        self.file_io.report_error = lambda title, message: print(f"{title}: {message}")

        # Include every column. The keys come from source/columns.py, the single
        # source of truth the GUI's checkbox grid is also built from.
        checkbox_dict = all_columns_selected()

        # Process every inventory PDF, routing status to stdout (not the results file)
        self.processor.process_all_inventories(checkbox_dict, print)

    def start_application(self) -> None:
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
        from source.gui.inventory_app_display import InventoryAppDisplay  # noqa: PLC0415

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
            process_all_callback=self.handle_process_all_inventories,
            read_file_callback=self.file_io.read_text_file,
            check_for_updates_callback=self.handle_check_for_updates,
            view_patch_notes_callback=self.handle_view_patch_notes,
            save_settings_callback=self.handle_save_setting,
            title="Automated Inventory Processor",
            window_resolution="700x700",
            settings=saved_settings,
        )

        # Wire the GUI's popup into the file I/O controller and the settings
        # repository so file and database failures reach the user without coupling
        # either of them to the GUI. File I/O errors are raised on the processing
        # worker thread, so they reach the popup through after() rather than
        # touching the toolkit from that thread; database errors only arise on
        # the GUI thread.
        self.file_io.report_error = lambda title, message: self.display.after(
            0, self.display.show_popup, title, message
        )
        self.settings_repository.report_error = self.display.show_popup

        # Kick off a background check for a newer release before entering the GUI
        # loop. Built here rather than in __init__ because it reports through the
        # display, and confined to this branch so integration-test mode performs
        # no network I/O. The asset pattern names this app's installer among the
        # release's assets, which is what lets the user update in place rather
        # than downloading it by hand.
        self.update_coordinator = UpdateCoordinator(
            current_version=VERSION,
            repo=GITHUB_REPO,
            display=self.display,
            asset_pattern=INSTALLER_ASSET_PATTERN,
        )
        self.update_coordinator.start()

        # Tell the user what changed if this is the first launch after an update.
        # Built here, in the GUI branch, for the same reason as everything above
        # it: headless mode reads no settings and opens no window.
        self.patch_notes = PatchNotes(notes_path=PATCH_NOTES_PATH)
        self.show_patch_notes_if_updated(saved_settings)

        self.display.mainloop()
