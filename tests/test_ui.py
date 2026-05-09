from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QImage, QMouseEvent, QPainter
from PySide6.QtWidgets import QApplication

from quick_translate.config import AppConfig
from quick_translate.ui.main import (
    DragHandle,
    FrostedPanel,
    OVERLAY_TEXT_PIXEL_SIZE,
    TranslatorWindow,
    WINDOW_OPACITY,
)


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
            log_path=Path("quick-translate.log").resolve(),
            window_width=280,
            window_height=104,
            surface_opacity=0.08,
        )

    def test_close_button_uses_plain_x(self) -> None:
        window = TranslatorWindow(
            config=self._config(),
            repository=_DummyRepository(),
            service=_DummyService(),
        )
        self.addCleanup(window.close)

        self.assertEqual(window._close_button.text(), "x")

    def test_window_is_compact_and_partly_transparent(self) -> None:
        window = TranslatorWindow(
            config=self._config(),
            repository=_DummyRepository(),
            service=_DummyService(),
        )
        self.addCleanup(window.close)

        self.assertEqual(window.size().width(), 280)
        self.assertEqual(window.size().height(), 104)
        self.assertAlmostEqual(window.windowOpacity(), WINDOW_OPACITY, places=2)

    def test_text_edits_use_bold_outlined_compact_style(self) -> None:
        window = TranslatorWindow(
            config=self._config(),
            repository=_DummyRepository(),
            service=_DummyService(),
        )
        self.addCleanup(window.close)
        window.show()
        self.app.processEvents()

        style = window.styleSheet()
        self.assertIn("font-weight: 700", style)
        self.assertIn("font-size: 18px", style)
        self.assertEqual(window._source_edit.minimumHeight(), 32)
        self.assertEqual(window._result_edit.maximumHeight(), 38)

        window._source_edit.setPlainText("word")
        self.app.processEvents()

        image = QImage(window._source_edit.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        window._source_edit.render(painter, QPoint())
        painter.end()

        white_pixels = 0
        black_pixels = 0
        for y in range(image.height()):
            for x in range(image.width()):
                color = image.pixelColor(x, y)
                if color.alpha() > 140 and color.red() > 200 and color.green() > 200 and color.blue() > 200:
                    white_pixels += 1
                if color.alpha() > 100 and color.red() < 60 and color.green() < 60 and color.blue() < 60:
                    black_pixels += 1

        self.assertEqual(window._source_edit.toPlainText(), "word")
        self.assertEqual(window._source_edit.font().pixelSize(), OVERLAY_TEXT_PIXEL_SIZE)
        self.assertTrue(window._source_edit.font().bold())
        self.assertGreater(white_pixels, 20)
        self.assertGreater(black_pixels, 20)

    def test_panel_renders_translucent_surface(self) -> None:
        panel = FrostedPanel(0.1)
        panel.resize(80, 80)

        image = QImage(panel.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        panel.render(painter, QPoint())
        painter.end()

        center_alpha = image.pixelColor(40, 40).alpha()
        self.assertGreater(center_alpha, 0)
        self.assertLess(center_alpha, 80)

    def test_text_edit_viewports_are_translucent(self) -> None:
        window = TranslatorWindow(
            config=self._config(),
            repository=_DummyRepository(),
            service=_DummyService(),
        )
        self.addCleanup(window.close)

        self.assertTrue(
            window._source_edit.viewport().testAttribute(
                Qt.WidgetAttribute.WA_TranslucentBackground
            )
        )
        self.assertTrue(
            window._result_edit.viewport().testAttribute(
                Qt.WidgetAttribute.WA_TranslucentBackground
            )
        )

    def test_drag_handle_accepts_left_mouse_drag(self) -> None:
        handle = DragHandle()
        started: list[QPoint] = []
        moved: list[QPoint] = []
        released: list[bool] = []
        handle.drag_started.connect(started.append)
        handle.drag_moved.connect(moved.append)
        handle.drag_released.connect(lambda: released.append(True))

        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(4, 4),
            QPointF(14, 14),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(24, 24),
            QPointF(34, 34),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        release = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(24, 24),
            QPointF(34, 34),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )

        handle.mousePressEvent(press)
        handle.mouseMoveEvent(move)
        handle.mouseReleaseEvent(release)

        self.assertTrue(press.isAccepted())
        self.assertTrue(move.isAccepted())
        self.assertTrue(release.isAccepted())
        self.assertEqual(started, [QPoint(14, 14)])
        self.assertEqual(moved, [QPoint(34, 34)])
        self.assertEqual(released, [True])

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

    def test_closing_history_window_keeps_translator_visible(self) -> None:
        previous_quit_setting = self.app.quitOnLastWindowClosed()
        self.app.setQuitOnLastWindowClosed(False)
        self.addCleanup(self.app.setQuitOnLastWindowClosed, previous_quit_setting)

        window = TranslatorWindow(
            config=self._config(),
            repository=_DummyRepository(),
            service=_DummyService(),
        )
        self.addCleanup(window.close)
        window.show()
        self.app.processEvents()

        window._show_history()
        self.app.processEvents()

        assert window._history_window is not None
        window._history_window.close()
        self.app.processEvents()

        self.assertTrue(window.isVisible())

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
