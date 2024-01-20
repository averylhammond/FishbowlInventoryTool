import logging

# InventoryLine class to hold all attributes of the InventoryLine that
# passes to the .xlsx file
class InventoryLine:
    def __init__(self):
        self.partDescription = 0.0  # Part number and description
        self.onHand          = 0.0  # Number of parts at location
        self.allocated       = 0.0  # Number of parts already allocated to a job (already included in onHand)
        self.notAvailable    = 0.0  # Number of parts not available for use
        self.dropShip        = 0.0  # Not used, but listed in table
        self.available       = 0.0  # Number of available parts (onHand - allocated)
        self.onOrder         = 0.0  # Number of parts on order but not arrived
        self.committed       = 0.0  # TODO: is this the same as allocated?
        self.short           = 0.0  # TODO: Is this like being in the negative?

    def dumpInventoryLine(self):
        logging.debug("*****************************")
        logging.debug(f"partDescription: {self.partDescription}")
        logging.debug(f"onHand: {self.onHand}")
        logging.debug(f"allocated: {self.allocated}")
        logging.debug(f"notAvailable: {self.notAvailable}")
        logging.debug(f"dropShip: {self.dropShip}")
        logging.debug(f"available: {self.available}")
        logging.debug(f"onOrder: {self.onOrder}")
        logging.debug(f"committed: {self.committed}")
        logging.debug(f"short: {self.short}")
        logging.debug("*****************************")

    # populateInventoryLine initializes the appropriate fields of a given InventoryLine object
    # params: text: str taken from the first page of the invoice
    # params: allSalesReps: dict, all possible sales rep codes and names
    # params: allPaymentTerms: list, all possible payment terms
    # returns: N/A
    """def populateInvoice(self, text, allSalesReps, allPaymentTerms):
        self.invoiceNum = searchInvoice(text, "S(\d{5})")
        self.date = searchInvoice(text, "\d{2}/\d{2}/\d{4}")
        self.customer = searchInvoice(text, "Customer: .+").replace("Customer: ", "")
        self.poNum = (searchInvoice(text, "PO Number: .+S")[:-1]).replace("PO Number: ", "")
        self.paymentTerms = findPaymentTerms(text, allPaymentTerms)
        self.rep = findSalesRep(text, allSalesReps)"""