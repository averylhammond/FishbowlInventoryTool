from pathlib import Path

# Base directories. The specific file paths below are composed from these.
INVENTORY_DIR = Path("InventoryAvailability")
TURNOVER_DIR = Path("TurnoverReports")

# Logs directory containing the results file with application output
LOGS_DIR = Path("logs")
RESULTS_FILE = LOGS_DIR / "results.txt"
