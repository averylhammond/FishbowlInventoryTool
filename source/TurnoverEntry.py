from dataclasses import dataclass


# TurnoverEntry class to hold all attributes of the TurnoverEntry that
# passes to the .xlsx file. The values arrive from PdfTableParser already converted
# to numbers; the three averages default to None because the report leaves them
# blank where the part's turnover is undefined. Every field has a default, so
# TurnoverEntry() default-constructs while callers may also build one straight from
# a parsed row, e.g. TurnoverEntry(*row).
@dataclass
class TurnoverEntry:

    # fmt:off
    part_description: str              = ""    # Part description
    units_sold: int | float            = 0     # Units sold
    avg_qoh: int | float | None        = None  # Average quantity on hand
    avg_to_days: int | float | None    = None  # Average turnover days
    to_rate: int | float | None        = None  # Turnover rate
    # fmt:on

    ###########################################################################
    ###               TurnoverEntry -> to_formatted_string()                ###
    ###########################################################################
    def to_formatted_string(self):
        """
        Returns a formatted string of the attributes of a given TurnoverEntry object

        Returns:
            str: A formatted string containing all of the entry's fields on separate
                lines
        """

        return (
            "*****************************\n"
            f"partDescription: {self.part_description}\n"
            f"unitsSold: {self.units_sold}\n"
            f"avgQOH: {self.avg_qoh}\n"
            f"avgTODays: {self.avg_to_days}\n"
            f"TORate: {self.to_rate}\n"
            "*****************************"
        )
