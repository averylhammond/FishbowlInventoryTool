from dataclasses import dataclass


# InventoryEntry class to hold all attributes of the InventoryEntry that
# passes to the .xlsx file. The quantities arrive from PdfTableParser already
# converted to numbers, so they reach the spreadsheet as numeric cells. The fields
# below are exactly one parsed row, in the parser's column order, so a caller may
# build one straight from a row with InventoryEntry(*row). Every field also has a
# default, so InventoryEntry() default-constructs.
@dataclass
class InventoryEntry:

    # fmt:off
    part: str                    = ""  # Part number
    description: str             = ""  # Part description
    uom: str                     = ""  # Unit of measurement (usually "ea"), blank in reports omitting the column
    on_hand: int | float         = 0   # Number of parts at location
    allocated: int | float       = 0   # Number of parts already allocated to a job (already included in on_hand)
    not_available: int | float   = 0   # Number of parts not available for use
    drop_ship: int | float       = 0   # Not used, but listed in table
    available: int | float       = 0   # Number of available parts (on_hand - allocated)
    on_order: int | float        = 0   # Number of parts on order but not arrived
    committed: int | float       = 0   # TODO: is this the same as allocated?
    short: int | float           = 0   # TODO: Is this like being in the negative?
    # fmt:on

    ###########################################################################
    ###               InventoryEntry -> to_formatted_string()               ###
    ###########################################################################
    def to_formatted_string(self):
        """
        Returns a formatted string of the attributes of a given InventoryEntry object

        Returns:
            str: A formatted string containing all of the entry's fields on separate
                lines
        """

        return (
            "*****************************\n"
            f"part: {self.part}\n"
            f"description: {self.description}\n"
            f"uom: {self.uom}\n"
            f"onHand: {self.on_hand}\n"
            f"allocated: {self.allocated}\n"
            f"notAvailable: {self.not_available}\n"
            f"dropShip: {self.drop_ship}\n"
            f"available: {self.available}\n"
            f"onOrder: {self.on_order}\n"
            f"committed: {self.committed}\n"
            f"short: {self.short}\n"
            "*****************************"
        )
