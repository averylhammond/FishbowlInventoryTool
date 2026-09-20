---
paths:
  - "source/gui/**"
---

# GUI conventions

`source/gui/` holds **exactly one class**: this app's own `InventoryAppDisplay`. Every themed
subwindow, the tooltip and the styling data it uses come from `fishbowl_common.gui`, so this is
the only module in the repo that imports tkinter directly. **Do not re-add a local copy of a
shared window** — fix or extend it in `fishbowl-common` and bump the pin in
`requirements/release.txt`.

## What comes from `fishbowl_common.gui`

| Name | Role |
| --- | --- |
| `ThemedSubwindow` | `tk.Toplevel` base that snapshots the active theme/font and centers over its parent |
| `MessageWindow` | The themed OK-button popup `show_popup()` builds |
| `AboutWindow` | Help -> About; takes `APP_NAME` and `VERSION` by injection |
| `FileEditorWindow` | The read-only file viewer; its `editable` flag toggles a Save button |
| `PatchNotesWindow` | What's New; takes the notes as a string |
| `UpdateWindow` | Announces a newer release; "Exit and Update" / "Update and Restart" |
| `Tooltip` | Hover text on the buttons and every column checkbutton |
| Theme/font data | `Theme`, `RED`, `DARK`, `ALL_THEMES`, `THEME_BY_NAME`, `FONT_FAMILIES`, `FONT_SIZES`, `DEFAULT_FONT_FAMILY`, `DEFAULT_FONT_SIZE` |

All of it is re-exported from that one name, so `InventoryAppDisplay` imports from
`fishbowl_common.gui` rather than the individual modules. It is a **separate import** from the
top-level `fishbowl_common`, which stays tkinter-free so a headless run never loads tkinter —
that split is what the `[gui]` extra in the pin marks. Their unit tests live upstream in
`fishbowl-common/tests/gui/` and deliberately have **no counterpart here**; this repo tests only
its own display and the wiring around the shared classes.

Details worth knowing before touching them:

- `FileEditorWindow` is only ever opened here with `editable=False` — there are no editable
  config files in this app.
- `PatchNotesWindow` takes the notes as a **string**, not a path: they are frequently several
  releases' sections concatenated, which is why it is not a `FileEditorWindow(editable=False)`.
  The display's whole share of it is passing the current theme/font, exactly as `handle_about()`
  does.
- `UpdateWindow`'s "Exit and Update" button `webbrowser.open()`s the release page, then closes
  the **whole application** after `CLOSE_DELAY_MS` (3s) via the injected `close_app_callback` —
  the display's `handle_exit`. The app must exit because Windows file-locks the running
  executable, so an installer that finds it open hangs trying to close it. When
  `start_install_callback` is supplied it additionally offers "Update and Restart" with a
  progress bar, driving the download itself and exiting through the same callback once the
  installer has started.
- `Tooltip` binds `<Enter>`/`<Leave>`/`<ButtonPress>` on its target widget and shows a borderless
  `Toplevel` after `SHOW_DELAY_MS` (500ms), so a pointer merely crossing a widget never flashes a
  tip. **Those bindings use `add="+"`; keep it that way.** The reason is that an instance-level
  `bind()` without it replaces the widget's other *instance* bindings — it does **not** touch a
  Checkbutton's `command`, which is a widget option dispatched through the class bindtag and
  cannot be clobbered by `bind()` at all. (The column checkbuttons do carry their own `command`,
  and it is safe either way; do not go looking for that failure mode.)
- Unlike the sibling's display, this one puts **no `integration_test_mode` guard** on
  `show_update_available()` — it holds no argument provider and is never constructed headless,
  the same reason `show_popup()` has no guard either.

## `InventoryAppDisplay`

A `tk.Tk` subclass that takes every dependency as a constructor argument and never imports the
controller. The five callbacks are `process_callback`, `read_file_callback`,
`check_for_updates_callback`, `view_patch_notes_callback` and `save_settings_callback`, followed
by the required `title` and `window_resolution` and the defaulted
`theme`/`font_family`/`font_size`/`settings`.

It owns the file picker, the two checkbox grids, the Process/Exit buttons, the `ScrolledText`
output box and the menu bar, and exposes `show_popup()`, `show_update_available()`,
`show_patch_notes()`, `write_output()`, `clear_output()` and `get_selected_columns()`.
`write_output()` calls `update_idletasks()` because processing runs on the GUI thread — without
it a status line would not paint until the work it announces had already finished.

**Settings restore happens in `__init__`, before `build_widgets()`**, so every widget is created
already themed rather than restyled afterwards, and no `save_settings_callback` fires during
startup. The `theme`/`font_family`/`font_size`/`window_resolution` arguments are the *fallbacks*
the restore resolves against, which is why they stay even though the controller passes
`settings`: the defaults live in one place and a missing or corrupt setting falls back to an
injected value rather than a hardcoded one. Four helpers do the resolving — `THEME_BY_NAME.get()`
inline for the theme, `_parse_font_size()` (`int()`, falling back on `TypeError`/`ValueError`),
`_parse_geometry()` (accepts a value only if it matches `GEOMETRY_PATTERN`, since a corrupt
string handed to `geometry()` would raise), and `_restore_column()` (one checkbox state per
column — see `rules/spreadsheet.md` for what an absent value means).

### The menu bar

Built inline in `build_widgets()`, with no separate `MenuBar` class (matching the sibling):

- **File** — Open / Clear / Exit. Exit calls `self.handle_exit`, not `self.quit`, to match the
  Exit button's own convention.
- **View** — Results Log opens `RESULTS_FILE` in a read-only `FileEditorWindow` via
  `_open_readonly_file_viewer()`, or a "File Not Found" popup if it does not exist yet.
  Inventories / Turnover Reports / Spreadsheets open a browse-only
  `filedialog.askopenfilename` rooted at `INVENTORY_DIR` / `TURNOVER_DIR` / `OUTPUT_DIR` and
  filtered to that folder's file type, reusing the same dialog mechanism as the top-level Browse
  button rather than shelling out to the OS's file explorer.
- **Preferences** — Theme / Font / Font Size submenus built by looping
  `ALL_THEMES` / `FONT_FAMILIES` / `FONT_SIZES`, each `command` a
  `lambda x=option: self.apply_x(x)` to avoid a late-binding closure bug.
- **Help** — About opens `AboutWindow` with `APP_NAME` and `VERSION` from `constants.py`; Check
  for Updates just calls `check_for_updates_callback`; What's New just calls
  `view_patch_notes_callback`. The display never touches the network and reads no file: the
  controller reports back through `show_update_available()` / `show_popup()` /
  `show_patch_notes()`.

### Reconfiguration, toggling and exit

- **`apply_theme()` / `apply_font_family()` / `apply_font_size()` / `_apply_font()`** apply a
  Preferences choice live by explicitly reconfiguring every widget the display owns, including
  every checkbutton in `column_checkbuttons` (the sibling has no checkbox grid, so this loop has
  no sibling analog). The first three persist the choice as their last statement; `_apply_font()`
  deliberately does not, since it runs for both font settings and would write two keys per
  change. Exactly two of them call **`_refresh_tooltips()`** so hover tooltips follow the new
  styling: `apply_theme()` and `_apply_font()`. `apply_font_family()` and `apply_font_size()`
  both route through `_apply_font()`, so a call there as well would restyle every tooltip twice
  per change.
- **`handle_column_toggled(key)`** persists one column's checkbox state, wired as each
  checkbutton's `command` with the key captured as a default argument (the same late-binding
  guard the Preferences lambdas use). Tk runs `command` after updating the variable, so it reads
  the new state.
- **`handle_exit()`** is the single way out of the application: it persists `winfo_geometry()`
  and then calls `destroy()`. The Exit button, File -> Exit, the window's close box (bound via
  `protocol("WM_DELETE_WINDOW", …)` in `build_widgets()`) and `UpdateWindow`'s
  `close_app_callback` all route through it, so the geometry is saved whichever way the user
  leaves. Geometry is saved on exit rather than on `<Configure>` so a window drag does not write
  to the database on every frame.
- Tooltips are attached through **`_attach_tooltip(widget, text)`**, which tracks each one in
  `self.tooltips` — initialized in `__init__` **before** `build_widgets()`, since the grid
  builder attaches as it goes. Two groups get them: the three action buttons, attached at the end
  of `build_widgets()` as the sibling does, and **every column checkbutton**, attached in
  `_build_checkbox_grid()` from that column's own `Column.tooltip`. The checkbox group has no
  sibling analog and is why the feature is worth more here than there — the labels are Fishbowl
  report jargon (`Not Available`, `Avg TO Days`, `TO Rate`). A column marked `always` has no
  checkbutton, so its tooltip text is never shown; it carries one anyway so the
  every-column-has-hover-text invariant survives an `always` flag being dropped later.

## Styling recipes

Ported from the sibling: pure `tk`, zero `ttk`; no banner comment above a method (both repos
have now dropped the `###`-bordered banners they once carried); a `# fmt:off` block of aligned `self.widget: tk.X` declarations in `__init__`, with
`build_widgets()` called last; `pack` for the vertical page flow and `grid` inside frames.

Buttons use one recipe — `bg=theme.button_bg, fg=theme.button_fg,
activebackground=theme.accent, activeforeground=theme.fg_text, relief="flat",
font=(family, size, "bold")` — with the Exit button set apart by `bg=theme.bg_entry,
activebackground=RED`.

**Checkbuttons need `selectcolor=theme.bg_entry` and `highlightthickness=0`.** This is the one
styling recipe with no sibling precedent. Without them Tk paints the check box interior white and
draws a light focus ring, both of which read as rendering artifacts against a dark `bg_main`.
Their font is deliberately not bold: fifteen bold labels crowd the two grids.

**The widget declarations are annotations, not assignments, and the widgets are not optional.**
`build_widgets()` is the last statement of `__init__` and creates every widget in the `# fmt:off`
block, so nothing can observe one unset and no method needs to guard against `None`. A new widget
goes in that block *and* in `build_widgets()`.

**`# fmt:off` stops the formatter, not the linter.** `ruff format` honors it, including this
repo's no-space spelling, so the aligned declaration block survives untouched — but `ruff check`
still reads every line inside one. No aligned line here exceeds the 120-column limit today, so
none carries a directive; one added later that does would need an explicit `# noqa: E501`.

**`build_widgets()` carries `# noqa: PLR0915`.** It is a flat run of `tk.Widget(...)` calls, one
statement per widget, in the order they appear in the window, and it is over the 50-statement
default only because the window holds that many widgets. Splitting it on a statement count would
scatter the layout without simplifying anything. The reason sits at the site rather than in
`pyproject.toml` because `RUF100` polices an inline directive that stops applying; nothing
reports an unused entry in the config's ignore list.

**A window opened from a startup path goes through `display.after(0, …)`, never inline.**
`ThemedSubwindow._center_over_parent()` reads the parent's geometry, which is `1x1+0+0` until the
root window has been mapped, so an inline call lands the window in the corner of the screen
instead of over the app. The patch-notes window is the live example (see `rules/shared-package.md`).
