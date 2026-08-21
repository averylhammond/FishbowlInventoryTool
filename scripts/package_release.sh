#!/usr/bin/env bash
#######################################################################################
#                                                                                     #
# 08/16/2026 - Author - Avery Hammond                                                 #
#                                                                                     #
# This script is intended to take the FishbowlInventoryTool and package it as a       #
# release executable using PyInstaller. It assumes only that the                      #
# FishbowlInventoryTool repository has been cloned. Unlike the sibling                #
# FishbowlInvoiceTool's packaging script, nothing in the release payload comes from   #
# the private automated-inventory-testing submodule, so packaging never needs it      #
# initialized. The release ships empty InventoryAvailability/ and TurnoverReports/    #
# folders for the customer to drop their own reports into. This helper script         #
# automates the packaging process for speed and automated testing purposes. It can be #
# ran in or out of the python virtual environment, as it will create it's own if      #
# needed.                                                                             #
#                                                                                     #
# An example project structure is as follows:                                         #
# project_root/                                                                       #
# └── FishbowlInventoryTool/                                                          #
#   └── scripts/package_release.sh                                                    #
#   └── main.py                                                                       #
#                                                                                     #
# Usage: ./package_release.sh                                                         #
#######################################################################################

# Fail safely on errors and undefined variables, and ensure pipelines fully succeed
set -euo pipefail

# Detect whether we are running in a CI environment (GitHub Actions sets CI=true).
# In CI the workspace is already a clean, freshly-checked-out tree, so the
# local-developer-only environment prep below is skipped.
IS_CI="${CI:-false}"

# Get the location of this script, and use it to derive the project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Derived project root: $ROOT_DIR"

# Local-developer-only environment prep. These steps prepare a developer's working tree
# for a clean build; in CI they are unnecessary and the git clean would delete the test
# data the workflow staged before packaging, so guard them behind the CI check.
if [[ "$IS_CI" == "true" ]]; then
    echo "CI detected; skipping local env prep (venv deactivate, git clean)."
else
    # Exit any active virtual environment so a fresh one can be created below
    if [[ -n "${VIRTUAL_ENV:-}" ]]; then
        echo "Exiting current virtual environment to create a fresh one: $VIRTUAL_ENV"
        deactivate
    fi

    # Run a git clean to clean up the project tree before packaging, including removing
    # the old virtual environment if necessary. Note this is a single -f, unlike the
    # sibling invoice tool's -ff: a single -f makes git skip nested repositories, which
    # leaves the automated-inventory-testing submodule checkout intact. Nothing here is
    # packaged from that submodule, so there is no reason to delete and re-init it.
    git clean -fdx
fi

# Create a fresh virtual environment to ensure the minimal set of dependencies are
# packaged with the application release
echo "Creating a fresh virtual environment for packaging..."
python -m venv "$ROOT_DIR/venv"

# Determine the OS type, only Linux and Windows are supported
# Activating the venv requires different paths on Windows/Linux
# Exit on unknown OS
OS_TYPE="$(uname -s 2>/dev/null || echo unknown)"
if [[ "$OS_TYPE" == "Linux" ]]; then
    source "$ROOT_DIR/venv/bin/activate"
elif [[ "$OS_TYPE" == "MINGW"* || "$OS_TYPE" == "CYGWIN"* || "$OS_TYPE" == "MSYS"* ]]; then
    source "$ROOT_DIR/venv/Scripts/activate"
else
    echo "Unknown/Unsupported OS: ${OS_TYPE:-}... Exiting"
    exit 1
fi
echo "Activated virtual environment: $VIRTUAL_ENV"

# Make sure that all project dependencies are installed in the virtual environment
echo "Installing project dependencies into virtual environment..."
pip install -r "$ROOT_DIR/requirements/release.txt"

# Install PyInstaller
echo "Installing PyInstaller into virtual environment..."
pip install PyInstaller

# Use PyInstaller to package the application into an executable
echo "Packaging the application into a release executable..."
python -OO -m PyInstaller --onefile --noconsole --name AutoInventoryProc main.py

# Set up the desired release project structure. The input folders are created empty with
# mkdir and are never copied from the repo root: a CI release run has already staged real
# customer PDFs into the repo's InventoryAvailability/ and TurnoverReports/ to run the
# integration test, and copying those in would publish private data in the release.
RELEASE_DIR="$ROOT_DIR/release/FishbowlInventoryTool"
INVENTORY_DIR="$RELEASE_DIR/InventoryAvailability"
TURNOVER_DIR="$RELEASE_DIR/TurnoverReports"

mkdir -p "$RELEASE_DIR"
mkdir -p "$INVENTORY_DIR"
mkdir -p "$TURNOVER_DIR"

# Determine the extension of the binary depending on OS
if [[ "$OS_TYPE" == "Linux" ]]; then
    BINARY_EXT=""
else
    BINARY_EXT=".exe"
fi

# Move the necessary existing files over to the release directory, including
# the executable created by PyInstaller, the user guide, and the patch notes the
# app shows on the first launch after an update
mv "$ROOT_DIR/dist/AutoInventoryProc$BINARY_EXT" "$RELEASE_DIR/"
cp "$ROOT_DIR/USER_GUIDE.txt" "$RELEASE_DIR/"
cp "$ROOT_DIR/PATCH_NOTES.md" "$RELEASE_DIR/"

# Zip up the release folder for distribution. Use Python's shutil.make_archive (the
# build venv is active here, so python is guaranteed available) to produce a real,
# DEFLATE-compressed .zip that standard tools can open. This is portable across the
# Windows/Linux cases above and avoids tar, which only produces gzip tarballs. It also
# preserves the empty InventoryAvailability/ and TurnoverReports/ folders, which the
# customer needs somewhere to drop their reports. The base_dir "FishbowlInventoryTool"
# makes the archive store that relative folder rather than absolute paths.
echo "Creating zip archive of the release..."
cd "$ROOT_DIR/release"
python -c "import shutil; shutil.make_archive('FishbowlInventoryTool', 'zip', '.', 'FishbowlInventoryTool')"

# Additionally build a double-click Windows installer (FishbowlInventoryTool_Setup.exe) from the
# populated release/FishbowlInventoryTool payload using Inno Setup (scripts/installer.iss). Inno's
# ISCC.exe is Windows-only, so this is skipped on Linux and on Windows machines without Inno
# installed -- the .zip above is the guaranteed artifact. CI installs Inno so the installer is
# always produced there.
if [[ "$OS_TYPE" == "MINGW"* || "$OS_TYPE" == "CYGWIN"* || "$OS_TYPE" == "MSYS"* ]]; then
    # Locate the Inno Setup compiler: explicit $ISCC override, then the default install
    # location, then anything named iscc on PATH.
    ISCC_EXE="${ISCC:-}"
    if [[ -z "$ISCC_EXE" && -x "/c/Program Files (x86)/Inno Setup 6/ISCC.exe" ]]; then
        ISCC_EXE="/c/Program Files (x86)/Inno Setup 6/ISCC.exe"
    fi
    if [[ -z "$ISCC_EXE" ]] && command -v iscc >/dev/null 2>&1; then
        ISCC_EXE="$(command -v iscc)"
    fi

    if [[ -z "$ISCC_EXE" ]]; then
        echo "Inno Setup (ISCC.exe) not found; skipping installer build. The release zip is still available."
        echo "Install Inno Setup 6 or set the ISCC environment variable to build FishbowlInventoryTool_Setup.exe."
    else
        # Pass the in-app version (the single source of truth in source/constants.py) to the
        # installer. Use //D (double slash) so Git Bash/MSYS does not path-mangle the
        # /DAppVersion argument into a filesystem path.
        VERSION="$(cd "$ROOT_DIR" && python -c 'from source import constants; print(constants.VERSION)')"
        echo "Building installer with Inno Setup ($ISCC_EXE) for version $VERSION..."
        "$ISCC_EXE" //DAppVersion="$VERSION" "$ROOT_DIR/scripts/installer.iss"
        echo "Created installer: $ROOT_DIR/release/FishbowlInventoryTool_Setup.exe"
    fi
else
    echo "Non-Windows OS ($OS_TYPE); skipping Inno Setup installer build (ISCC.exe is Windows-only)."
fi

# Exit virtual environment on script exit
echo "Deactivating virtual environment: $VIRTUAL_ENV"
deactivate
