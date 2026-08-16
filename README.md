# FishbowlInventoryTool

[![Unit Tests](https://github.com/averylhammond/FishbowlInventoryTool/actions/workflows/unit-tests.yml/badge.svg?branch=main)](https://github.com/averylhammond/FishbowlInventoryTool/actions/workflows/unit-tests.yml)
[![Integration Tests](https://github.com/averylhammond/FishbowlInventoryTool/actions/workflows/integration-tests.yml/badge.svg?branch=main)](https://github.com/averylhammond/FishbowlInventoryTool/actions/workflows/integration-tests.yml)
[![Code Coverage](https://github.com/averylhammond/FishbowlInventoryTool/actions/workflows/code-coverage.yml/badge.svg?branch=main)](https://github.com/averylhammond/FishbowlInventoryTool/actions/workflows/code-coverage.yml)
[![codecov](https://codecov.io/gh/averylhammond/FishbowlInventoryTool/branch/main/graph/badge.svg)](https://codecov.io/gh/averylhammond/FishbowlInventoryTool)

A Python desktop app (tkinter) that parses Fishbowl-generated **Inventory Availability**
and **Turnover Report** PDFs and produces a formatted Excel (`.xlsx`) report. Pick an
inventory availability PDF and check which inventory and turnover columns to include;
the app parses that PDF plus every turnover report found in `TurnoverReports/`, matches
turnover rows to inventory rows by part, and writes a single styled worksheet named
after the date in the inventory PDF's filename.

## Setup

**1. Clone the repo** into a project folder.

**2. Initialize the test-data submodule.** Sample inventory availability and turnover
report PDFs live in
[automated-inventory-testing](https://github.com/averylhammond/automated-inventory-testing),
which is wired in as a submodule:

```bash
git submodule update --init
```

> **Note:** this submodule is private because it contains private company data. Never
> commit data sourced from it back into this repo.

The resulting folder structure:

```
project_root/
└── FishbowlInventoryTool/
    ├── scripts/copy_resources.sh
    └── automated-inventory-testing/
        └── resources/
```

**3. Stage the sample resources** so the app has PDFs to run against:

```bash
./scripts/copy_resources.sh
```

This adds:

```
FishbowlInventoryTool/
├── InventoryAvailability/
│   └── Inventory Availability 01222024.pdf
└── TurnoverReports/
    ├── Q3-2023.pdf
    ├── Q1-2024.pdf
    └── ...
```

**4. Create and activate a virtual environment** (Python 3.11):

```bash
python -m venv venv
source venv/Scripts/activate   # Windows; use venv/bin/activate on Linux/Mac
```

**5. Install dependencies:**

```bash
pip install -r requirements/dev.txt      # release.txt plus pytest and pytest-cov
pip install -r requirements/release.txt  # runtime dependencies only
```

> **Note:** on Linux, `tkinter` is not part of the standard library install and must be
> installed separately, then the virtual environment reactivated:
>
> - Debian-based: `sudo apt-get install python3-tk`
> - Fedora: `sudo dnf install python3-tkinter`
> - Arch-based: `sudo pacman -S python3-tk`

## Usage

```bash
python main.py                    # run the GUI
python main.py --integration-test # run headless, writing logs/results.txt
```

Headless mode processes every PDF in `InventoryAvailability/` with all columns included
and exits without opening a window. It is what CI uses to validate output without GUI
interaction.

See [`USER_GUIDE.txt`](USER_GUIDE.txt) for end-user instructions.

## Testing

```bash
pytest tests/*                                        # unit tests
pytest --cov=./ --cov-report=term-missing tests/*     # unit tests with a coverage table
```

The `tests/*` glob is required: test files use the `_tests.py` suffix, which pytest's
default discovery does not match.

Reproduce the integration test locally (after `./scripts/copy_resources.sh`):

```bash
python main.py --integration-test
diff logs/results.txt automated-inventory-testing/canonical_correct_results.txt
```

When the parser changes output intentionally, regenerate
`canonical_correct_results.txt` in the `automated-inventory-testing` repo and bump the
submodule pointer.

## Continuous integration

All three workflows run on pull requests to `main` and on manual dispatch; the coverage
workflow additionally runs on pushes to `main` so Codecov records a baseline for PR
diffs.

| Workflow | What it checks |
| --- | --- |
| [Unit Tests](.github/workflows/unit-tests.yml) | `pytest tests/*` on `ubuntu-latest`. |
| [Integration Tests](.github/workflows/integration-tests.yml) | Runs the app headless and fails unless `logs/results.txt` matches the submodule's `canonical_correct_results.txt`. Needs the `CUSTOMER_DATA_PAT` secret to check out the private submodule. |
| [Code Coverage](.github/workflows/code-coverage.yml) | `pytest --cov=./ --cov-report=xml --cov-fail-under=90 tests/*`, uploaded to Codecov. Needs the `CODECOV_TOKEN` secret. |

Every measured module is currently at 100%, so the 90% gate is headroom for an
in-progress refactor rather than a target to climb toward.

## Related projects

- [FishbowlInvoiceTool](https://github.com/averylhammond/FishbowlInvoiceTool) — the
  sibling desktop app, which parses Fishbowl invoice PDFs and computes cost breakdowns.
  This tool is being incrementally brought up to its architecture and engineering
  standards.
- [fishbowl-common](https://github.com/averylhammond/fishbowl-common) — the shared
  infrastructure package both apps depend on, providing `ArgumentProvider`.
