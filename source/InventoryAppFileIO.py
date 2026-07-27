import pypdf
import xlsxwriter
from pathlib import Path
from typing import Callable, Optional

from source.constants import INVENTORY_DIR, RESULTS_FILE, TURNOVER_DIR


# InventoryAppFileIO class to handle all file input/output operations
class InventoryAppFileIO:

    ###########################################################################
    ###                 InventoryAppFileIO -> __init__()                    ###
    ###########################################################################
    def __init__(
        self, report_error: Callable[[str, str], None] = lambda *_: None
    ):
        """
        Initializes the InventoryAppFileIO object

        Args:
            report_error (Callable[[str, str], None]): Callback used to surface a
                file I/O failure to the user, taking an error title and message.
                Defaults to a no-op so file I/O never depends on a reporter being
                wired in (the controller injects the GUI's error reporter)
        """

        # Callback used to report file I/O failures to the user
        self.report_error = report_error

    ###########################################################################
    ###            InventoryAppFileIO -> reset_results_file()               ###
    ###########################################################################
    def reset_results_file(self) -> None:
        """
        Clears the results file so each run starts with a clean log, creating the
        logs directory if it does not yet exist
        """

        try:
            RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            RESULTS_FILE.write_text("", encoding="utf-8")

        except OSError:
            self.report_error(
                "File Error",
                f"Could not write to the results file: {RESULTS_FILE}",
            )
            pass

    ###########################################################################
    ###           InventoryAppFileIO -> write_to_results_file()             ###
    ###########################################################################
    def write_to_results_file(self, contents: str) -> None:
        """
        Writes a line to the results file, which holds the inventory/turnover
        processing output the app would otherwise print to the terminal. Errors are
        not written here — they go to the GUI via report_error.

        Args:
            contents (str): The text to append (a trailing newline is added)
        """

        try:
            # mkdir is a safety net in case reset_results_file could not create it
            RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(RESULTS_FILE, "a", encoding="utf-8") as f:
                f.write(contents + "\n")

        except OSError:
            self.report_error(
                "File Error",
                f"Could not write to the results file: {RESULTS_FILE}",
            )

    ###########################################################################
    ###                  InventoryAppFileIO -> read_pdf()                   ###
    ###########################################################################
    def read_pdf(self, filepath) -> list:
        """
        Reads every page of a PDF into a list of strings, one string per page.
        Backs both inventory and turnover reads since the two are identical.

        Args:
            filepath: The path to the PDF to read

        Returns:
            list: One string of page text per page, or an empty list if the PDF
                could not be read
        """

        try:
            pdf = pypdf.PdfReader(stream=filepath)

            # Layout mode preserves the horizontal spacing that separates one
            # column from the next; the default mode runs adjacent columns
            # together and is unusable for a table
            pages = []
            for page in pdf.pages:
                pages.append(page.extract_text(extraction_mode="layout"))

            return pages

        except (OSError, pypdf.errors.PdfReadError) as error:
            self.report_error(
                "File Error",
                f"Could not read the PDF at {filepath}: {error}",
            )
            return []

    ###########################################################################
    ###            InventoryAppFileIO -> list_inventory_files()             ###
    ###########################################################################
    def list_inventory_files(self) -> list:
        """
        Lists the inventory availability PDFs found in the inventory directory

        Returns:
            list: A sorted list of full Paths to the *.pdf files in the inventory
                directory, or an empty list if the directory is missing or could
                not be read
        """

        try:
            # Only return PDFs (the directory may hold other files), sorted by name so
            # the inventory files are processed in the same order on every platform
            # (Path comparison is case-insensitive on Windows, case-sensitive on POSIX)
            return sorted(
                (f for f in INVENTORY_DIR.iterdir() if f.suffix.lower() == ".pdf"),
                key=lambda f: f.name,
            )

        except OSError as error:
            self.report_error(
                "File Error",
                f"Could not read the inventory directory at {INVENTORY_DIR}: {error}",
            )
            return []

    ###########################################################################
    ###             InventoryAppFileIO -> list_turnover_files()             ###
    ###########################################################################
    def list_turnover_files(self) -> list:
        """
        Lists the turnover report PDFs found in the turnover reports directory

        Returns:
            list: A sorted list of full Paths to the *.pdf files in the turnover
                directory, or an empty list if the directory is missing or could
                not be read
        """

        try:
            # Only return PDFs (the directory may hold other files), sorted by name so
            # the turnover columns are emitted in the same order on every platform
            return sorted(
                (f for f in TURNOVER_DIR.iterdir() if f.suffix.lower() == ".pdf"),
                key=lambda f: f.name,
            )

        except OSError as error:
            self.report_error(
                "File Error",
                f"Could not read the turnover reports directory at {TURNOVER_DIR}: {error}",
            )
            return []

    ###########################################################################
    ###               InventoryAppFileIO -> create_workbook()               ###
    ###########################################################################
    def create_workbook(self, filename: str) -> Optional[xlsxwriter.Workbook]:
        """
        Opens an xlsxwriter Workbook for the output spreadsheet

        Args:
            filename (str): The output filename (without extension); ".xlsx" is appended

        Returns:
            Optional[xlsxwriter.Workbook]: The open workbook, or None if it could not
                be created (the failure is also surfaced via report_error)
        """

        output_path = Path(filename + ".xlsx")

        try:
            # Ensure the output directory exists before opening the workbook
            output_path.parent.mkdir(parents=True, exist_ok=True)
            return xlsxwriter.Workbook(str(output_path))

        except (OSError, xlsxwriter.exceptions.XlsxWriterException) as error:
            self.report_error(
                "File Error",
                f"Could not create the output spreadsheet at {output_path}: {error}",
            )
            return None

    ###########################################################################
    ###                InventoryAppFileIO -> save_workbook()                ###
    ###########################################################################
    def save_workbook(self, workbook: xlsxwriter.Workbook) -> bool:
        """
        Saves and closes the output workbook, committing it to disk

        Args:
            workbook (xlsxwriter.Workbook): The workbook to save and close

        Returns:
            bool: True if the workbook was saved, False if it could not be written
                (the failure is also surfaced via report_error)
        """

        try:
            # close() is where xlsxwriter flushes the spreadsheet to disk
            workbook.close()
            return True

        except (OSError, xlsxwriter.exceptions.XlsxWriterException) as error:
            self.report_error(
                "File Error",
                f"Could not save the output spreadsheet: {error}",
            )
            return False
