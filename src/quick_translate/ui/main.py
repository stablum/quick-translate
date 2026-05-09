from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
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

WINDOW_OPACITY = 0.82
OVERLAY_TEXT_PIXEL_SIZE = 16
OVERLAY_TEXT_OUTLINE_WIDTH = 1.35


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


class OutlinedPlainTextEdit(QPlainTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self._is_applying_outline = False
        self._outline_format = self._build_outline_format()
        self._set_overlay_font()
        self._apply_outline_format()
        self.textChanged.connect(self._apply_outline_format)

    def _set_overlay_font(self) -> None:
        font = QFont("Segoe UI")
        font.setPixelSize(OVERLAY_TEXT_PIXEL_SIZE)
        font.setWeight(QFont.Weight.Bold)
        self.setFont(font)
        self.document().setDefaultFont(font)

    @staticmethod
    def _build_outline_format() -> QTextCharFormat:
        text_format = QTextCharFormat()
        text_format.setForeground(QColor(255, 255, 255))
        text_format.setFontWeight(QFont.Weight.Bold)
        text_format.setTextOutline(QPen(QColor(0, 0, 0), OVERLAY_TEXT_OUTLINE_WIDTH))
        return text_format

    def _apply_outline_format(self) -> None:
        if self._is_applying_outline:
            return

        self._is_applying_outline = True
        try:
            cursor = self.textCursor()
            cursor_position = cursor.position()
            cursor_anchor = cursor.anchor()

            document_cursor = QTextCursor(self.document())
            document_cursor.select(QTextCursor.SelectionType.Document)
            document_cursor.mergeCharFormat(self._outline_format)
            self.setCurrentCharFormat(self._outline_format)

            cursor.setPosition(cursor_anchor)
            if cursor_position != cursor_anchor:
                cursor.setPosition(cursor_position, QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(cursor)
        finally:
            self._is_applying_outline = False


class SubmitTextEdit(OutlinedPlainTextEdit):
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
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        rect = self.rect().adjusted(0, 0, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)

        fill_alpha = max(0, min(255, round(255 * self._surface_opacity)))
        border_alpha = max(fill_alpha, min(255, round(255 * min(1.0, self._surface_opacity + 0.15))))
        painter.fillPath(path, QColor(248, 251, 255, fill_alpha))
        painter.setPen(QPen(QColor(255, 255, 255, border_alpha), 1))
        painter.drawPath(path)


class DragHandle(QFrame):
    drag_started = Signal(QPoint)
    drag_moved = Signal(QPoint)
    drag_released = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            self.drag_started.emit(event.globalPosition().toPoint())
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.buttons() & Qt.MouseButton.LeftButton:
            event.accept()
            self.drag_moved.emit(event.globalPosition().toPoint())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            self.drag_released.emit()
            return
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
        self.setAutoFillBackground(False)
        self.setWindowOpacity(WINDOW_OPACITY)
        self.resize(self._config.window_width, self._config.window_height)

        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(2, 2, 2, 2)

        self._panel = FrostedPanel(self._surface_opacity)
        self._panel.setObjectName("panel")
        self._panel.installEventFilter(self)
        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(6, 3, 6, 4)
        panel_layout.setSpacing(2)

        input_background_alpha = max(0, min(255, round(255 * max(0.1, self._surface_opacity * 1.2))))
        input_border_alpha = max(0, min(255, round(255 * max(0.22, self._surface_opacity * 2.2))))
        result_background_alpha = max(0, min(255, round(255 * max(0.08, self._surface_opacity))))
        hover_background_alpha = max(0, min(255, round(255 * max(0.18, self._surface_opacity * 1.6))))

        self._drag_handle = DragHandle()
        self._drag_handle.setObjectName("handle")
        self._drag_handle.setFixedHeight(18)
        handle_layout = QHBoxLayout(self._drag_handle)
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
        self._make_text_edit_translucent(self._source_edit)
        self._source_edit.setPlaceholderText("Type word")
        self._source_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._source_edit.setMinimumHeight(30)
        self._source_edit.setMaximumHeight(32)
        self._source_edit.submit_requested.connect(self._start_translation)

        self._result_edit = OutlinedPlainTextEdit()
        self._result_edit.setObjectName("resultEdit")
        self._make_text_edit_translucent(self._result_edit)
        self._result_edit.setReadOnly(True)
        self._result_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._result_edit.setMinimumHeight(36)
        self._result_edit.setMaximumHeight(38)

        panel_layout.addWidget(self._drag_handle)
        panel_layout.addWidget(self._source_edit, 1)
        panel_layout.addWidget(self._result_edit, 1)
        root_layout.addWidget(self._panel)

        self._drag_handle.drag_started.connect(self._begin_drag)
        self._drag_handle.drag_moved.connect(self._drag_to)
        self._drag_handle.drag_released.connect(self._end_drag)

        self.setStyleSheet(
            """
            QWidget {
                background: transparent;
                color: rgb(255, 255, 255);
                font-size: 16px;
                font-family: "Segoe UI";
            }
            QFrame#panel {
                border: none;
            }
            QFrame#handle {
                background: transparent;
            }
            QPlainTextEdit {
                background-color: rgba(0, 0, 0, %d);
                border: 1px solid rgba(255, 255, 255, %d);
                border-radius: 7px;
                color: rgb(255, 255, 255);
                font-size: 16px;
                font-weight: 700;
                padding: 2px 5px;
                selection-background-color: rgba(100, 145, 255, 92);
            }
            QPlainTextEdit#resultEdit {
                background-color: rgba(0, 0, 0, %d);
            }
            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                color: rgb(24, 28, 34);
                font-size: 12px;
                font-family: "Segoe UI Emoji", "Segoe UI Symbol", "Segoe UI";
                min-width: 20px;
                min-height: 18px;
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

    @staticmethod
    def _make_text_edit_translucent(edit: QPlainTextEdit) -> None:
        edit.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        edit.setAutoFillBackground(False)
        edit.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        edit.viewport().setAutoFillBackground(False)
        edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def _make_icon_button(self, text: str, tooltip: str) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def eventFilter(self, watched: QObject, event) -> bool:  # type: ignore[override]
        if watched is self._panel and self._handle_panel_drag_event(event):
            return True
        return super().eventFilter(watched, event)

    def _handle_panel_drag_event(self, event) -> bool:
        event_type = event.type()
        if event_type == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            self._begin_drag(event.globalPosition().toPoint())
            return True
        if event_type == QEvent.Type.MouseMove and event.buttons() & Qt.MouseButton.LeftButton:
            event.accept()
            self._drag_to(event.globalPosition().toPoint())
            return True
        if event_type == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            self._end_drag()
            return True
        return False

    def _request_exit(self) -> None:
        self.close()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        logger.info("Showing translator overlay")
        enable_blur(int(self.winId()), self._surface_opacity)
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
