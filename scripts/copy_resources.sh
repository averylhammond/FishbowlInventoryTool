#!/usr/bin/env bash

#######################################################################################
#                                                                                     #
# 06/23/2026 - Author - Avery Hammond                                                 #
#                                                                                     #
# This script is intended to copy resource files from the automated-inventory-testing #
# submodule into the FishbowlInventoryTool repo for use during testing. The           #
# application repo does not contain resource files that contain private company       #
# data since it is a public repository. This helper script assumes that the           #
# FishbowlInventory tool has been cloned, and the automated-inventory-testing          #
# submodule has been cloned inside of the project.                                    #
#                                                                                     #
# An example project structure is as follows, after initializing the submodule:       #
# project_root/                                                                       #
# └── FishbowlInventoryTool/                                                          #
#   └── scripts/copy_resources.sh                                                     #
#   └── automated-inventory-testing/                                                  #
#       └── resources/                                                               #
#                                                                                     #
# Note: This script will not work if the automated-inventory-testing submodule has    #
# not been initialized and cloned with a git submodule update --init                  #
#                                                                                     #
# Usage: ./copy_resources.sh                                                          #
#######################################################################################

# Fail safely on errors and undefined variables, and ensure pipelines fully succeed
set -euo pipefail

# Get the location of this script, and use it to derive the project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Project root directory: $ROOT_DIR"

# Use the derived project directory to set source and destination paths
SRC="$ROOT_DIR/automated-inventory-testing/resources"
DST="$ROOT_DIR"

# Ensure that the source and destination directories exist
if [[ ! -d "$SRC" ]]; then
  echo "Source directory does not exist: $SRC"
  exit 1
fi
if [[ ! -d "$DST" ]]; then
  echo "Destination directory does not exist: $DST"
  exit 1
fi

# Copy the resources over to the application folder
echo "Copying resources from submodule..."
cp -a "$SRC"/. "$DST"/
echo "Done."
