from pathlib import Path

# Current application version. Single source of truth for the version, kept
# consistent with application releases and surfaced to the user via Help -> About.
VERSION = "2.0.1"

# GitHub repository ("owner/name") this app releases from. Passed to the shared
# UpdateChecker so it knows which repo's releases to compare VERSION against.
GITHUB_REPO = "averylhammond/FishbowlInventoryTool"

# Base directories. The specific file paths below are composed from these.
INVENTORY_DIR = Path("InventoryAvailability")
TURNOVER_DIR = Path("TurnoverReports")

# Logs directory containing the results file with application output
LOGS_DIR = Path("logs")
RESULTS_FILE = LOGS_DIR / "results.txt"
