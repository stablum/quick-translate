from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quick_translate.database import TranslationRepository
from support import workspace_temp_dir


class DatabaseTests(unittest.TestCase):
    def test_repository_saves_and_lists_translations(self) -> None:
        with workspace_temp_dir() as temp_dir:
            repository = TranslationRepository(temp_dir / "translations.db")
            repository.save_translation("Hallo", "Hello")
            time.sleep(1)
            repository.save_translation("Tot ziens", "Goodbye")

            rows = repository.list_translations()

            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0].source_text, "Tot ziens")
            self.assertEqual(rows[0].translated_text, "Goodbye")
            self.assertEqual(rows[1].source_text, "Hallo")


if __name__ == "__main__":
    unittest.main()
