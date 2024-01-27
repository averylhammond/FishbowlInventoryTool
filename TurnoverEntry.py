import logging

# turnoverEntry class to hold all attributes of the TurnoverEntry that
# passes to the .xlsx file
class TurnoverEntry:
    def __init__(self):
        self.partDescription = None  # Part description
        self.unitsSold       = 0     # Units sold
        self.avgQOH          = 0.0   # Average quantity on hand
        self.avgTODays       = 0.0   # Average turnover days
        self.TORate          = 0.0   # Turnover rate
    
    # dumpTurnoverEntry is a debug function to print the attributes of a given TurnoverEntry object
    # to the terminal
    # params: N/A
    # returns: N/A
    def dumpTurnoverEntry(self):
        logging.debug("*****************************")
        logging.debug(f"partDescription: {self.partDescription}")
        logging.debug(f"unitsSold: {self.unitsSold}")
        logging.debug(f"avgQOH: {self.avgQOH}")
        logging.debug(f"avgTODays: {self.avgTODays}")
        logging.debug(f"TORate: {self.TORate}")
        logging.debug("*****************************")


    # populateTurnoverEntry initializes the appropriate fields of a given TurnoverEntry object
    # params: list: list, a list of parameters in order of definition to be mapped to the object
    # returns: N/A
    def populateTurnoverEntry(self, list):
        
        # Make sure to strip off any leading whitespace (result from using double space as the string
        # splitting delimiter) and make sure to remove any commas in numbers
        self.partDescription = list[1].lstrip(' ').replace(' Totals:', '')
        self.unitsSold       = list[3].lstrip(' ').replace(',', '')
        self.avgQOH          = list[4].lstrip(' ').replace(',', '')
        self.avgTODays       = list[5].lstrip(' ').replace(',', '')
        self.TORate          = list[6].lstrip(' ').replace(',', '')
        