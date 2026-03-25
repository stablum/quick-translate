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
    log_path: Path
    window_width: int
    window_height: int


def _resolve_path(base_dir: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key or key in os.environ:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ[key] = value


def load_config(config_path: Path) -> AppConfig:
    if not config_path.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")

    base_dir = config_path.parent.resolve()
    _load_dotenv(base_dir / ".env")

    with config_path.open("rb") as handle:
        data = tomllib.load(handle)

    openai_data = data.get("openai", {})
    translation_data = data.get("translation", {})
    storage_data = data.get("storage", {})
    logging_data = data.get("logging", {})
    ui_data = data.get("ui", {})

    api_key = os.environ.get("OPENAI_API_KEY") or str(openai_data.get("api_key", "")).strip()
    if not api_key or api_key.startswith("replace-me"):
        raise ConfigError(
            "Set OPENAI_API_KEY in a local .env file or provide it as an "
            "environment variable."
        )

    prompt_template_path = _resolve_path(
        base_dir,
        str(translation_data.get("template_path", "prompt_template.txt")),
    )
    database_path = _resolve_path(
        base_dir,
        str(storage_data.get("database_path", "translations.db")),
    )
    log_path = _resolve_path(
        base_dir,
        str(logging_data.get("path", "quick-translate.log")),
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
        log_path=log_path,
        window_width=int(ui_data.get("width", 360)),
        window_height=int(ui_data.get("height", 200)),
    )
