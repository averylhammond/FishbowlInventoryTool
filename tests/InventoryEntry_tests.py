import pytest

from source.InventoryEntry import *


###############################################################################
###                    InventoryEntry -> Row Fixture                        ###
###############################################################################
# One inventory row as PdfTableParser hands it over: the part, description and UOM
# as strings, the eight quantities already converted to numbers. The entry is built
# straight from it, so the field order below is the constructor's argument order.
PARSED_ROW = ["PART-A", "WIDGET ONE", "ea", 100, 5, 0, 0, 95, 20, 5, 0]


###############################################################################
###                   Tests InventoryEntry -> Constructor                   ###
###############################################################################
def test_inventory_entry_initialization():
    """
    Tests that the default initialization of the InventoryEntry() object will
    correctly populate all default values to class attributes
    """

    # Create default instance of InventoryEntry class
    entry = InventoryEntry()

    # Check that all string fields are initialized to an empty string
    assert entry.part == ""
    assert entry.description == ""
    assert entry.uom == ""

    # Check that all quantity fields are initialized to zero
    assert entry.on_hand == 0
    assert entry.allocated == 0
    assert entry.not_available == 0
    assert entry.drop_ship == 0
    assert entry.available == 0
    assert entry.on_order == 0
    assert entry.committed == 0
    assert entry.short == 0


def test_inventory_entry_initialization_with_arguments():
    """
    Tests that the InventoryEntry() constructor accepts optional arguments and uses
    them to populate the corresponding attributes, leaving unspecified fields at
    their defaults
    """

    # Create an InventoryEntry supplying a mix of string and quantity fields
    entry = InventoryEntry(part="PART-A", on_hand=100, available=95)

    # Check that the supplied arguments populated their attributes
    assert entry.part == "PART-A"
    assert entry.on_hand == 100
    assert entry.available == 95

    # Check that unspecified fields fall back to their defaults
    assert entry.description == ""
    assert entry.uom == ""
    assert entry.allocated == 0


def test_inventory_entry_initialization_from_a_parsed_row():
    """
    Tests that a row from PdfTableParser expands positionally into the constructor,
    landing each field in declaration order and filling the entry completely
    """

    # Build the entry the way the controller does
    entry = InventoryEntry(*PARSED_ROW)

    # Every field of the row lands in the attribute at its position
    assert entry.part == "PART-A"
    assert entry.description == "WIDGET ONE"
    assert entry.uom == "ea"
    assert entry.on_hand == 100
    assert entry.allocated == 5
    assert entry.not_available == 0
    assert entry.drop_ship == 0
    assert entry.available == 95
    assert entry.on_order == 20
    assert entry.committed == 5
    assert entry.short == 0


def test_inventory_entry_keeps_a_fractional_quantity_as_a_float():
    """
    Tests that a quantity the report printed with a decimal point is held as the
    float the parser produced, rather than being coerced to a whole number
    """

    # A report can print a fractional quantity for a part measured by weight
    entry = InventoryEntry(part="PART-A", on_hand=12.5)

    assert entry.on_hand == 12.5


###############################################################################
###              Tests InventoryEntry -> to_formatted_string()              ###
###############################################################################
def test_inventory_entry_to_formatted_string_default():
    """
    Tests that to_formatted_string() will correctly print default values when the
    InventoryEntry class is initialized as default
    """

    # Create default instance of InventoryEntry class
    entry = InventoryEntry()

    # Output all default attributes as a formatted string
    output = entry.to_formatted_string()

    # Verify every field appears in the output string at its default
    assert "part: \n" in output
    assert "description: \n" in output
    assert "uom: \n" in output
    assert "onHand: 0\n" in output
    assert "allocated: 0\n" in output
    assert "notAvailable: 0\n" in output
    assert "dropShip: 0\n" in output
    assert "available: 0\n" in output
    assert "onOrder: 0\n" in output
    assert "committed: 0\n" in output
    assert "short: 0\n" in output


def test_inventory_entry_to_formatted_string_values():
    """
    Tests that to_formatted_string() will correctly print the set values of all
    entry attributes. The labels stay in the report's own casing rather than
    following the attribute names, since the results file is diffed against a
    canonical copy
    """

    # Create an entry from a parsed row
    entry = InventoryEntry(*PARSED_ROW)

    # Get the entry attributes as a formatted string
    output = entry.to_formatted_string()

    # Verify all fields appear in the output string under their report labels
    assert "part: PART-A\n" in output
    assert "description: WIDGET ONE\n" in output
    assert "uom: ea\n" in output
    assert "onHand: 100\n" in output
    assert "allocated: 5\n" in output
    assert "notAvailable: 0\n" in output
    assert "dropShip: 0\n" in output
    assert "available: 95\n" in output
    assert "onOrder: 20\n" in output
    assert "committed: 5\n" in output
    assert "short: 0\n" in output


def test_inventory_entry_to_formatted_string_is_wrapped_in_banners():
    """
    Tests that the dump opens and closes with the banner separating one entry from
    the next in the results file
    """

    # Output a default entry as a formatted string
    output = InventoryEntry().to_formatted_string()

    # The banner brackets the field lines
    assert output.startswith("*****************************\n")
    assert output.endswith("\n*****************************")
