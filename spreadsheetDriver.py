import xlsxwriter

def formatTurnoverRow(workbook, col):
    
    evenFormat = workbook.add_format({
            "valign": "vcenter",
            "font_size": 12,
            "bg_color": "#F0F0F0",  # Light Blue
            "border": 1
            })
    oddFormat = workbook.add_format({
            "valign": "vcenter",
            "font_size": 12,
            "bg_color": "#E6F0FF",  # Light Gray
            "border": 1
            })
    
    # Get worksheet
    worksheet = workbook.get_worksheet_by_name("Sheet1")

    # Alternate row colors for visibility
    for row in range(618):
        if row % 2 == 0 and row != 0:
            worksheet.write(row, col, 'N/A', evenFormat)
        elif row % 2 == 1 and row != 0:
            worksheet.write(row, col, 'N/A', oddFormat)


# setupSpreadsheetInventoryHeader will write the header information for each column to the spreadsheet
# params: workbook, xlsx.Workbook, the workbook object containing the worksheet
# params: worksheet, workbook.worksheet, the sheet to write the header information to
# params: checkboxDict, dict, the state of all column checkboxes from GUI
# returns: N/A 
def setupSpreadsheetInventoryHeader(workbook, worksheet, checkboxDict):
    
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


# setupSpreadsheetTurnoverHeader will write the header information for each column to the spreadsheet
# params: workbook, xlsx.Workbook, the workbook object containing the worksheet
# params: checkboxDict, dict, the state of all column checkboxes from GUI
# params: col, int, the leftmost empty column to write to
# params: filename, str, the filename of the turnover report
# returns: N/A 
def setupSpreadsheetTurnoverHeader(workbook, checkboxDict, col, filename):

    headerFormat = workbook.add_format({
        "valign": "vcenter",
        "align": "center",
        "bold": True,
        "font_size": 16,
        "bg_color": "#F0F0F0",
        "border": 1
    })

    # Only using one worksheet, so it's always index 0
    worksheet = workbook.get_worksheet_by_name("Sheet1")

    # This is the current solution to dynamically settings the columns for different
    # headers based on which entry attributes the user wants to see. We check each
    # dictionary entry to see if the user checked the box to see the attribute. If
    # he/she did, then write to the current column and increment col by one for the
    # next write.
    if checkboxDict["tDescription"] == True:
        worksheet.write(0, col, "TO Description", headerFormat)
        formatTurnoverRow(workbook, col)
        col+=1

    if checkboxDict["tUnits Sold"] == True:
        worksheet.write(0, col, f"Units Sold {filename}", headerFormat)
        formatTurnoverRow(workbook, col)
        col+=1

    if checkboxDict["tAvg QOH"] == True:
        worksheet.write(0, col, f"Avg QOH {filename}", headerFormat)
        formatTurnoverRow(workbook, col)
        col+=1

    if checkboxDict["tAvg TO Days"] == True:
        worksheet.write(0, col, f"Avg TO Days {filename}", headerFormat)
        formatTurnoverRow(workbook, col)
        col+=1

    if checkboxDict["tTO Rate"] == True:
        worksheet.write(0, col, f"TO Rate {filename}", headerFormat)
        formatTurnoverRow(workbook, col)
        col+=1


# writeInventoryEntryToSpreadSheet will write all of the data present in a InventoryEntry object
# to the corresponding column and row in the workbook
# params: workbook, xlsx.Workbook, the workbook object containing the worksheet
# params: worksheet, workbook.worksheet, the sheet to write the header information to
# params: row, str, the row number to write to
# params: entry, InventoryEntry, the object holding all inventory entry data to be written to the row
# params: checkboxDict, dict, the state of all column checkboxes from GUI
# returns: col, int, the next available free column that can be written to
def writeInventoryEntryToSpreadsheet(workbook, worksheet, row, entry, checkboxDict):

    # Cast to int (is str initially)
    row = int(row)
    
    # Alternate row colors for visibility
    if row % 2 == 0:
        entryFormat = workbook.add_format({
            "valign": "vcenter",
            "font_size": 12,
            "bg_color": "#F0F0F0",  # Light Blue
            "border": 1
        })
    else:
        entryFormat = workbook.add_format({
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
        worksheet.write(row, col, entry.part, entryFormat)
        entry.rowWrittenTo = row
        col+=1

    if checkboxDict["Description"] == True:
        worksheet.write(row, col, entry.description, entryFormat)
        entry.rowWrittenTo = row
        col+=1
        
    if checkboxDict["UOM"] == True:
        worksheet.write(row, col, entry.uom, entryFormat)
        entry.rowWrittenTo = row
        col+=1

    if checkboxDict["OnHand"] == True:
        worksheet.write(row, col, entry.onHand, entryFormat)
        entry.rowWrittenTo = row
        col+=1

    if checkboxDict["Allocated"] == True:
        worksheet.write(row, col, entry.allocated, entryFormat)
        entry.rowWrittenTo = row
        col+=1

    if checkboxDict["NotAvailable"] == True:
        worksheet.write(row, col, entry.notAvailable, entryFormat)
        entry.rowWrittenTo = row
        col+=1

    if checkboxDict["DropShip"] == True:
        worksheet.write(row, col, entry.dropShip, entryFormat)
        entry.rowWrittenTo = row
        col+=1

    if checkboxDict["Available"] == True:
        worksheet.write(row, col, entry.available, entryFormat)
        entry.rowWrittenTo = row
        col+=1

    if checkboxDict["OnOrder"] == True:
        worksheet.write(row, col, entry.onOrder, entryFormat)
        entry.rowWrittenTo = row
        col+=1

    if checkboxDict["Committed"] == True:
        worksheet.write(row, col, entry.committed, entryFormat)
        entry.rowWrittenTo = row
        col+=1

    if checkboxDict["Short"] == True:
        worksheet.write(row, col, entry.short, entryFormat)
        entry.rowWrittenTo = row
        col+=1

    return col


# writeTurnoverEntryToSpreadSheet will write all of the data present in a TurnoverEntry object
# to the corresponding column and row in the workbook
# params: workbook, xlsx.Workbook, the workbook object containing the worksheet
# params: worksheet, workbook.worksheet, the sheet to write the header information to
# params: row, int, the row number to write to
# params: col, int, the column to write to
# params: entry, InventoryEntry, the object holding all inventory entry data to be written to the row
# params: checkboxDict, dict, the state of all column checkboxes from GUI
# returns: N/A
def writeTurnoverEntryToSpreadsheet(workbook, worksheet, row, col, entry, checkboxDict):

    # Alternate row colors for visibility
    if row % 2 == 0:
         entryFormat = workbook.add_format({
            "valign": "vcenter",
            "font_size": 12,
            "bg_color": "#F0F0F0",  # Light Blue
            "border": 1
        })
    else:
        entryFormat = workbook.add_format({
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
    if checkboxDict["tDescription"] == True:
        worksheet.write(row, col, entry.partDescription, entryFormat)
        entry.rowWrittenTo = row
        col+=1

    if checkboxDict["tUnits Sold"] == True:
        worksheet.write(row, col, entry.unitsSold, entryFormat)
        entry.rowWrittenTo = row
        col+=1
        
    if checkboxDict["tAvg QOH"] == True:
        worksheet.write(row, col, entry.avgQOH, entryFormat)
        entry.rowWrittenTo = row
        col+=1

    if checkboxDict["tAvg TO Days"] == True:
        worksheet.write(row, col, entry.avgTODays, entryFormat)
        entry.rowWrittenTo = row
        col+=1

    if checkboxDict["tTO Rate"] == True:
        worksheet.write(row, col, entry.TORate, entryFormat)
        entry.rowWrittenTo = row
        col+=1


# setupMainSpreadSheet will create a .xlsx file and write all parsed contents to it
# params: workbook: xlsx object, the open workbook to be written to
# params: inventory: list of InventoryEntry objects, to be written to spreadsheet
# params: checkboxDict, dict, the state of all column checkboxes from GUI
# returns: nextCol, int, the next column that can be written to
def setupMainSpreadsheet(workbook, inventory, checkboxDict):
    
    # Start writing data on row 1 since header data is written to row 0
    row = 1
    nextCol = 0

    worksheet = workbook.add_worksheet()
    setupSpreadsheetInventoryHeader(workbook, worksheet, checkboxDict)

    # Loop through each table entry in the table and write to contents
    # to the corresponding worksheet
    for entry in inventory:
        nextCol = writeInventoryEntryToSpreadsheet(workbook, worksheet, str(row), entry, checkboxDict)
        row +=1

    return nextCol


# appendTurnoverToSpreadsheet takes a given workbook and writes the turnover pdf data to the most
# recent unused column, matching the turnover entries to the inventory entries
# params: workbook: xlsxwriter class, the spreadsheet object
# params: turnover: list, list of TurnoverEntry objects from the turnover pdf
# params: inventory: list, list of InventoryEntry objects from the inventory pdf
# params: coll: int, the column to start writing to since the previous columns
# are holding inventory entry data
# params: checkboxDict, dict, the state of all column checkboxes from GUI
# returns: N/A
def appendTurnoverToSpreadsheet(workbook, turnover, inventory, col, checkboxDict):

    # Only using one worksheet, so it's always index 0
    worksheet = workbook.get_worksheet_by_name("Sheet1")

    # Need to loop through each TurnoverEntry object and match it to an InventoryEntry object
    # based on the part name. If the names match, find the row that the InventoryEntry was
    # written to and write the TurnoverEntry data to that same row, but new column
    for tEntry in turnover:
        for iEntry in inventory:
            if (iEntry.part.replace(' ', '')) == (tEntry.partDescription.replace(' ', '')):
                writeTurnoverEntryToSpreadsheet(workbook, worksheet, iEntry.rowWrittenTo, 
                                                col, tEntry, checkboxDict)