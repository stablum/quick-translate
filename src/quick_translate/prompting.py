from __future__ import annotations

from pathlib import Path


class PromptTemplateError(RuntimeError):
    """Raised when the prompt template cannot be rendered."""


def render_prompt(
    template_path: Path,
    text: str,
    source_language: str,
    target_language: str,
) -> str:
    if not template_path.exists():
        raise PromptTemplateError(f"Prompt template file not found: {template_path}")

    template = template_path.read_text(encoding="utf-8")
    try:
        return template.format(
            text=text,
            source_language=source_language,
            target_language=target_language,
        )
    except KeyError as exc:
        placeholder = exc.args[0]
        raise PromptTemplateError(
            "Unknown placeholder "
            f"'{placeholder}' in {template_path}. Supported placeholders are "
            "{text}, {source_language}, and {target_language}."
        ) from exc

