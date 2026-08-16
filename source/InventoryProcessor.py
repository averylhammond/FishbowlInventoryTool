import re
from pathlib import Path
from source.InventoryAppFileIO import InventoryAppFileIO
from source.PdfTableParser import PdfTableParser
from source.InventoryEntry import InventoryEntry
from source.TurnoverEntry import TurnoverEntry
from source.spreadsheetDriver import *


# InventoryProcessor class to parse inventory and turnover report PDFs and write
# the resulting data out to a spreadsheet.
class InventoryProcessor:

    ###########################################################################
    ###                  InventoryProcessor -> __init__()                   ###
    ###########################################################################
    def __init__(self, file_io: InventoryAppFileIO):
        """
        Initializes the InventoryProcessor object.

        Args:
            file_io (InventoryAppFileIO): File I/O controller used to read the PDFs,
                open and save the workbook, and write the results file
        """

        # File I/O controller used for every read and write this class performs
        self.file_io = file_io

        # Parser that turns page text into the rows the entry classes are built from
        self.parser = PdfTableParser()

    ###########################################################################
    ###            InventoryProcessor -> process_inventory_file()           ###
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
    ###            InventoryProcessor -> process_turnover_file()            ###
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
    ###               InventoryProcessor -> process_inventory()             ###
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
