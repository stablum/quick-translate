from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication

from quick_translate.config import AppConfig
from quick_translate.ui.main import TranslatorWindow


class _DummyRepository:
    def save_translation(self, source_text: str, translated_text: str) -> None:
        return None

    def list_translations(self) -> list[object]:
        return []


class _DummyService:
    def translate(self, text: str) -> str:
        return text


class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _config(self) -> AppConfig:
        return AppConfig(
            config_path=Path("config.toml").resolve(),
            openai_api_key="test-key",
            model="gpt-4.1-mini",
            source_language="auto-detect",
            target_language="English",
            prompt_template_path=Path("prompt_template.txt").resolve(),
            database_path=Path("translations.db").resolve(),
            window_width=360,
            window_height=200,
        )

    def test_close_button_uses_plain_x(self) -> None:
        window = TranslatorWindow(
            config=self._config(),
            repository=_DummyRepository(),
            service=_DummyService(),
        )
        self.addCleanup(window.close)

        self.assertEqual(window._close_button.text(), "x")

    def test_close_event_closes_history_window(self) -> None:
        window = TranslatorWindow(
            config=self._config(),
            repository=_DummyRepository(),
            service=_DummyService(),
        )
        window.show()
        self.app.processEvents()

        window._show_history()
        self.app.processEvents()

        self.assertIsNotNone(window._history_window)
        assert window._history_window is not None
        self.assertTrue(window._history_window.isVisible())

        window.close()
        self.app.processEvents()

        self.assertIsNone(window._history_window)
        self.assertFalse(window.isVisible())

    def test_submit_selects_entire_input_for_replacement(self) -> None:
        window = TranslatorWindow(
            config=self._config(),
            repository=_DummyRepository(),
            service=_DummyService(),
        )
        self.addCleanup(window.close)
        window.show()
        self.app.processEvents()

        window._source_edit.setPlainText("replace me")
        window._start_translation()
        self.app.processEvents()

        self.assertEqual(window._source_edit.textCursor().selectedText(), "replace me")


if __name__ == "__main__":
    unittest.main()
