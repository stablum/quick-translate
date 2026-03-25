from __future__ import annotations

import os
import sys
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quick_translate.config import ConfigError, load_config
from support import workspace_temp_dir


class ConfigTests(unittest.TestCase):
    def test_load_config_resolves_relative_paths(self) -> None:
        with workspace_temp_dir() as temp_dir:
            config_path = temp_dir / "config.toml"
            config_path.write_text(
                textwrap.dedent(
                    """
                    [openai]
                    api_key = "test-key"
                    model = "gpt-test"

                    [translation]
                    source_language = "German"
                    target_language = "English"
                    template_path = "templates/prompt.txt"

                    [storage]
                    database_path = "data/history.db"

                    [ui]
                    width = 480
                    height = 360
                    """
                ).strip(),
                encoding="utf-8",
            )

            config = load_config(config_path)

            self.assertEqual(config.model, "gpt-test")
            self.assertEqual(config.prompt_template_path, (config_path.parent / "templates/prompt.txt").resolve())
            self.assertEqual(config.database_path, (config_path.parent / "data/history.db").resolve())
            self.assertEqual(config.window_width, 480)
            self.assertEqual(config.window_height, 360)

    def test_env_key_overrides_placeholder(self) -> None:
        with workspace_temp_dir() as temp_dir:
            config_path = temp_dir / "config.toml"
            config_path.write_text(
                "[openai]\napi_key = \"replace-me-with-your-openai-api-key\"\n",
                encoding="utf-8",
            )

            previous = os.environ.get("OPENAI_API_KEY")
            os.environ["OPENAI_API_KEY"] = "env-key"
            try:
                config = load_config(config_path)
            finally:
                if previous is None:
                    del os.environ["OPENAI_API_KEY"]
                else:
                    os.environ["OPENAI_API_KEY"] = previous

            self.assertEqual(config.openai_api_key, "env-key")

    def test_missing_real_api_key_raises(self) -> None:
        with workspace_temp_dir() as temp_dir:
            config_path = temp_dir / "config.toml"
            config_path.write_text("[openai]\napi_key = \"replace-me\"\n", encoding="utf-8")

            previous = os.environ.pop("OPENAI_API_KEY", None)
            try:
                with self.assertRaises(ConfigError):
                    load_config(config_path)
            finally:
                if previous is not None:
                    os.environ["OPENAI_API_KEY"] = previous


if __name__ == "__main__":
    unittest.main()
