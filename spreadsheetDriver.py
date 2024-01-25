import xlsxwriter

# setupSpreadsheetHeader will write the header information for each column to the spreadsheet
# params: workbook, xlsx.Workbook, the workbook object containing the worksheet
# params: worksheet, workbook.worksheet, the sheet to write the header information to
# returns: N/A 
def setupSpreadsheetHeader(workbook, worksheet):
    
    headerFormat = workbook.add_format({
        "valign": "vcenter",
        "align": "center",
        "bold": True,
        "font_size": 16,
        "bg_color": "#F0F0F0",
        "border": 1
    })
    
    # TODO: Design UI such that user can choose which columns to show/hide
    worksheet.write(0, 0, 'Part', headerFormat)
    worksheet.write(0, 1, 'Description', headerFormat)
    worksheet.write(0, 2, 'UOM', headerFormat)
    worksheet.write(0, 3, 'On Hand', headerFormat)
    worksheet.write(0, 4, 'Allocated', headerFormat)
    worksheet.write(0, 5, 'Not Available', headerFormat)
    worksheet.write(0, 6, 'Drop Ship', headerFormat)
    worksheet.write(0, 7, 'Available', headerFormat)
    worksheet.write(0, 8, 'On Order', headerFormat)
    worksheet.write(0, 9, 'Committed', headerFormat)
    worksheet.write(0, 10, 'Short', headerFormat)


# writeEntryToSpreadSheet will write all of the data present in a InventoryEntry object
# to the corresponding column and row in the workbook
# params: workbook, xlsx.Workbook, the workbook object containing the worksheet
# params: worksheet, workbook.worksheet, the sheet to write the header information to
# params: row, int, the row number to write to
# params: entry, InventoryEntry, the object holding all inventory entry data to be written to the row
# returns: N/A
def writeEntryToSpreadsheet(workbook, worksheet, row, entry):

    if int(row) % 2 == 0:
        infoFormat = workbook.add_format({
            "valign": "vcenter",
            "font_size": 12,
            "bg_color": "#E6F0FF",
            "border": 1
        })
    else:
        infoFormat = workbook.add_format({
            "valign": "vcenter",
            "font_size": 12,
            "bg_color": "#F0F0F0",
            "border": 1
        })

    worksheet.write("A" + row, entry.part, infoFormat)
    worksheet.write("B" + row, entry.description, infoFormat)
    worksheet.write("C" + row, entry.uom, infoFormat)
    worksheet.write("D" + row, entry.onHand, infoFormat)
    worksheet.write("E" + row, entry.allocated, infoFormat)
    worksheet.write("F" + row, entry.notAvailable, infoFormat)
    worksheet.write("G" + row, entry.dropShip, infoFormat)
    worksheet.write("H" + row, entry.available, infoFormat)
    worksheet.write("I" + row, entry.onOrder, infoFormat)
    worksheet.write("J" + row, entry.committed, infoFormat)
    worksheet.write("K" + row, entry.short, infoFormat)


# setupSpreadSheet will create a .xlsx file and write all parsed contents to it
# params: inventory: list of InventoryEntry objects, to be written to spreadsheet
# params: name: str, the date of the inventory file that is being processed
# params: checkboxDict, dict, the state of all column checkboxes from GUI
# returns: N/A
def setupSpreadsheet(inventory, name, checkboxDict):

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