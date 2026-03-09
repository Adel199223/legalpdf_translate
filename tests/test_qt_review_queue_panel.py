from __future__ import annotations

from types import SimpleNamespace

import legalpdf_translate.qt_gui.dialogs as dialogs
from legalpdf_translate.qt_gui.dialogs import (
    QtReviewQueueDialog,
    build_review_queue_markdown,
    normalize_review_queue_entries,
)


class _FakeItem:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeLabel:
    def __init__(self) -> None:
        self.value = ""

    def setText(self, text: str) -> None:
        self.value = text


class _FakeTable:
    def __init__(self) -> None:
        self.rows: list[list[object | None]] = []
        self.sorting_enabled = False

    def setSortingEnabled(self, enabled: bool) -> None:
        self.sorting_enabled = enabled

    def setRowCount(self, value: int) -> None:
        if value == 0:
            self.rows = []

    def rowCount(self) -> int:
        return len(self.rows)

    def insertRow(self, row: int) -> None:
        self.rows.insert(row, [None, None, None, None, None])

    def setItem(self, row: int, column: int, item: object) -> None:
        self.rows[row][column] = item

    def sortItems(self, column: int, _order: object) -> None:
        if column != 1:
            return
        self.rows.sort(
            key=lambda row: float(getattr(row[column], "text", "0") or 0.0),
            reverse=True,
        )


def test_normalize_review_queue_entries_sorts_and_filters() -> None:
    entries = normalize_review_queue_entries(
        [
            {"page_number": "3", "score": "0.42", "status": "done", "reasons": ["validator_failed"]},
            {"page_number": 1, "score": 0.9, "status": "failed", "reasons": ["page_failed"]},
            {"page_number": 0, "score": 1.0, "status": "failed", "reasons": ["invalid_page"]},
            {"page_number": "x", "score": "0.1"},
        ]
    )

    assert [item["page_number"] for item in entries] == [1, 3]
    assert [item["score"] for item in entries] == [0.9, 0.42]
    assert entries[0]["status"] == "failed"
    assert entries[1]["reasons"] == ["validator_failed"]


def test_build_review_queue_markdown_handles_empty_and_filled() -> None:
    empty = build_review_queue_markdown([])
    assert "No flagged pages were found for the current run." in empty

    filled = build_review_queue_markdown(
        [
            {
                "page_number": 2,
                "score": 0.7777,
                "status": "done",
                "recommended_action": "manual_review",
                "reasons": ["validator_failed", "transport_retries"],
            }
        ]
    )
    assert "| 2 | 0.7777 | done | manual_review | validator_failed | transport_retries |" in filled


def test_review_queue_panel_populates_filled_state(monkeypatch) -> None:
    monkeypatch.setattr(dialogs, "QTableWidgetItem", _FakeItem)

    fake = SimpleNamespace(
        _entries=[
            {"page_number": 5, "score": 0.55, "status": "done", "reasons": ["retry_used"], "recommended_action": "spot_check"},
            {"page_number": 2, "score": 0.91, "status": "failed", "reasons": ["page_failed"], "recommended_action": "rerun_page"},
        ],
        table=_FakeTable(),
        summary_label=_FakeLabel(),
    )

    QtReviewQueueDialog._populate_table(fake)

    assert fake.table.rowCount() == 2
    assert fake.summary_label.value == "Flagged pages: 2 (sorted by score)."
    assert getattr(fake.table.rows[0][0], "text") == "2"
    assert getattr(fake.table.rows[0][1], "text") == "0.9100"


def test_review_queue_panel_populates_empty_state(monkeypatch) -> None:
    monkeypatch.setattr(dialogs, "QTableWidgetItem", _FakeItem)

    fake = SimpleNamespace(
        _entries=[],
        table=_FakeTable(),
        summary_label=_FakeLabel(),
    )

    QtReviewQueueDialog._populate_table(fake)

    assert fake.table.rowCount() == 0
    assert fake.summary_label.value == "No flagged pages found for this run."
