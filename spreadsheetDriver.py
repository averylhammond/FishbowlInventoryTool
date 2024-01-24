import xlsxwriter

# setupSpreadsheetHeader will write the header information for each column to the spreadsheet
# params: workbook, xlsx.Workbook, the workbook object containing the worksheet
# params: worksheet, workbook.worksheet, the sheet to write the header information to
# returns: N/A 
def setupSpreadsheetHeader(workbook, worksheet):
    
    # TODO: Design UI such that user can choose which columns to show/hide
    worksheet.write('A1', 'Part')
    worksheet.write('B1', 'Description')
    worksheet.write('C1', 'UOM')
    worksheet.write('D1', 'On Hand')
    worksheet.write('E1', 'Allocated')
    worksheet.write('F1', 'Not Available')
    worksheet.write('G1', 'Drop Ship')
    worksheet.write('H1', 'Available')
    worksheet.write('I1', 'On Order')
    worksheet.write('J1', 'Committed')
    worksheet.write('K1', 'Short')


# writeEntryToSpreadSheet will write all of the data present in a InventoryEntry object
# to the corresponding column and row in the workbook
# params: workbook, xlsx.Workbook, the workbook object containing the worksheet
# params: worksheet, workbook.worksheet, the sheet to write the header information to
# params: row, int, the row number to write to
# params: entry, InventoryEntry, the object holding all inventory entry data to be written to the row
# returns: N/A
def writeEntryToSpreadsheet(workbook, worksheet, row, entry):
    worksheet.write("A" + row, entry.part)
    worksheet.write("B" + row, entry.description)
    worksheet.write("C" + row, entry.uom)
    worksheet.write("D" + row, entry.onHand)
    worksheet.write("E" + row, entry.allocated)
    worksheet.write("F" + row, entry.notAvailable)
    worksheet.write("G" + row, entry.dropShip)
    worksheet.write("H" + row, entry.available)
    worksheet.write("I" + row, entry.onOrder)
    worksheet.write("J" + row, entry.committed)
    worksheet.write("K" + row, entry.short)


# setupSpreadSheet will create a .xlsx file and write all parsed contents to it
# params: inventory: list of InventoryEntry objects, to be written to spreadsheet
# params: name: str, the date of the inventory file that is being processed
# returns: N/A
def setupSpreadsheet(inventory, name):

    # Spreadsheet Workbook definition
    workbook = xlsxwriter.Workbook(name + ".xlsx")
    
    # Start writing data on row 2 since header data is written to row 1
    row = 2

    worksheet = workbook.add_worksheet()
    setupSpreadsheetHeader(workbook, worksheet)

    # Loop through each table entry in the table and write to contents
    # to the corresponding worksheet
    for entry in inventory:
        writeEntryToSpreadsheet(workbook, worksheet, str(row), entry)
        row +=1

    # Save and close the spreadsheet
    workbook.close()