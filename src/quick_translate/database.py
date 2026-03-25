from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class TranslationRecord:
    source_text: str
    translated_text: str
    created_at: str


class TranslationRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS translations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_text TEXT NOT NULL,
                    translated_text TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_translations_created_at
                ON translations (created_at DESC, id DESC)
                """
            )

    def save_translation(self, source_text: str, translated_text: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO translations (source_text, translated_text)
                VALUES (?, ?)
                """,
                (source_text, translated_text),
            )

    def list_translations(self) -> list[TranslationRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source_text, translated_text, created_at
                FROM translations
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()

        return [
            TranslationRecord(
                source_text=row["source_text"],
                translated_text=row["translated_text"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

