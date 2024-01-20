import logging

# InventoryLine class to hold all attributes of the InventoryEntry that
# passes to the .xlsx file
class InventoryEntry:
    def __init__(self):
        self.part         = None  # Part number
        self.description  = None  # Part description
        self.onHand       = 0.0   # Number of parts at location
        self.allocated    = 0.0   # Number of parts already allocated to a job (already included in onHand)
        self.notAvailable = 0.0   # Number of parts not available for use
        self.dropShip     = 0.0   # Not used, but listed in table
        self.available    = 0.0   # Number of available parts (onHand - allocated)
        self.onOrder      = 0.0   # Number of parts on order but not arrived
        self.committed    = 0.0   # TODO: is this the same as allocated?
        self.short        = 0.0   # TODO: Is this like being in the negative?

    
    # dumpInventoryEntry is a debug function to print the attributes of a given InventoryEntry object
    # to the terminal
    # params: N/A
    # returns: N/A
    def dumpInventoryEntry(self):
        logging.debug("*****************************")
        logging.debug(f"part: {self.part}")
        logging.debug(f"description: {self.description}")
        logging.debug(f"onHand: {self.onHand}")
        logging.debug(f"allocated: {self.allocated}")
        logging.debug(f"notAvailable: {self.notAvailable}")
        logging.debug(f"dropShip: {self.dropShip}")
        logging.debug(f"available: {self.available}")
        logging.debug(f"onOrder: {self.onOrder}")
        logging.debug(f"committed: {self.committed}")
        logging.debug(f"short: {self.short}")
        logging.debug("*****************************")


    # populateInventoryEntry initializes the appropriate fields of a given InventoryEntry object
    # params: list: list, a list of parameters in order of definition to be mapped to the object
    # returns: N/A
    def populateInventoryEntry(self, list):
        
        # Make sure to strip off any leading whitespace (result from using double space as the string
        # splitting delimiter) and make sure to remove any commas in numbers
        self.part         = list[1].lstrip(' ')
        self.description  = list[2].lstrip(' ')
        self.onHand       = list[3].lstrip(' ').replace(',', '')
        self.allocated    = list[4].lstrip(' ').replace(',', '')
        self.notAvailable = list[5].lstrip(' ').replace(',', '')
        self.dropShip     = list[6].lstrip(' ').replace(',', '')
        self.available    = list[7].lstrip(' ').replace(',', '')
        self.onOrder      = list[8].lstrip(' ').replace(',', '')
        self.committed    = list[9].lstrip(' ').replace(',', '')
        self.short        = list[10].lstrip(' ').replace(',', '')