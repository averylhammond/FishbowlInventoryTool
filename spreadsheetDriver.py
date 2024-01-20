import xlsxwriter

# Global workbook definition
workbook = xlsxwriter.Workbook("InventoryAvailability.xlsx")

# setupSpreadsheetHeader will write the header information for each column to the spreadsheet
# params: worksheet, xlsx object, the workbook object to write the header information to
# returns: N/A 
def setupSpreadsheetHeader(worksheet):
    worksheet.write('A1', 'Part')
    worksheet.write('B1', 'Description')
    worksheet.write('C1', 'On Hand')
    worksheet.write('D1', 'Allocated')
    worksheet.write('E1', 'Not Available')
    worksheet.write('F1', 'Drop Ship')
    worksheet.write('G1', 'Available')
    worksheet.write('H1', 'On Order')
    worksheet.write('I1', 'Committed')
    worksheet.write('J1', 'Short')


# writeEntryToSpreadSheet will write all of the data present in a InventoryEntry object
# to the corresponding column and row in the workbook
# params: worksheet, worksheet, the sheet label to write to
# params: row, int, the row number to write to
# params: entry, InventoryEntry, the object holding all inventory entry data to be written to the row
# returns: N/A
def writeEntryToSpreadsheet(worksheet, row, entry):
    worksheet.write("A" + row, entry.part)
    worksheet.write("B" + row, entry.description)
    worksheet.write("C" + row, entry.onHand)
    worksheet.write("D" + row, entry.allocated)
    worksheet.write("E" + row, entry.notAvailable)
    worksheet.write("F" + row, entry.dropShip)
    worksheet.write("G" + row, entry.available)
    worksheet.write("H" + row, entry.onOrder)
    worksheet.write("I" + row, entry.committed)
    worksheet.write("J" + row, entry.short)


# setupSpreadSheet will create a .xlsx file and write all parsed contents to it
# params: allInventories: list of list of InventoryEntries, all tables to be written
# to the spreadsheet
# returns: N/A
def setupSpreadsheet(allInventories):
    
    # Start writing data on row 2 since header data is written to row 1
    row = 2

    # Loop through all inventory PDF files, set up a worksheet for each of them in
    # the spreadsheet
    for table in allInventories:
        worksheet = workbook.add_worksheet()
        setupSpreadsheetHeader(worksheet)

        # Loop through each table entry in each table and write to contents
        # to the corresponding worksheet
        for entry in table:
            writeEntryToSpreadsheet(worksheet, str(row), entry)
            row +=1

    workbook.close()