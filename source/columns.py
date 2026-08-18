from dataclasses import dataclass


# One selectable spreadsheet column: the key the spreadsheet writers consult, the
# label the GUI shows on that column's checkbox, and the hover text explaining what
# the column holds. The key and label are separate because the same label
# ("Description") appears in both the inventory and turnover sections under
# different keys.
@dataclass(frozen=True)
class Column:

    # fmt:off
    key:     str            # Key the spreadsheet writers look up in the checkbox dict
    label:   str            # Text shown on this column's GUI checkbox
    always:  bool = False   # True for a column always emitted, with no checkbox
    tooltip: str = ""       # Hover text explaining what this column holds
    # fmt:on


# Inventory availability columns, in the order the spreadsheet writers emit them
# fmt:off
INVENTORY_COLUMNS = (
    Column("Part",         "Part", always=True,
           tooltip="The part number as it appears in Fishbowl"),
    Column("Description",  "Description",
           tooltip="The part's description"),
    Column("UOM",          "UOM",
           tooltip="Unit of measure the part is stocked in"),
    Column("OnHand",       "On Hand",
           tooltip="Total quantity physically in inventory"),
    Column("Allocated",    "Allocated",
           tooltip="Quantity on hand already committed to open orders"),
    Column("NotAvailable", "Not Available",
           tooltip="Quantity on hand that cannot be sold"),
    Column("DropShip",     "Drop Ship",
           tooltip="Quantity shipped direct from the vendor rather than from stock"),
    Column("Available",    "Available",
           tooltip="Quantity free to sell: on hand minus allocated and not available"),
    Column("OnOrder",      "On Order",
           tooltip="Quantity on open purchase orders, not yet received"),
    Column("Committed",    "Committed",
           tooltip="Quantity promised to open sales and work orders"),
    Column("Short",        "Short",
           tooltip="Quantity needed beyond what is on hand or on order"),
)

# Turnover report columns. Note the irregular keys: "tDescription" has no space
# after the t prefix, the rest do. These are the strings spreadsheetDriver reads.
TURNOVER_COLUMNS = (
    Column("tDescription", "Description",
           tooltip="The part's description as it appears on the turnover report"),
    Column("tUnits Sold",  "Units Sold",
           tooltip="Total units sold over the turnover report's date range"),
    Column("tAvg QOH",     "Avg QOH",
           tooltip="Average quantity on hand over the report's date range"),
    Column("tAvg TO Days", "Avg TO Days",
           tooltip="Average number of days it takes to sell through the stock on hand"),
    Column("tTO Rate",     "TO Rate",
           tooltip="Times the stock on hand turned over during the report period"),
)
# fmt:on

# Every column, inventory first, in the order the spreadsheet writers walk them
ALL_COLUMNS = INVENTORY_COLUMNS + TURNOVER_COLUMNS

# Every checkbox key, in spreadsheet column order
COLUMN_KEYS = tuple(column.key for column in ALL_COLUMNS)


###############################################################################
###                     columns -> all_columns_selected()                   ###
###############################################################################
def all_columns_selected() -> dict:
    """
    Builds a checkbox dict with every column included, used by the headless
    integration test path where there is no GUI to read selections from

    Returns:
        dict: A mapping of every column key to True
    """
    return {key: True for key in COLUMN_KEYS}
