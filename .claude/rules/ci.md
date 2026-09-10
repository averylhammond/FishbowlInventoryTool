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

- **The coverage gate is a workflow flag, not config.** `code-coverage.yml` runs
  `pytest --cov=./ --cov-report=xml --cov-fail-under=90 tests/`, so a local `pytest --cov` does
  **not** enforce it. (The sibling moved its gate into `pyproject.toml`'s `fail_under`; this repo
  has no `pyproject.toml` — #64.) `.coveragerc` only scopes *what* is measured; see
  `rules/tests.md`. The Codecov upload step is `if: always()` so the report still lands when the
  gate fails — exactly when the PR comment is most useful. `CODECOV_TOKEN` is the upload token,
  and the extra `push: branches: [main]` trigger exists so Codecov records a main-branch baseline
  for PR diffs; without it the badge never updates.
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
- **The integration check is a `diff`**, not an assertion suite: it runs
  `python main.py --integration-test` and compares `logs/results.txt` against the submodule's
  `canonical_correct_results.txt`. The diff is inlined in the workflow; the submodule's
  `run_automated_tests.sh` is a local convenience script that CI never invokes. When the parser
  changes output intentionally, regenerate `canonical_correct_results.txt` in the
  `automated-inventory-testing` repo and bump the submodule pointer.
- **The integration job runs on Linux while the app ships as a Windows executable.** That is only
  safe because the results file is platform-independent by construction (see
  `rules/inventory-processing.md`). `release.yml` re-runs the same integration test on
  `windows-latest`, so a Windows-specific regression is caught at release time — but not on every
  PR. If one ever slips through to a release, add a `windows-latest` leg to a `strategy.matrix`
  here.
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
