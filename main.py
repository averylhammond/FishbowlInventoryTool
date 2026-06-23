from source.InventoryAppController import InventoryAppController

# Entry Point
if __name__ == "__main__":
    """
    Entry point to the application. Initializes the InventoryAppController and
    starts the application.
    """

    # Create the InventoryAppController instance
    controller = InventoryAppController()

    # Start the Inventory Processor App
    controller.start_application()
