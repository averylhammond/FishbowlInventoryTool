import pytest

from source.columns import *


###############################################################################
###                    Tests columns -> Column Definitions                  ###
###############################################################################
def test_column_keys_are_in_spreadsheet_order():
    """
    Tests that COLUMN_KEYS holds every checkbox key in the order the spreadsheet
    writers walk them. The literal is repeated here rather than derived so a
    reordering or a renamed key fails loudly: spreadsheetDriver looks these keys
    up by name, and a silent change would drop a column from the report.
    """

    assert COLUMN_KEYS == (
        "Part",
        "Description",
        "UOM",
        "OnHand",
        "Allocated",
        "NotAvailable",
        "DropShip",
        "Available",
        "OnOrder",
        "Committed",
        "Short",
        "tDescription",
        "tUnits Sold",
        "tAvg QOH",
        "tAvg TO Days",
        "tTO Rate",
    )


def test_all_columns_is_inventory_columns_then_turnover_columns():
    """
    Tests that ALL_COLUMNS concatenates the two sections in order, since the
    spreadsheet emits every inventory column before any turnover column
    """

    assert ALL_COLUMNS == INVENTORY_COLUMNS + TURNOVER_COLUMNS


def test_part_is_the_only_always_included_column():
    """
    Tests that Part is the single column marked always, so it is emitted without
    a checkbox while every other column is left to the user to select
    """

    assert [column.key for column in ALL_COLUMNS if column.always] == ["Part"]


def test_every_column_has_a_label():
    """
    Tests that every column carries a non-empty GUI label, since the display
    builds its checkbox text straight from these
    """

    for column in ALL_COLUMNS:
        assert column.label


def test_every_column_has_a_tooltip():
    """
    Tests that every column carries non-empty hover text, since the display
    attaches these straight to the checkboxes. A column added without one would
    show an empty tooltip rather than no tooltip at all.
    """

    for column in ALL_COLUMNS:
        assert column.tooltip


def test_turnover_labels_drop_the_key_prefix():
    """
    Tests that the turnover columns show plain labels rather than their
    t-prefixed keys, since the GUI groups them under their own heading
    """

    assert [column.label for column in TURNOVER_COLUMNS] == [
        "Description",
        "Units Sold",
        "Avg QOH",
        "Avg TO Days",
        "TO Rate",
    ]


###############################################################################
###                  Tests columns -> all_columns_selected()                ###
###############################################################################
def test_all_columns_selected_includes_every_column():
    """
    Tests that all_columns_selected() returns every column key mapped to True,
    which is what the headless integration test path uses in place of the GUI's
    checkbox state
    """

    selected = all_columns_selected()

    # Every key the spreadsheet writers consult must be present
    assert tuple(selected.keys()) == COLUMN_KEYS

    # Every column must be included, as real booleans: spreadsheetDriver compares
    # each value against True with ==, so a truthy non-bool would drop the column
    for value in selected.values():
        assert value is True


def test_all_columns_selected_returns_a_new_dict_each_call():
    """
    Tests that callers get their own dict, so mutating one caller's column
    selection cannot leak into another's
    """

    first = all_columns_selected()
    second = all_columns_selected()

    assert first is not second
