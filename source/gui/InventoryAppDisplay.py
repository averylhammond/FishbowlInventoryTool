import tkinter as tk
from pathlib import Path
from tkinter import filedialog, scrolledtext
from typing import Callable

from source.columns import ALL_COLUMNS, INVENTORY_COLUMNS, TURNOVER_COLUMNS, Column
from source.constants import INVENTORY_DIR, RESULTS_FILE, TURNOVER_DIR, VERSION
from source.gui.AboutWindow import AboutWindow
from source.gui.FileEditorWindow import FileEditorWindow
from source.gui.MessageWindow import MessageWindow
from source.gui.color_theme import (
    ALL_THEMES,  # Themes offered in the Preferences -> Theme menu
    DARK,  # Default theme used by the GUI
    RED,  # Used for the EXIT button
    Theme,
)
from source.gui.font_settings import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    FONT_FAMILIES,
    FONT_SIZES,
)

# Number of checkboxes placed per row in each of the two column-selection grids
INVENTORY_CHECKBOXES_PER_ROW = 4
TURNOVER_CHECKBOXES_PER_ROW = 3


# Inventory App Display class to own the GUI for selecting an inventory
# availability PDF, choosing which columns the report includes, and processing it.
# This implementation uses tkinter for the GUI.
class InventoryAppDisplay(tk.Tk):

    ###########################################################################
    ###                 InventoryAppDisplay -> __init__()                   ###
    ###########################################################################
    def __init__(
        self,
        process_callback: Callable[[str, dict], bool],
        read_file_callback: Callable[[Path], str],
        title: str,
        window_resolution: str,
        theme: Theme = DARK,
        font_family: str = DEFAULT_FONT_FAMILY,
        font_size: int = DEFAULT_FONT_SIZE,
    ):
        """
        Initializes the InventoryAppDisplay object

        Args:
            process_callback (Callable[[str, dict], bool]): Callback that processes
                the selected inventory PDF, taking the chosen file path and the
                column-selection dict
            read_file_callback (Callable[[Path], str]): Callback that reads a text
                file's contents, used to populate the read-only file viewer (e.g.
                View -> Results Log)
            title (str): Title of the application window
            window_resolution (str): Resolution of the application window (e.g. "700x700")
            theme (Theme): The color theme to style the application with
            font_family (str): The font family to display the text with
            font_size (int): The font size to display the text with
        """

        super().__init__()

        # Title applied to the application window
        self.title(title)

        # Resolution of the application window
        self.geometry(window_resolution)

        # Allow user to resize window in x and y direction
        self.resizable(True, True)

        # Callback function to process the selected inventory file
        self.process_callback = process_callback

        # Callback function to read a text file's contents for the file viewer
        self.read_file_callback = read_file_callback

        # Styling applied to every widget as it is created
        self.current_theme = theme
        self.current_font_family = font_family
        self.current_font_size = font_size

        # Holds the last selected inventory availability filepath
        self.selected_file = tk.StringVar()

        # One checkbox state per column, keyed by the key the spreadsheet writers
        # look up. Built from ALL_COLUMNS so the GUI cannot offer a column the
        # spreadsheet does not know about, or miss one that it does. A column
        # marked always starts checked and is never given a checkbox to uncheck.
        self.column_vars = {
            column.key: tk.BooleanVar(value=column.always) for column in ALL_COLUMNS
        }

        # Tkinter Widgets
        # fmt:off
        self.menu_bar:                 tk.Menu                   | None = None
        self.file_menu:                tk.Menu                   | None = None
        self.view_menu:                tk.Menu                   | None = None
        self.preferences_menu:         tk.Menu                   | None = None
        self.help_menu:                tk.Menu                   | None = None
        self.title_label:              tk.Label                  | None = None
        self.file_frame:               tk.Frame                  | None = None
        self.file_entry:               tk.Entry                  | None = None
        self.browse_button:            tk.Button                 | None = None
        self.inventory_label:          tk.Label                  | None = None
        self.inventory_frame:          tk.Frame                  | None = None
        self.turnover_label:           tk.Label                  | None = None
        self.turnover_frame:           tk.Frame                  | None = None
        self.button_frame:             tk.Frame                  | None = None
        self.process_inventory_button: tk.Button                 | None = None
        self.exit_button:              tk.Button                 | None = None
        self.output_label:             tk.Label                  | None = None
        self.output_box:               scrolledtext.ScrolledText | None = None
        # fmt:on

        # The column checkbuttons, keyed by column key. Columns marked always get
        # no checkbutton, so they are absent from this mapping.
        self.column_checkbuttons = {}

        # Build the GUI
        self.build_widgets()

    ###########################################################################
    ###               InventoryAppDisplay -> build_widgets()                ###
    ###########################################################################
    def build_widgets(self):
        """
        Creates the GUI widgets for the application. This includes a title label,
        the file selection entry and browse button, a checkbox grid for each of
        the two column groups, the action buttons, and the output box
        """

        self.configure(bg=self.current_theme.bg_main)

        self.menu_bar = tk.Menu(self)

        # File dropdown
        #  -> Open option to choose an inventory availability PDF
        #  -> Clear option to clear the output box and reset the selected file
        #  -> Exit option to close the application
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.file_menu.add_command(label="Open", command=self.handle_browse_button)
        self.file_menu.add_command(label="Clear", command=self.handle_clear)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.destroy)
        self.menu_bar.add_cascade(label="File", menu=self.file_menu)

        # View dropdown
        #  -> Results Log option to view the results log file
        #  -> Inventories option to browse the inventory availability PDFs
        #  -> Turnover Reports option to browse the turnover report PDFs
        self.view_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.view_menu.add_command(
            label="Results Log", command=self.handle_results_log
        )
        self.view_menu.add_command(
            label="Inventories", command=self.handle_open_inventories
        )
        self.view_menu.add_command(
            label="Turnover Reports", command=self.handle_open_turnover_reports
        )
        self.menu_bar.add_cascade(label="View", menu=self.view_menu)

        # Preferences dropdown
        #  -> Theme option to select from available color themes
        #  -> Font option to select the font family used throughout the application
        #  -> Font Size option to adjust the text size throughout the application
        self.preferences_menu = tk.Menu(self.menu_bar, tearoff=0)

        theme_menu = tk.Menu(self.preferences_menu, tearoff=0)
        for theme_option in ALL_THEMES:
            theme_menu.add_command(
                label=theme_option.name,
                command=lambda t=theme_option: self.apply_theme(t),
            )
        self.preferences_menu.add_cascade(label="Theme", menu=theme_menu)

        font_menu = tk.Menu(self.preferences_menu, tearoff=0)
        for family in FONT_FAMILIES:
            font_menu.add_command(
                label=family,
                command=lambda f=family: self.apply_font_family(f),
            )
        self.preferences_menu.add_cascade(label="Font", menu=font_menu)

        font_size_menu = tk.Menu(self.preferences_menu, tearoff=0)
        for size in FONT_SIZES:
            font_size_menu.add_command(
                label=str(size),
                command=lambda s=size: self.apply_font_size(s),
            )
        self.preferences_menu.add_cascade(label="Font Size", menu=font_size_menu)

        self.menu_bar.add_cascade(label="Preferences", menu=self.preferences_menu)

        # Help dropdown
        #  -> About option to show the current application version
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.help_menu.add_command(label="About", command=self.handle_about)
        self.menu_bar.add_cascade(label="Help", menu=self.help_menu)

        self.config(menu=self.menu_bar)

        self.title_label = tk.Label(
            self,
            text="Choose an Inventory Availability PDF to Process",
            font=(self.current_font_family, self.current_font_size, "bold"),
            bg=self.current_theme.bg_main,
            fg=self.current_theme.label_fg,
        )
        self.title_label.pack(pady=(20, 10))

        # Row holding the selected file path and the button that chooses it
        self.file_frame = tk.Frame(self, bg=self.current_theme.bg_main)
        self.file_frame.pack(padx=20, fill="x")

        # Readonly so the path can only be set through the file dialog
        self.file_entry = tk.Entry(
            self.file_frame,
            textvariable=self.selected_file,
            state="readonly",
            width=50,
            bg=self.current_theme.bg_entry,
            fg=self.current_theme.bg_main,
            insertbackground=self.current_theme.fg_text,
            relief="flat",
        )
        self.file_entry.pack(side="left", fill="x", expand=True, padx=(0, 5), pady=8)

        self.browse_button = tk.Button(
            self.file_frame,
            text="Browse",
            command=self.handle_browse_button,
            bg=self.current_theme.button_bg,
            fg=self.current_theme.button_fg,
            activebackground=self.current_theme.accent,
            activeforeground=self.current_theme.fg_text,
            relief="flat",
            font=(self.current_font_family, self.current_font_size, "bold"),
        )
        self.browse_button.pack(side="left", padx=(10, 0), pady=8)

        # Inventory column selection
        self.inventory_label = tk.Label(
            self,
            text="Check the INVENTORY columns to include on the report:",
            font=(self.current_font_family, self.current_font_size, "bold"),
            bg=self.current_theme.bg_main,
            fg=self.current_theme.label_fg,
        )
        self.inventory_label.pack(anchor="w", padx=22, pady=(15, 2))

        self.inventory_frame = tk.Frame(self, bg=self.current_theme.bg_main)
        self.inventory_frame.pack(anchor="w", padx=20, fill="x")
        self._build_checkbox_grid(
            self.inventory_frame, INVENTORY_COLUMNS, INVENTORY_CHECKBOXES_PER_ROW
        )

        # Turnover column selection
        self.turnover_label = tk.Label(
            self,
            text="Check the TURNOVER columns to include on the report:",
            font=(self.current_font_family, self.current_font_size, "bold"),
            bg=self.current_theme.bg_main,
            fg=self.current_theme.label_fg,
        )
        self.turnover_label.pack(anchor="w", padx=22, pady=(15, 2))

        self.turnover_frame = tk.Frame(self, bg=self.current_theme.bg_main)
        self.turnover_frame.pack(anchor="w", padx=20, fill="x")
        self._build_checkbox_grid(
            self.turnover_frame, TURNOVER_COLUMNS, TURNOVER_CHECKBOXES_PER_ROW
        )

        self.button_frame = tk.Frame(self, bg=self.current_theme.bg_main)
        self.button_frame.pack(pady=20)

        self.process_inventory_button = tk.Button(
            self.button_frame,
            text="Process This Inventory",
            command=self.handle_process_inventory,
            bg=self.current_theme.button_bg,
            fg=self.current_theme.button_fg,
            activebackground=self.current_theme.accent,
            activeforeground=self.current_theme.fg_text,
            relief="flat",
            font=(self.current_font_family, self.current_font_size, "bold"),
        )
        self.process_inventory_button.grid(row=0, column=0, padx=10)

        # destroy() rather than quit() so the button and the window's close box
        # behave identically: quit() would only end the main loop, leaving the
        # window and the interpreter's Tk state alive behind it
        self.exit_button = tk.Button(
            self.button_frame,
            text="Exit",
            command=self.destroy,
            bg=self.current_theme.bg_entry,
            fg=self.current_theme.fg_text,
            activebackground=RED,
            activeforeground=self.current_theme.fg_text,
            relief="flat",
            font=(self.current_font_family, self.current_font_size, "bold"),
        )
        self.exit_button.grid(row=1, column=0, pady=(10, 0))

        self.output_label = tk.Label(
            self,
            text="Output:",
            font=(self.current_font_family, self.current_font_size, "bold"),
            bg=self.current_theme.bg_main,
            fg=self.current_theme.label_fg,
        )
        self.output_label.pack(anchor="w", padx=22, pady=(0, 2))

        self.output_box = scrolledtext.ScrolledText(
            self,
            height=10,
            wrap="word",
            font=(self.current_font_family, self.current_font_size, "bold"),
            bg=self.current_theme.bg_entry,
            fg=self.current_theme.fg_text,
            insertbackground=self.current_theme.fg_text,
            relief="flat",
        )
        self.output_box.pack(padx=20, pady=(0, 10), fill="both", expand=True)

    ###########################################################################
    ###            InventoryAppDisplay -> _build_checkbox_grid()             ###
    ###########################################################################
    def _build_checkbox_grid(self, parent: tk.Frame, columns: tuple, per_row: int):
        """
        Fills a frame with one checkbutton per selectable column, wrapping onto a
        new row every per_row columns

        Args:
            parent (tk.Frame): The frame the checkbuttons are placed in
            columns (tuple): The Column objects to build checkbuttons for, in the
                order they are displayed
            per_row (int): How many checkbuttons to place before wrapping
        """

        row = 0
        position = 0

        for column in columns:

            # A column that is always included has no checkbox to toggle
            if column.always:
                continue

            checkbutton = self._build_checkbutton(parent, column)
            checkbutton.grid(row=row, column=position, sticky="w", padx=6, pady=2)
            self.column_checkbuttons[column.key] = checkbutton

            position += 1
            if position == per_row:
                position = 0
                row += 1

    ###########################################################################
    ###             InventoryAppDisplay -> _build_checkbutton()              ###
    ###########################################################################
    def _build_checkbutton(self, parent: tk.Frame, column: Column) -> tk.Checkbutton:
        """
        Creates one themed checkbutton bound to its column's state variable

        Args:
            parent (tk.Frame): The frame the checkbutton is placed in
            column (Column): The column this checkbutton selects

        Returns:
            tk.Checkbutton: The created checkbutton
        """

        # selectcolor and highlightthickness are load bearing on a dark theme:
        # without them Tk paints the box interior white and draws a light focus
        # ring around the label, both of which read as artifacts against bg_main
        return tk.Checkbutton(
            parent,
            text=column.label,
            variable=self.column_vars[column.key],
            onvalue=True,
            offvalue=False,
            anchor="w",
            bg=self.current_theme.bg_main,
            fg=self.current_theme.fg_text,
            activebackground=self.current_theme.bg_main,
            activeforeground=self.current_theme.accent,
            selectcolor=self.current_theme.bg_entry,
            highlightthickness=0,
            relief="flat",
            font=(self.current_font_family, self.current_font_size),
        )

    ###########################################################################
    ###           InventoryAppDisplay -> handle_browse_button()              ###
    ###########################################################################
    def handle_browse_button(self):
        """
        On "Browse" button press, opens a file dialog to select an inventory
        availability PDF. Once selected, the file is set to the selected_file
        member variable
        """

        # Open a file dialog to select a PDF inventory file (Tk requires a str path)
        file_path = filedialog.askopenfilename(
            initialdir=str(INVENTORY_DIR),
            title="Select Inventory Availability PDF",
            filetypes=[("PDF files", "*.pdf")],  # Filter for PDF files only
        )

        # If a valid filepath was selected, update the selected_file variable
        if file_path:
            self.selected_file.set(file_path)

    ###########################################################################
    ###                InventoryAppDisplay -> handle_clear()                ###
    ###########################################################################
    def handle_clear(self):
        """
        On "Clear" menu press, resets the selected file path and empties the
        output box
        """

        self.selected_file.set("")
        self.clear_output()

    ###########################################################################
    ###           InventoryAppDisplay -> get_selected_columns()              ###
    ###########################################################################
    def get_selected_columns(self) -> dict:
        """
        Snapshots the checkbox state into the dict the spreadsheet writers read to
        decide which columns to emit

        Returns:
            dict: A mapping of every column key to whether that column is included
        """

        # bool() is required, not cosmetic: the spreadsheet writers compare each
        # value against True with ==, which a BooleanVar would fail, silently
        # dropping the column from the report
        return {key: bool(var.get()) for key, var in self.column_vars.items()}

    ###########################################################################
    ###          InventoryAppDisplay -> handle_process_inventory()           ###
    ###########################################################################
    def handle_process_inventory(self):
        """
        On "Process This Inventory" button press, hands the selected file and the
        chosen columns to the process callback, after clearing any output left
        over from a previous run
        """

        file_path = self.selected_file.get()

        # Nothing to process until the user has chosen a file
        if not file_path:
            self.show_popup(
                "No File Selected",
                "Please choose a valid Inventory Availability PDF file!",
            )
            return

        self.clear_output()
        self.process_callback(file_path, self.get_selected_columns())

    ###########################################################################
    ###                InventoryAppDisplay -> write_output()                ###
    ###########################################################################
    def write_output(self, message: str):
        """
        Appends a status message to the output box and scrolls it into view

        Args:
            message (str): The status message to display to the user
        """

        if self.output_box is None:
            return

        self.output_box.insert(tk.END, f"{message}\n")
        self.output_box.see(tk.END)

        # Repaint now rather than at the next idle moment: processing runs on the
        # GUI thread, so without this a status message would not appear until the
        # work it announces has already finished
        self.output_box.update_idletasks()

    ###########################################################################
    ###                InventoryAppDisplay -> clear_output()                ###
    ###########################################################################
    def clear_output(self):
        """
        Empties the output box, so each run starts from a clean slate
        """

        if self.output_box is None:
            return

        self.output_box.delete(1.0, tk.END)

    ###########################################################################
    ###                 InventoryAppDisplay -> show_popup()                 ###
    ###########################################################################
    def show_popup(self, title: str, message: str):
        """
        Shows the user a short message in a themed popup window

        Args:
            title (str): Title of the popup window
            message (str): The message to display to the user
        """

        # Use a themed window (rather than tkinter's native messagebox) so the
        # popup matches the application's styling and centers over the application
        # window instead of the screen
        MessageWindow(
            parent=self,
            title=title,
            message=message,
            theme=self.current_theme,
            font_family=self.current_font_family,
            font_size=self.current_font_size,
        )

    ###########################################################################
    ###         InventoryAppDisplay -> _open_readonly_file_viewer()         ###
    ###########################################################################
    def _open_readonly_file_viewer(
        self, file_path: Path, title: str, missing_message: str
    ):
        """
        Opens a native, read-only window showing the given text file if it
        exists. Shows an error popup with the provided message if the file is
        not present.

        Args:
            file_path (Path): The text file to open for viewing
            title (str): The title to display on the viewer window
            missing_message (str): The popup message shown when the file does
                not exist
        """

        if file_path.exists():
            FileEditorWindow(
                parent=self,
                title=title,
                file_path=file_path,
                initial_text=self.read_file_callback(file_path),
                theme=self.current_theme,
                font_family=self.current_font_family,
                font_size=self.current_font_size,
                editable=False,
            )
        else:
            self.show_popup(title="File Not Found", message=missing_message)

    ###########################################################################
    ###            InventoryAppDisplay -> handle_results_log()              ###
    ###########################################################################
    def handle_results_log(self):
        """
        On "Results Log" menu press, opens the results log file in a native
        read-only viewer window if it exists. Shows an error popup if the file
        has not been created yet.
        """

        self._open_readonly_file_viewer(
            RESULTS_FILE,
            "Results Log",
            f"Log not found at: {RESULTS_FILE}. Process an inventory to generate the log.",
        )

    ###########################################################################
    ###           InventoryAppDisplay -> handle_open_inventories()          ###
    ###########################################################################
    def handle_open_inventories(self):
        """
        On "Inventories" menu press, opens a file dialog rooted at the
        inventory availability directory so the user can browse its contents
        """

        filedialog.askopenfilename(
            initialdir=str(INVENTORY_DIR),
            title="Inventories",
            filetypes=[("PDF files", "*.pdf")],
        )

    ###########################################################################
    ###        InventoryAppDisplay -> handle_open_turnover_reports()        ###
    ###########################################################################
    def handle_open_turnover_reports(self):
        """
        On "Turnover Reports" menu press, opens a file dialog rooted at the
        turnover reports directory so the user can browse its contents
        """

        filedialog.askopenfilename(
            initialdir=str(TURNOVER_DIR),
            title="Turnover Reports",
            filetypes=[("PDF files", "*.pdf")],
        )

    ###########################################################################
    ###                InventoryAppDisplay -> handle_about()                ###
    ###########################################################################
    def handle_about(self):
        """
        On "About" menu press, opens the About window showing the current
        application version, themed to match the rest of the application
        """

        AboutWindow(
            parent=self,
            title="About",
            version=VERSION,
            theme=self.current_theme,
            font_family=self.current_font_family,
            font_size=self.current_font_size,
        )

    ###########################################################################
    ###                 InventoryAppDisplay -> apply_theme()                ###
    ###########################################################################
    def apply_theme(self, theme: Theme):
        """
        Applies a color theme to every widget in the application

        Args:
            theme (Theme): The theme to apply
        """

        self.current_theme = theme

        self.configure(bg=theme.bg_main)
        self.title_label.configure(bg=theme.bg_main, fg=theme.label_fg)
        self.file_frame.configure(bg=theme.bg_main)
        self.file_entry.configure(
            bg=theme.bg_entry, fg=theme.bg_main, insertbackground=theme.fg_text
        )
        self.browse_button.configure(
            bg=theme.button_bg,
            fg=theme.button_fg,
            activebackground=theme.accent,
            activeforeground=theme.fg_text,
        )
        self.inventory_label.configure(bg=theme.bg_main, fg=theme.label_fg)
        self.inventory_frame.configure(bg=theme.bg_main)
        self.turnover_label.configure(bg=theme.bg_main, fg=theme.label_fg)
        self.turnover_frame.configure(bg=theme.bg_main)

        for checkbutton in self.column_checkbuttons.values():
            checkbutton.configure(
                bg=theme.bg_main,
                fg=theme.fg_text,
                activebackground=theme.bg_main,
                activeforeground=theme.accent,
                selectcolor=theme.bg_entry,
            )

        self.button_frame.configure(bg=theme.bg_main)
        self.process_inventory_button.configure(
            bg=theme.button_bg,
            fg=theme.button_fg,
            activebackground=theme.accent,
            activeforeground=theme.fg_text,
        )
        self.exit_button.configure(
            bg=theme.bg_entry,
            fg=theme.fg_text,
            activeforeground=theme.fg_text,
        )
        self.output_label.configure(bg=theme.bg_main, fg=theme.label_fg)
        self.output_box.configure(
            bg=theme.bg_entry, fg=theme.fg_text, insertbackground=theme.fg_text
        )

    ###########################################################################
    ###              InventoryAppDisplay -> apply_font_family()             ###
    ###########################################################################
    def apply_font_family(self, family: str):
        """
        Applies a font family to all text on screen

        Args:
            family (str): The font family to apply
        """

        self.current_font_family = family
        self._apply_font()

    ###########################################################################
    ###               InventoryAppDisplay -> apply_font_size()              ###
    ###########################################################################
    def apply_font_size(self, size: int):
        """
        Applies a font size to all text on screen

        Args:
            size (int): The font size to apply
        """

        self.current_font_size = size
        self._apply_font()

    ###########################################################################
    ###                 InventoryAppDisplay -> _apply_font()                ###
    ###########################################################################
    def _apply_font(self):
        """
        Applies the current font family and size to every widget in the
        application
        """

        font = (self.current_font_family, self.current_font_size, "bold")
        self.title_label.configure(font=font)
        self.browse_button.configure(font=font)
        self.inventory_label.configure(font=font)
        self.turnover_label.configure(font=font)
        self.process_inventory_button.configure(font=font)
        self.exit_button.configure(font=font)
        self.output_label.configure(font=font)
        self.output_box.configure(font=font)

        # Checkbuttons use a non-bold font, matching _build_checkbutton()
        checkbutton_font = (self.current_font_family, self.current_font_size)
        for checkbutton in self.column_checkbuttons.values():
            checkbutton.configure(font=checkbutton_font)
