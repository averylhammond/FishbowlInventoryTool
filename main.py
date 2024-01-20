import os, xlsxwriter, logging, tabula
from search import *
from InventoryEntry import *

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
# params: filename, str, the name of the file to be opened and processed
# returns: inventoryTable[], list of InventoryEntry class objects pertaining
# to filenames inventory entries
def processInventoryFile(filename):
    
    # Table that will contain InventoryEntry objects
    inventoryTable = []

    # Read pdf data
    data = tabula.read_pdf(inventoryDir + filename, pages="all")

    if __debug__:
        logging.debug(f"Processing file: {filename}")
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
    
    # Initialize list of all Inventory Availability PDFs
    allInventories = []

    # Create a list of all the Inventory Availability files to be parsed
    for filename in os.listdir(inventoryDir):
        allInventories.append(filename)

    # Main loop through all Inventory Availability PDFs
    # Each call to processInventoryFile will return a list
    # of inventory entries pertaining to it's table
    for filename in allInventories:
        allInventories.append(processInventoryFile(filename))

    # TODO: Create excel sheet with this information


        
# Entry point
if __name__ == "__main__":

    # Setup logging
    logging.basicConfig(level = logging.DEBUG, format = "[%(levelname)s] %(asctime)s - %(message)s")

    workbook = xlsxwriter.Workbook("Availability.xlsx")
    worksheet = workbook.add_worksheet()
    worksheet.write('A1', 'Hello..')
    worksheet.write('B1', 'Geeks')
    worksheet.write('C1', 'For')
    worksheet.write('D1', 'Geeks')
    workbook.close()

    # Setup and run main program loop
    run()