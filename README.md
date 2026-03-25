# Quick Translate

Quick Translate is a small Windows 11 overlay app for fast OpenAI-powered translations. The main window stays above other windows, uses a translucent blurred panel, stores every translation in SQLite, and includes a sortable history view.

## Features

- Always-on-top floating translator box
- Transparent, blurred Win11-style panel
- OpenAI configuration through `config.toml`
- Prompt instructions loaded from `prompt_template.txt`
- SQLite-backed translation history
- Sortable, scrollable history window with source and translation columns

## Setup

1. Install dependencies:

   ```powershell
   uv sync
   ```

2. Edit `config.toml` and set your OpenAI API key.
3. Adjust `prompt_template.txt` if you want different translation instructions.
4. Start the app:

   ```powershell
   uv run quick-translate
   ```

## Config

`config.toml` supports these sections:

- `[openai]`: `api_key`, `model`
- `[translation]`: `source_language`, `target_language`, `template_path`
- `[storage]`: `database_path`
- `[ui]`: `width`, `height`

Relative paths are resolved from the folder containing `config.toml`.

## Prompt Template

`prompt_template.txt` is rendered with:

- `{source_language}`
- `{target_language}`
- `{text}`

If you want literal braces in the template, escape them as `{{` and `}}`.

