from dataclasses import dataclass


# One selectable spreadsheet column: the key the spreadsheet writer consults, the
# label the GUI shows on that column's checkbox and the spreadsheet writes as its
# header, the entry attribute holding the value, and the hover text explaining what
# the column holds. The key and label are separate because the same label
# ("Description") appears in both the inventory and turnover sections under
# different keys.
@dataclass(frozen=True)
class Column:

    # fmt:off
    key:     str            # Key the spreadsheet writer looks up in the checkbox dict
    label:   str            # Text shown on this column's GUI checkbox and sheet header
    field:   str            # Entry attribute this column's value is read from
    always:  bool = False   # True for a column always emitted, with no checkbox
    tooltip: str = ""       # Hover text explaining what this column holds
    # fmt:on


# Inventory availability columns, in the order the spreadsheet writer emits them.
# Each field names an InventoryEntry attribute; test_columns.py checks that it
# resolves, since a typo here would otherwise surface as an AttributeError midway
# through writing a report.
# fmt:off
INVENTORY_COLUMNS = (
    Column("Part",         "Part",          field="part", always=True,
           tooltip="The part number as it appears in Fishbowl"),
    Column("Description",  "Description",   field="description",
           tooltip="The part's description"),
    Column("UOM",          "UOM",           field="uom",
           tooltip="Unit of measure the part is stocked in"),
    Column("OnHand",       "On Hand",       field="on_hand",
           tooltip="Total quantity physically in inventory"),
    Column("Allocated",    "Allocated",     field="allocated",
           tooltip="Quantity on hand already committed to open orders"),
    Column("NotAvailable", "Not Available", field="not_available",
           tooltip="Quantity on hand that cannot be sold"),
    Column("DropShip",     "Drop Ship",     field="drop_ship",
           tooltip="Quantity shipped direct from the vendor rather than from stock"),
    Column("Available",    "Available",     field="available",
           tooltip="Quantity free to sell: on hand minus allocated and not available"),
    Column("OnOrder",      "On Order",      field="on_order",
           tooltip="Quantity on open purchase orders, not yet received"),
    Column("Committed",    "Committed",     field="committed",
           tooltip="Quantity promised to open sales and work orders"),
    Column("Short",        "Short",         field="short",
           tooltip="Quantity needed beyond what is on hand or on order"),
)

# Turnover report columns, each field naming a TurnoverEntry attribute. Note the
# irregular keys: "tDescription" has no space after the t prefix, the rest do.
TURNOVER_COLUMNS = (
    Column("tDescription", "Description",   field="part_description",
           tooltip="The part's description as it appears on the turnover report"),
    Column("tUnits Sold",  "Units Sold",    field="units_sold",
           tooltip="Total units sold over the turnover report's date range"),
    Column("tAvg QOH",     "Avg QOH",       field="avg_qoh",
           tooltip="Average quantity on hand over the report's date range"),
    Column("tAvg TO Days", "Avg TO Days",   field="avg_to_days",
           tooltip="Average number of days it takes to sell through the stock on hand"),
    Column("tTO Rate",     "TO Rate",       field="to_rate",
           tooltip="Times the stock on hand turned over during the report period"),
)
# fmt:on

# Every column, inventory first, in the order the spreadsheet writer walks them
ALL_COLUMNS = INVENTORY_COLUMNS + TURNOVER_COLUMNS

# Every checkbox key, in spreadsheet column order
COLUMN_KEYS = tuple(column.key for column in ALL_COLUMNS)


def all_columns_selected() -> dict[str, bool]:
    """
    Builds a checkbox dict with every column included, used by the headless
    integration test path where there is no GUI to read selections from

    Returns:
        A mapping of every column key to True
    """
    return {key: True for key in COLUMN_KEYS}
