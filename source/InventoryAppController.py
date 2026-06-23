import os, logging, tabula, re
import PySimpleGUI as sg
import xlsxwriter
from source.InventoryEntry import *
from source.TurnoverEntry import *
from source.spreadsheetDriver import *

# Uncomment these lines when running pyinstaller to hide the windows terminal
# upon program execution
# import win32gui, win32con
# hide = win32gui.GetForegroundWindow()
# win32gui.ShowWindow(hide, win32con.SW_HIDE)


# InventoryAppController class to drive logic for processing inventory and
# turnover report PDFs.
class InventoryAppController:

    ###########################################################################
    ###                InventoryAppController -> __init__()                 ###
    ###########################################################################
    def __init__(self):
        """
        Initializes the InventoryAppController object.

        Sets up the directories that hold the inventory and turnover report PDFs
        (relative to the executable's current working directory) and configures
        logging for the application.
        """

        # Setup logging
        logging.basicConfig(
            level=logging.DEBUG, format="[%(levelname)s] %(asctime)s - %(message)s"
        )

        # Get cwd of executable plus folder that contains PDFs
        self.inventory_dir = os.getcwd() + "/InventoryAvailability/"
        self.turnover_dir = os.getcwd() + "/TurnoverReports/"

    ###########################################################################
    ###          InventoryAppController -> process_inventory_page()         ###
    ###########################################################################
    def process_inventory_page(self, page: str, inventory_table: list) -> list:
        """
        Parses a page worth of PDF table data, converting each line into an
        InventoryEntry object and appending it to the running table

        Args:
            page (str): The page of PDF table data.
            inventory_table (list): The current list of InventoryEntry table entries

        Returns:
            list: The up-to-date list of InventoryEntry objects, including the page
                that was just processed
        """

        # Loop through all lines in the page but skip first two lines that contain header info
        for line in page.splitlines()[2:]:

            # Use double space to separate white space from strings
            data = line.split("  ")

            # Strip out excess spaces
            data = [i for i in data if i != ""]

            # Case: This row is the first, contains all data to populate an entry
            if data[-1] != "NaN":
                entry = InventoryEntry()
                entry.populateInventoryEntry(data)
                inventory_table.append(entry)

            # Case: Not the first row, see if part or description data needs to be updated
            else:
                if data[1].lstrip() != "NaN":
                    inventory_table[-1].part += data[1]
                if data[2].lstrip() != "NaN":
                    inventory_table[-1].description += data[2]

        # Return up to date list with new entries
        return inventory_table

    ###########################################################################
    ###          InventoryAppController -> process_inventory_file()         ###
    ###########################################################################
    def process_inventory_file(self, filepath: str) -> list:
        """
        Processes an inventory PDF by splitting it into pages and processing each
        page in turn

        Args:
            filepath (str): The path to the inventory PDF to be opened and processed

        Returns:
            list: A list of InventoryEntry objects for the file's inventory entries
        """

        # Table that will contain InventoryEntry objects
        inventory_table = []

        # Read pdf data
        data = tabula.read_pdf(filepath, pages="all")

        if __debug__:
            logging.debug(f"Processing inventory file: {filepath}")
            logging.debug(f"Number of Pages in Inventory: {len(data)}")

        # Loop through each page of table data and process each page
        # Update inventory_table with each new page processed
        for page in data:
            inventory_table = self.process_inventory_page(
                page.to_string(), inventory_table
            )

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
    ###           InventoryAppController -> process_turnover_page()         ###
    ###########################################################################
    def process_turnover_page(self, page: str, turnover_table: list) -> list:
        """
        Parses a page worth of PDF table data, converting each "Totals:" line into
        a TurnoverEntry object and appending it to the running table

        Args:
            page (str): The page of PDF table data
            turnover_table (list): The current list of TurnoverEntry table entries

        Returns:
            list: The up-to-date list of TurnoverEntry objects, including the page
                that was just processed
        """

        i = 0
        # Loop through all lines in the page but skip first two lines that contain header info
        for line in page.splitlines():

            # Use double space to separate white space from strings
            data = line.split("  ")

            # Strip out excess spaces
            data = [i for i in data if i != ""]

            # Second word will always contain 'Totals:' if a valid total line
            if "Totals:" in data[1]:
                entry = TurnoverEntry()
                entry.populateTurnoverEntry(data)
                turnover_table.append(entry)

        # Return up to date list with new entries
        return turnover_table

    ###########################################################################
    ###          InventoryAppController -> process_turnover_file()          ###
    ###########################################################################
    def process_turnover_file(self, filepath: str) -> list:
        """
        Processes a turnover report PDF by splitting it into pages and processing
        each page in turn

        Args:
            filepath (str): The path to the turnover report PDF to be opened and
                processed

        Returns:
            list: A list of TurnoverEntry objects for the file's turnover entries
        """

        # Table that will contain InventoryEntry objects
        turnover_table = []

        # Read pdf data
        data = tabula.read_pdf(filepath, pages="all")

        if __debug__:
            logging.debug(f"Processing turnover file: {filepath}")
            logging.debug(f"Number of Pages in turnover report: {len(data)}")

        # Loop through each page of table data and process each page
        # Update inventory_table with each new page processed
        for page in data:
            turnover_table = self.process_turnover_page(
                page.to_string(), turnover_table
            )

        if __debug__:
            for i in turnover_table:
                i.dumpTurnoverEntry()

        return turnover_table

    ###########################################################################
    ###            InventoryAppController -> start_application()            ###
    ###########################################################################
    def start_application(self):
        """
        Starts the application by building the GUI window and running the main
        event loop until the user exits.
        """

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
                    initial_folder=self.inventory_dir,
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
        window = sg.Window("Automated Inventory Processor", layout, size=(650, 500))

        # Main program loop
        while True:
            # Read user input from GUI
            event, values = window.read()

            # If exit is pressed, break out of loop and close window
            if event in (sg.WIN_CLOSED, "Exit"):
                break

            # If the process button is selected, process the invoice
            elif event == "Process This Inventory":

                # TODO: Revise this if else structure, don't like it
                if values["-FILE_PATH-"] == "":
                    output.update(
                        "Please choose a valid Inventory Availability PDF file!"
                    )

                else:
                    # Update output text
                    output.update("Processing Inventory... Please wait.")

                    # Create a dictionary with checkbox input to determine which columns to show
                    # based on user input
                    checkboxDict = self.build_checkbox_dict(values)

                    # Read in all data from the inventory PDF file
                    inventory = self.process_inventory_file(values["-FILE_PATH-"])

                    # Get the date of the inventory file from the name. This will be the name of the excel file
                    filename = (
                        (re.search("(\d*).pdf", values["-FILE_PATH-"]))
                        .group()
                        .replace(".pdf", "")
                    )

                    # Spreadsheet Workbook definition
                    workbook = xlsxwriter.Workbook(filename + ".xlsx")

                    # Setup a spreadsheet with the inventory availability
                    nextCol = setupMainSpreadsheet(workbook, inventory, checkboxDict)

                    if __debug__:
                        for i in inventory:
                            i.dumpInventoryEntry()

                    # Process each turnover report file in the TurnoverReports directory
                    for file in os.listdir(self.turnover_dir):
                        turnover = self.process_turnover_file(self.turnover_dir + file)

                        setupSpreadsheetTurnoverHeader(
                            workbook, checkboxDict, nextCol, file.replace(".pdf", "")
                        )

                        # Append turnover data to columns in workbook
                        appendTurnoverToSpreadsheet(
                            workbook, turnover, inventory, nextCol, checkboxDict
                        )
                        nextCol += 1

                    # Save and close the spreadsheet
                    workbook.close()

                    output.update("Successfully processed Inventory Availability!")

        # If break, close app
        window.close()
