from pathlib import Path
from unittest.mock import MagicMock, patch

import pypdf
import pytest
import xlsxwriter

from source.inventory_app_file_io import InventoryAppFileIO


@pytest.fixture
def file_io():
    """
    Test fixture to set up an InventoryAppFileIO object for testing to maximize
    code reuse. The error reporter is a mock so failure paths can assert that the
    failure was surfaced to the user.
    """

    return InventoryAppFileIO(report_error=MagicMock())


def test_init_default_report_error_is_a_noop():
    """
    Tests that an InventoryAppFileIO built without an error reporter still has a
    callable report_error, so file I/O never depends on a reporter being wired in.
    """

    # The object is constructed without injecting an error reporter
    default_file_io = InventoryAppFileIO()

    # The default callback accepts a title and message and does nothing
    assert default_file_io.report_error("File Error", "some message") is None


def test_init_stores_the_injected_report_error(file_io):
    """
    Tests that the injected error reporter is stored on the object so every
    failure path can surface through it.

    Args:
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # The fixture injects a mock error reporter
    file_io.report_error("File Error", "some message")

    # The injected callback is the one that gets called
    file_io.report_error.assert_called_once_with("File Error", "some message")


@patch("source.inventory_app_file_io.RESULTS_FILE")
def test_reset_results_file_deletes_an_existing_file(mock_results_file, file_io):
    """
    Tests that reset_results_file() ensures the logs directory exists and deletes
    the results file when one is present, so each run starts with no log until
    something is actually processed.

    Args:
        mock_results_file (unittest.mock.MagicMock): Mocks the RESULTS_FILE constant
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # A results file from a previous run is present
    mock_results_file.is_file.return_value = True

    file_io.reset_results_file()

    # The logs directory is ensured and the existing file is deleted
    mock_results_file.parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_results_file.unlink.assert_called_once_with()
    file_io.report_error.assert_not_called()


@patch("source.inventory_app_file_io.RESULTS_FILE")
def test_reset_results_file_does_nothing_when_no_file_exists(mock_results_file, file_io):
    """
    Tests that reset_results_file() does not attempt to delete a results file
    that is not present, while still ensuring the logs directory exists.

    Args:
        mock_results_file (unittest.mock.MagicMock): Mocks the RESULTS_FILE constant
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # No results file exists yet (e.g. a fresh checkout)
    mock_results_file.is_file.return_value = False

    file_io.reset_results_file()

    # The directory is ensured but nothing is deleted
    mock_results_file.parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_results_file.unlink.assert_not_called()
    file_io.report_error.assert_not_called()


@patch("source.inventory_app_file_io.RESULTS_FILE")
def test_reset_results_file_reports_on_error(mock_results_file, file_io):
    """
    Tests that reset_results_file() swallows a deletion failure and surfaces it to
    the user instead of crashing the app.

    Args:
        mock_results_file (unittest.mock.MagicMock): Mocks the RESULTS_FILE constant
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # Deleting the existing results file fails
    mock_results_file.is_file.return_value = True
    mock_results_file.unlink.side_effect = OSError("permission denied")

    # No exception is raised, and the failure is reported to the user
    file_io.reset_results_file()
    file_io.report_error.assert_called_once()


def test_write_to_results_file_appends_with_newline(tmp_path, file_io):
    """
    Tests that write_to_results_file() appends each line to the results file with a
    trailing newline, creating the logs directory if it does not exist yet.

    Args:
        tmp_path (pathlib.Path): pytest's per-test temporary directory
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # Two lines are written to a results file whose parent directory does not exist
    results_file = tmp_path / "logs" / "results.txt"
    with patch("source.inventory_app_file_io.RESULTS_FILE", results_file):
        file_io.write_to_results_file("some processing output")
        file_io.write_to_results_file("more processing output")

    # Both landed in order, each terminated by a newline, and nothing was reported
    assert results_file.read_text(encoding="utf-8") == "some processing output\nmore processing output\n"
    file_io.report_error.assert_not_called()


def test_write_to_results_file_reports_on_error(tmp_path, file_io):
    """
    Tests that write_to_results_file() swallows a write failure and surfaces it to
    the user instead of crashing the app.

    Args:
        tmp_path (pathlib.Path): pytest's per-test temporary directory
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # A directory occupies the results file's path, so opening it for append fails
    # the way an unwritable location would
    results_file = tmp_path / "logs" / "results.txt"
    results_file.mkdir(parents=True)

    # No exception is raised, and the failure is reported to the user
    with patch("source.inventory_app_file_io.RESULTS_FILE", results_file):
        file_io.write_to_results_file("some processing output")

    file_io.report_error.assert_called_once()


def test_read_text_file_returns_contents(tmp_path, file_io):
    """
    Tests that read_text_file() returns the full contents of the given text file.

    Args:
        tmp_path (pathlib.Path): pytest's per-test temporary directory
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    text_file = tmp_path / "results.txt"
    text_file.write_text("log contents\nsecond line\n")

    # Every line is returned as one string, not just the first
    assert file_io.read_text_file(text_file) == "log contents\nsecond line\n"
    file_io.report_error.assert_not_called()


def test_read_text_file_reports_and_returns_empty_string_on_error(tmp_path, file_io):
    """
    Tests that read_text_file() returns an empty string and surfaces the failure
    when the text file cannot be read.

    Args:
        tmp_path (pathlib.Path): pytest's per-test temporary directory
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # The file does not exist, so an empty string comes back and the failure is
    # reported to the user
    assert file_io.read_text_file(tmp_path / "missing.txt") == ""
    file_io.report_error.assert_called_once()


@patch("source.inventory_app_file_io.pypdf.PdfReader")
def test_read_pdf_extracts_each_page_in_layout_mode(mock_pdf_reader, file_io):
    """
    Tests that read_pdf() returns one string per page, extracted in layout mode.
    Layout mode is mandatory because the parser relies on the horizontal spacing
    that the default extraction mode discards.

    Args:
        mock_pdf_reader (unittest.mock.MagicMock): Mocks pypdf.PdfReader
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # The PDF holds two pages of text
    first_page = MagicMock()
    first_page.extract_text.return_value = "first page text"
    second_page = MagicMock()
    second_page.extract_text.return_value = "second page text"
    mock_pdf_reader.return_value.pages = [first_page, second_page]

    # Each page is extracted in layout mode and returned in order
    assert file_io.read_pdf(Path("InventoryAvailability/report.pdf")) == [
        "first page text",
        "second page text",
    ]
    mock_pdf_reader.assert_called_once_with(stream=Path("InventoryAvailability/report.pdf"))
    first_page.extract_text.assert_called_once_with(extraction_mode="layout")
    second_page.extract_text.assert_called_once_with(extraction_mode="layout")
    file_io.report_error.assert_not_called()


@patch("source.inventory_app_file_io.pypdf.PdfReader")
def test_read_pdf_returns_empty_for_a_pdf_with_no_pages(mock_pdf_reader, file_io):
    """
    Tests that read_pdf() returns an empty list for a readable PDF that holds no
    pages, without reporting an error.

    Args:
        mock_pdf_reader (unittest.mock.MagicMock): Mocks pypdf.PdfReader
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # The PDF opens successfully but holds no pages
    mock_pdf_reader.return_value.pages = []

    # An empty list is returned and no failure is reported
    assert file_io.read_pdf(Path("InventoryAvailability/empty.pdf")) == []
    file_io.report_error.assert_not_called()


@patch(
    "source.inventory_app_file_io.pypdf.PdfReader",
    side_effect=OSError("file not found"),
)
def test_read_pdf_reports_and_returns_empty_on_os_error(_mock_pdf_reader, file_io):
    """
    Tests that read_pdf() returns an empty list and surfaces the failure when the
    PDF cannot be opened.

    Args:
        _mock_pdf_reader (unittest.mock.MagicMock): Mocks pypdf.PdfReader to raise
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # An empty list is returned and the failure is reported to the user
    assert file_io.read_pdf(Path("InventoryAvailability/missing.pdf")) == []
    file_io.report_error.assert_called_once()


@patch(
    "source.inventory_app_file_io.pypdf.PdfReader",
    side_effect=pypdf.errors.PdfReadError("corrupt PDF"),
)
def test_read_pdf_reports_and_returns_empty_on_pdf_read_error(_mock_pdf_reader, file_io):
    """
    Tests that read_pdf() returns an empty list and surfaces the failure when the
    file exists but is not a readable PDF.

    Args:
        _mock_pdf_reader (unittest.mock.MagicMock): Mocks pypdf.PdfReader to raise
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # An empty list is returned and the failure is reported to the user
    assert file_io.read_pdf(Path("InventoryAvailability/corrupt.pdf")) == []
    file_io.report_error.assert_called_once()


@patch("source.inventory_app_file_io.INVENTORY_DIR")
def test_list_inventory_files_returns_only_pdfs(mock_inventory_dir, file_io):
    """
    Tests that list_inventory_files() drops the non-PDF entries the inventory
    directory may also hold.

    Args:
        mock_inventory_dir (unittest.mock.MagicMock): Mocks the INVENTORY_DIR constant
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # The directory holds a mix of PDFs and other files
    mock_inventory_dir.iterdir.return_value = [
        Path("InventoryAvailability/inventory.pdf"),
        Path("InventoryAvailability/notes.txt"),
        Path("InventoryAvailability/README"),
    ]

    # Only the PDF is returned, as a full path ready to read
    assert file_io.list_inventory_files() == [Path("InventoryAvailability/inventory.pdf")]
    file_io.report_error.assert_not_called()


@patch("source.inventory_app_file_io.INVENTORY_DIR")
def test_list_inventory_files_matches_suffix_case_insensitively(mock_inventory_dir, file_io):
    """
    Tests that list_inventory_files() includes an uppercase .PDF extension, since
    the report exporter's casing is not guaranteed.

    Args:
        mock_inventory_dir (unittest.mock.MagicMock): Mocks the INVENTORY_DIR constant
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # The directory holds a PDF with an uppercase extension
    mock_inventory_dir.iterdir.return_value = [Path("InventoryAvailability/inventory.PDF")]

    # The uppercase extension is matched just like a lowercase one
    assert file_io.list_inventory_files() == [Path("InventoryAvailability/inventory.PDF")]


@patch("source.inventory_app_file_io.INVENTORY_DIR")
def test_list_inventory_files_sorts_by_name(mock_inventory_dir, file_io):
    """
    Tests that list_inventory_files() sorts by filename rather than relying on
    Path ordering, so the files are processed in the same order on every platform
    and the results file stays diffable against the canonical results.

    Args:
        mock_inventory_dir (unittest.mock.MagicMock): Mocks the INVENTORY_DIR constant
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # The directory yields the PDFs out of order and in mixed case
    mock_inventory_dir.iterdir.return_value = [
        Path("InventoryAvailability/c.pdf"),
        Path("InventoryAvailability/A.pdf"),
        Path("InventoryAvailability/b.pdf"),
    ]

    # The list is sorted by the bare filename
    assert file_io.list_inventory_files() == [
        Path("InventoryAvailability/A.pdf"),
        Path("InventoryAvailability/b.pdf"),
        Path("InventoryAvailability/c.pdf"),
    ]


@patch("source.inventory_app_file_io.INVENTORY_DIR")
def test_list_inventory_files_reports_and_returns_empty_on_error(mock_inventory_dir, file_io):
    """
    Tests that list_inventory_files() returns an empty list and surfaces the
    failure when the inventory directory is missing or unreadable.

    Args:
        mock_inventory_dir (unittest.mock.MagicMock): Mocks the INVENTORY_DIR constant
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # The inventory directory cannot be read
    mock_inventory_dir.iterdir.side_effect = OSError("no such directory")

    # An empty list is returned and the failure is reported to the user
    assert file_io.list_inventory_files() == []
    file_io.report_error.assert_called_once()


@patch("source.inventory_app_file_io.TURNOVER_DIR")
def test_list_turnover_files_returns_only_pdfs(mock_turnover_dir, file_io):
    """
    Tests that list_turnover_files() drops the non-PDF entries the turnover
    reports directory may also hold.

    Args:
        mock_turnover_dir (unittest.mock.MagicMock): Mocks the TURNOVER_DIR constant
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # The directory holds a mix of PDFs and other files
    mock_turnover_dir.iterdir.return_value = [
        Path("TurnoverReports/turnover.pdf"),
        Path("TurnoverReports/notes.txt"),
        Path("TurnoverReports/README"),
    ]

    # Only the PDF is returned, as a full path ready to read
    assert file_io.list_turnover_files() == [Path("TurnoverReports/turnover.pdf")]
    file_io.report_error.assert_not_called()


@patch("source.inventory_app_file_io.TURNOVER_DIR")
def test_list_turnover_files_matches_suffix_case_insensitively(mock_turnover_dir, file_io):
    """
    Tests that list_turnover_files() includes an uppercase .PDF extension, since
    the report exporter's casing is not guaranteed.

    Args:
        mock_turnover_dir (unittest.mock.MagicMock): Mocks the TURNOVER_DIR constant
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # The directory holds a PDF with an uppercase extension
    mock_turnover_dir.iterdir.return_value = [Path("TurnoverReports/turnover.PDF")]

    # The uppercase extension is matched just like a lowercase one
    assert file_io.list_turnover_files() == [Path("TurnoverReports/turnover.PDF")]


@patch("source.inventory_app_file_io.TURNOVER_DIR")
def test_list_turnover_files_sorts_by_name(mock_turnover_dir, file_io):
    """
    Tests that list_turnover_files() sorts by filename rather than relying on Path
    ordering, so the turnover columns are emitted in the same order on every
    platform and the results file stays diffable against the canonical results.

    Args:
        mock_turnover_dir (unittest.mock.MagicMock): Mocks the TURNOVER_DIR constant
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # The directory yields the PDFs out of order and in mixed case
    mock_turnover_dir.iterdir.return_value = [
        Path("TurnoverReports/c.pdf"),
        Path("TurnoverReports/A.pdf"),
        Path("TurnoverReports/b.pdf"),
    ]

    # The list is sorted by the bare filename
    assert file_io.list_turnover_files() == [
        Path("TurnoverReports/A.pdf"),
        Path("TurnoverReports/b.pdf"),
        Path("TurnoverReports/c.pdf"),
    ]


@patch("source.inventory_app_file_io.TURNOVER_DIR")
def test_list_turnover_files_reports_and_returns_empty_on_error(mock_turnover_dir, file_io):
    """
    Tests that list_turnover_files() returns an empty list and surfaces the failure
    when the turnover reports directory is missing or unreadable.

    Args:
        mock_turnover_dir (unittest.mock.MagicMock): Mocks the TURNOVER_DIR constant
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # The turnover reports directory cannot be read
    mock_turnover_dir.iterdir.side_effect = OSError("no such directory")

    # An empty list is returned and the failure is reported to the user
    assert file_io.list_turnover_files() == []
    file_io.report_error.assert_called_once()


@patch("source.inventory_app_file_io.xlsxwriter.Workbook")
@patch("source.inventory_app_file_io.OUTPUT_DIR")
def test_create_workbook_appends_xlsx_extension(mock_output_dir, mock_workbook, file_io):
    """
    Tests that create_workbook() appends the .xlsx extension under the output
    directory, ensures that directory exists, and returns the open workbook.

    Args:
        mock_output_dir (unittest.mock.MagicMock): Mocks the output directory Path
        mock_workbook (unittest.mock.MagicMock): Mocks xlsxwriter.Workbook
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # The output path is the caller's extensionless filename under the output directory
    output_path = mock_output_dir.__truediv__.return_value

    # The extension is appended, the directory is ensured, and the workbook opens
    assert file_io.create_workbook("01-01-2026") is mock_workbook.return_value
    mock_output_dir.__truediv__.assert_called_once_with("01-01-2026.xlsx")
    output_path.parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_workbook.assert_called_once_with(str(output_path))
    file_io.report_error.assert_not_called()


@patch(
    "source.inventory_app_file_io.xlsxwriter.Workbook",
    side_effect=OSError("permission denied"),
)
def test_create_workbook_reports_and_returns_none_on_os_error(_mock_workbook, file_io):
    """
    Tests that create_workbook() returns None and surfaces the failure when the
    output spreadsheet cannot be created on disk.

    Args:
        _mock_workbook (unittest.mock.MagicMock): Mocks xlsxwriter.Workbook to raise
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # None is returned and the failure is reported to the user
    assert file_io.create_workbook("01-01-2026") is None
    file_io.report_error.assert_called_once()


@patch(
    "source.inventory_app_file_io.xlsxwriter.Workbook",
    side_effect=xlsxwriter.exceptions.XlsxWriterException("bad filename"),
)
def test_create_workbook_reports_and_returns_none_on_xlsxwriter_error(_mock_workbook, file_io):
    """
    Tests that create_workbook() returns None and surfaces the failure when
    xlsxwriter itself rejects the workbook.

    Args:
        _mock_workbook (unittest.mock.MagicMock): Mocks xlsxwriter.Workbook to raise
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # None is returned and the failure is reported to the user
    assert file_io.create_workbook("01-01-2026") is None
    file_io.report_error.assert_called_once()


def test_save_workbook_closes_and_returns_true(file_io):
    """
    Tests that save_workbook() closes the workbook, which is where xlsxwriter
    flushes the spreadsheet to disk, and reports success.

    Args:
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # A populated workbook is ready to be committed to disk
    mock_workbook = MagicMock(spec=xlsxwriter.Workbook)

    # The workbook is closed and success is reported
    assert file_io.save_workbook(mock_workbook) is True
    mock_workbook.close.assert_called_once()
    file_io.report_error.assert_not_called()


def test_save_workbook_reports_and_returns_false_on_os_error(file_io):
    """
    Tests that save_workbook() returns False and surfaces the failure when the
    spreadsheet cannot be written to disk.

    Args:
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # Writing the spreadsheet fails, e.g. the file is open in Excel
    mock_workbook = MagicMock(spec=xlsxwriter.Workbook)
    mock_workbook.close.side_effect = OSError("permission denied")

    # False is returned and the failure is reported to the user
    assert file_io.save_workbook(mock_workbook) is False
    file_io.report_error.assert_called_once()


def test_save_workbook_reports_and_returns_false_on_xlsxwriter_error(file_io):
    """
    Tests that save_workbook() returns False and surfaces the failure when
    xlsxwriter itself fails while committing the spreadsheet.

    Args:
        file_io (pytest.fixture): Test fixture to create the InventoryAppFileIO object
    """

    # xlsxwriter rejects the workbook while closing it
    mock_workbook = MagicMock(spec=xlsxwriter.Workbook)
    mock_workbook.close.side_effect = xlsxwriter.exceptions.XlsxWriterException("duplicate worksheet name")

    # False is returned and the failure is reported to the user
    assert file_io.save_workbook(mock_workbook) is False
    file_io.report_error.assert_called_once()
