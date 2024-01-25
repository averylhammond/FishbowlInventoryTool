import os, glob, logging, tabula, re
import PySimpleGUI as sg
from InventoryEntry import *
from spreadsheetDriver import *

# Get cwd of executable plus folder that contains PDFs
inventoryDir = os.getcwd() + "/InventoryAvailability/"

# processInventoryPage is responsibile for parsing a page worth of PDF table data
# and converting each line into an InventoryEntry object
# params: page: str, the page of PDF table data
# params: inventoryTable[], InventoryEntry: the current list of table entries
# returns: inventoryTable[], InventoryEntry: the new up-to-date list of all
# pdf table entries including the page that was just processed
def processInventoryPage(page, inventoryTable):

    # Loop through all lines in the page but skip first two lines that contain header info
    for line in page.splitlines()[2:]:
        
        # Use double space to separate white space from strings
        data = line.split("  ")
        
        # Strip out excess spaces
        data = [i for i in data if i != '']

        # Case: This row is the first, contains all data to populate an entry
        if data[-1] != 'NaN':
            entry = InventoryEntry()
            entry.populateInventoryEntry(data)
            inventoryTable.append(entry)

        # Case: Not the first row, see if part or description data needs to be updated
        else:
            if data[1].lstrip() != 'NaN':
                inventoryTable[-1].part += data[1]
            if data[2].lstrip() != 'NaN':
                inventoryTable[-1].description += data[2]

    # Return up to date list with new entries
    return inventoryTable

# processInventoryFile processes a given inventory table by splitting the pdf into
# pages and processing each page
# params: filepath, str, the path to the file to be opened and processed
# returns: inventoryTable[], list of InventoryEntry class objects pertaining
# to filenames inventory entries
def processInventoryFile(filepath):
    
    # Table that will contain InventoryEntry objects
    inventoryTable = []

    # Read pdf data
    data = tabula.read_pdf(filepath, pages="all")

    if __debug__:
        logging.debug(f"Processing file: {filepath}")
        logging.debug(f"Number of Pages in Inventory: {len(data)}")

    # Loop through each page of table data and process each page
    # Update inventoryTable with each new page processed
    for page in data:
        inventoryTable = processInventoryPage(page.to_string(), inventoryTable)

    if __debug__:
        for i in inventoryTable:
            i.dumpInventoryEntry()

    return inventoryTable


def buildCheckboxDict(values):
    return {
        "Part" : values["-PART-"],
        "Description" : values["-DESCRIPTION-"],
        "UOM" : values["-UOM-"],
        "OnHand" : values["-ONHAND-"],
        "Allocated" : values["-ALLOCATED-"],
        "NotAvailable" : values["-NOTAVAILABLE-"],
        "DropShip" : values["-DROPSHIP-"],
        "Available" : values["-AVAILABLE-"],
        "OnOrder" : values["-ONORDER-"],
        "Committed" : values["-COMMITTED-"],
        "Short" : values["-SHORT-"]
     }
    
    
# run is the main loop of the program.
# params: N/A
# returns: N/A
def run():

    # Instantiate output window
    output = sg.Text()

    # Define GUI layout
    layout = [
        [sg.Text("Choose an Inventory Availability PDF to process...")],  # First text window
        [sg.InputText(key = "-FILE_PATH-"), sg.FileBrowse(initial_folder=inventoryDir, file_types=[("PDF Files", "*.pdf")])],
        [sg.Text("Please check all elements that you would like to have included on the report:")],  # First text window
        [sg.Checkbox("Part", key="-PART-"), sg.Checkbox("Description", key="-DESCRIPTION-"), sg.Checkbox("UOM", key="-UOM-"), sg.Checkbox("On Hand", key="-ONHAND-")],
        [sg.Checkbox("Allocated", key="-ALLOCATED-"), sg.Checkbox("Not Available", key="-NOTAVAILABLE-"), sg.Checkbox("Drop Ship", key="-DROPSHIP-")],
        [sg.Checkbox("Available", key="-AVAILABLE-"), sg.Checkbox("On Order", key="-ONORDER-"), sg.Checkbox("Committed", key="-COMMITTED-"), sg.Checkbox("Short", key="-SHORT-")],
        [sg.Button("Process This Inventory"), sg.Exit()],  # Exit button
        [output]  # Output text window
    ]

    # Set theme for big style
    sg.theme("LightGreen5")

    # Create window
    window = sg.Window("Automated Inventory Processor", layout, size=(500,500))

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
                output.update("Please choose a valid Inventory Availability PDF file!")
            
            else:
                # Update output text
                output.update("Processing Inventory... Please wait.")

                # Create a dictionary with checkbox input to determine which columns to show
                # based on user input
                checkboxDict = buildCheckboxDict(values)

                # Read in all data from the inventory PDF file
                inventory = processInventoryFile(values["-FILE_PATH-"])

                # Get the date of the inventory file from the name. This will be the name of the excel file
                filename = (re.search("(\d*).pdf", values["-FILE_PATH-"])).group().replace(".pdf", "")
            
                # Setup a spreadsheet with the inventory availability
                setupSpreadsheet(inventory, filename, checkboxDict)
            
                output.update("Successfully processed Inventory Availability!")

    # If break, close app
    window.close()

        
# Entry point
if __name__ == "__main__":

    # Setup logging
    logging.basicConfig(level = logging.DEBUG, format = "[%(levelname)s] %(asctime)s - %(message)s")

    # Setup and run main program loop
    run()