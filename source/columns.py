from dataclasses import dataclass


# One selectable spreadsheet column: the key the spreadsheet writers consult and
# the label the GUI shows on that column's checkbox. The two are separate because
# the same label ("Description") appears in both the inventory and turnover
# sections under different keys.
@dataclass(frozen=True)
class Column:

    # fmt:off
    key:    str            # Key the spreadsheet writers look up in the checkbox dict
    label:  str            # Text shown on this column's GUI checkbox
    always: bool = False   # True for a column always emitted, with no checkbox
    # fmt:on


# Inventory availability columns, in the order the spreadsheet writers emit them
# fmt:off
INVENTORY_COLUMNS = (
    Column("Part",         "Part", always=True),
    Column("Description",  "Description"),
    Column("UOM",          "UOM"),
    Column("OnHand",       "On Hand"),
    Column("Allocated",    "Allocated"),
    Column("NotAvailable", "Not Available"),
    Column("DropShip",     "Drop Ship"),
    Column("Available",    "Available"),
    Column("OnOrder",      "On Order"),
    Column("Committed",    "Committed"),
    Column("Short",        "Short"),
)

# Turnover report columns. Note the irregular keys: "tDescription" has no space
# after the t prefix, the rest do. These are the strings spreadsheetDriver reads.
TURNOVER_COLUMNS = (
    Column("tDescription", "Description"),
    Column("tUnits Sold",  "Units Sold"),
    Column("tAvg QOH",     "Avg QOH"),
    Column("tAvg TO Days", "Avg TO Days"),
    Column("tTO Rate",     "TO Rate"),
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
