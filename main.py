"""
Entry point to the application. Initializes the InventoryAppController and starts
the application.
"""

from source.inventory_app_controller import InventoryAppController

if __name__ == "__main__":
    # Create the InventoryAppController instance
    controller = InventoryAppController()

    # Start the Inventory Processor App
    controller.start_application()
