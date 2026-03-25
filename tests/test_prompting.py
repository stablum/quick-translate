from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quick_translate.prompting import PromptTemplateError, render_prompt
from support import workspace_temp_dir


class PromptingTests(unittest.TestCase):
    def test_render_prompt_injects_expected_values(self) -> None:
        with workspace_temp_dir() as temp_dir:
            template_path = temp_dir / "prompt.txt"
            template_path.write_text(
                "Translate from {source_language} to {target_language}: {text}",
                encoding="utf-8",
            )

            prompt = render_prompt(
                template_path=template_path,
                text="Guten Morgen",
                source_language="German",
                target_language="English",
            )

            self.assertEqual(
                prompt,
                "Translate from German to English: Guten Morgen",
            )

    def test_render_prompt_rejects_unknown_placeholders(self) -> None:
        with workspace_temp_dir() as temp_dir:
            template_path = temp_dir / "prompt.txt"
            template_path.write_text("Translate {unknown}", encoding="utf-8")

            with self.assertRaises(PromptTemplateError):
                render_prompt(
                    template_path=template_path,
                    text="Hallo",
                    source_language="German",
                    target_language="English",
                )


if __name__ == "__main__":
    unittest.main()
