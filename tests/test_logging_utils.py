from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quick_translate.logging_utils import configure_logging, get_logger
from support import workspace_temp_dir


class LoggingTests(unittest.TestCase):
    def test_configure_logging_creates_log_file(self) -> None:
        with workspace_temp_dir() as temp_dir:
            log_path = temp_dir / "quick-translate.log"
            logger = configure_logging(log_path)
            logger.info("hello from test")

            self.assertTrue(log_path.exists())
            self.assertIn("hello from test", log_path.read_text(encoding="utf-8"))

    def test_named_logger_uses_quick_translate_namespace(self) -> None:
        logger = get_logger("ui")
        self.assertEqual(logger.name, "quick_translate.ui")

    def test_module_logger_name_is_not_double_prefixed(self) -> None:
        logger = get_logger("quick_translate.ui.main")
        self.assertEqual(logger.name, "quick_translate.ui.main")


if __name__ == "__main__":
    unittest.main()
