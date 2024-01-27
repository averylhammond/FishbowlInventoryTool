import os, logging, tabula, re, win32gui, win32con
import PySimpleGUI as sg
from InventoryEntry import *
from TurnoverEntry import *
from spreadsheetDriver import *

# Uncomment these lines when running pyinstaller to hide the windows terminal
# upon program execution
#hide = win32gui.GetForegroundWindow()
#win32gui.ShowWindow(hide, win32con.SW_HIDE)

# Get cwd of executable plus folder that contains PDFs
inventoryDir = os.getcwd() + "/InventoryAvailability/"
turnoverDir = os.getcwd() + "/TurnoverReports/"

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
        logging.debug(f"Processing inventory file: {filepath}")
        logging.debug(f"Number of Pages in Inventory: {len(data)}")

    # Loop through each page of table data and process each page
    # Update inventoryTable with each new page processed
    for page in data:
        inventoryTable = processInventoryPage(page.to_string(), inventoryTable)

    return inventoryTable


# buildCheckboxDict will take GUI inputs and build a dictionary representing the
# checkbox input data from the user
# params: values: list, all user inputs from the GUI
# returns: N/A
def buildCheckboxDict(values):
    return {
        "Part" : True,  # Always include part 
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


# processTurnoverPage is responsibile for parsing a page worth of PDF table data
# and converting each "totals" line into a TurnoverEntry object
# params: page: str, the page of PDF table data
# params: turnoverTable[], TurnoverEntry: the current list of table entries
# returns: turnoverTable[], TurnoverEntry: the new up-to-date list of all
# pdf table entries including the page that was just processed
def processTurnoverPage(page, turnoverTable):

    # Loop through all lines in the page but skip first two lines that contain header info
    for line in page.splitlines():
        
        # Use double space to separate white space from strings
        data = line.split("  ")
        
        # Strip out excess spaces
        data = [i for i in data if i != '']

        # Second word will always contain 'Totals:' if a valid total line
        if 'Totals:' in data[1]:
            entry = TurnoverEntry()
            entry.populateTurnoverEntry(data)
            turnoverTable.append(entry)

    # Return up to date list with new entries
    return turnoverTable


# processTurnoverFile processes a given turnover table by splitting the pdf into
# pages and processing each page
# params: filepath, str, the path to the file to be opened and processed
# returns: turnoverTable[], list of TurnoverEntry class objects pertaining
# to filenames turnover entries
def processTurnoverFile(filepath):

    # Table that will contain InventoryEntry objects
    turnoverTable = []

    # Read pdf data
    data = tabula.read_pdf(filepath, pages="all")

    if __debug__:
        logging.debug(f"Processing turnover file: {filepath}")
        logging.debug(f"Number of Pages in turnover report: {len(data)}")

    # Loop through each page of table data and process each page
    # Update inventoryTable with each new page processed
    for page in data:
        turnoverTable = processTurnoverPage(page.to_string(), turnoverTable)
    
    #if __debug__:
        #for i in turnoverTable:
            #i.dumpTurnoverEntry()

    return turnoverTable
    
    
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
        [sg.Checkbox("Description", key="-DESCRIPTION-"), sg.Checkbox("UOM", key="-UOM-"), sg.Checkbox("On Hand", key="-ONHAND-"), sg.Checkbox("Allocated", key="-ALLOCATED-")],
        [sg.Checkbox("Not Available", key="-NOTAVAILABLE-"), sg.Checkbox("Drop Ship", key="-DROPSHIP-"), sg.Checkbox("Available", key="-AVAILABLE-")],
        [sg.Checkbox("On Order", key="-ONORDER-"), sg.Checkbox("Committed", key="-COMMITTED-"), sg.Checkbox("Short", key="-SHORT-")],
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
            
                # Spreadsheet Workbook definition
                workbook = xlsxwriter.Workbook(filename + ".xlsx")
                
                # Setup a spreadsheet with the inventory availability
                nextCol = setupMainSpreadsheet(workbook, inventory, checkboxDict)

                if __debug__:
                    for i in inventory:
                        i.dumpInventoryEntry()

                # Process each turnover report file in the TurnoverReports directory
                for file in os.listdir(turnoverDir):
                    turnover = processTurnoverFile(turnoverDir + file)

                    # Append turnover data to columns in workbook
                    appendTurnoverToSpreadsheet(workbook, turnover, inventory, nextCol)
                    nextCol += 1

                # Save and close the spreadsheet
                workbook.close()
            
                output.update("Successfully processed Inventory Availability!")

    # If break, close app
    window.close()

        
# Entry point
if __name__ == "__main__":

    # Setup logging
    logging.basicConfig(level = logging.DEBUG, format = "[%(levelname)s] %(asctime)s - %(message)s")

    # Setup and run main program loop
    run()