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
            (temp_dir / ".env").write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")

            previous = os.environ.get("OPENAI_API_KEY")
            os.environ.pop("OPENAI_API_KEY", None)
            try:
                config = load_config(config_path)
            finally:
                if previous is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = previous

            self.assertEqual(config.model, "gpt-test")
            self.assertEqual(config.prompt_template_path, (config_path.parent / "templates/prompt.txt").resolve())
            self.assertEqual(config.database_path, (config_path.parent / "data/history.db").resolve())
            self.assertEqual(config.window_width, 480)
            self.assertEqual(config.window_height, 360)

    def test_dotenv_key_is_loaded(self) -> None:
        with workspace_temp_dir() as temp_dir:
            config_path = temp_dir / "config.toml"
            config_path.write_text(
                "[openai]\nmodel = \"gpt-4.1-mini\"\n",
                encoding="utf-8",
            )
            (temp_dir / ".env").write_text(
                "OPENAI_API_KEY=dotenv-key\n",
                encoding="utf-8",
            )

            previous = os.environ.get("OPENAI_API_KEY")
            os.environ.pop("OPENAI_API_KEY", None)
            try:
                config = load_config(config_path)
            finally:
                if previous is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = previous

            self.assertEqual(config.openai_api_key, "dotenv-key")

    def test_env_var_still_overrides_dotenv(self) -> None:
        with workspace_temp_dir() as temp_dir:
            config_path = temp_dir / "config.toml"
            config_path.write_text("[openai]\nmodel = \"gpt-4.1-mini\"\n", encoding="utf-8")
            (temp_dir / ".env").write_text("OPENAI_API_KEY=dotenv-key\n", encoding="utf-8")

            previous = os.environ.get("OPENAI_API_KEY")
            os.environ["OPENAI_API_KEY"] = "env-key"
            try:
                config = load_config(config_path)
            finally:
                if previous is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = previous

            self.assertEqual(config.openai_api_key, "env-key")

    def test_missing_real_api_key_raises(self) -> None:
        with workspace_temp_dir() as temp_dir:
            config_path = temp_dir / "config.toml"
            config_path.write_text("[openai]\nmodel = \"gpt-4.1-mini\"\n", encoding="utf-8")

            previous = os.environ.pop("OPENAI_API_KEY", None)
            try:
                with self.assertRaises(ConfigError):
                    load_config(config_path)
            finally:
                if previous is not None:
                    os.environ["OPENAI_API_KEY"] = previous


if __name__ == "__main__":
    unittest.main()
