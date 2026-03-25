from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    """Raised when the application configuration is invalid."""


@dataclass(slots=True, frozen=True)
class AppConfig:
    config_path: Path
    openai_api_key: str
    model: str
    source_language: str
    target_language: str
    prompt_template_path: Path
    database_path: Path
    window_width: int
    window_height: int


def _resolve_path(base_dir: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def load_config(config_path: Path) -> AppConfig:
    if not config_path.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")

    with config_path.open("rb") as handle:
        data = tomllib.load(handle)

    openai_data = data.get("openai", {})
    translation_data = data.get("translation", {})
    storage_data = data.get("storage", {})
    ui_data = data.get("ui", {})

    api_key = (
        os.environ.get("OPENAI_API_KEY")
        or str(openai_data.get("api_key", "")).strip()
    )
    if not api_key or api_key.startswith("replace-me"):
        raise ConfigError(
            "Set a real OpenAI API key in config.toml [openai].api_key or "
            "provide OPENAI_API_KEY."
        )

    base_dir = config_path.parent.resolve()
    prompt_template_path = _resolve_path(
        base_dir,
        str(translation_data.get("template_path", "prompt_template.txt")),
    )
    database_path = _resolve_path(
        base_dir,
        str(storage_data.get("database_path", "translations.db")),
    )

    return AppConfig(
        config_path=config_path.resolve(),
        openai_api_key=api_key,
        model=str(openai_data.get("model", "gpt-4.1-mini")).strip() or "gpt-4.1-mini",
        source_language=str(
            translation_data.get("source_language", "auto-detect")
        ).strip()
        or "auto-detect",
        target_language=str(translation_data.get("target_language", "English")).strip()
        or "English",
        prompt_template_path=prompt_template_path,
        database_path=database_path,
        window_width=int(ui_data.get("width", 440)),
        window_height=int(ui_data.get("height", 320)),
    )

