# InventoryEntry class to hold all attributes of the InventoryEntry that
# passes to the .xlsx file
class InventoryEntry:
    def __init__(self):
        self.part         = None  # Part number
        self.description  = None  # Part description
        self.uom          = None  # Unit of measurement (usually "ea")
        self.onHand       = 0     # Number of parts at location
        self.allocated    = 0     # Number of parts already allocated to a job (already included in onHand)
        self.notAvailable = 0     # Number of parts not available for use
        self.dropShip     = 0     # Not used, but listed in table
        self.available    = 0     # Number of available parts (onHand - allocated)
        self.onOrder      = 0     # Number of parts on order but not arrived
        self.committed    = 0     # TODO: is this the same as allocated?
        self.short        = 0     # TODO: Is this like being in the negative?
        self.rowWrittenTo = 0     # The row that the entry is written to through the xlsxwriter API

    
    # to_formatted_string returns a formatted string of the attributes of a given
    # InventoryEntry object
    # params: N/A
    # returns: str, the formatted attribute dump
    def to_formatted_string(self):
        return (
            "*****************************\n"
            f"part: {self.part}\n"
            f"description: {self.description}\n"
            f"uom: {self.uom}\n"
            f"onHand: {self.onHand}\n"
            f"allocated: {self.allocated}\n"
            f"notAvailable: {self.notAvailable}\n"
            f"dropShip: {self.dropShip}\n"
            f"available: {self.available}\n"
            f"onOrder: {self.onOrder}\n"
            f"committed: {self.committed}\n"
            f"short: {self.short}\n"
            f"rowWrittenTo: {self.rowWrittenTo}\n"
            "*****************************"
        )


    # populateInventoryEntry initializes the appropriate fields of a given InventoryEntry object
    # params: list: list, a list of parameters in order of definition to be mapped to the object
    # returns: N/A
    def populateInventoryEntry(self, list):
        
        # The parser has already trimmed each field; commas are the thousands
        # separators the report prints inside its numbers
        # fmt:off
        self.part         = list[0]
        self.description  = list[1]
        self.uom          = list[2]
        self.onHand       = list[3].replace(',', '')
        self.allocated    = list[4].replace(',', '')
        self.notAvailable = list[5].replace(',', '')
        self.dropShip     = list[6].replace(',', '')
        self.available    = list[7].replace(',', '')
        self.onOrder      = list[8].replace(',', '')
        self.committed    = list[9].replace(',', '')
        self.short        = list[10].replace(',', '')
        # fmt:on