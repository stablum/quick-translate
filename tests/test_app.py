from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import quick_translate.app as app_module


class AppTests(unittest.TestCase):
    def test_default_config_path_uses_cwd_when_not_frozen(self) -> None:
        with patch.object(app_module, "_runtime_root", return_value=Path("C:/tmp/runtime")):
            self.assertEqual(
                app_module._default_config_path(),
                Path("C:/tmp/runtime/config.toml"),
            )

    def test_runtime_root_uses_executable_directory_when_frozen(self) -> None:
        with patch.object(app_module.sys, "frozen", True, create=True):
            with patch.object(app_module.sys, "executable", "C:/apps/quick-translate/quick-translate.exe"):
                self.assertEqual(
                    app_module._runtime_root(),
                    Path("C:/apps/quick-translate"),
                )

    def test_application_does_not_quit_when_history_window_closes(self) -> None:
        class DummyApplication:
            def __init__(self) -> None:
                self.application_name = ""
                self.quit_on_last_window_closed = True

            def setApplicationName(self, name: str) -> None:
                self.application_name = name

            def setQuitOnLastWindowClosed(self, enabled: bool) -> None:
                self.quit_on_last_window_closed = enabled

        app = DummyApplication()

        app_module._configure_application(app)  # type: ignore[arg-type]

        self.assertEqual(app.application_name, "Quick Translate")
        self.assertFalse(app.quit_on_last_window_closed)


if __name__ == "__main__":
    unittest.main()
