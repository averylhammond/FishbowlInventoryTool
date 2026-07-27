Integration Test Status: [![Integration Tests](https://github.com/averylhammond/FishbowlInventoryTool/actions/workflows/integration-tests.yml/badge.svg?branch=main)](https://github.com/averylhammond/FishbowlInventoryTool/actions/workflows/integration-tests.yml)

**************************************
INSTRUCTIONS TO SET UP FOR DEVELOPMENT
**************************************

1) Clone this repo into a project folder.

2) In order to test with example resources (inventory availability and turnover report PDFs, located here
   <https://github.com/averylhammond/automated-inventory-testing>), the automated-inventory-testing repo
   has been added as a submodule to this project.

   Run git submodule update --init to clone and initialize the repo
    - NOTE: This submodule is private because it contains private company data. Never commit
            data sourced from it back into this repo.
    - The resulting folder structure is shown below:
     <PRE>- project_root/
          └── FishbowlInventoryTool/
              └── scripts/copy_resources.sh
              └── automated-inventory-testing/
                  └── resources/</PRE>

3) Run ./FishbowlInventoryTool/scripts/copy_resources.sh to copy the necessary resource files. This will
   allow you to run the application using sample inventory availability and turnover report PDFs. After
   running the script, your folder structure should have the following additions:
     <PRE>-FishbowlInventoryTool/
          ├── InventoryAvailability/
          │   └── Inventory Availability 01222024.pdf
          └── TurnoverReports/
              └── Q3-2023.pdf
              └── Q1-2024.pdf
              └── etc</PRE>

4) Open a Python virtual environment
    - python -m venv venv

5) Activate virtual environment
    - Linux
        - source venv/bin/activate
    - Windows
        - source venv/Scripts/activate

6) Install dependencies
    - pip install -r requirements/release.txt

    - NOTE: If on Linux, you need to install tkinter separately since it's not
            included in the standard library. Then activate the virtual environment
            again.

        - For Debian based distros:
            - sudo apt-get install python3-tk for deb based distros
        - For Fedora users:
            - sudo dnf install python3-tkinter
        - For Arch based distros:
            - sudo pacman -S python3-tk

7) Run application
    - python main.py

8) Run the integration test locally
    - python main.py --integration-test
        - Runs headless, processing every PDF in InventoryAvailability/ with all columns
          included, and writes logs/results.txt
    - diff logs/results.txt automated-inventory-testing/canonical_correct_results.txt
        - This is the same comparison CI performs on every pull request to main. When the
          parser changes output intentionally, regenerate canonical_correct_results.txt in
          the automated-inventory-testing repo and bump the submodule pointer.
