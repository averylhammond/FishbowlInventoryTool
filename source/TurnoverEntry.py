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

        # Index from the front rather than counting back from the end: the report
        # leaves a column blank now and then, and the parser preserves that as an
        # empty field. Commas are the thousands separators inside the numbers.
        # fmt:off
        self.partDescription = list[0]
        self.unitsSold       = list[1].replace(',', '')
        self.avgQOH          = list[2].replace(',', '')
        self.avgTODays       = list[3].replace(',', '')
        self.TORate          = list[4].replace(',', '')
        # fmt:on
