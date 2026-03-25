from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from quick_translate.config import ConfigError, load_config
from quick_translate.database import TranslationRepository
from quick_translate.openai_client import TranslationService
from quick_translate.ui.main import TranslatorWindow


def _default_config_path() -> Path:
    return Path.cwd() / "config.toml"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Quick Translate")
    app.setQuitOnLastWindowClosed(True)

    try:
        config = load_config(_default_config_path())
        repository = TranslationRepository(config.database_path)
        service = TranslationService(config)
    except ConfigError as exc:
        QMessageBox.critical(None, "Quick Translate", str(exc))
        return 1

    window = TranslatorWindow(
        config=config,
        repository=repository,
        service=service,
    )
    window.show()
    return app.exec()

