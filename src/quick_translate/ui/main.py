from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from quick_translate.config import AppConfig
from quick_translate.database import TranslationRepository
from quick_translate.openai_client import TranslationService
from quick_translate.ui.history import HistoryWindow
from quick_translate.windows_effects import enable_blur


class WorkerSignals(QObject):
    succeeded = Signal(str)
    failed = Signal(str)


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
            self.signals.failed.emit(str(exc))
            return
        self.signals.succeeded.emit(translated_text)


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
        self._drag_origin: QPoint | None = None
        self._window_origin: QPoint | None = None
        self._positioned_once = False

        self.setWindowTitle("Quick Translate")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(self._config.window_width, self._config.window_height)

        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 14, 16, 16)
        panel_layout.setSpacing(10)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 12)
        shadow.setColor(Qt.GlobalColor.black)
        panel.setGraphicsEffect(shadow)

        handle = DragHandle()
        handle.setObjectName("handle")
        handle_layout = QHBoxLayout(handle)
        handle_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("Quick Translate")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title_label.setFont(title_font)

        target_label = QLabel(f"to {self._config.target_language}")
        target_label.setObjectName("metaLabel")

        handle_layout.addWidget(title_label)
        handle_layout.addWidget(target_label)
        handle_layout.addStretch(1)

        history_button = QPushButton("History")
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        history_button.clicked.connect(self._show_history)
        handle_layout.addWidget(history_button)
        handle_layout.addWidget(close_button)

        self._source_edit = QPlainTextEdit()
        self._source_edit.setPlaceholderText("Enter text and press Ctrl+Enter")
        self._source_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._translate_button = QPushButton("Translate")
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self._clear_text)
        self._translate_button.clicked.connect(self._start_translation)

        actions_layout = QHBoxLayout()
        actions_layout.addStretch(1)
        actions_layout.addWidget(clear_button)
        actions_layout.addWidget(self._translate_button)

        self._result_edit = QPlainTextEdit()
        self._result_edit.setReadOnly(True)
        self._result_edit.setPlaceholderText("Translation appears here")
        self._result_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("statusLabel")

        panel_layout.addWidget(handle)
        panel_layout.addWidget(self._source_edit, 1)
        panel_layout.addLayout(actions_layout)
        panel_layout.addWidget(self._result_edit, 1)
        panel_layout.addWidget(self._status_label)
        root_layout.addWidget(panel)

        handle.drag_started.connect(self._begin_drag)
        handle.drag_moved.connect(self._drag_to)
        handle.drag_released.connect(self._end_drag)

        shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        shortcut.activated.connect(self._start_translation)

        self.setStyleSheet(
            """
            QWidget {
                color: rgb(36, 40, 45);
                font-size: 13px;
            }
            QFrame#panel {
                background-color: rgba(250, 252, 255, 170);
                border: 1px solid rgba(255, 255, 255, 115);
                border-radius: 20px;
            }
            QFrame#handle {
                background: transparent;
            }
            QLabel#metaLabel, QLabel#statusLabel {
                color: rgba(36, 40, 45, 170);
            }
            QPlainTextEdit {
                background-color: rgba(255, 255, 255, 110);
                border: 1px solid rgba(255, 255, 255, 125);
                border-radius: 14px;
                padding: 10px;
                selection-background-color: rgba(72, 128, 255, 110);
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 140);
                border: 1px solid rgba(255, 255, 255, 125);
                border-radius: 12px;
                min-height: 34px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 180);
            }
            QPushButton:disabled {
                color: rgba(36, 40, 45, 110);
                background-color: rgba(255, 255, 255, 90);
            }
            """
        )

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        enable_blur(int(self.winId()))
        if not self._positioned_once:
            self._positioned_once = True
            screen = self.screen()
            if screen is not None:
                geometry = screen.availableGeometry()
                x = geometry.right() - self.width() - 32
                y = geometry.top() + 32
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
        self._status_label.setText("Ready")

    def _set_busy(self, is_busy: bool) -> None:
        self._translate_button.setDisabled(is_busy)
        self._source_edit.setDisabled(is_busy)

    def _start_translation(self) -> None:
        source_text = self._source_edit.toPlainText().strip()
        if not source_text:
            self._status_label.setText("Enter some text to translate.")
            return

        self._set_busy(True)
        self._status_label.setText("Translating...")

        task = TranslationTask(self._service, source_text)
        task.signals.succeeded.connect(
            lambda translated_text, original_text=source_text: self._handle_success(
                original_text,
                translated_text,
            )
        )
        task.signals.failed.connect(self._handle_failure)
        self._thread_pool.start(task)

    def _handle_success(self, source_text: str, translated_text: str) -> None:
        self._result_edit.setPlainText(translated_text)
        self._repository.save_translation(source_text, translated_text)
        self._status_label.setText("Saved to translation history.")
        self._set_busy(False)

        if self._history_window is not None:
            self._history_window.load_records(self._repository.list_translations())

    def _handle_failure(self, message: str) -> None:
        self._status_label.setText(message)
        self._set_busy(False)

    def _show_history(self) -> None:
        if self._history_window is None:
            self._history_window = HistoryWindow()

        self._history_window.load_records(self._repository.list_translations())
        self._history_window.show()
        self._history_window.raise_()
        self._history_window.activateWindow()
