import re

# Trailing numeric columns of an inventory row: onHand, allocated, notAvailable,
# dropShip, available, onOrder, committed, short. UOM sits ahead of them and is
# missing from some reports, so it is counted separately off the header.
INVENTORY_NUMERIC_COLUMNS = 8

# The four numeric turnover columns, named as they appear in the report header.
# "Avg. TO" wraps onto the line above "Days", so only "Days" is on the line the
# column offsets are read from.
TURNOVER_COLUMN_LABELS = ("Units Sold", "Avg QOH", "Days", "TO Rate")

# The inventory column header, whose offsets anchor every column on the page
INVENTORY_HEADER = re.compile(r"^\s*Part\s{2,}Description\b")

# The turnover column header, identified by its first numeric column
TURNOVER_HEADER = re.compile(r"\bUnits Sold\b")

# The date/page stamp closing every page. The turnover reports render it with no
# space before the page count ("Page 1 of42"), hence the \s* rather than \s+.
PAGE_FOOTER = re.compile(r"Page\s+\d+\s+of\s*\d+\s*$")

# A turnover totals row: a part label, "Totals:", then the numeric columns. The
# label is non-greedy so one containing spaces still binds to the last "Totals:".
TOTALS_ROW = re.compile(r"^(?P<label>.*?)\s+Totals:(?P<numbers>.*)$")

# The report closes with a grand total belonging to no part
GRAND_TOTAL_LABEL = "Company"

# Two or more spaces separate one column from the next in layout-extracted text
COLUMN_GAP = re.compile(r" {2,}")

# A single numeric cell; the punctuation covers thousands separators, decimals
# and negatives
NUMERIC_VALUE = re.compile(r"[\d,.-]+")

# Joins the fragments of a part or description that the report wrapped across
# several lines. A single space reads the way the report intends; set it to ""
# to concatenate the fragments with nothing between them.
CONTINUATION_SEPARATOR = " "


# PdfTableParser class to turn layout-extracted PDF page text into the positional
# field lists the entry data classes are constructed from
class PdfTableParser:

    ###########################################################################
    ###             PdfTableParser -> parse_inventory_page()                ###
    ###########################################################################
    def parse_inventory_page(self, page: str, rows: list) -> list:
        """
        Parses one inventory availability page onto the running list of rows. A row
        whose part or description wrapped across several lines is folded back into
        the row it continues, which may sit on the previous page, so the caller
        passes the rows parsed so far back in.

        Args:
            page (str): Layout-extracted text for a single page
            rows (list): The rows parsed so far

        Returns:
            list: The rows parsed so far plus this page's, each one a list of
                [part, description, uom, on_hand, allocated, not_available, drop_ship,
                available, on_order, committed, short], the quantities as numbers
        """

        lines = page.splitlines()

        # Column offsets drift by a character or two from page to page, so they are
        # re-read from each page's own header rather than hardcoded
        header_index = next(
            (i for i, line in enumerate(lines) if INVENTORY_HEADER.match(line)),
            None,
        )
        if header_index is None:
            return rows

        header = lines[header_index]
        description_column = header.index("Description")

        # Some inventory reports omit the UOM column; the header says which
        has_uom_column = "UOM" in header
        trailing_columns = INVENTORY_NUMERIC_COLUMNS + (1 if has_uom_column else 0)

        for line in lines[header_index + 1 :]:

            # The date/page stamp closes the table, and blank lines pad up to it
            if PAGE_FOOTER.search(line):
                break
            if not line.strip():
                continue

            # Splitting Part from the rest at the Description offset rather than on
            # the gap between them keeps a part number that itself contains a run of
            # spaces ('3/4"  BLANK HINGE') in one piece
            part = line[:description_column].strip()
            fields = [
                field
                for field in COLUMN_GAP.split(line[description_column:].strip())
                if field
            ]

            # A full row carries a description plus every trailing column; a
            # continuation line carries only a fragment of the wrapped text
            if len(fields) > trailing_columns:
                split = len(fields) - trailing_columns

                # Rejoin a description that itself contained a run of spaces
                description = " ".join(fields[:split])
                trailing = fields[split:]

                # Hold the field positions steady for reports with no UOM column
                if not has_uom_column:
                    trailing.insert(0, "")

                # UOM is a label; everything after it is a quantity
                uom, *numbers = trailing
                rows.append(
                    [part, description, uom]
                    + [self.to_number(number) for number in numbers]
                )

            elif rows:
                if part:
                    rows[-1][0] += CONTINUATION_SEPARATOR + part
                if fields:
                    rows[-1][1] += CONTINUATION_SEPARATOR + fields[0]

        return rows

    ###########################################################################
    ###             PdfTableParser -> parse_turnover_page()                 ###
    ###########################################################################
    def parse_turnover_page(self, page: str, rows: list) -> list:
        """
        Parses one turnover report page onto the running list of rows, adding a row
        for each part's "Totals:" line

        Args:
            page (str): Layout-extracted text for a single page
            rows (list): The rows parsed so far

        Returns:
            list: The rows parsed so far plus this page's, each one a list of
                [part_description, units_sold, avg_qoh, avg_to_days, to_rate], the
                trailing four as numbers
        """

        lines = page.splitlines()

        header = next(
            (line for line in lines if TURNOVER_HEADER.search(line)), None
        )
        if header is None:
            return rows

        column_ends = [
            header.index(label) + len(label) for label in TURNOVER_COLUMN_LABELS
        ]
        numbers_column = header.index(TURNOVER_COLUMN_LABELS[0])

        for index, line in enumerate(lines):

            match = TOTALS_ROW.match(line)
            if match is None:
                continue

            label = match.group("label").strip()
            if label == GRAND_TOTAL_LABEL:
                continue

            numbers = match.group("numbers")
            values = self.align_to_columns(
                numbers, column_ends, len(line) - len(numbers)
            )

            # A part name long enough to wrap pushes "Totals:" onto a line of its
            # own, leaving the values on the line above alongside the first half of
            # the name
            if not any(values) and index > 0:
                wrapped = lines[index - 1]
                values = self.align_to_columns(
                    wrapped[numbers_column:], column_ends, numbers_column
                )
                label = f"{wrapped[:numbers_column].strip()} {label}".strip()

            # Convert only once the wrapped-row check above is done, since that check
            # reads the values as the strings align_to_columns produced
            rows.append([label] + [self.to_number(value) for value in values])

        return rows

    ###########################################################################
    ###               PdfTableParser -> align_to_columns()                  ###
    ###########################################################################
    def align_to_columns(self, text: str, column_ends: list, offset: int) -> list:
        """
        Assigns each value in a row's numeric region to the column its right edge
        lines up with. Matching edges rather than counting values off the end of the
        row keeps a column the report left blank blank, instead of shifting every
        later value one column to the left.

        Args:
            text (str): The slice of the line holding the numeric columns
            column_ends (list): End offset of each column's header label
            offset (int): Offset of text within its line, so a value's right edge can
                be compared against the header's

        Returns:
            list: One value per column, "" wherever the report printed nothing
        """

        values = [""] * len(column_ends)

        for value in NUMERIC_VALUE.finditer(text):
            right_edge = value.end() + offset
            column = min(
                range(len(column_ends)),
                key=lambda index: abs(column_ends[index] - right_edge),
            )
            values[column] = value.group()

        return values

    ###########################################################################
    ###                  PdfTableParser -> to_number()                      ###
    ###########################################################################
    def to_number(self, text: str):
        """
        Converts one numeric cell of the report into the number it holds, dropping
        the thousands separators the report prints inside it. The cell is typed by
        what it says rather than by which column it came from, so a column mixing
        whole and fractional values keeps each one as written.

        Args:
            text (str): The cell as the report printed it

        Returns:
            int: The value of a cell holding no decimal point
            float: The value of a cell holding one
            None: For a cell the report left blank, keeping that distinct from a
                value of zero
        """

        text = text.replace(",", "")

        if not text:
            return None

        # NUMERIC_VALUE matches runs of digits and punctuation, so a stray token
        # like "-" can reach here. Handing it back unconverted keeps a malformed
        # cell out of the numbers instead of failing the whole report over it.
        try:
            return float(text) if "." in text else int(text)
        except ValueError:
            return text
