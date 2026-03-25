from __future__ import annotations

from typing import Iterable

from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from quick_translate.database import TranslationRecord


class HistoryWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Quick Translate History")
        self.resize(840, 520)

        self._summary_label = QLabel("0 translations")
        self._table = QTableView()
        self._model = QStandardItemModel(0, 2, self)
        self._model.setHorizontalHeaderLabels(["Source", "Translation"])

        self._table.setModel(self._model)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.setWordWrap(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Interactive,
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        self._table.setColumnWidth(0, 300)

        layout = QVBoxLayout(self)
        layout.addWidget(self._summary_label)
        layout.addWidget(self._table)

    def load_records(self, records: Iterable[TranslationRecord]) -> None:
        rows = list(records)
        self._model.setRowCount(0)

        for record in rows:
            source_item = QStandardItem(record.source_text)
            translation_item = QStandardItem(record.translated_text)
            source_item.setEditable(False)
            translation_item.setEditable(False)
            self._model.appendRow([source_item, translation_item])

        self._summary_label.setText(f"{len(rows)} translations")
        self._table.resizeRowsToContents()

