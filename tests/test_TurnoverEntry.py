import pytest

from source.TurnoverEntry import *


###############################################################################
###                     TurnoverEntry -> Row Fixture                        ###
###############################################################################
# One turnover "Totals:" row as PdfTableParser hands it over: the part label as a
# string, the four numeric columns already converted. Units sold is whole while the
# averages are fractional, which is why each cell is typed by what it says rather
# than by which column it came from.
PARSED_ROW = ["PART-A", 12, 800, 1234.50, 0.02500]


###############################################################################
###                    Tests TurnoverEntry -> Constructor                   ###
###############################################################################
def test_turnover_entry_initialization():
    """
    Tests that the default initialization of the TurnoverEntry() object will
    correctly populate all default values to class attributes
    """

    # Create default instance of TurnoverEntry class
    entry = TurnoverEntry()

    # Check that the part description is initialized to an empty string
    assert entry.part_description == ""

    # Check that units sold, which the report always prints, starts at zero
    assert entry.units_sold == 0

    # Check that the averages, which the report can leave blank, start at None
    assert entry.avg_qoh is None
    assert entry.avg_to_days is None
    assert entry.to_rate is None


def test_turnover_entry_initialization_with_arguments():
    """
    Tests that the TurnoverEntry() constructor accepts optional arguments and uses
    them to populate the corresponding attributes, leaving unspecified fields at
    their defaults
    """

    # Create a TurnoverEntry supplying a mix of string and numeric fields
    entry = TurnoverEntry(part_description="PART-A", units_sold=12, to_rate=0.025)

    # Check that the supplied arguments populated their attributes
    assert entry.part_description == "PART-A"
    assert entry.units_sold == 12
    assert entry.to_rate == 0.025

    # Check that unspecified fields fall back to their defaults
    assert entry.avg_qoh is None
    assert entry.avg_to_days is None


def test_turnover_entry_initialization_from_a_parsed_row():
    """
    Tests that a row from PdfTableParser expands positionally into the constructor,
    landing each field in declaration order
    """

    # Build the entry the way the controller does
    entry = TurnoverEntry(*PARSED_ROW)

    # Every field of the row lands in the attribute at its position
    assert entry.part_description == "PART-A"
    assert entry.units_sold == 12
    assert entry.avg_qoh == 800
    assert entry.avg_to_days == 1234.50
    assert entry.to_rate == 0.02500


def test_turnover_entry_holds_a_blank_column_as_none():
    """
    Tests that a column the report left blank stays None on the entry, keeping a
    part whose turnover is undefined distinct from one that genuinely turned over
    zero times
    """

    # The report leaves the turnover days blank when the average quantity is zero
    entry = TurnoverEntry("PART-A", 3, 0, None, 0)

    assert entry.avg_to_days is None
    assert entry.avg_qoh == 0


###############################################################################
###               Tests TurnoverEntry -> to_formatted_string()              ###
###############################################################################
def test_turnover_entry_to_formatted_string_default():
    """
    Tests that to_formatted_string() will correctly print default values when the
    TurnoverEntry class is initialized as default
    """

    # Create default instance of TurnoverEntry class
    entry = TurnoverEntry()

    # Output all default attributes as a formatted string
    output = entry.to_formatted_string()

    # Verify every field appears in the output string at its default
    assert "partDescription: \n" in output
    assert "unitsSold: 0\n" in output
    assert "avgQOH: None\n" in output
    assert "avgTODays: None\n" in output
    assert "TORate: None\n" in output


def test_turnover_entry_to_formatted_string_values():
    """
    Tests that to_formatted_string() will correctly print the set values of all
    entry attributes. The labels stay in the report's own casing rather than
    following the attribute names, since the results file is diffed against a
    canonical copy
    """

    # Create an entry from a parsed row
    entry = TurnoverEntry(*PARSED_ROW)

    # Get the entry attributes as a formatted string
    output = entry.to_formatted_string()

    # Verify all fields appear in the output string under their report labels
    assert "partDescription: PART-A\n" in output
    assert "unitsSold: 12\n" in output
    assert "avgQOH: 800\n" in output
    assert "avgTODays: 1234.5\n" in output
    assert "TORate: 0.025\n" in output


def test_turnover_entry_to_formatted_string_is_wrapped_in_banners():
    """
    Tests that the dump opens and closes with the banner separating one entry from
    the next in the results file
    """

    # Output a default entry as a formatted string
    output = TurnoverEntry().to_formatted_string()

    # The banner brackets the field lines
    assert output.startswith("*****************************\n")
    assert output.endswith("\n*****************************")
