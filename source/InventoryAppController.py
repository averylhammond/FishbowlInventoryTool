from fishbowl_common import ArgumentProvider
from source.columns import all_columns_selected
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

        # Create the GUI, giving it the callback that processes a chosen inventory
        self.display = InventoryAppDisplay(
            process_callback=self.handle_process_inventory,
            read_file_callback=self.file_io.read_text_file,
            title="Automated Inventory Processor",
            window_resolution="700x700",
        )

        # Wire the GUI's popup into the file I/O controller so file failures reach
        # the user without coupling file I/O to the GUI
        self.file_io.report_error = self.display.show_popup

        self.display.mainloop()
