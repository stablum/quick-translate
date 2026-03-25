from __future__ import annotations

import faulthandler
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from PySide6.QtCore import QtMsgType, qInstallMessageHandler


LOGGER_NAME = "quick_translate"
_fault_handler_stream = None
_previous_sys_excepthook = sys.excepthook
_previous_threading_excepthook = getattr(threading, "excepthook", None)
_previous_qt_message_handler = None

_package_logger = logging.getLogger(LOGGER_NAME)
if not _package_logger.handlers:
    _package_logger.addHandler(logging.NullHandler())


def get_logger(name: str | None = None) -> logging.Logger:
    if not name:
        return logging.getLogger(LOGGER_NAME)
    if name == LOGGER_NAME or name.startswith(f"{LOGGER_NAME}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def configure_logging(log_path: Path) -> logging.Logger:
    global _fault_handler_stream

    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = get_logger()
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_048_576,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
    )
    logger.addHandler(file_handler)

    if _fault_handler_stream is not None:
        try:
            faulthandler.disable()
        except RuntimeError:
            pass
        _fault_handler_stream.close()

    _fault_handler_stream = log_path.open("a", encoding="utf-8")
    faulthandler.enable(_fault_handler_stream, all_threads=True)

    install_exception_logging()
    logger.info("Logging initialized at %s", log_path)
    return logger


def install_exception_logging() -> None:
    global _previous_qt_message_handler

    logger = get_logger("crash")

    def handle_exception(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: Any,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            _previous_sys_excepthook(exc_type, exc_value, exc_traceback)
            return

        logger.critical(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        _previous_sys_excepthook(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception

    if _previous_threading_excepthook is not None:
        def handle_thread_exception(args: Any) -> None:
            if issubclass(args.exc_type, KeyboardInterrupt):
                _previous_threading_excepthook(args)
                return

            logger.critical(
                "Unhandled thread exception in %s",
                getattr(args.thread, "name", "unknown"),
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
            _previous_threading_excepthook(args)

        threading.excepthook = handle_thread_exception

    if _previous_qt_message_handler is None:
        def handle_qt_message(message_type: QtMsgType, context: Any, message: str) -> None:
            message_logger = get_logger("qt")
            level_map = {
                QtMsgType.QtDebugMsg: logging.DEBUG,
                QtMsgType.QtInfoMsg: logging.INFO,
                QtMsgType.QtWarningMsg: logging.WARNING,
                QtMsgType.QtCriticalMsg: logging.ERROR,
                QtMsgType.QtFatalMsg: logging.CRITICAL,
            }
            location = ""
            if getattr(context, "file", None):
                location = f" ({context.file}:{context.line})"
            message_logger.log(level_map.get(message_type, logging.INFO), "Qt: %s%s", message, location)

        _previous_qt_message_handler = qInstallMessageHandler(handle_qt_message)
