from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from quick_translate.config import ConfigError, load_config
from quick_translate.database import TranslationRepository
from quick_translate.logging_utils import configure_logging, get_logger
from quick_translate.openai_client import TranslationService
from quick_translate.ui.main import TranslatorWindow


def _default_config_path() -> Path:
    return Path.cwd() / "config.toml"


def main() -> int:
    config_path = _default_config_path()
    bootstrap_log_path = config_path.parent.resolve() / "quick-translate.log"
    configure_logging(bootstrap_log_path)
    logger = get_logger(__name__)
    logger.info("Starting Quick Translate")

    app = QApplication(sys.argv)
    app.setApplicationName("Quick Translate")
    app.setQuitOnLastWindowClosed(True)

    try:
        config = load_config(config_path)
        if config.log_path != bootstrap_log_path:
            configure_logging(config.log_path)
            logger = get_logger(__name__)
        logger.info("Loaded configuration from %s", config.config_path)
        repository = TranslationRepository(config.database_path)
        service = TranslationService(config)
    except ConfigError as exc:
        logger.exception("Configuration error during startup")
        QMessageBox.critical(None, "Quick Translate", str(exc))
        return 1
    except Exception:
        logger.exception("Unexpected startup failure")
        QMessageBox.critical(
            None,
            "Quick Translate",
            f"The app failed to start. Check {bootstrap_log_path.name} for details.",
        )
        return 1

    window = TranslatorWindow(
        config=config,
        repository=repository,
        service=service,
    )
    window.show()
    app.aboutToQuit.connect(lambda: logger.info("Quick Translate is shutting down"))
    exit_code = app.exec()
    logger.info("Quick Translate exited with code %s", exit_code)
    return exit_code
