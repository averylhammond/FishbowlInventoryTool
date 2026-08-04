import pytest

from source.PdfTableParser import *


###############################################################################
###                    PdfTableParser -> Page Fixtures                      ###
###############################################################################
# Synthetic page text, structurally identical to a Fishbowl report but at reduced
# column widths so the lines stay readable. Column positions are load-bearing, so
# each page is built by joining explicit line literals rather than by dedenting a
# block that an editor could reflow.
INVENTORY_HEADER_BLOCK = [
    "                                            On                     Not   Drop                 On",
    "Part          Description             UOM  Hand  Allocated  Available   Ship  Available    Order  Committed  Short",
]

# The same header from a report that omits the UOM column
NO_UOM_HEADER_BLOCK = [
    "                                       On                     Not   Drop                 On",
    "Part          Description         Hand  Allocated  Available   Ship  Available    Order  Committed  Short",
]

# The same header with every column pushed three characters to the right, as the
# offsets drift from page to page
SHIFTED_HEADER_BLOCK = [
    "                                               On                     Not   Drop                 On",
    "Part             Description             UOM  Hand  Allocated  Available   Ship  Available    Order  Committed  Short",
]

# "Avg. TO" wraps onto the line above "Days", so only "Days" sits on the line the
# turnover column offsets are read from
TURNOVER_HEADER_BLOCK = [
    " Location                                                Avg. TO",
    " Group      Part Description       Units Sold   Avg QOH     Days   TO Rate",
]

# The date/page stamp closing every page
FOOTER_LINE = (
    "January 22, 2024 1:07:23 PM CST                                        Page 1 of 25"
)


def build_page(header_block: list, *lines: str) -> str:
    """
    Joins a header block and the lines beneath it into one page of layout-extracted
    text.

    Args:
        header_block (list): The header lines the column offsets are read from
        *lines (str): The table lines following the header

    Returns:
        str: The page text as read_pdf() would return it
    """

    return "\n".join(header_block + list(lines))


###############################################################################
###                     PdfTableParser -> Test Fixture                      ###
###############################################################################
@pytest.fixture
def parser():
    """
    Test fixture to set up a PdfTableParser object for testing to maximize code
    reuse. The parser owns no collaborators and performs no I/O, so nothing needs
    to be mocked out.
    """

    return PdfTableParser()


###############################################################################
###             Tests PdfTableParser -> parse_inventory_page()              ###
###############################################################################
def test_parse_inventory_page_parses_a_full_row(parser):
    """
    Tests that a complete inventory line becomes one row of part, description, UOM
    and the eight trailing numeric columns.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # A page holding a single complete row
    page = build_page(
        INVENTORY_HEADER_BLOCK,
        "PART-A        WIDGET ONE               ea   100          0          0      0        100        0          0      0",
    )

    # Every column lands in its own field, in the order the entry class expects
    assert parser.parse_inventory_page(page, []) == [
        ["PART-A", "WIDGET ONE", "ea", "100", "0", "0", "0", "100", "0", "0", "0"]
    ]


def test_parse_inventory_page_inserts_a_blank_uom_when_the_report_omits_it(parser):
    """
    Tests that a report whose header carries no UOM column still produces a row of
    the same shape, with an empty UOM, so the numeric fields stay at the positions
    the entry class reads them from.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # The header says the report has no UOM column
    page = build_page(
        NO_UOM_HEADER_BLOCK,
        "PART-A        WIDGET ONE           100          0          0      0        100        0          0      0",
    )

    # An empty UOM holds the numeric columns in place
    assert parser.parse_inventory_page(page, []) == [
        ["PART-A", "WIDGET ONE", "", "100", "0", "0", "0", "100", "0", "0", "0"]
    ]


def test_parse_inventory_page_returns_the_rows_unchanged_with_no_header(parser):
    """
    Tests that a page carrying no inventory header, such as a cover page, is passed
    over without disturbing the rows parsed so far.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # A page with no column header on it
    page = "Example Company Inc.\nInventory Availability"

    # The rows parsed so far come back untouched
    assert parser.parse_inventory_page(page, [["PART-A", "WIDGET ONE"]]) == [
        ["PART-A", "WIDGET ONE"]
    ]


def test_parse_inventory_page_stops_at_the_page_footer(parser):
    """
    Tests that the date/page stamp closes the table, so anything printed below it is
    not mistaken for another row.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # A row is printed below the footer that closes the table
    page = build_page(
        INVENTORY_HEADER_BLOCK,
        "PART-A        WIDGET ONE               ea   100          0          0      0        100        0          0      0",
        FOOTER_LINE,
        "PART-Z        AFTER THE FOOTER         ea     1          0          0      0          1        0          0      0",
    )

    # Only the row above the footer is parsed
    assert parser.parse_inventory_page(page, []) == [
        ["PART-A", "WIDGET ONE", "ea", "100", "0", "0", "0", "100", "0", "0", "0"]
    ]


def test_parse_inventory_page_skips_blank_lines(parser):
    """
    Tests that the blank lines padding the table out to the footer neither become
    rows nor break the row that precedes them.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # A blank line separates two rows
    page = build_page(
        INVENTORY_HEADER_BLOCK,
        "PART-A        WIDGET ONE               ea   100          0          0      0        100        0          0      0",
        "",
        "PART-B        WIDGET TWO               ea    50          5          0      0         45        0          0      0",
    )

    # Both rows are parsed and the blank line is dropped
    assert parser.parse_inventory_page(page, []) == [
        ["PART-A", "WIDGET ONE", "ea", "100", "0", "0", "0", "100", "0", "0", "0"],
        ["PART-B", "WIDGET TWO", "ea", "50", "5", "0", "0", "45", "0", "0", "0"],
    ]


def test_parse_inventory_page_keeps_a_part_containing_spaces_in_one_piece(parser):
    """
    Tests that a part number containing a run of spaces survives intact, which is
    why the part is sliced off at the description offset rather than split on the
    gap between the two columns.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # The part number itself contains a run of spaces
    page = build_page(
        INVENTORY_HEADER_BLOCK,
        "PART  B       WIDGET TWO               ea    50          5          0      0         45        0          0      0",
    )

    # The part is not split at its internal gap
    assert parser.parse_inventory_page(page, [])[0][0] == "PART  B"


def test_parse_inventory_page_rejoins_a_description_containing_spaces(parser):
    """
    Tests that a description broken into several fields by its own internal spacing
    is rejoined into one description rather than shifting the numeric columns.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # The description itself contains a run of spaces
    page = build_page(
        INVENTORY_HEADER_BLOCK,
        "PART-A        WIDGET  ONE              ea   100          0          0      0        100        0          0      0",
    )

    # The description comes back as one field, with its fragments joined by a space
    assert parser.parse_inventory_page(page, []) == [
        ["PART-A", "WIDGET ONE", "ea", "100", "0", "0", "0", "100", "0", "0", "0"]
    ]


def test_parse_inventory_page_folds_a_continuation_line_into_the_previous_row(parser):
    """
    Tests that a line carrying only fragments of a wrapped part and description is
    appended to the row it continues rather than becoming a row of its own.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # The part and description both wrap onto the line below
    page = build_page(
        INVENTORY_HEADER_BLOCK,
        "PART-A        WIDGET ONE               ea   100          0          0      0        100        0          0      0",
        "AND MORE      CONTINUED",
    )

    # Both fragments are folded onto the previous row, joined by the separator
    assert parser.parse_inventory_page(page, []) == [
        [
            "PART-A" + CONTINUATION_SEPARATOR + "AND MORE",
            "WIDGET ONE" + CONTINUATION_SEPARATOR + "CONTINUED",
            "ea",
            "100",
            "0",
            "0",
            "0",
            "100",
            "0",
            "0",
            "0",
        ]
    ]


def test_parse_inventory_page_folds_a_continuation_into_a_row_from_a_prior_page(
    parser,
):
    """
    Tests that a row wrapping across a page boundary is folded back into the row it
    continues on the previous page, which is why the caller threads the running list
    of rows back in.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # The row was parsed off the bottom of the previous page
    rows = [
        ["PART-A", "WIDGET ONE", "ea", "100", "0", "0", "0", "100", "0", "0", "0"]
    ]

    # This page opens with the rest of that row's part and description
    page = build_page(INVENTORY_HEADER_BLOCK, "AND MORE      CONTINUED")

    # The fragments are folded onto the row from the previous page
    assert parser.parse_inventory_page(page, rows) == [
        [
            "PART-A" + CONTINUATION_SEPARATOR + "AND MORE",
            "WIDGET ONE" + CONTINUATION_SEPARATOR + "CONTINUED",
            "ea",
            "100",
            "0",
            "0",
            "0",
            "100",
            "0",
            "0",
            "0",
        ]
    ]


def test_parse_inventory_page_drops_a_continuation_with_no_row_to_continue(parser):
    """
    Tests that a continuation line arriving before any row has been parsed is
    dropped rather than crashing on an empty list of rows.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # The first line under the header is a fragment continuing nothing
    page = build_page(INVENTORY_HEADER_BLOCK, "ORPHAN        FRAGMENT")

    # No row is produced and no error is raised
    assert parser.parse_inventory_page(page, []) == []


def test_parse_inventory_page_rereads_the_column_offsets_from_each_page(parser):
    """
    Tests that the column offsets are re-derived from each page's own header, since
    they drift by a character or two from page to page.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # The same row laid out under a header shifted three characters right
    page = build_page(
        SHIFTED_HEADER_BLOCK,
        "PART-A           WIDGET ONE               ea   100          0          0      0        100        0          0      0",
    )

    # The row parses identically to one laid out under the unshifted header
    assert parser.parse_inventory_page(page, []) == [
        ["PART-A", "WIDGET ONE", "ea", "100", "0", "0", "0", "100", "0", "0", "0"]
    ]


###############################################################################
###             Tests PdfTableParser -> parse_turnover_page()               ###
###############################################################################
def test_parse_turnover_page_parses_a_totals_row(parser):
    """
    Tests that a part's "Totals:" line becomes one row of the part label and its
    four numeric columns.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # A page holding a single part's totals
    page = build_page(
        TURNOVER_HEADER_BLOCK,
        "                        PART-A Totals:    12       800   1,234.50   0.02500",
    )

    # The label and every numeric column land in their own field
    assert parser.parse_turnover_page(page, []) == [
        ["PART-A", "12", "800", "1,234.50", "0.02500"]
    ]


def test_parse_turnover_page_returns_the_rows_unchanged_with_no_header(parser):
    """
    Tests that a page carrying no turnover header is passed over without disturbing
    the rows parsed so far.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # A page with no column header on it
    page = "Example Company Inc.\nTurnover Report"

    # The rows parsed so far come back untouched
    assert parser.parse_turnover_page(page, [["PART-A", "12", "800", "0", "0"]]) == [
        ["PART-A", "12", "800", "0", "0"]
    ]


def test_parse_turnover_page_ignores_the_detail_lines(parser):
    """
    Tests that the per-location detail lines above each "Totals:" line are not
    parsed, since only the totals belong in the report.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # The part's detail line sits above its totals line
    page = build_page(
        TURNOVER_HEADER_BLOCK,
        "PART-A",
        " Main       WIDGET ONE                    12       800   1,234.50   0.02500",
        "                        PART-A Totals:    12       800   1,234.50   0.02500",
    )

    # Only the totals line becomes a row
    assert parser.parse_turnover_page(page, []) == [
        ["PART-A", "12", "800", "1,234.50", "0.02500"]
    ]


def test_parse_turnover_page_skips_the_company_grand_total(parser):
    """
    Tests that the grand total closing the report is skipped, since it belongs to no
    part and so has no inventory row to match against.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # The report closes with a company-wide total
    page = build_page(
        TURNOVER_HEADER_BLOCK,
        "                        PART-A Totals:    12       800   1,234.50   0.02500",
        f"                       {GRAND_TOTAL_LABEL} Totals:    24     1,173",
    )

    # Only the part's totals become a row
    assert parser.parse_turnover_page(page, []) == [
        ["PART-A", "12", "800", "1,234.50", "0.02500"]
    ]


def test_parse_turnover_page_binds_a_label_containing_spaces_to_the_last_totals(
    parser,
):
    """
    Tests that a part label made of several space-separated words is captured whole,
    rather than only the word immediately before "Totals:".

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # The part label contains spaces
    page = build_page(
        TURNOVER_HEADER_BLOCK,
        "                    PART B TWO Totals:     0       132          0         0",
    )

    # The whole label is captured
    assert parser.parse_turnover_page(page, [])[0][0] == "PART B TWO"


def test_parse_turnover_page_takes_the_values_from_above_when_the_name_wraps(parser):
    """
    Tests that a part name long enough to wrap, which pushes "Totals:" onto a line
    of its own, has its label rejoined and its values read off the line above.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # The part name wraps, leaving "Totals:" alone on the line below the values
    page = build_page(
        TURNOVER_HEADER_BLOCK,
        "A VERY LONG PART NAME - WRAPPED",
        " Main       A VERY LONG PART NAME -        5    200.75      1,500   0.04000",
        "            WRAPPED",
        "            A VERY LONG PART NAME          5    200.75      1,500   0.04000",
        "                          - WRAPPED Totals:",
    )

    # The label is rejoined and the values come from the line above
    assert parser.parse_turnover_page(page, []) == [
        ["A VERY LONG PART NAME - WRAPPED", "5", "200.75", "1,500", "0.04000"]
    ]


def test_parse_turnover_page_returns_empty_values_for_a_wrapped_totals_at_the_top(
    parser,
):
    """
    Tests that a valueless "Totals:" line with no line above it yields empty values,
    rather than reading the values off the last line of the page.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # The valueless totals line opens the page, with the header below it
    page = "\n".join(["PART-A Totals:"] + TURNOVER_HEADER_BLOCK)

    # The row is produced with no values rather than borrowed ones
    assert parser.parse_turnover_page(page, []) == [["PART-A", "", "", "", ""]]


def test_parse_turnover_page_appends_to_the_rows_from_the_previous_page(parser):
    """
    Tests that this page's rows are appended to the rows parsed so far, so a report
    spanning many pages accumulates into one list.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # A row was parsed off the previous page
    rows = [["PART-A", "12", "800", "1,234.50", "0.02500"]]

    # This page holds the next part's totals
    page = build_page(
        TURNOVER_HEADER_BLOCK,
        "                        PART-B Totals:     0       132          0         0",
    )

    # The new row is appended after the earlier one
    assert parser.parse_turnover_page(page, rows) == [
        ["PART-A", "12", "800", "1,234.50", "0.02500"],
        ["PART-B", "0", "132", "0", "0"],
    ]


###############################################################################
###               Tests PdfTableParser -> align_to_columns()                ###
###############################################################################
def test_align_to_columns_assigns_each_value_to_its_nearest_column_edge(parser):
    """
    Tests that each value is assigned to the column whose header right edge it lines
    up with.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # Two values, each ending at one of the two column edges
    assert parser.align_to_columns("       1,234        56", [12, 22], 0) == [
        "1,234",
        "56",
    ]


def test_align_to_columns_leaves_a_column_the_report_skipped_blank(parser):
    """
    Tests that a column the report printed nothing in stays blank, instead of the
    following values each shifting one column to the left.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # The middle column is empty
    assert parser.align_to_columns(
        "       1,234                78", [12, 22, 30], 0
    ) == ["1,234", "", "78"]


def test_align_to_columns_matches_values_with_separators_and_signs(parser):
    """
    Tests that a thousands separator, a decimal point and a leading minus sign are
    all read as part of one value rather than splitting it.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # The first value carries a sign, a separator and a decimal point
    assert parser.align_to_columns("  -1,234.5      99", [12, 20], 0) == [
        "-1,234.5",
        "99",
    ]


def test_align_to_columns_returns_all_blanks_for_text_with_no_values(parser):
    """
    Tests that a numeric region holding no values yields one blank per column, which
    is the signal the caller uses to look for a wrapped row.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # The slice holds no numeric value at all
    assert parser.align_to_columns("", [12, 22], 0) == ["", ""]


def test_align_to_columns_shifts_the_comparison_by_the_offset(parser):
    """
    Tests that the offset places the text within its line, so the same text lands in
    a different column depending on where the slice started.

    Args:
        parser (pytest.fixture): Test fixture to create the PdfTableParser object
    """

    # The same value, sliced from two different positions in its line
    assert parser.align_to_columns("5", [1, 11], 0) == ["5", ""]
    assert parser.align_to_columns("5", [1, 11], 10) == ["", "5"]
