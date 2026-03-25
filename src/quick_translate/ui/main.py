from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QCloseEvent, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QPlainTextEdit,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from quick_translate.config import AppConfig
from quick_translate.database import TranslationRepository
from quick_translate.logging_utils import get_logger
from quick_translate.openai_client import TranslationService
from quick_translate.ui.history import HistoryWindow
from quick_translate.windows_effects import enable_blur


logger = get_logger(__name__)


class WorkerSignals(QObject):
    succeeded = Signal(str)
    failed = Signal(str)
    finished = Signal()


class TranslationTask(QRunnable):
    def __init__(self, service: TranslationService, text: str) -> None:
        super().__init__()
        self._service = service
        self._text = text
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            translated_text = self._service.translate(self._text)
        except Exception as exc:  # pragma: no cover - UI thread handles display.
            logger.exception("Translation task crashed")
            self.signals.failed.emit(str(exc))
        else:
            self.signals.succeeded.emit(translated_text)
        finally:
            self.signals.finished.emit()


class SubmitTextEdit(QPlainTextEdit):
    submit_requested = Signal()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        is_submit = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        modifiers = event.modifiers()
        if is_submit and not (modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                event.accept()
                self.submit_requested.emit()
            return
        super().keyPressEvent(event)


class FrostedPanel(QFrame):
    def __init__(self, surface_opacity: float) -> None:
        super().__init__()
        self._surface_opacity = surface_opacity

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect().adjusted(0, 0, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 18, 18)

        fill_alpha = max(0, min(255, round(255 * self._surface_opacity)))
        border_alpha = max(fill_alpha, min(255, round(255 * min(1.0, self._surface_opacity + 0.15))))
        painter.fillPath(path, QColor(248, 251, 255, fill_alpha))
        painter.setPen(QPen(QColor(255, 255, 255, border_alpha), 1))
        painter.drawPath(path)


class DragHandle(QFrame):
    drag_started = Signal(QPoint)
    drag_moved = Signal(QPoint)
    drag_released = Signal()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_started.emit(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.drag_moved.emit(event.globalPosition().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self.drag_released.emit()
        super().mouseReleaseEvent(event)


class TranslatorWindow(QWidget):
    def __init__(
        self,
        config: AppConfig,
        repository: TranslationRepository,
        service: TranslationService,
    ) -> None:
        super().__init__()
        self._config = config
        self._repository = repository
        self._service = service
        self._thread_pool = QThreadPool.globalInstance()
        self._history_window: HistoryWindow | None = None
        self._active_tasks: set[TranslationTask] = set()
        self._drag_origin: QPoint | None = None
        self._window_origin: QPoint | None = None
        self._positioned_once = False
        self._surface_opacity = self._config.surface_opacity

        self.setWindowTitle("Quick Translate")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.resize(self._config.window_width, self._config.window_height)

        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)

        panel = FrostedPanel(self._surface_opacity)
        panel.setObjectName("panel")
        panel.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        panel.setAutoFillBackground(False)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 10, 12, 12)
        panel_layout.setSpacing(8)

        input_background_alpha = max(0, min(255, round(255 * self._surface_opacity * 0.35)))
        input_border_alpha = max(0, min(255, round(255 * min(1.0, self._surface_opacity * 0.8))))
        result_background_alpha = max(0, min(255, round(255 * self._surface_opacity * 0.22)))
        hover_background_alpha = max(0, min(255, round(255 * self._surface_opacity * 0.5)))
        shadow_alpha = max(0, min(255, round(255 * min(0.25, 0.08 + (self._surface_opacity * 0.5)))))

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, shadow_alpha))
        panel.setGraphicsEffect(shadow)

        handle = DragHandle()
        handle.setObjectName("handle")
        handle.setFixedHeight(28)
        handle_layout = QHBoxLayout(handle)
        handle_layout.setContentsMargins(0, 0, 0, 0)
        handle_layout.addStretch(1)

        self._clear_button = self._make_icon_button("⌫", "Clear")
        self._history_button = self._make_icon_button("🕘", "History")
        self._close_button = self._make_icon_button("x", "Exit")
        self._close_button.clicked.connect(self._request_exit)
        self._history_button.clicked.connect(self._show_history)
        self._clear_button.clicked.connect(self._clear_text)
        handle_layout.addWidget(self._clear_button)
        handle_layout.addWidget(self._history_button)
        handle_layout.addWidget(self._close_button)

        self._source_edit = SubmitTextEdit()
        self._source_edit.setObjectName("sourceEdit")
        self._source_edit.setPlaceholderText("Type and press Enter")
        self._source_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._source_edit.setMinimumHeight(56)
        self._source_edit.setMaximumHeight(84)
        self._source_edit.submit_requested.connect(self._start_translation)

        self._result_edit = QPlainTextEdit()
        self._result_edit.setObjectName("resultEdit")
        self._result_edit.setReadOnly(True)
        self._result_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._result_edit.setMinimumHeight(56)
        self._result_edit.setMaximumHeight(112)

        panel_layout.addWidget(handle)
        panel_layout.addWidget(self._source_edit, 1)
        panel_layout.addWidget(self._result_edit, 1)
        root_layout.addWidget(panel)

        handle.drag_started.connect(self._begin_drag)
        handle.drag_moved.connect(self._drag_to)
        handle.drag_released.connect(self._end_drag)

        self.setStyleSheet(
            """
            QWidget {
                background: transparent;
                color: rgb(24, 28, 34);
                font-size: 12px;
                font-family: "Segoe UI";
            }
            QFrame#panel {
                border: none;
            }
            QFrame#handle {
                background: transparent;
            }
            QPlainTextEdit {
                background-color: rgba(255, 255, 255, %d);
                border: 1px solid rgba(255, 255, 255, %d);
                border-radius: 12px;
                padding: 8px 10px;
                selection-background-color: rgba(100, 145, 255, 92);
            }
            QPlainTextEdit#resultEdit {
                background-color: rgba(255, 255, 255, %d);
            }
            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 10px;
                color: rgb(24, 28, 34);
                font-size: 14px;
                font-family: "Segoe UI Emoji", "Segoe UI Symbol", "Segoe UI";
                min-width: 28px;
                min-height: 28px;
                padding: 0;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, %d);
            }
            QToolButton:disabled {
                color: rgba(24, 28, 34, 90);
            }
            """
            % (
                input_background_alpha,
                input_border_alpha,
                result_background_alpha,
                hover_background_alpha,
            )
        )

    def _make_icon_button(self, text: str, tooltip: str) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _request_exit(self) -> None:
        self.close()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        logger.info("Showing translator overlay")
        enable_blur(int(self.winId()))
        if not self._positioned_once:
            self._positioned_once = True
            screen = self.screen()
            if screen is not None:
                geometry = screen.availableGeometry()
                x = geometry.center().x() - (self.width() // 2)
                y = geometry.bottom() - self.height() - 28
                self.move(x, y)

    def _begin_drag(self, cursor_position: QPoint) -> None:
        self._drag_origin = cursor_position
        self._window_origin = self.frameGeometry().topLeft()

    def _drag_to(self, cursor_position: QPoint) -> None:
        if self._drag_origin is None or self._window_origin is None:
            return
        self.move(self._window_origin + (cursor_position - self._drag_origin))

    def _end_drag(self) -> None:
        self._drag_origin = None
        self._window_origin = None

    def _clear_text(self) -> None:
        self._source_edit.clear()
        self._result_edit.clear()

    def _select_source_text_for_replacement(self) -> None:
        self._source_edit.setFocus(Qt.FocusReason.OtherFocusReason)
        self._source_edit.selectAll()

    def _release_task(self, task: TranslationTask) -> None:
        self._active_tasks.discard(task)

    def _set_busy(self, is_busy: bool) -> None:
        self._source_edit.setReadOnly(is_busy)
        self._clear_button.setDisabled(is_busy)
        self._close_button.setDisabled(False)

    def _start_translation(self) -> None:
        source_text = self._source_edit.toPlainText().strip()
        if not source_text:
            return

        self._set_busy(True)
        self._result_edit.clear()
        self._select_source_text_for_replacement()
        logger.info("Starting translation for %s characters", len(source_text))

        task = TranslationTask(self._service, source_text)
        task.setAutoDelete(False)
        self._active_tasks.add(task)
        task.signals.succeeded.connect(
            lambda translated_text, original_text=source_text: self._handle_success(
                original_text,
                translated_text,
            )
        )
        task.signals.failed.connect(self._handle_failure)
        task.signals.finished.connect(lambda task=task: self._release_task(task))
        self._thread_pool.start(task)

    def _handle_success(self, source_text: str, translated_text: str) -> None:
        self._result_edit.setPlainText(translated_text)
        self._repository.save_translation(source_text, translated_text)
        self._set_busy(False)
        self._select_source_text_for_replacement()
        logger.info("Saved translation to history")

        if self._history_window is not None:
            self._history_window.load_records(self._repository.list_translations())

    def _handle_failure(self, message: str) -> None:
        self._result_edit.setPlainText(message)
        self._set_busy(False)
        self._select_source_text_for_replacement()
        logger.error("Translation failed: %s", message)

    def _show_history(self) -> None:
        if self._history_window is None:
            self._history_window = HistoryWindow()

        logger.info("Opening translation history window")
        self._history_window.load_records(self._repository.list_translations())
        self._history_window.show()
        self._history_window.raise_()
        self._history_window.activateWindow()

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        logger.info("Closing translator overlay")
        self._thread_pool.clear()
        self._active_tasks.clear()
        if self._history_window is not None:
            self._history_window.close()
            self._history_window.deleteLater()
            self._history_window = None
        super().closeEvent(event)
