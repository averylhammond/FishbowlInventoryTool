import os, glob, logging, tabula, re
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
    
    
# run is the main loop of the program.
# params: N/A
# returns: N/A
def run():
    
    # Find the most recent inventory file in the /InventoryAvailability/ folder
    allFiles = glob.glob(inventoryDir + "*")
    mostRecentInventoryFile = max(allFiles, key=os.path.getctime)

    # Get the date of the inventory file from the name. This will be the name of the excel file
    filename = (re.search("(\d*).pdf", mostRecentInventoryFile)).group().replace(".pdf", "")

    # If no file found, exit program
    # TODO: Add UI warning if this happens
    if filename is None:
        os.exit()

    # Read in all data from the inventory PDF file
    inventory = processInventoryFile(mostRecentInventoryFile)

    # Setup a spreadsheet with the inventory availability
    setupSpreadsheet(inventory, filename)


        
# Entry point
if __name__ == "__main__":

    # Setup logging
    logging.basicConfig(level = logging.DEBUG, format = "[%(levelname)s] %(asctime)s - %(message)s")

    # Setup and run main program loop
    run()