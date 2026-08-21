from pathlib import Path

# Display name of this application. Passed to the shared AboutWindow, which is
# application-agnostic and takes the name it shows by injection.
APP_NAME = "Fishbowl Inventory Tool"

# Current application version. Single source of truth for the version, kept
# consistent with application releases and surfaced to the user via Help -> About.
VERSION = "2.3.0"

# GitHub repository ("owner/name") this app releases from. Passed to the shared
# UpdateCoordinator so it knows which repo's releases to compare VERSION against.
GITHUB_REPO = "averylhammond/FishbowlInventoryTool"

# Name of the installer asset published on each GitHub release, matched against the
# release's assets by the shared UpdateCoordinator to find the file an in-app update
# downloads and runs. Injected rather than hardcoded upstream because each Fishbowl
# app names its own installer; a release without a matching asset simply offers the
# manual download instead. Must stay in step with installer.iss's OutputBaseFilename.
INSTALLER_ASSET_PATTERN = "FishbowlInventoryTool_Setup.exe"

# Patch notes shipped alongside the executable, holding one "## X.Y.Z" section
# per release. Shown on the first launch after an update and available any time
# from Help -> What's New. Read at runtime rather than fetched, so the first
# launch after an update needs no network.
PATCH_NOTES_PATH = Path("PATCH_NOTES.md")

# Base directories. The specific file paths below are composed from these.
INVENTORY_DIR = Path("InventoryAvailability")
TURNOVER_DIR = Path("TurnoverReports")

# Directory the generated .xlsx reports are written to. The application root
# (i.e. the executable's CWD), so a finished spreadsheet sits next to the app.
OUTPUT_DIR = Path(".")

# Logs directory containing the results file with application output
LOGS_DIR = Path("logs")
RESULTS_FILE = LOGS_DIR / "results.txt"

# Data directory holding the database of persisted user settings
DATA_DIR = Path("data")
SETTINGS_DB_PATH = DATA_DIR / "settings.db"

# Keys under which user settings are persisted in the settings database. Shared
# between the display (which reads/writes them) and any other consumer so the
# two never drift apart. Every value is stored as text, so a non-string setting
# is converted on the way out and parsed on the way back in.
SETTING_KEY_THEME = "theme"
SETTING_KEY_FONT_FAMILY = "font_family"
SETTING_KEY_FONT_SIZE = "font_size"
SETTING_KEY_GEOMETRY = "window_geometry"

# Version the application was running the last time it was launched, compared
# against VERSION on startup to spot the first launch after an update.
SETTING_KEY_LAST_SEEN_VERSION = "last_seen_version"

# Prefix each column's checkbox state is persisted under, e.g. "column_OnHand".
# The column key itself completes the setting key, so a column added to
# source/columns.py needs no new constant here.
SETTING_KEY_COLUMN_PREFIX = "column_"
