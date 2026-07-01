# turnoverEntry class to hold all attributes of the TurnoverEntry that
# passes to the .xlsx file
class TurnoverEntry:
    def __init__(self):
        #fmt:off
        self.partDescription = None  # Part description
        self.unitsSold       = 0     # Units sold
        self.avgQOH          = 0.0   # Average quantity on hand
        self.avgTODays       = 0.0   # Average turnover days
        self.TORate          = 0.0   # Turnover rate
        # fmt:on

    # to_formatted_string returns a formatted string of the attributes of a given
    # TurnoverEntry object
    # params: N/A
    # returns: str, the formatted attribute dump
    def to_formatted_string(self):
        return (
            "*****************************\n"
            f"partDescription: {self.partDescription}\n"
            f"unitsSold: {self.unitsSold}\n"
            f"avgQOH: {self.avgQOH}\n"
            f"avgTODays: {self.avgTODays}\n"
            f"TORate: {self.TORate}\n"
            "*****************************"
        )

    # populateTurnoverEntry initializes the appropriate fields of a given TurnoverEntry object
    # params: list: list, a list of parameters in order of definition to be mapped to the object
    # returns: N/A
    def populateTurnoverEntry(self, list):

        # Make sure to strip off any leading whitespace (result from using double space as the string
        # splitting delimiter) and make sure to remove any commas in numbers
        # fmt:off
        self.partDescription = list[1].lstrip(' ').replace(' Totals:', '')
        self.unitsSold       = list[-4].lstrip(' ').replace(',', '').replace('.0', '')  # int value, strip .0
        self.avgQOH          = list[-3].lstrip(' ').replace(',', '')
        self.avgTODays       = list[-2].lstrip(' ').replace(',', '')
        self.TORate          = list[-1].lstrip(' ').replace(',', '')
        # fmt:on
