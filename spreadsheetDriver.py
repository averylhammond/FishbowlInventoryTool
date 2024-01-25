import xlsxwriter

# setupSpreadsheetHeader will write the header information for each column to the spreadsheet
# params: workbook, xlsx.Workbook, the workbook object containing the worksheet
# params: worksheet, workbook.worksheet, the sheet to write the header information to
# params: checkboxDict, dict, the state of all column checkboxes from GUI
# returns: N/A 
def setupSpreadsheetHeader(workbook, worksheet, checkboxDict):
    
    headerFormat = workbook.add_format({
        "valign": "vcenter",
        "align": "center",
        "bold": True,
        "font_size": 16,
        "bg_color": "#F0F0F0",
        "border": 1
    })

    
    # This is the current solution to dynamically settings the columns for different
    # headers based on which entry attributes the user wants to see. We check each
    # dictionary entry to see if the user checked the box to see the attribute. If
    # he/she did, then write to the current column and increment col by one for the
    # next write.
    col = 0   
    if checkboxDict["Part"] == True:
        worksheet.write(0, col, "Part", headerFormat)
        col+=1

    if checkboxDict["Description"] == True:
        worksheet.write(0, col, "Description", headerFormat)
        col+=1

    if checkboxDict["UOM"] == True:
        worksheet.write(0, col, "UOM", headerFormat)
        col+=1

    if checkboxDict["OnHand"] == True:
        worksheet.write(0, col, "OnHand", headerFormat)
        col+=1

    if checkboxDict["Allocated"] == True:
        worksheet.write(0, col, "Allocated", headerFormat)
        col+=1

    if checkboxDict["NotAvailable"] == True:
        worksheet.write(0, col, "NotAvailable", headerFormat)
        col+=1

    if checkboxDict["DropShip"] == True:
        worksheet.write(0, col, "DropShip", headerFormat)
        col+=1

    if checkboxDict["Available"] == True:
        worksheet.write(0, col, "Available", headerFormat)
        col+=1

    if checkboxDict["OnOrder"] == True:
        worksheet.write(0, col, "OnOrder", headerFormat)
        col+=1

    if checkboxDict["Committed"] == True:
        worksheet.write(0, col, "Committed", headerFormat)
        col+=1

    if checkboxDict["Short"] == True:
        worksheet.write(0, col, "Short", headerFormat)
        col+=1


# writeEntryToSpreadSheet will write all of the data present in a InventoryEntry object
# to the corresponding column and row in the workbook
# params: workbook, xlsx.Workbook, the workbook object containing the worksheet
# params: worksheet, workbook.worksheet, the sheet to write the header information to
# params: row, str, the row number to write to
# params: entry, InventoryEntry, the object holding all inventory entry data to be written to the row
# params: checkboxDict, dict, the state of all column checkboxes from GUI
# returns: N/A
def writeEntryToSpreadsheet(workbook, worksheet, row, entry, checkboxDict):

    # Cast to int (is str initially)
    row = int(row)
    
    # Alternate row colors for visibility
    if row % 2 == 0:
        infoFormat = workbook.add_format({
            "valign": "vcenter",
            "font_size": 12,
            "bg_color": "#F0F0F0",  # Light Blue
            "border": 1
        })
    else:
        infoFormat = workbook.add_format({
            "valign": "vcenter",
            "font_size": 12,
            "bg_color": "#E6F0FF",  # Light Gray
            "border": 1
        })


    # This is the current solution to dynamically settings the columns for different
    # headers based on which entry attributes the user wants to see. We check each
    # dictionary entry to see if the user checked the box to see the attribute. If
    # he/she did, then write to the current column and increment col by one for the
    # next write.
    col = 0   
    if checkboxDict["Part"] == True:
        worksheet.write(row, col, entry.part, infoFormat)
        col+=1

    if checkboxDict["Description"] == True:
        worksheet.write(row, col, entry.description, infoFormat)
        col+=1
        
    if checkboxDict["UOM"] == True:
        worksheet.write(row, col, entry.uom, infoFormat)
        col+=1

    if checkboxDict["OnHand"] == True:
        worksheet.write(row, col, entry.onHand, infoFormat)
        col+=1

    if checkboxDict["Allocated"] == True:
        worksheet.write(row, col, entry.allocated, infoFormat)
        col+=1

    if checkboxDict["NotAvailable"] == True:
        worksheet.write(row, col, entry.notAvailable, infoFormat)
        col+=1

    if checkboxDict["DropShip"] == True:
        worksheet.write(row, col, entry.dropShip, infoFormat)
        col+=1

    if checkboxDict["Available"] == True:
        worksheet.write(row, col, entry.available, infoFormat)
        col+=1

    if checkboxDict["OnOrder"] == True:
        worksheet.write(row, col, entry.onOrder, infoFormat)
        col+=1

    if checkboxDict["Committed"] == True:
        worksheet.write(row, col, entry.committed, infoFormat)
        col+=1

    if checkboxDict["Short"] == True:
        worksheet.write(row, col, entry.short, infoFormat)
        col+=1


# setupSpreadSheet will create a .xlsx file and write all parsed contents to it
# params: inventory: list of InventoryEntry objects, to be written to spreadsheet
# params: name: str, the date of the inventory file that is being processed
# params: checkboxDict, dict, the state of all column checkboxes from GUI
# returns: N/A
def setupSpreadsheet(inventory, name, checkboxDict):

    # Spreadsheet Workbook definition
    workbook = xlsxwriter.Workbook(name + ".xlsx")
    
    # Start writing data on row 1 since header data is written to row 0
    row = 1

    worksheet = workbook.add_worksheet()
    setupSpreadsheetHeader(workbook, worksheet, checkboxDict)

    # Loop through each table entry in the table and write to contents
    # to the corresponding worksheet
    for entry in inventory:
        writeEntryToSpreadsheet(workbook, worksheet, str(row), entry, checkboxDict)
        row +=1

    # Save and close the spreadsheet
    workbook.close()