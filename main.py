import PyPDF2, os, xlsxwriter, logging, tabula
from search import *
from InventoryLine import *

from tabulate import tabulate

# Get cwd of executable plus folder that contains PDFs
inventoryDir = os.getcwd() + "/InventoryAvailability/"


def processInventoryLine(line):
    
    lineObj = InventoryLine()
    wordList = line.split(" ")
    print(wordList)

    if len(wordList) >= 10:
        lineObj.short = wordList[-1]
        del wordList[-1]
        lineObj.committed = wordList[-1]
        del wordList[-1]
        lineObj.onOrder = wordList[-1]
        del wordList[-1]
        lineObj.available = wordList[-1]
        del wordList[-1]
        lineObj.dropShip = wordList[-1]
        del wordList[-1]
        lineObj.notAvailable = wordList[-1]
        del wordList[-1]
        lineObj.allocated = wordList[-1]
        del wordList[-1]
        lineObj.onHand = wordList[-1]
        del wordList[-1]

        lineObj.partDescription = " ".join(wordList)

    lineObj.dumpInventoryLine()
    

def processInventoryPage(page):

    # Trim off everything before table data (before the line "Order Committed Short")
    page = page[(page.find("Order Committed Short")):]
    
    # Loop through all lines in the page but skip first line
    for line in page.splitlines()[1:]:
        processInventoryLine(line)
    #processInventoryLine(page.splitlines()[1])

def processInventoryFile(filename):
        
    pdf = PyPDF2.PdfReader(inventoryDir + filename)
    numPages = len(pdf.pages)

    if __debug__:
        print(f"Processing file: {filename}")
        print(f"Number of Pages in Inventory: {numPages}")

    # This will eventually be the loop that processes each page
    # For now only doing one page until it's repeatable
    #for page in pdf.pages:
    #processInventoryPage(page.extract_text())
    processInventoryPage(pdf.pages[0].extract_text())
    
    #df = tabula.read_pdf(inventoryDir + filename, pages="all")
    


def run():
    # Initialize list of all Inventory Availability PDFs
    allInventories = []

    # Create a list of all the Inventory Availability files to be parsed
    for filename in os.listdir(inventoryDir):
        allInventories.append(filename)

    # Main loop through all Inventory Availability PDFs
    for filename in allInventories:
        processInventoryFile(filename)


        
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

    run()