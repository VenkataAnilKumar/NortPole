from nortpole.chat.verified_excerpts import select_excerpts
from nortpole.chat.verified_table_comparison import TableFinding, compare_tables
from nortpole.file_store.models import ContextFileMetadata


OLD_POLICY = """| Change type | Notice | Budget |
| --- | --- | --- |
| Standard change | 5 business days | $25 |
| Emergency change | 2 hours | $50 |
| Archive change | 1 calendar day | $75 |
"""

NEW_POLICY = """| Change type | Budget | Notice |
| --- | --- | --- |
| Standard change | $25.00 | 72 hours |
| Emergency change | EUR 50 | 3 hours |
"""


def test_matches_exact_row_labels_and_headers_across_reordered_columns():
    assert compare_tables("Compare selected tables", {"old": [OLD_POLICY], "new": [NEW_POLICY]}) == [
        TableFinding("Standard change · Notice", "5 business days", "72 hours", "Different or unclear units"),
        TableFinding("Standard change · Budget", "$25", "$25.00", "Same stated value"),
        TableFinding("Emergency change · Notice", "2 hours", "3 hours", "Different stated values"),
        TableFinding("Emergency change · Budget", "$50", "EUR 50", "Different or unclear units"),
        TableFinding("Archive change · Notice", "1 calendar day", None, "Missing evidence"),
        TableFinding("Archive change · Budget", "$75", None, "Missing evidence"),
    ]


def test_duplicate_rows_and_clipped_cells_cannot_support_a_comparison():
    truncated = """| Change type | Notice | Budget |
| --- | --- | --- |
| Standard change | 10 days | USD 24 |
| Standard change | 12 days | USD 30 |
| Emergency change | 2 hours | USD 50"""
    findings = compare_tables("Compare the selected documents", {"old": [OLD_POLICY], "new": [truncated]})
    assert findings[0] == TableFinding("Standard change · Notice", "5 business days", None, "Ambiguous row")
    assert findings[2] == TableFinding("Emergency change · Notice", "2 hours", None, "Missing evidence")
    assert compare_tables("Compare tables", {"old": ["```md\n" + OLD_POLICY + "```"], "new": ["Ordinary text."]}) == []


def test_verified_table_output_uses_the_selected_sources_and_citations():
    sources = [
        ContextFileMetadata(file_id="old", filename="Old | policy", file_content=OLD_POLICY),
        ContextFileMetadata(file_id="new", filename="New policy", file_content=NEW_POLICY),
        ContextFileMetadata(file_id="restricted", filename="Restricted", file_content="Private data."),
    ]
    result = select_excerpts("Compare the selected tables", sources, {"old": 1, "new": 2})
    assert "### Verified table comparison" in result
    assert r"| Row · field | Old \| policy | New policy | Finding |" in result
    assert "| Standard change · Notice | 5 business days [[1]] | 72 hours [[2]] | Different or unclear units |" in result
    assert "| Archive change · Notice | 1 calendar day [[1]] | Unavailable | Missing evidence |" in result
    assert "Private data" not in result and "Restricted" not in result

    focused = select_excerpts("Compare the emergency change row", sources, {"old": 1, "new": 2})
    table = focused.split("### Verified table comparison")[1].split("###")[0]
    assert "Emergency change · Notice" in table and "Standard change" not in table

    research = select_excerpts("Compare the tables", sources, {"old": 1, "new": 2}, research=True)
    assert "Verified table comparison" not in research
