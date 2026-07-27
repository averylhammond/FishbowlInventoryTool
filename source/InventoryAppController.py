import re
from collections import defaultdict
from pathlib import Path
from fishbowl_common import ArgumentProvider
from source.constants import INVENTORY_DIR
from source.InventoryAppFileIO import InventoryAppFileIO
from source.PdfTableParser import PdfTableParser
from source.InventoryEntry import *
from source.TurnoverEntry import *
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

        # Table that will contain InventoryEntry objects
        inventory_table = []
        for row in rows:
            entry = InventoryEntry()
            entry.populateInventoryEntry(row)
            inventory_table.append(entry)

        return inventory_table

    ###########################################################################
    ###           InventoryAppController -> build_checkbox_dict()           ###
    ###########################################################################
    def build_checkbox_dict(self, values: dict) -> dict:
        """
        Builds a dictionary representing the checkbox input data from the user,
        used to determine which columns to include in the report

        Args:
            values (dict): All user inputs read from the GUI window

        Returns:
            dict: A mapping of column name to bool indicating whether each column
                should be included in the output spreadsheet
        """
        return {
            "Part": True,  # Always include part
            "Description": values["-DESCRIPTION-"],
            "UOM": values["-UOM-"],
            "OnHand": values["-ONHAND-"],
            "Allocated": values["-ALLOCATED-"],
            "NotAvailable": values["-NOTAVAILABLE-"],
            "DropShip": values["-DROPSHIP-"],
            "Available": values["-AVAILABLE-"],
            "OnOrder": values["-ONORDER-"],
            "Committed": values["-COMMITTED-"],
            "Short": values["-SHORT-"],
            "tDescription": values["-TDESCRIPTION-"],
            "tUnits Sold": values["-TUNITSSOLD-"],
            "tAvg QOH": values["-TQOH-"],
            "tAvg TO Days": values["-TAVGTODAYS-"],
            "tTO Rate": values["-TTORATE-"],
        }

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
        turnover_table = []
        for row in rows:
            entry = TurnoverEntry()
            entry.populateTurnoverEntry(row)
            turnover_table.append(entry)

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

        # Include every column, reusing build_checkbox_dict as the single source of
        # the column keys (defaultdict returns True for every checkbox lookup)
        checkbox_dict = self.build_checkbox_dict(defaultdict(lambda: True))

        # Process every inventory PDF, routing status to stdout (not the results file)
        for path in self.file_io.list_inventory_files():
            self.process_inventory(str(path), checkbox_dict, print)

    ###########################################################################
    ###            InventoryAppController -> start_application()            ###
    ###########################################################################
    def start_application(self):
        """
        Starts the application by building the GUI window and running the main
        event loop until the user exits.

        Note: In integration test mode the GUI is skipped entirely and every inventory
        PDF is processed headless instead.
        """

        # In integration test mode, process all inventories headless without a GUI
        if self.argument_provider.integration_test_mode:
            self.run_integration_test()
            return

        # Imported here rather than at module scope so headless runs never pull in
        # PySimpleGUI (and the tkinter it imports), which they have no use for.
        # Remove this local import once the GUI moves into its own class — the
        # controller should not be importing GUI modules at all.
        import PySimpleGUI as sg

        # Instantiate output window
        output = sg.Text()

        # Define GUI layout
        layout = [
            [
                sg.Text("Choose an Inventory Availability PDF to process...")
            ],  # First text window
            [
                sg.InputText(key="-FILE_PATH-"),
                sg.FileBrowse(
                    initial_folder=str(INVENTORY_DIR),
                    file_types=[("PDF Files", "*.pdf")],
                ),
            ],
            [
                sg.Text(
                    "Please check all INVENTORY elements that you would like to have included on the report:"
                )
            ],  # First text window
            [
                sg.Checkbox("Description", key="-DESCRIPTION-"),
                sg.Checkbox("UOM", key="-UOM-"),
                sg.Checkbox("On Hand", key="-ONHAND-"),
                sg.Checkbox("Allocated", key="-ALLOCATED-"),
            ],
            [
                sg.Checkbox("Not Available", key="-NOTAVAILABLE-"),
                sg.Checkbox("Drop Ship", key="-DROPSHIP-"),
                sg.Checkbox("Available", key="-AVAILABLE-"),
            ],
            [
                sg.Checkbox("On Order", key="-ONORDER-"),
                sg.Checkbox("Committed", key="-COMMITTED-"),
                sg.Checkbox("Short", key="-SHORT-"),
            ],
            [
                sg.Text(
                    "Please check all TURNOVER elements that you would like to have included on the report:"
                )
            ],  # Second text window
            [
                sg.Checkbox("Description", key="-TDESCRIPTION-"),
                sg.Checkbox("Units Sold", key="-TUNITSSOLD-"),
                sg.Checkbox("Avg QOH", key="-TQOH-"),
            ],
            [
                sg.Checkbox("Avg TO Days", key="-TAVGTODAYS-"),
                sg.Checkbox("TO Rate", key="-TTORATE-"),
            ],
            [sg.Button("Process This Inventory"), sg.Exit()],  # Exit button
            [output],  # Output text window
        ]

        # Set theme for big style
        sg.theme("LightGreen5")

        # Create window
        window = sg.Window(
            "Automated Inventory Processor", layout, size=(650, 500)
        )

        # Now that the output element exists, surface any file I/O failure to the GUI
        # output line so the app never crashes on bad files.
        self.file_io.report_error = lambda title, message: output.update(
            f"{title}: {message}"
        )

        # Main program loop
        while True:
            # Read user input from GUI
            event, values = window.read()

            # If exit is pressed, break out of loop and close window
            if event in (sg.WIN_CLOSED, "Exit"):
                break

            # If the process button is selected, process the inventory
            elif event == "Process This Inventory":

                if values["-FILE_PATH-"] == "":
                    output.update(
                        "Please choose a valid Inventory Availability PDF file!"
                    )

                else:
                    # Process the chosen inventory PDF, surfacing status to the GUI
                    # output line
                    self.process_inventory(
                        values["-FILE_PATH-"],
                        self.build_checkbox_dict(values),
                        output.update,
                    )

        # If break, close app
        window.close()
