import re
from pathlib import Path
from fishbowl_common import ArgumentProvider
from source.columns import all_columns_selected
from source.InventoryAppFileIO import InventoryAppFileIO
from source.PdfTableParser import PdfTableParser
from source.InventoryEntry import InventoryEntry
from source.TurnoverEntry import TurnoverEntry
from source.spreadsheetDriver import *


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

        # Parser that turns page text into the rows the entry classes are built from
        self.parser = PdfTableParser()

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
    ###          InventoryAppController -> process_inventory_file()         ###
    ###########################################################################
    def process_inventory_file(self, filepath: str) -> list:
        """
        Processes an inventory PDF by parsing every page into rows, then converting
        each row into an InventoryEntry

        Args:
            filepath (str): The path to the inventory PDF to be opened and processed

        Returns:
            list: A list of InventoryEntry objects for the file's inventory entries
        """

        # Read pdf data
        pages = self.file_io.read_pdf(filepath)

        # Log the bare filename, not the path, so the results file reads the same
        # regardless of the platform or how the file was selected
        self.file_io.write_to_results_file(
            f"Processing inventory file: {Path(filepath).name}"
        )
        self.file_io.write_to_results_file(
            f"Number of Pages in Inventory: {len(pages)}"
        )

        # Parse every page before building entries, since a row's part or
        # description may wrap from the bottom of one page onto the top of the next
        rows = []
        for page in pages:
            rows = self.parser.parse_inventory_page(page, rows)

        # Table that will contain InventoryEntry objects. Each row holds one field
        # per column in declaration order, so it expands straight into the constructor
        inventory_table = [InventoryEntry(*row) for row in rows]

        return inventory_table

    ###########################################################################
    ###          InventoryAppController -> process_turnover_file()          ###
    ###########################################################################
    def process_turnover_file(self, filepath: Path) -> list:
        """
        Processes a turnover report PDF by parsing every page into rows, then
        converting each row into a TurnoverEntry

        Args:
            filepath (Path): The path to the turnover report PDF to be opened and
                processed

        Returns:
            list: A list of TurnoverEntry objects for the file's turnover entries
        """

        # Read pdf data
        pages = self.file_io.read_pdf(filepath)

        self.file_io.write_to_results_file(
            f"Processing turnover file: {Path(filepath).name}"
        )
        self.file_io.write_to_results_file(
            f"Number of Pages in turnover report: {len(pages)}"
        )

        rows = []
        for page in pages:
            rows = self.parser.parse_turnover_page(page, rows)

        # Table that will contain TurnoverEntry objects
        turnover_table = [TurnoverEntry(*row) for row in rows]

        for entry in turnover_table:
            self.file_io.write_to_results_file(entry.to_formatted_string())

        return turnover_table

    ###########################################################################
    ###             InventoryAppController -> process_inventory()           ###
    ###########################################################################
    def process_inventory(
        self, inventory_pdf_path: str, checkbox_dict: dict, report_status
    ) -> bool:
        """
        Processes a single inventory availability PDF into an output spreadsheet,
        appending each turnover report's columns, then saves the workbook. Shared by
        the GUI event loop and the headless integration-test path.

        Args:
            inventory_pdf_path (str): Path to the inventory availability PDF to process
            checkbox_dict (dict): Column-selection dict deciding which columns to emit
            report_status (Callable[[str], None]): Callback for user-facing status
                messages (the GUI output line, or stdout in headless mode)

        Returns:
            bool: True if the spreadsheet was saved, False if any step failed
        """

        report_status("Processing Inventory... Please wait.")

        # Read in all data from the inventory PDF file
        inventory = self.process_inventory_file(inventory_pdf_path)

        # Bail gracefully if the inventory PDF could not be read (the file I/O
        # controller has already surfaced the underlying error)
        if not inventory:
            report_status(
                "Could not read the selected Inventory PDF. See log for details."
            )
            return False

        # Get the date of the inventory file from the name. This will be the name of
        # the excel file. Fall back to a generic name if the path has no digit/.pdf.
        match = re.search(r"(\d*)\.pdf", inventory_pdf_path)
        filename = (
            match.group().replace(".pdf", "") if match else "InventoryReport"
        )

        # Spreadsheet Workbook definition
        workbook = self.file_io.create_workbook(filename)
        if workbook is None:
            report_status(
                "Could not create the output spreadsheet. See log for details."
            )
            return False

        # Setup a spreadsheet with the inventory availability
        nextCol = setupMainSpreadsheet(workbook, inventory, checkbox_dict)

        for i in inventory:
            self.file_io.write_to_results_file(i.to_formatted_string())

        # Process each turnover report file in the TurnoverReports directory
        for file in self.file_io.list_turnover_files():
            turnover = self.process_turnover_file(file)

            setupSpreadsheetTurnoverHeader(
                workbook, checkbox_dict, nextCol, file.stem
            )

            # Append turnover data to columns in workbook
            appendTurnoverToSpreadsheet(
                workbook, turnover, inventory, nextCol, checkbox_dict
            )
            nextCol += 1

        # Save and close the spreadsheet
        if self.file_io.save_workbook(workbook):
            report_status("Successfully processed Inventory Availability!")
            return True

        report_status(
            "Could not save the output spreadsheet. See log for details."
        )
        return False

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

        return self.process_inventory(
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
            self.process_inventory(str(path), checkbox_dict, print)

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
            title="Automated Inventory Processor",
            window_resolution="700x700",
        )

        # Wire the GUI's popup into the file I/O controller so file failures reach
        # the user without coupling file I/O to the GUI
        self.file_io.report_error = self.display.show_popup

        self.display.mainloop()
