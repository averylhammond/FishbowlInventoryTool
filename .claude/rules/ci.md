---
paths:
  - ".github/workflows/**"
  - "requirements/**"
---

# CI workflows

Four workflows live in `.github/workflows/`. There is **no lint job** — ruff is not configured in
this repo yet (#65), so nothing here checks formatting or style.

| Workflow | Trigger | Runner | Does |
| --- | --- | --- | --- |
| `unit-tests.yml` | PRs to `main`, manual | `ubuntu-latest` | `pytest tests/` |
| `code-coverage.yml` | PRs to `main`, pushes to `main`, manual | `ubuntu-latest` | `pytest --cov` with the 90% gate, uploads to Codecov |
| `integration-tests.yml` | PRs to `main`, manual | `ubuntu-latest` | Runs the app headless and diffs the output |
| `release.yml` | pushes of a `v*` tag | `windows-latest` | Verifies, tests, packages and publishes the release |

**The `python-version` values are not consistent.** `unit-tests.yml`, `integration-tests.yml` and
`release.yml` pin `"3.11.9"` on `actions/setup-python@v4`; `code-coverage.yml` floats on `"3.11"`
on `@v5` with `cache: 'pip'`. The action-version and cache split is a deliberate mirror of the
sibling's file; the `3.11` vs `3.11.9` drift is not deliberate — **#66 covers it**, along with the
missing concurrency group and the `--cov=./` scope.

Notes that are easy to get wrong:

- **The coverage gate is `fail_under = 90` in `pyproject.toml`**, not a workflow flag, so a local
  `pytest --cov` enforces it too. `code-coverage.yml` runs
  `pytest --cov=./ --cov-report=xml tests/`; the same file's `[tool.coverage.run]` scopes *what*
  is measured, see `rules/tests.md`. The Codecov upload step is `if: always()` so the report
  still lands when the gate fails — exactly when the PR comment is most useful. `CODECOV_TOKEN`
  is the upload token, and the extra `push: branches: [main]` trigger exists so Codecov records a
  main-branch baseline for PR diffs; without it the badge never updates.
- **Every measured module is at 100%** (689 statements, 218 tests), so the 90% gate is headroom
  for an in-progress refactor rather than a target to climb toward, and it matches the sibling's.
  Keep it there: a new module landing untested should fail the check,
  not quietly lower the average. Nothing is omitted for being untestable — the inert styling data
  that used to be excluded now lives upstream in `fishbowl_common.gui`.
- **Only the submodule-using jobs need a secret.** `integration-tests.yml` and `release.yml` check
  out `automated-inventory-testing` with `token: ${{ secrets.CUSTOMER_DATA_PAT }}` and stage the
  PDFs with `scripts/copy_resources.sh`. That submodule holds private company data — **never echo
  its contents into a workflow log.** `unit-tests.yml` and `code-coverage.yml` check out
  **without** it and need no secret, because unit tests mock all their I/O. Keep it that way: a
  test that needs a real PDF belongs in the integration test instead.
- **The integration check is two `diff`s**, not an assertion suite. It runs
  `python main.py --integration-test`, then `python scripts/dump_workbooks.py`, and compares each
  output against a canonical copy in the submodule:

  | Generated | Canonical | Covers |
  | --- | --- | --- |
  | `logs/results.txt` | `canonical_correct_results.txt` | The parser trace, built from the entry objects |
  | `logs/spreadsheet_dump.txt` | `canonical_correct_spreadsheets.txt` | The generated `.xlsx` files, cell by cell |

  They are **separate workflow steps** so a failure names which artifact drifted. Both diffs are
  inlined in the workflow; the submodule's `run_automated_tests.sh` checks the same two files but
  is a local convenience script CI never invokes. When the output changes intentionally,
  regenerate the affected canonical file in the `automated-inventory-testing` repo and bump the
  submodule pointer — and capture it from a build you have reason to trust, since the canonical
  file records whatever the app did, bug included.
- **`scripts/dump_workbooks.py` is what makes the spreadsheet checkable**, and it is CI tooling,
  not application code: never imported by the app, no unit tests, and its `openpyxl` reader is
  pinned in `requirements/dev.txt` **only** — `XlsxWriter` is write-only, but the app never reads
  a workbook, so putting the reader in `release.txt` would bundle it into the shipped executable
  for nothing. That pin is why `integration-tests.yml` installs `dev.txt` rather than
  `release.txt`. The dump is one line per sheet row with each cell rendered as
  `<style code>:<value>` (`H` header, `E`/`O` alternating data rows, `?` for a format the dumper
  does not recognize, `-` for a cell that is both empty and unstyled), so a diff names the cell
  that moved. It writes into the gitignored `logs/` directory and prints only a line count —
  **the dump is full of customer part data and must never reach a CI log or this public repo.**
  It exits non-zero if it finds no workbooks, so a run that produced nothing fails loudly instead
  of diffing clean against a fixture.
- **Why the check is a semantic dump rather than a comparison of the `.xlsx` itself.** Byte-
  comparing the file is impossible without changing shipped behavior — xlsxwriter stamps
  `<dcterms:created>` with the current time unless the app passes `set_properties()` — and
  diffing the XML inside the zip would pin the fixture to xlsxwriter's emission rather than to
  the spreadsheet: strings are `sharedStrings.xml` indices, formats are style indices numbered in
  `add_format` call order, so hoisting a format out of a loop rewrites the whole sheet without
  changing what a user opens. The dump gives up sheet-level properties (column widths, freeze
  panes, merges); the writers set none of those today, and the `dims:` line plus the `?` code
  cover the gap until they do.
- **The integration job runs on Linux while the app ships as a Windows executable.** That is only
  safe because the results file is platform-independent by construction (see
  `rules/inventory-processing.md`); the spreadsheet dump is too, for the same reason — both are
  written through Python's text mode and hold no paths. `release.yml` re-runs both checks on
  `windows-latest`, so a Windows-specific regression is caught at release time — but not on every
  PR. If one ever slips through to a release, add a `windows-latest` leg to a `strategy.matrix`
  here.
- **The results diff quietly depends on `core.autocrlf` being on for the Windows runner.** Both
  canonical files are stored LF, the app writes CRLF on Windows, and the results check passes
  there only because git checks the fixture out as CRLF to match. The spreadsheet check does not
  rely on that — it diffs with `--strip-trailing-cr`. If the results check ever fails on
  `release.yml` with no visible difference, this is why; the fix is the same flag, not a
  regenerated fixture.
- **The GUI tests need no display and no `python3-tk`.** `actions/setup-python`'s CPython builds
  bundle `_tkinter` and its Tcl/Tk libraries, and the display tests patch `tk.Tk.__init__` and
  every widget class, so no real window is ever created.

## Release gates

`release.yml` fails the tag before building if either gate trips, both reported with `::error::`:

1. **Tag versus source version** — `${GITHUB_REF_NAME#v}` must equal `VERSION` in
   `source/constants.py`, so a release can never ship an About box that disagrees with its tag.
2. **Patch notes must document the version** — the check is
   `grep -qE "^## v?${VERSION}( |$)"` against `PATCH_NOTES.md`: the leading `v` is optional and a
   space or end-of-line must follow, so `## 2.3.0` and `## v2.3.0` both pass while `## 2.3.01`
   does not. The app shows these notes on the first launch after an update, so a release missing
   its section would ship silently and only surface when a customer updated into it.

It then runs the unit tests and the integration test against the tagged commit, installs Inno
Setup via Chocolatey, runs `scripts/package_release.sh`, writes `SHA256SUMS.txt` over the built
artifacts **from inside `release/`** so the names in it are bare and match the asset names, and
uploads `release/FishbowlInventoryTool.zip`, `release/FishbowlInventoryTool_Setup.exe` and
`release/SHA256SUMS.txt` with `gh release create --generate-notes`. The updater verifies the
installer against that checksum file **before executing it**, so a release missing that asset
offers only the manual download — graceful degradation, not a failure.

**Cutting a release is therefore:** bump `VERSION` in `source/constants.py`, add that version's
`PATCH_NOTES.md` section, merge, then push a matching `vX.Y.Z` tag.
