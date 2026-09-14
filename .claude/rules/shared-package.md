---
paths:
  - "source/InventoryAppController.py"
  - "source/constants.py"
  - "requirements/**"
---

# The shared package, updates and patch notes

`fishbowl-common` is a **pinned git dependency** in `requirements/release.txt`
(`fishbowl-common[gui] @ git+…@vX.Y.Z`), never a path or a submodule, so a change there is
invisible here until the pin moves. Its classes are application-agnostic and take **every**
app-specific value by constructor injection — that is the contract to preserve when touching this
wiring. Definitions and their tests live in that repo; do not duplicate either here.

| Imported from | Name | Injected from here |
| --- | --- | --- |
| `fishbowl_common` | `ArgumentProvider` | — (parses `--integration-test`) |
| `fishbowl_common` | `SettingsRepository` | `SETTINGS_DB_PATH` as `db_path` |
| `fishbowl_common` | `UpdateCoordinator` | `VERSION`, `GITHUB_REPO`, `display`, `INSTALLER_ASSET_PATTERN` as `asset_pattern` |
| `fishbowl_common` | `PatchNotes` | `PATCH_NOTES_PATH` as `notes_path` |
| `fishbowl_common` | `compare_versions()` | — (helper) |

`UpdateChecker` is **not** imported here at all — the coordinator constructs it. The pin requests
the **`[gui]` extra**, which adds the package's GUI half (the themed subwindows, the tooltip and
the theme/font data this app shares with the sibling — see `rules/gui.md`). The extra installs no
additional requirements; its only dependency is tkinter, which ships with CPython. It marks
intent: the top-level `fishbowl_common` stays importable with no tkinter present, which is what
keeps a headless run tkinter-free.

`requirements/dev.txt` is `-r release.txt` plus `pytest` and `pytest-cov`. There is **no ruff pin
here yet** (#65), unlike the sibling; `pyproject.toml` already exists to hold its config.

## Construction and gating in `InventoryAppController`

`__init__` builds only what a headless run needs: the `InventoryAppFileIO` collaborator, the
`InventoryProcessor` handed **that same** file I/O instance (not a fresh one — the headless path
reassigns `file_io.report_error`, which only reaches the object doing the reads if the two share
one instance), and the `ArgumentProvider`. It then clears the results file
(`reset_results_file()`) so each run starts with a fresh diagnostics log, and sets four
attributes to `None`: `display`, `settings_repository`, `update_coordinator` and `patch_notes`.

**All four are built inside `start_application()`'s non-integration-test branch, after the early
return.** That placement is the one deliberate divergence from the sibling, which builds its
collaborators in `__init__` — **do not "fix" it to match.** A headless CI run must perform no
database I/O, leave no `data/` directory behind and make no network call, and building these here
gets that structurally rather than by a flag check.
`tests/test_InventoryAppController.py` guards it: `mock_display_cls`, `mock_settings_cls`,
`mock_coordinator_cls` and `mock_patch_notes_cls` all `assert_not_called()` in integration-test
mode.

`start_application()` therefore reads: check `argument_provider.integration_test_mode` and call
`run_integration_test()` if set; otherwise construct `SettingsRepository` at `SETTINGS_DB_PATH`
and read `get_all_settings()`, import and construct `InventoryAppDisplay` (passing
`process_callback`, `read_file_callback=self.file_io.read_text_file`,
`check_for_updates_callback=self.handle_check_for_updates`,
`view_patch_notes_callback=self.handle_view_patch_notes`,
`save_settings_callback=self.handle_save_setting`, `title`, `window_resolution` and the settings
just read), wire both the file I/O controller's and the settings repository's `report_error` to
the display's `show_popup`, `start()` the background update check, construct `PatchNotes` and run
`show_patch_notes_if_updated(saved_settings)`, then enter `mainloop()`.

Because `SettingsRepository.__init__` runs `initialize_database()` before any display exists, an
error from that first call falls to the repository's no-op default reporter; only later reads and
writes reach `show_popup`. `handle_save_setting(key, value)` forwards to
`settings_repository.save_setting()` and is the display's only route to the database — the
display never imports the repository.

## The controller's own two callbacks

- `handle_process_inventory(inventory_pdf_path, checkbox_dict)` — the callback handed to the
  display. It runs `self.processor.process_inventory()` with status routed to the display's output
  box, keeping the display's callback contract to two arguments.
- `run_integration_test()` — the headless entry point. Routes `report_error` to stdout, takes an
  all-columns-checked `checkbox_dict` from `columns.all_columns_selected()`, and calls
  `self.processor.process_inventory()` for every PDF from
  `InventoryAppFileIO.list_inventory_files()`. Lets a CI workflow generate `logs/results.txt` with
  no GUI interaction.

New logic goes in the class that owns that concern, not bolted onto the controller: it owns
wiring, not parsing, spreadsheet or display behavior.

## The update check

`UpdateCoordinator` owns the **whole** feature: the `daemon=True` worker thread, the
`UpdateChecker` call, the `display.after(0, …)` hop back onto the GUI thread, the download, digest
verification, the silent detached launch of the installer, and the choice between opening
`UpdateWindow` and popping "No Updates Available" / "Update Check Failed" (the latter two only on
a manual check, so a startup check never interrupts a launch just because the user is offline).
It takes its display as a `typing.Protocol`, which is what lets it live in the headless half of
`fishbowl_common`; the display satisfies it through `after()`, `show_update_available()` and
`show_popup()`. **Only the wiring is tested here** — the threading and result handling are
covered upstream.

The controller's whole share is two things: constructing it in `start_application()` and
`handle_check_for_updates()`, the Help-menu callback that calls
`update_coordinator.start(manual=True)`. `INSTALLER_ASSET_PATTERN` is its only other
contribution: it names this app's installer among a release's assets, which the shared package
cannot know since each Fishbowl app names its own. Given that asset and a published
`SHA256SUMS.txt`, the coordinator downloads, verifies and launches the installer and reports back
— `show_update_available()` receives that flow as a second `start_install` argument and forwards
it to `UpdateWindow` as `start_install_callback`. **The display's whole share of the feature is
forwarding that callback**; it never downloads or executes anything. When the argument is `None`
— no matching installer asset, no checksums asset, or a non-Windows platform — the window falls
back to the browser-only "Exit and Update" it has always offered, which is also where a failed
download lands. Both routes exit through the same `close_app_callback`.

## The patch notes

`PatchNotes` reads `PATCH_NOTES_PATH`, the `## X.Y.Z` changelog packaged next to the executable,
and returns the sections between two versions. The controller owns both halves the shared package
cannot:

- `show_patch_notes_if_updated(saved_settings)` compares `SETTING_KEY_LAST_SEEN_VERSION` against
  `VERSION` with `compare_versions()` and shows what changed only when the stored version is
  **older**. A fresh install (nothing stored), an ordinary relaunch and a downgrade all show
  nothing, and every one of the four cases stamps `VERSION` — so an update's notes appear once
  rather than on every launch after it. The first launch after upgrading *into* this feature shows
  nothing either, since a build that never wrote the key is indistinguishable from a fresh
  install.
- **The window is opened through `display.after(0, …)`, not inline**, and it must stay that way:
  `ThemedSubwindow._center_over_parent()` reads the parent's geometry, which is `1x1+0+0` until
  the root window has been mapped, so an inline call would put the window in the corner of the
  screen instead of over the app.
- `handle_view_patch_notes()` is the display's Help-menu callback, showing every section up to
  `VERSION` (`notes_since(VERSION, None)`) — a user who dismissed the window after an update has
  no other way back to the notes, and without the menu item the feature is unreachable in a
  manual test without hand-editing the settings database. Unlike the silent startup check it
  reports when there is nothing to show, the same manual-versus-automatic split the update check
  makes.

## `constants.py`

One module, every app-specific value the rest of the app and the shared classes read:

- `VERSION` — surfaced via Help -> About and compared against the latest release by the update
  check. The release workflow refuses a tag that disagrees with it.
- `GITHUB_REPO` — the `"owner/name"` string naming the repo whose releases that check reads.
- `INSTALLER_ASSET_PATTERN` — this app's installer asset on a release; keep it in step with
  `installer.iss`'s `OutputBaseFilename`.
- Relative `Path` constants, all resolved against the executable's CWD: the input directories
  (`INVENTORY_DIR`, `TURNOVER_DIR`), the generated spreadsheets (`OUTPUT_DIR`, the application
  root — shared by `create_workbook()` and the display's View -> Spreadsheets browser so the two
  cannot point at different folders), the diagnostics log (`LOGS_DIR`, `RESULTS_FILE`), the
  settings database (`DATA_DIR`, `SETTINGS_DB_PATH`) and the packaged patch notes
  (`PATCH_NOTES_PATH`).
- The keys user settings are persisted under — `SETTING_KEY_THEME`, `SETTING_KEY_FONT_FAMILY`,
  `SETTING_KEY_FONT_SIZE`, `SETTING_KEY_GEOMETRY`, `SETTING_KEY_LAST_SEEN_VERSION` and the
  `SETTING_KEY_COLUMN_PREFIX` each column's key is appended to — shared between the display that
  reads and writes them and any other consumer so the two never drift apart.

A change to a **public signature** in `fishbowl-common` is three PRs, in order: the package, then
this repo's pin, then `FishbowlInvoiceTool`.
