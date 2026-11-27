"""Read-only profiling of the spreadsheet attached to a single chat turn."""

import csv
import re
from collections import Counter
from collections.abc import Iterable
from datetime import date
from decimal import Decimal, localcontext
from io import BytesIO, StringIO
from pathlib import PurePath
from statistics import median
from uuid import UUID
from zipfile import BadZipFile, ZipFile

from openpyxl import load_workbook
from openpyxl.utils.cell import column_index_from_string, coordinate_from_string, get_column_letter
from openpyxl.utils.exceptions import CellCoordinatesException, InvalidFileException
from openpyxl.worksheet._read_only import ReadOnlyWorksheet
from openpyxl.xml.functions import iterparse
from sqlalchemy.orm import Session

from nortpole.db.models import UserFile
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.file_store.models import ChatFileType, FileDescriptor
from nortpole.file_store.utils import get_default_file_store


MAX_BYTES = 1024 * 1024
MAX_EXPANDED_BYTES = 8 * MAX_BYTES
MAX_ROWS = 5_000
MAX_COLUMNS = 24
MAX_SHEETS = 5
_NUMBER = re.compile(r"[+-]?(?:[0-9]{1,22}(?:\.[0-9]{1,12})?|\.[0-9]{1,12})(?:[eE][+-]?[0-9]{1,2})?")
_UNAVAILABLE = object()


def _invalid(message: str) -> NortPoleError:
    return NortPoleError(NortPoleErrorCode.INVALID_INPUT, message)


def spreadsheet_attachment(
    files: list[FileDescriptor], user_id: UUID, chat_id: UUID, private: bool, db: Session,
) -> FileDescriptor:
    if len(files) != 1 or not files[0].get("user_file_id"):
        raise _invalid("Attach one CSV or XLSX file from your uploads.")
    submitted = files[0]
    try:
        file_id = UUID(submitted["user_file_id"] or "")
    except ValueError:
        raise _invalid("Attach one CSV or XLSX file from your uploads.") from None
    file = db.get(UserFile, file_id)
    if (
        file is None or file.user_id != user_id or file.file_id != submitted["id"]
        or file.incognito != private
        or (private and file.incognito_session_id not in (None, chat_id))
    ):
        raise NortPoleError(NortPoleErrorCode.INSUFFICIENT_PERMISSIONS, "The selected spreadsheet is unavailable.")
    if PurePath(file.name).suffix.lower() not in {".csv", ".xlsx"}:
        raise _invalid("Attach a UTF-8 CSV or an XLSX workbook.")
    return FileDescriptor(id=file.file_id, user_file_id=str(file.id), type=ChatFileType.TABULAR, name=file.name)


def _safe(value: object) -> str:
    text = " ".join(str(value).split())[:100]
    return re.sub(r"([\\`*_{}\[\]<>|!#~&])", lambda match: "\\" + match[0], text)


def _numeric(value: object) -> Decimal | None:
    if isinstance(value, (bool, date)):
        return None
    text = str(value).strip()
    if not _NUMBER.fullmatch(text):
        return None
    number = Decimal(text)
    # Bound scale as well as input length for exact, inexpensive arithmetic.
    if number and (not -24 <= number.adjusted() <= 24 or number.as_tuple().exponent < -30):
        return None
    return number


def _blank(value: object) -> bool:
    return value is None or isinstance(value, str) and not value.strip()


def _number_text(number: Decimal) -> str:
    whole, dot, fraction = format(number, "f").partition(".")
    fraction = fraction.rstrip("0")
    return whole + dot + fraction if fraction else whole


def _analyze_sheet(name: str, rows: Iterable[tuple], *, csv_rows: bool = False) -> list[str]:
    iterator = iter(rows)
    try:
        headers = next(iterator)
    except StopIteration:
        return []
    width = len(headers)
    if width > MAX_COLUMNS:
        raise _invalid(f"Each sheet can have up to {MAX_COLUMNS} columns.")
    if not width or all(_blank(value) for value in headers):
        return []

    records: list[tuple[int, tuple]] = []
    for number, row in enumerate(iterator, start=2):
        if number > MAX_ROWS + 1:
            raise _invalid(f"Each sheet can have up to {MAX_ROWS:,} data rows.")
        if len(row) > width:
            raise _invalid("A spreadsheet row has more cells than its header. Check the first row and retry.")
        if not all(_blank(value) for value in row):
            records.append((number, row + (None,) * (width - len(row))))
    row_kind = "CSV record" if csv_rows else "row"
    result = [f"### {_safe(name)}", f"**{len(records):,} data rows** across **{width} columns**. The first row is the header."]
    seen: set[tuple] = set()
    duplicates: list[int] = []
    for number, row in records:
        if _UNAVAILABLE in row:
            continue
        signature = tuple((type(value), value) for value in row)
        if signature in seen:
            duplicates.append(number)
        seen.add(signature)
    if duplicates:
        sample = ", ".join(map(str, duplicates[:5]))
        result.append(f"Duplicate rows after the first occurrence: {len(duplicates)} (first {row_kind} references: {sample}).")
    formulas = sum(value is _UNAVAILABLE for _, row in records for value in row)
    if formulas:
        result.append(f"Formula or error cells skipped: {formulas}. Use a values-only copy to include these cells.")
    if not records:
        return result

    result.extend([
        "",
        "| Column | Missing | Supported numeric values | Total | Min / Max | Change from first to last |",
        "| --- | ---: | ---: | ---: | --- | ---: |",
    ])
    exceptions = []
    with localcontext() as context:
        context.prec = 64
        for index, header in enumerate(headers):
            column = get_column_letter(index + 1)
            label = f"{column} · {_safe(header)}" if not _blank(header) and header is not _UNAVAILABLE else column
            cells = [(row_id, row[index]) for row_id, row in records]
            missing = sum(_blank(value) for _, value in cells)
            values = [(row_id, number) for row_id, value in cells if (number := _numeric(value)) is not None]
            skipped = sum(value is _UNAVAILABLE for _, value in cells)
            if not values or len(values) + missing + skipped != len(cells):
                result.append(f"| {label} | {missing} | {len(values)} | — | — | — |")
                continue
            numbers = [number for _, number in values]
            low, high = min(numbers), max(numbers)
            total = _number_text(sum(numbers, Decimal(0)))
            delta = _number_text(numbers[-1] - numbers[0]) if len(numbers) > 1 else "—"
            result.append(f"| {label} | {missing} | {len(values)} | {total} | {_number_text(low)} / {_number_text(high)} | {delta} |")
            if len(numbers) >= 8:
                ordered = sorted(numbers)
                half = len(ordered) // 2
                q1, q3 = median(ordered[:half]), median(ordered[-half:])
                spread = (q3 - q1) * Decimal("1.5")
                unusual = [row_id for row_id, value in values if value < q1 - spread or value > q3 + spread]
                if unusual:
                    sample = ", ".join(map(str, unusual[:5]))
                    exceptions.append(f"- Column {column}: {len(unusual)} potential outliers (first {row_kind} references: {sample}).")
    if exceptions:
        result.extend(["", "**Potential outliers using the 1.5 × IQR rule**", *exceptions])
    return result


def _sheet_dimensions(sheet: ReadOnlyWorksheet) -> tuple[int, int]:
    # The workbook's advertised dimensions may be missing or stale. Bound the
    # actual coordinates before openpyxl expands sparse rows into tuples.
    width = height = row = column = 0
    with sheet._get_source() as source:
        for event, element in iterparse(source, events=("start", "end")):
            if event == "end":
                element.clear()
                continue
            tag = element.tag.rsplit("}", 1)[-1]
            if tag == "row":
                row = int(element.get("r") or row + 1)
                column = 0
                height = max(height, row)
            elif tag == "c":
                coordinate = element.get("r")
                if coordinate:
                    column_name, cell_row = coordinate_from_string(coordinate)
                    column = column_index_from_string(column_name)
                    height = max(height, cell_row)
                else:
                    column += 1
                width = max(width, column)
            if width > MAX_COLUMNS or height > MAX_ROWS + 1:
                raise _invalid(f"Each sheet can have up to {MAX_ROWS:,} data rows and {MAX_COLUMNS} columns.")
    return width, height


def analyze_spreadsheet(raw: bytes, filename: str) -> str:
    if len(raw) > MAX_BYTES:
        raise _invalid("Attach a spreadsheet up to 1 MB.")
    try:
        if PurePath(filename).suffix.lower() == ".csv":
            reader = csv.reader(StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
            report = _analyze_sheet("CSV", map(tuple, reader), csv_rows=True)
        else:
            source = BytesIO(raw)
            with ZipFile(source) as archive:
                if sum(item.file_size for item in archive.infolist()) > MAX_EXPANDED_BYTES:
                    raise _invalid("This workbook is too large when opened. Save a smaller copy and retry.")
            source.seek(0)
            workbook = load_workbook(source, read_only=True, data_only=False, keep_links=False)
            try:
                sheets = [sheet for sheet in workbook.worksheets if sheet.sheet_state == "visible"]
                if len(sheets) > MAX_SHEETS:
                    raise _invalid(f"Attach a workbook with up to {MAX_SHEETS} visible sheets.")
                report = []
                for sheet in sheets:
                    width, height = _sheet_dimensions(sheet)
                    if not width or not height:
                        continue
                    rows = (
                        tuple(_UNAVAILABLE if cell.data_type in {"f", "e"} else cell.value for cell in row)
                        for row in sheet.iter_rows(max_col=width, max_row=height)
                    )
                    section = _analyze_sheet(sheet.title, rows)
                    if section:
                        report.extend([*section, ""])
            finally:
                workbook.close()
    except (csv.Error, BadZipFile, InvalidFileException, CellCoordinatesException, ValueError, KeyError, SyntaxError) as error:
        raise _invalid("Could not read the spreadsheet. Save it as a UTF-8 CSV or a valid XLSX workbook.") from error
    if not report:
        raise _invalid("The spreadsheet has no readable header row.")
    return "\n".join([
        f"## Spreadsheet analysis · {_safe(filename)}", "", *report, "",
        "Change uses row order. Totals use supported plain numbers and skip blanks, formulas, and error cells.",
    ])


def load_spreadsheet_analysis(descriptor: FileDescriptor) -> str:
    store = get_default_file_store()
    try:
        with store.read_file(descriptor["id"], mode="b") as source:
            raw = source.read(MAX_BYTES + 1)
    except FileNotFoundError as error:
        raise _invalid("The attached spreadsheet could not be opened. Attach it again.") from error
    return analyze_spreadsheet(raw, descriptor.get("name") or "")
