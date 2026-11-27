from io import BytesIO
from unittest.mock import Mock
from uuid import uuid4

import pytest
from openpyxl import Workbook

from nortpole.chat.spreadsheet_analysis import analyze_spreadsheet, spreadsheet_attachment
from nortpole.db.models import UserFile
from nortpole.error_handling.error_codes import NortPoleErrorCode
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.file_store.models import ChatFileType


def test_csv_totals_duplicates_gaps_and_outliers_have_record_references() -> None:
    report = analyze_spreadsheet(
        b"Amount,Team\n0.1,A\n0.1,A\n0.2,B\n0.2,B\n0.2,C\n0.3,D\n0.3,E\n9.4,F\n,G\n",
        "week.csv",
    )
    assert "| A · Amount | 1 | 8 | 10.8 | 0.1 / 9.4 | 9.3 |" in report
    assert "Duplicate rows after the first occurrence: 2 (first CSV record references: 3, 5)." in report
    assert "Column A: 1 potential outliers (first CSV record references: 9)." in report


def test_xlsx_is_read_only_and_reports_only_visible_sheets_and_static_values() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Support"
    sheet.append(["Tickets", "Ratio"])
    sheet.append([4, "=A2/2"])
    sheet.append([6, 3])
    hidden = workbook.create_sheet("Restricted summary")
    hidden.sheet_state = "hidden"
    hidden.append(["Leak"])
    hidden.append([99999])
    data = BytesIO()
    workbook.save(data)
    workbook.close()

    report = analyze_spreadsheet(data.getvalue(), "week.xlsx")
    assert "| A · Tickets | 0 | 2 | 10 | 4 / 6 | 2 |" in report
    assert "Formula or error cells skipped: 1" in report
    assert "Restricted summary" not in report
    assert "99999" not in report


@pytest.mark.parametrize(("data", "name", "detail"), [
    (b"", "empty.csv", "no readable header"),
    (b"A\n1,2", "ragged.csv", "more cells"),
    (b"\xff", "bad.csv", "Could not read"),
    (b"not a zip", "bad.xlsx", "Could not read"),
    (b"A\n" + b"1\n" * 5001, "long.csv", "5,000 data rows"),
    (b"x" * (1024 * 1024 + 1), "large.csv", "up to 1 MB"),
])
def test_invalid_or_oversized_spreadsheets_return_helpful_errors(data: bytes, name: str, detail: str) -> None:
    with pytest.raises(NortPoleError, match=detail) as error:
        analyze_spreadsheet(data, name)
    assert error.value.error_code == NortPoleErrorCode.INVALID_INPUT


def test_attachment_uses_canonical_name_and_checks_owner_and_privacy() -> None:
    owner, stranger, chat_id, file_id = uuid4(), uuid4(), uuid4(), uuid4()
    db = Mock()
    record = UserFile(id=file_id, user_id=owner, file_id="object", name="Actual.csv", incognito=False)
    db.get.return_value = record
    submitted = [{"id": "object", "name": "spoof.xlsx", "type": ChatFileType.DOC, "user_file_id": str(file_id)}]
    allowed = spreadsheet_attachment(submitted, owner, chat_id, False, db)
    assert allowed["name"] == "Actual.csv"
    assert allowed["type"] == ChatFileType.TABULAR
    for user, is_private in ((stranger, False), (owner, True)):
        with pytest.raises(NortPoleError) as error:
            spreadsheet_attachment(submitted, user, chat_id, is_private, db)
        assert error.value.error_code == NortPoleErrorCode.INSUFFICIENT_PERMISSIONS
    record.incognito = True
    record.incognito_session_id = uuid4()
    with pytest.raises(NortPoleError, match="unavailable"):
        spreadsheet_attachment(submitted, owner, chat_id, True, db)
