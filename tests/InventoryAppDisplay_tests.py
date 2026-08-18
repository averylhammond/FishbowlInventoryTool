import tkinter as tk
import pytest
from types import SimpleNamespace
from unittest.mock import DEFAULT, patch, MagicMock

from source.columns import ALL_COLUMNS, COLUMN_KEYS
from source.constants import (
    INVENTORY_DIR,
    OUTPUT_DIR,
    RESULTS_FILE,
    TURNOVER_DIR,
    VERSION,
)
from source.gui.InventoryAppDisplay import InventoryAppDisplay
from source.gui.color_theme import ALL_THEMES, DARK, FOREST, LIGHT
from source.gui.font_settings import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    FONT_FAMILIES,
    FONT_SIZES,
)


###############################################################################
###                  InventoryAppDisplay -> Test Helpers                    ###
###############################################################################
def _distinct_widget(*_args, **_kwargs):
    """
    Side effect for patched tkinter widget classes that returns a fresh
    MagicMock for every constructed widget, so each widget attribute on the
    display (e.g. title_label vs. output_box) is a distinct mock that can be
    asserted on independently.
    """

    return MagicMock()


class _FakeStringVar:
    """
    Stand-in for tk.StringVar that holds a real string. A tkinter variable cannot
    be constructed without a default root window, and the real Tk root is never
    created here, so the constructor would raise "Too early to create variable".
    A plain MagicMock would not do: the display reads this value back to decide
    whether a file was selected, so the stored value has to be real.
    """

    def __init__(self, value: str = "", **_kwargs):
        self._value = value

    def get(self) -> str:
        return self._value

    def set(self, value: str):
        self._value = value


class _FakeBooleanVar:
    """
    Stand-in for tk.BooleanVar that holds a real bool, for the same reason as
    _FakeStringVar. get_selected_columns() is asserted to return real booleans,
    which a MagicMock's return value could never be.
    """

    def __init__(self, value: bool = False, **_kwargs):
        self._value = value

    def get(self) -> bool:
        return self._value

    def set(self, value: bool):
        self._value = value


def tooltip_texts_by_widget(display):
    """
    Maps each widget a tooltip was attached to onto the hover text it was given,
    so an attachment can be asserted against the widget it belongs to

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out

    Returns:
        dict: A mapping of widget to the tooltip text attached to it
    """

    return {
        made_call.kwargs["widget"]: made_call.kwargs["text"]
        for made_call in display.tooltip_cls.call_args_list
    }


def button_call(display, text: str):
    """
    Finds the tk.Button construction call that created the button with the given
    label, so its wiring and styling can be asserted

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
        text (str): The label of the button to look up

    Returns:
        unittest.mock.call: The call that constructed that button
    """

    return next(
        made_call
        for made_call in display.button_cls.call_args_list
        if made_call.kwargs.get("text") == text
    )


###############################################################################
###                  InventoryAppDisplay -> Test Fixture                    ###
###############################################################################
@pytest.fixture
def display(request):
    """
    Builds an InventoryAppDisplay in complete isolation from tkinter: the real
    Tk.__init__ is neutralized, the inherited Tk methods the display calls
    (title/geometry/resizable/configure/protocol/destroy/winfo_geometry) are
    mocked, the tkinter variables are replaced with stubs holding real values, and
    every widget class is replaced so no real window or widgets are created. The
    patches stay active for the duration of each test, since the display's methods
    keep calling into the mocked widgets after construction.

    Constructor arguments can be customized per test by parametrizing the fixture
    indirectly (e.g. @pytest.mark.parametrize("display", [{"theme": FOREST}],
    indirect=True)); when not parametrized, the display is built with the same
    arguments the controller supplies. Persisted settings are supplied the same
    way, as a {"settings": {...}} override.

    Returns:
        types.SimpleNamespace: Holds the constructed display (`display`), the
            mocked Tk methods (`title`, `geometry`, `resizable`, `configure`,
            `config`, `protocol`, `destroy`), the patched widget classes whose calls
            are asserted (`button_cls`, `checkbutton_cls`, `message_window_cls`,
            `about_window_cls`, `file_editor_window_cls`, `update_window_cls`,
            `tooltip_cls`), and the callbacks passed at construction (`process_callback`,
            `read_file_callback`, `check_for_updates_callback`,
            `save_settings_callback`)
    """

    # Constructor overrides supplied indirectly by a test, or none when not
    # parametrized
    overrides = getattr(request, "param", None) or {}

    with (
        patch.object(tk.Tk, "__init__", return_value=None),
        # Patched together rather than one context manager each: Python allows only
        # twenty statically nested blocks, and this with statement is at the limit
        patch.multiple(
            InventoryAppDisplay,
            title=DEFAULT,
            geometry=DEFAULT,
            resizable=DEFAULT,
            configure=DEFAULT,
            config=DEFAULT,
            protocol=DEFAULT,
            destroy=DEFAULT,
            winfo_geometry=DEFAULT,
        ) as tk_methods,
        patch(
            "source.gui.InventoryAppDisplay.tk.StringVar", side_effect=_FakeStringVar
        ),
        patch(
            "source.gui.InventoryAppDisplay.tk.BooleanVar", side_effect=_FakeBooleanVar
        ),
        patch("source.gui.InventoryAppDisplay.tk.Menu", side_effect=_distinct_widget),
        patch("source.gui.InventoryAppDisplay.tk.Label", side_effect=_distinct_widget),
        patch("source.gui.InventoryAppDisplay.tk.Frame", side_effect=_distinct_widget),
        patch("source.gui.InventoryAppDisplay.tk.Entry", side_effect=_distinct_widget),
        patch(
            "source.gui.InventoryAppDisplay.tk.Button", side_effect=_distinct_widget
        ) as mock_button_cls,
        patch(
            "source.gui.InventoryAppDisplay.tk.Checkbutton",
            side_effect=_distinct_widget,
        ) as mock_checkbutton_cls,
        patch(
            "source.gui.InventoryAppDisplay.scrolledtext.ScrolledText",
            side_effect=_distinct_widget,
        ),
        patch("source.gui.InventoryAppDisplay.MessageWindow") as mock_message_window_cls,
        patch("source.gui.InventoryAppDisplay.AboutWindow") as mock_about_window_cls,
        patch(
            "source.gui.InventoryAppDisplay.FileEditorWindow"
        ) as mock_file_editor_window_cls,
        patch("source.gui.InventoryAppDisplay.UpdateWindow") as mock_update_window_cls,
        patch(
            "source.gui.InventoryAppDisplay.Tooltip", side_effect=_distinct_widget
        ) as mock_tooltip_cls,
    ):

        # The geometry handle_exit() persists, in the format Tk reports it in
        tk_methods["winfo_geometry"].return_value = "780x820+320+180"

        # The callbacks the controller would normally supply; mocks are sufficient
        process_callback = MagicMock()
        read_file_callback = MagicMock()
        check_for_updates_callback = MagicMock()
        save_settings_callback = MagicMock()

        arguments = {
            "process_callback": process_callback,
            "read_file_callback": read_file_callback,
            "check_for_updates_callback": check_for_updates_callback,
            "save_settings_callback": save_settings_callback,
            "title": "Automated Inventory Processor",
            "window_resolution": "700x700",
        }
        arguments.update(overrides)

        built_display = InventoryAppDisplay(**arguments)

        yield SimpleNamespace(
            display=built_display,
            title=tk_methods["title"],
            geometry=tk_methods["geometry"],
            resizable=tk_methods["resizable"],
            configure=tk_methods["configure"],
            config=tk_methods["config"],
            protocol=tk_methods["protocol"],
            destroy=tk_methods["destroy"],
            button_cls=mock_button_cls,
            checkbutton_cls=mock_checkbutton_cls,
            message_window_cls=mock_message_window_cls,
            about_window_cls=mock_about_window_cls,
            file_editor_window_cls=mock_file_editor_window_cls,
            update_window_cls=mock_update_window_cls,
            tooltip_cls=mock_tooltip_cls,
            process_callback=process_callback,
            read_file_callback=read_file_callback,
            check_for_updates_callback=check_for_updates_callback,
            save_settings_callback=save_settings_callback,
        )


###############################################################################
###                Tests InventoryAppDisplay -> __init__()                  ###
###############################################################################
def test_init_applies_the_window_properties(display):
    """
    Tests that the title and resolution passed by the controller are applied to
    the window, and that the user is allowed to resize it

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.title.assert_called_once_with("Automated Inventory Processor")
    display.geometry.assert_called_once_with("700x700")
    display.resizable.assert_called_once_with(True, True)


def test_init_stores_the_process_callback(display):
    """
    Tests that the controller's processing callback is stored, since the process
    button is wired straight to it

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    assert display.display.process_callback is display.process_callback


def test_init_stores_the_read_file_callback(display):
    """
    Tests that the controller's file-reading callback is stored, since the
    read-only file viewer is populated straight from it

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    assert display.display.read_file_callback is display.read_file_callback


def test_init_stores_the_check_for_updates_callback(display):
    """
    Tests that the controller's update-check callback is stored, since the Help
    menu's "Check for Updates" item is wired straight to it

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    assert (
        display.display.check_for_updates_callback is display.check_for_updates_callback
    )


def test_init_defaults_to_the_dark_theme_and_default_font(display):
    """
    Tests that the display styles itself with the same defaults as the sibling
    invoice tool when the caller supplies no theme or font

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    assert display.display.current_theme is DARK
    assert display.display.current_font_family == DEFAULT_FONT_FAMILY
    assert display.display.current_font_size == DEFAULT_FONT_SIZE


@pytest.mark.parametrize(
    "display",
    [{"theme": FOREST, "font_family": "Arial", "font_size": 14}],
    indirect=True,
)
def test_init_accepts_an_injected_theme_and_font(display):
    """
    Tests that the theme and font are injectable rather than hardcoded, so the
    application's styling can be changed without editing the display

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    assert display.display.current_theme is FOREST
    assert display.display.current_font_family == "Arial"
    assert display.display.current_font_size == 14


def test_init_creates_one_checkbox_variable_per_column(display):
    """
    Tests that every column the spreadsheet writers consult has a state variable,
    so no column can be missing from the dict the writers read

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    assert tuple(display.display.column_vars.keys()) == COLUMN_KEYS


def test_init_starts_with_only_the_always_included_column_checked(display):
    """
    Tests that Part starts checked while every optional column starts unchecked,
    matching the previous GUI where the user opted in to each extra column

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    assert display.display.column_vars["Part"].get() is True

    for key in COLUMN_KEYS:
        if key != "Part":
            assert display.display.column_vars[key].get() is False


###############################################################################
###          Tests InventoryAppDisplay -> __init__() Settings Restore       ###
###############################################################################
@pytest.mark.parametrize(
    "display",
    [
        {
            "settings": {
                "theme": "Light",
                "font_family": "Arial",
                "font_size": "18",
            }
        }
    ],
    indirect=True,
)
def test_init_restores_the_persisted_theme_and_font(display):
    """
    Tests that the theme, font family and font size the user last chose are
    restored, with the stored theme name resolved back to its Theme and the
    stored font size converted from text back to an int

    Args:
        display (pytest.fixture): Test fixture building the display with the
            persisted theme and font settings
    """

    assert display.display.current_theme is LIGHT
    assert display.display.current_font_family == "Arial"
    assert display.display.current_font_size == 18


@pytest.mark.parametrize(
    "display",
    [{"theme": FOREST, "font_size": 14, "settings": {"theme": "Nonexistent"}}],
    indirect=True,
)
def test_init_falls_back_when_the_persisted_theme_is_unknown(display):
    """
    Tests that a persisted theme name matching no known theme falls back to the
    injected theme, so a settings database written by a version that had a theme
    this one does not cannot leave the GUI unstyled

    Args:
        display (pytest.fixture): Test fixture building the display with an
            unrecognized persisted theme name
    """

    assert display.display.current_theme is FOREST


@pytest.mark.parametrize(
    "display",
    [{"font_size": 14, "settings": {"font_size": "not-a-number"}}],
    indirect=True,
)
def test_init_falls_back_when_the_persisted_font_size_is_not_a_number(display):
    """
    Tests that a corrupt font size falls back to the injected size rather than
    reaching tkinter, which would raise on it

    Args:
        display (pytest.fixture): Test fixture building the display with a
            non-numeric persisted font size
    """

    assert display.display.current_font_size == 14


@pytest.mark.parametrize(
    "display",
    [{"settings": {"window_geometry": "900x850+120+60"}}],
    indirect=True,
)
def test_init_restores_the_persisted_window_geometry(display):
    """
    Tests that the window reopens at the size and position the user last left it
    at, rather than at the resolution the controller supplies

    Args:
        display (pytest.fixture): Test fixture building the display with a
            persisted window geometry
    """

    display.geometry.assert_called_once_with("900x850+120+60")


@pytest.mark.parametrize(
    "display",
    [{"settings": {"window_geometry": "not-a-geometry"}}],
    indirect=True,
)
def test_init_falls_back_when_the_persisted_geometry_is_malformed(display):
    """
    Tests that a corrupt geometry falls back to the injected resolution, since
    handing it straight to geometry() would raise and never build the window

    Args:
        display (pytest.fixture): Test fixture building the display with a
            malformed persisted window geometry
    """

    display.geometry.assert_called_once_with("700x700")


@pytest.mark.parametrize(
    "display",
    [
        {
            "settings": {
                "column_OnHand": "True",
                "column_Allocated": "False",
                "column_tTO Rate": "True",
            }
        }
    ],
    indirect=True,
)
def test_init_restores_the_persisted_column_selections(display):
    """
    Tests that each column's checkbox starts in the state the user last left it
    in, and that a column with nothing persisted for it still starts unchecked

    Note the "False" assertions are the point: settings are stored as text and
    bool("False") is True, so a converted round-trip would check every box.

    Args:
        display (pytest.fixture): Test fixture building the display with persisted
            column selections
    """

    assert display.display.column_vars["OnHand"].get() is True
    assert display.display.column_vars["tTO Rate"].get() is True
    assert display.display.column_vars["Allocated"].get() is False

    # Nothing was persisted for this column, so it keeps its own default
    assert display.display.column_vars["Committed"].get() is False


@pytest.mark.parametrize(
    "display", [{"settings": {"column_Part": "False"}}], indirect=True
)
def test_init_keeps_an_always_included_column_checked(display):
    """
    Tests that a column marked always stays checked even when the settings hold a
    stale unchecked state for it, since it has no checkbox the user could have
    unchecked it with

    Args:
        display (pytest.fixture): Test fixture building the display with a
            persisted unchecked state for an always-included column
    """

    assert display.display.column_vars["Part"].get() is True


###############################################################################
###              Tests InventoryAppDisplay -> build_widgets()               ###
###############################################################################
def test_build_widgets_creates_a_checkbutton_for_every_selectable_column(display):
    """
    Tests that the checkbox grid is built from the canonical column list, so the
    GUI cannot drift out of sync with the columns the spreadsheet emits

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    selectable = [column for column in ALL_COLUMNS if not column.always]

    assert display.checkbutton_cls.call_count == len(selectable)

    # Every selectable column is offered, under its own label
    built_labels = [
        made_call.kwargs["text"]
        for made_call in display.checkbutton_cls.call_args_list
    ]
    assert built_labels == [column.label for column in selectable]


def test_build_widgets_gives_the_always_included_column_no_checkbutton(display):
    """
    Tests that Part is emitted without offering the user a way to uncheck it,
    since a report keyed by part number is meaningless without it

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    assert "Part" not in display.display.column_checkbuttons
    assert set(display.display.column_checkbuttons.keys()) == {
        column.key for column in ALL_COLUMNS if not column.always
    }


def test_build_widgets_binds_each_checkbutton_to_its_own_column_variable(display):
    """
    Tests that each checkbutton toggles the variable for its own column, since a
    mis-wired variable would silently include or drop the wrong column

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    selectable = [column for column in ALL_COLUMNS if not column.always]

    for column, made_call in zip(selectable, display.checkbutton_cls.call_args_list):
        assert made_call.kwargs["variable"] is display.display.column_vars[column.key]


def test_build_widgets_wraps_the_checkbuttons_onto_multiple_rows(display):
    """
    Tests that the inventory checkboxes are laid out four per row rather than in
    a single line too wide for the window

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    # Grid positions of the ten selectable inventory columns
    positions = [
        checkbutton.grid.call_args.kwargs
        for key, checkbutton in display.display.column_checkbuttons.items()
        if not key.startswith("t")
    ]

    assert [(spot["row"], spot["column"]) for spot in positions] == [
        (0, 0),
        (0, 1),
        (0, 2),
        (0, 3),
        (1, 0),
        (1, 1),
        (1, 2),
        (1, 3),
        (2, 0),
        (2, 1),
    ]


def test_build_widgets_styles_the_checkbuttons_with_the_theme_and_font(display):
    """
    Tests that the checkbuttons carry the theme colors, including the two knobs
    that keep them readable on a dark background: the check box interior color
    and the removal of the focus ring

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    checkbutton_kwargs = display.checkbutton_cls.call_args.kwargs

    assert checkbutton_kwargs["bg"] == DARK.bg_main
    assert checkbutton_kwargs["fg"] == DARK.fg_text
    assert checkbutton_kwargs["selectcolor"] == DARK.bg_entry
    assert checkbutton_kwargs["highlightthickness"] == 0
    assert checkbutton_kwargs["font"] == (DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE)


def test_build_widgets_wires_the_process_button_to_its_handler(display):
    """
    Tests that the process button triggers processing of the selected inventory

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    assert (
        button_call(display, "Process This Inventory").kwargs["command"]
        == display.display.handle_process_inventory
    )


def test_build_widgets_wires_the_exit_button_to_handle_exit(display):
    """
    Tests that the exit button closes the application through handle_exit, so it
    saves the window geometry and behaves the same as the window's close box
    rather than only ending the main loop

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    assert button_call(display, "Exit").kwargs["command"] == (
        display.display.handle_exit
    )


def test_build_widgets_styles_the_buttons_with_the_theme_and_font(display):
    """
    Tests that the action button uses the application's button styling, and that
    the exit button is set apart by its own background and hover color

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    process_kwargs = button_call(display, "Process This Inventory").kwargs
    assert process_kwargs["bg"] == DARK.button_bg
    assert process_kwargs["fg"] == DARK.button_fg
    assert process_kwargs["activebackground"] == DARK.accent
    assert process_kwargs["font"] == (
        DEFAULT_FONT_FAMILY,
        DEFAULT_FONT_SIZE,
        "bold",
    )

    exit_kwargs = button_call(display, "Exit").kwargs
    assert exit_kwargs["bg"] == DARK.bg_entry
    assert exit_kwargs["activebackground"] != DARK.accent


def test_build_widgets_creates_and_attaches_the_menu_bar(display):
    """
    Tests that build_widgets constructs every menu cascade and registers the
    assembled menu bar on the window exactly once

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    assert display.display.menu_bar is not None
    assert display.display.file_menu is not None
    assert display.display.view_menu is not None
    assert display.display.preferences_menu is not None
    assert display.display.help_menu is not None

    display.config.assert_called_once_with(menu=display.display.menu_bar)


def test_build_widgets_wires_the_file_menu(display):
    """
    Tests that the File menu offers Open, Clear, and Exit (with a separator
    before Exit), each wired to its handler

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    calls = display.display.file_menu.add_command.call_args_list
    assert calls[0].kwargs == {
        "label": "Open",
        "command": display.display.handle_browse_button,
    }
    assert calls[1].kwargs == {
        "label": "Clear",
        "command": display.display.handle_clear,
    }
    assert calls[2].kwargs == {
        "label": "Exit",
        "command": display.display.handle_exit,
    }
    display.display.file_menu.add_separator.assert_called_once()


def test_build_widgets_wires_the_view_menu(display):
    """
    Tests that the View menu offers Results Log, Inventories, Turnover Reports
    and Spreadsheets, each wired to its handler

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    calls = display.display.view_menu.add_command.call_args_list
    assert calls[0].kwargs == {
        "label": "Results Log",
        "command": display.display.handle_results_log,
    }
    assert calls[1].kwargs == {
        "label": "Inventories",
        "command": display.display.handle_open_inventories,
    }
    assert calls[2].kwargs == {
        "label": "Turnover Reports",
        "command": display.display.handle_open_turnover_reports,
    }
    assert calls[3].kwargs == {
        "label": "Spreadsheets",
        "command": display.display.handle_open_spreadsheets,
    }


def test_build_widgets_wires_the_help_menu(display):
    """
    Tests that the Help menu offers About and Check for Updates, each wired to its
    handler

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    calls = display.display.help_menu.add_command.call_args_list
    assert calls[0].kwargs == {
        "label": "About",
        "command": display.display.handle_about,
    }
    assert calls[1].kwargs == {
        "label": "Check for Updates",
        "command": display.display.handle_check_for_updates,
    }


def test_build_widgets_theme_submenu_offers_every_theme_and_applies_it(display):
    """
    Tests that the Preferences -> Theme submenu offers every available theme, in
    order, and that choosing one applies it. Each command is built with a
    default-argument-capturing lambda to avoid a late-binding closure bug, so
    invoking every command in turn and checking the result after each call is
    what actually exercises that captured value.

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    cascade_call = next(
        c
        for c in display.display.preferences_menu.add_cascade.call_args_list
        if c.kwargs["label"] == "Theme"
    )
    theme_menu = cascade_call.kwargs["menu"]
    theme_commands = theme_menu.add_command.call_args_list

    assert [c.kwargs["label"] for c in theme_commands] == [
        theme.name for theme in ALL_THEMES
    ]

    for theme_option, made_call in zip(ALL_THEMES, theme_commands):
        made_call.kwargs["command"]()
        assert display.display.current_theme is theme_option


def test_build_widgets_font_submenu_offers_every_family_and_applies_it(display):
    """
    Tests that the Preferences -> Font submenu offers every available font
    family, in order, and that choosing one applies it

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    cascade_call = next(
        c
        for c in display.display.preferences_menu.add_cascade.call_args_list
        if c.kwargs["label"] == "Font"
    )
    font_menu = cascade_call.kwargs["menu"]
    font_commands = font_menu.add_command.call_args_list

    assert [c.kwargs["label"] for c in font_commands] == FONT_FAMILIES

    for family, made_call in zip(FONT_FAMILIES, font_commands):
        made_call.kwargs["command"]()
        assert display.display.current_font_family == family


def test_build_widgets_font_size_submenu_offers_every_size_and_applies_it(display):
    """
    Tests that the Preferences -> Font Size submenu offers every available font
    size, in order, and that choosing one applies it

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    cascade_call = next(
        c
        for c in display.display.preferences_menu.add_cascade.call_args_list
        if c.kwargs["label"] == "Font Size"
    )
    font_size_menu = cascade_call.kwargs["menu"]
    font_size_commands = font_size_menu.add_command.call_args_list

    assert [c.kwargs["label"] for c in font_size_commands] == [
        str(size) for size in FONT_SIZES
    ]

    for size, made_call in zip(FONT_SIZES, font_size_commands):
        made_call.kwargs["command"]()
        assert display.display.current_font_size == size


def test_build_widgets_attaches_a_tooltip_to_every_button(display):
    """
    Tests that build_widgets gives each action button a non-empty hover tooltip
    describing what it does

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    tooltip_texts = tooltip_texts_by_widget(display)

    for button in (
        display.display.browse_button,
        display.display.process_inventory_button,
        display.display.exit_button,
    ):
        assert tooltip_texts.get(button)


def test_build_widgets_gives_each_checkbutton_its_own_columns_tooltip(display):
    """
    Tests that every column checkbutton is given the hover text of the column it
    selects. Resolving each checkbutton back through column_checkbuttons is what
    catches a tooltip attached to the wrong checkbox, which a "has some text"
    assertion would pass right over.

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    tooltip_texts = tooltip_texts_by_widget(display)

    for column in ALL_COLUMNS:

        # A column that is always included has no checkbutton to hover
        if column.always:
            continue

        checkbutton = display.display.column_checkbuttons[column.key]
        assert tooltip_texts[checkbutton] == column.tooltip


def test_build_widgets_tracks_every_tooltip_for_restyling(display):
    """
    Tests that every tooltip built is kept in the tooltips list, since that list
    is the only handle apply_theme and _apply_font have to restyle them

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    # One per action button, plus one per column that has a checkbutton
    selectable = [column for column in ALL_COLUMNS if not column.always]

    assert len(display.display.tooltips) == 3 + len(selectable)


def test_build_widgets_styles_the_tooltips_with_the_theme_and_font(display):
    """
    Tests that each tooltip is built with the display's active theme and font, so
    a tooltip matches the rest of the application the first time it is shown

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    for made_call in display.tooltip_cls.call_args_list:
        assert made_call.kwargs["theme"] is DARK
        assert made_call.kwargs["font_family"] == DEFAULT_FONT_FAMILY
        assert made_call.kwargs["font_size"] == DEFAULT_FONT_SIZE


###############################################################################
###           Tests InventoryAppDisplay -> handle_browse_button()           ###
###############################################################################
def test_handle_browse_button_stores_the_chosen_file(display):
    """
    Tests that choosing a file in the dialog records it as the selected file, and
    that the dialog opens in the inventory directory filtered to PDFs

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    with patch(
        "source.gui.InventoryAppDisplay.filedialog.askopenfilename",
        return_value="C:/Inventory/Inventory 01222024.pdf",
    ) as mock_dialog:
        display.display.handle_browse_button()

    assert (
        display.display.selected_file.get() == "C:/Inventory/Inventory 01222024.pdf"
    )

    dialog_kwargs = mock_dialog.call_args.kwargs
    assert dialog_kwargs["initialdir"] == str(INVENTORY_DIR)
    assert dialog_kwargs["filetypes"] == [("PDF files", "*.pdf")]


def test_handle_browse_button_leaves_the_selection_alone_when_cancelled(display):
    """
    Tests that dismissing the file dialog does not clear a file the user had
    already chosen

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.selected_file.set("C:/Inventory/Already Chosen.pdf")

    with patch(
        "source.gui.InventoryAppDisplay.filedialog.askopenfilename",
        return_value="",
    ):
        display.display.handle_browse_button()

    assert display.display.selected_file.get() == "C:/Inventory/Already Chosen.pdf"


###############################################################################
###           Tests InventoryAppDisplay -> get_selected_columns()           ###
###############################################################################
def test_get_selected_columns_reports_every_column(display):
    """
    Tests that the returned dict holds every key the spreadsheet writers look up,
    since a missing key would raise rather than simply omit a column

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    assert tuple(display.display.get_selected_columns().keys()) == COLUMN_KEYS


def test_get_selected_columns_reflects_the_checkbox_state_as_real_booleans(display):
    """
    Tests that a checked column comes back True and an unchecked one False, as
    real booleans rather than merely truthy values: the spreadsheet writers
    compare each value against True with ==, so anything else drops the column

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.column_vars["UOM"].set(True)
    display.display.column_vars["tTO Rate"].set(True)

    selected = display.display.get_selected_columns()

    assert selected["Part"] is True
    assert selected["UOM"] is True
    assert selected["tTO Rate"] is True
    assert selected["Description"] is False
    assert selected["tAvg QOH"] is False


###############################################################################
###         Tests InventoryAppDisplay -> handle_process_inventory()         ###
###############################################################################
def test_handle_process_inventory_forwards_the_file_and_columns(display):
    """
    Tests that pressing the process button hands the chosen file and the current
    column selection to the controller's callback, after clearing the output left
    over from any previous run

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.selected_file.set("C:/Inventory/Inventory 01222024.pdf")
    display.display.column_vars["OnHand"].set(True)

    display.display.handle_process_inventory()

    display.process_callback.assert_called_once_with(
        "C:/Inventory/Inventory 01222024.pdf",
        display.display.get_selected_columns(),
    )

    # The previous run's output is cleared before the new one starts
    display.display.output_box.delete.assert_called_once_with(1.0, tk.END)


def test_handle_process_inventory_with_no_file_warns_and_does_not_process(display):
    """
    Tests that pressing the process button before choosing a file tells the user
    to pick one instead of handing an empty path to the controller

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.handle_process_inventory()

    display.message_window_cls.assert_called_once()
    display.process_callback.assert_not_called()


###############################################################################
###                Tests InventoryAppDisplay -> write_output()              ###
###############################################################################
def test_write_output_appends_the_message_and_scrolls_to_it(display):
    """
    Tests that a status message is appended to the output box on its own line,
    scrolled into view, and painted immediately rather than at the next idle
    moment, since processing blocks the GUI thread

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.write_output("Processing Inventory... Please wait.")

    display.display.output_box.insert.assert_called_once_with(
        tk.END, "Processing Inventory... Please wait.\n"
    )
    display.display.output_box.see.assert_called_once_with(tk.END)
    display.display.output_box.update_idletasks.assert_called_once_with()


def test_write_output_does_nothing_before_the_output_box_exists(display):
    """
    Tests that a status message arriving before the widgets are built is dropped
    rather than raising, so the caller never has to check

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.output_box = None

    # No assertion beyond not raising: there is nowhere to write the message
    display.display.write_output("Some status")


###############################################################################
###                Tests InventoryAppDisplay -> clear_output()              ###
###############################################################################
def test_clear_output_empties_the_output_box(display):
    """
    Tests that clearing the output removes everything currently in the box

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.clear_output()

    display.display.output_box.delete.assert_called_once_with(1.0, tk.END)


def test_clear_output_does_nothing_before_the_output_box_exists(display):
    """
    Tests that clearing before the widgets are built is a no-op rather than an error

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.output_box = None

    display.display.clear_output()


###############################################################################
###                 Tests InventoryAppDisplay -> show_popup()               ###
###############################################################################
def test_show_popup_opens_a_themed_message_window(display):
    """
    Tests that an error or notice is shown in a themed popup carrying the
    application's current styling, rather than a native message box

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.show_popup("File Error", "Could not read the file")

    display.message_window_cls.assert_called_once_with(
        parent=display.display,
        title="File Error",
        message="Could not read the file",
        theme=DARK,
        font_family=DEFAULT_FONT_FAMILY,
        font_size=DEFAULT_FONT_SIZE,
    )


###############################################################################
###                Tests InventoryAppDisplay -> handle_clear()              ###
###############################################################################
def test_handle_clear_resets_the_selected_file_and_output(display):
    """
    Tests that "Clear" resets the selected file path and empties the output box

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.selected_file.set("C:/Inventory/Already Chosen.pdf")

    display.display.handle_clear()

    assert display.display.selected_file.get() == ""
    display.display.output_box.delete.assert_called_once_with(1.0, tk.END)


###############################################################################
###             Tests InventoryAppDisplay -> handle_results_log()           ###
###############################################################################
def test_handle_results_log_opens_a_read_only_viewer_when_present(display):
    """
    Tests that "Results Log" opens a read-only viewer window populated from the
    read callback when the results file exists

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    with patch("source.gui.InventoryAppDisplay.RESULTS_FILE") as mock_results_file:
        mock_results_file.exists.return_value = True

        display.display.handle_results_log()

        display.read_file_callback.assert_called_once_with(mock_results_file)
        window_kwargs = display.file_editor_window_cls.call_args.kwargs
        assert window_kwargs["file_path"] is mock_results_file
        assert window_kwargs["editable"] is False
        assert window_kwargs["initial_text"] is display.read_file_callback.return_value


def test_handle_results_log_shows_an_error_when_missing(display):
    """
    Tests that "Results Log" shows a popup and opens no viewer when the results
    file has not been created yet

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    with patch("source.gui.InventoryAppDisplay.RESULTS_FILE") as mock_results_file:
        mock_results_file.exists.return_value = False

        display.display.handle_results_log()

        display.message_window_cls.assert_called_once()
        display.file_editor_window_cls.assert_not_called()


###############################################################################
###  Tests InventoryAppDisplay -> handle_open_inventories()/(turnover/xlsx) ###
###############################################################################
def test_handle_open_inventories_opens_a_dialog_rooted_at_the_inventory_dir(display):
    """
    Tests that "Inventories" opens a browse-only file dialog rooted at the
    inventory availability directory, filtered to PDFs

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    with patch(
        "source.gui.InventoryAppDisplay.filedialog.askopenfilename"
    ) as mock_dialog:
        display.display.handle_open_inventories()

    dialog_kwargs = mock_dialog.call_args.kwargs
    assert dialog_kwargs["initialdir"] == str(INVENTORY_DIR)
    assert dialog_kwargs["filetypes"] == [("PDF files", "*.pdf")]


def test_handle_open_turnover_reports_opens_a_dialog_rooted_at_the_turnover_dir(
    display,
):
    """
    Tests that "Turnover Reports" opens a browse-only file dialog rooted at the
    turnover reports directory, filtered to PDFs

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    with patch(
        "source.gui.InventoryAppDisplay.filedialog.askopenfilename"
    ) as mock_dialog:
        display.display.handle_open_turnover_reports()

    dialog_kwargs = mock_dialog.call_args.kwargs
    assert dialog_kwargs["initialdir"] == str(TURNOVER_DIR)
    assert dialog_kwargs["filetypes"] == [("PDF files", "*.pdf")]


def test_handle_open_spreadsheets_opens_a_dialog_rooted_at_the_output_dir(
    display,
):
    """
    Tests that "Spreadsheets" opens a browse-only file dialog rooted at the
    directory the generated spreadsheets are written to, filtered to .xlsx files

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    with patch(
        "source.gui.InventoryAppDisplay.filedialog.askopenfilename"
    ) as mock_dialog:
        display.display.handle_open_spreadsheets()

    dialog_kwargs = mock_dialog.call_args.kwargs
    assert dialog_kwargs["initialdir"] == str(OUTPUT_DIR)
    assert dialog_kwargs["filetypes"] == [("Excel files", "*.xlsx")]


###############################################################################
###                Tests InventoryAppDisplay -> handle_about()              ###
###############################################################################
def test_handle_about_opens_the_about_window(display):
    """
    Tests that "About" opens the About window showing the current application
    version, styled with the active theme/font

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.handle_about()

    display.about_window_cls.assert_called_once_with(
        parent=display.display,
        title="About",
        version=VERSION,
        theme=display.display.current_theme,
        font_family=display.display.current_font_family,
        font_size=display.display.current_font_size,
    )


###############################################################################
###         Tests InventoryAppDisplay -> handle_check_for_updates()         ###
###############################################################################
def test_handle_check_for_updates_invokes_the_callback(display):
    """
    Tests that "Check for Updates" asks the controller to run an on-demand update
    check, rather than reaching for the network itself

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.handle_check_for_updates()

    display.check_for_updates_callback.assert_called_once_with()


###############################################################################
###           Tests InventoryAppDisplay -> show_update_available()          ###
###############################################################################
def test_show_update_available_opens_the_update_window(display):
    """
    Tests that a newer release opens the update window showing that version, with
    the app's own exit handler as the close callback so the exiting app releases
    the executable's file lock for the installer

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    result = SimpleNamespace(
        update_available=True,
        latest_version="9.9.9",
        release_url="https://example.com/release",
    )

    display.display.show_update_available(result)

    display.update_window_cls.assert_called_once_with(
        parent=display.display,
        title="Update Available",
        latest_version="9.9.9",
        release_url="https://example.com/release",
        close_app_callback=display.display.handle_exit,
        theme=display.display.current_theme,
        font_family=display.display.current_font_family,
        font_size=display.display.current_font_size,
    )


###############################################################################
###                Tests InventoryAppDisplay -> apply_theme()               ###
###############################################################################
def test_apply_theme_updates_state_and_restyles_every_widget(display):
    """
    Tests that apply_theme stores the new theme and reconfigures the window and
    every tracked widget, including every column checkbutton, with that theme's
    colors

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.apply_theme(FOREST)

    assert display.display.current_theme is FOREST

    display.configure.assert_any_call(bg=FOREST.bg_main)
    display.display.output_box.configure.assert_called_once_with(
        bg=FOREST.bg_entry, fg=FOREST.fg_text, insertbackground=FOREST.fg_text
    )

    for checkbutton in display.display.column_checkbuttons.values():
        checkbutton.configure.assert_called_once_with(
            bg=FOREST.bg_main,
            fg=FOREST.fg_text,
            activebackground=FOREST.bg_main,
            activeforeground=FOREST.accent,
            selectcolor=FOREST.bg_entry,
        )

    # The hover tooltips are restyled to the new theme
    for tooltip in display.display.tooltips:
        tooltip.update_style.assert_called_once_with(
            FOREST, DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE
        )


def test_apply_theme_persists_the_choice(display):
    """
    Tests that choosing a theme persists its name, so the application reopens on
    the theme the user last picked

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.apply_theme(FOREST)

    display.save_settings_callback.assert_called_once_with("theme", FOREST.name)


###############################################################################
###             Tests InventoryAppDisplay -> apply_font_family()            ###
###############################################################################
def test_apply_font_family_updates_state_and_restyles_every_widget(display):
    """
    Tests that apply_font_family stores the chosen family and applies the new
    font (family, size, weight) to the tracked widgets, including the column
    checkbuttons at their own non-bold weight

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.apply_font_family("Arial")

    assert display.display.current_font_family == "Arial"
    display.display.title_label.configure.assert_called_once_with(
        font=("Arial", DEFAULT_FONT_SIZE, "bold")
    )

    for checkbutton in display.display.column_checkbuttons.values():
        checkbutton.configure.assert_called_once_with(
            font=("Arial", DEFAULT_FONT_SIZE)
        )


def test_apply_font_family_persists_the_choice(display):
    """
    Tests that choosing a font family persists it, so the application reopens on
    the font the user last picked

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.apply_font_family("Arial")

    display.save_settings_callback.assert_called_once_with("font_family", "Arial")


###############################################################################
###              Tests InventoryAppDisplay -> apply_font_size()             ###
###############################################################################
def test_apply_font_size_updates_state_and_restyles_every_widget(display):
    """
    Tests that apply_font_size stores the chosen size and applies the new font
    (family, size, weight) to the tracked widgets, including the column
    checkbuttons at their own non-bold weight

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.apply_font_size(20)

    assert display.display.current_font_size == 20
    display.display.output_box.configure.assert_called_once_with(
        font=(DEFAULT_FONT_FAMILY, 20, "bold")
    )

    for checkbutton in display.display.column_checkbuttons.values():
        checkbutton.configure.assert_called_once_with(
            font=(DEFAULT_FONT_FAMILY, 20)
        )

    # The hover tooltips are restyled to the new font
    for tooltip in display.display.tooltips:
        tooltip.update_style.assert_called_once_with(DARK, DEFAULT_FONT_FAMILY, 20)


def test_apply_font_size_persists_the_choice_as_text(display):
    """
    Tests that choosing a font size persists it as a string, since the settings
    database stores only text

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.apply_font_size(20)

    display.save_settings_callback.assert_called_once_with("font_size", "20")


###############################################################################
###          Tests InventoryAppDisplay -> handle_column_toggled()           ###
###############################################################################
def test_handle_column_toggled_persists_a_checked_column(display):
    """
    Tests that checking a column persists it as included, so the same columns are
    checked on the next launch

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.column_vars["OnHand"].set(True)

    display.display.handle_column_toggled("OnHand")

    display.save_settings_callback.assert_called_once_with("column_OnHand", "True")


def test_handle_column_toggled_persists_an_unchecked_column(display):
    """
    Tests that unchecking a column persists it as excluded rather than dropping
    the setting, so the choice survives a restart

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.column_vars["tTO Rate"].set(False)

    display.display.handle_column_toggled("tTO Rate")

    display.save_settings_callback.assert_called_once_with("column_tTO Rate", "False")


def test_build_widgets_wires_each_checkbutton_to_persist_its_own_column(display):
    """
    Tests that every checkbutton's command persists the column it belongs to
    rather than whichever column the build loop finished on, which is what the
    default-argument capture in the lambda protects against

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    for made_call in display.checkbutton_cls.call_args_list:
        display.save_settings_callback.reset_mock()

        made_call.kwargs["command"]()

        # The variable this checkbutton was bound to is the one that got persisted
        variable = made_call.kwargs["variable"]
        key = next(
            column_key
            for column_key, column_var in display.display.column_vars.items()
            if column_var is variable
        )
        display.save_settings_callback.assert_called_once_with(
            "column_" + key, str(variable.get())
        )


###############################################################################
###                Tests InventoryAppDisplay -> handle_exit()               ###
###############################################################################
def test_handle_exit_persists_the_geometry_then_closes_the_window(display):
    """
    Tests that closing the application saves the window's current size and
    position before destroying the window, so it reopens where the user left it

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.display.handle_exit()

    display.save_settings_callback.assert_called_once_with(
        "window_geometry", "780x820+320+180"
    )
    display.destroy.assert_called_once_with()


def test_build_widgets_routes_the_window_close_box_through_handle_exit(display):
    """
    Tests that the window's own close box exits through handle_exit too, since it
    is the one way out of the application that reaches none of the app's widgets

    Args:
        display (pytest.fixture): Test fixture building the display with tkinter
            fully mocked out
    """

    display.protocol.assert_called_once_with(
        "WM_DELETE_WINDOW", display.display.handle_exit
    )
