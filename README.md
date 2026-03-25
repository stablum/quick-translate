# Quick Translate

Quick Translate is a small Windows 11 overlay app for fast OpenAI-powered translations. The main window stays above other windows, uses a translucent blurred panel, stores every translation in SQLite, and includes a sortable history view.

## Features

- Always-on-top floating translator box
- Transparent, blurred Win11-style panel
- OpenAI key loaded from a local `.env`
- App configuration through `config.toml`
- Prompt instructions loaded from `prompt_template.txt`
- SQLite-backed translation history
- Sortable, scrollable history window with source and translation columns

## Setup

1. Install dependencies:

   ```powershell
   uv sync
   ```

2. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`.
3. Adjust `config.toml` if you want different model, languages, paths, or window size.
4. Adjust `prompt_template.txt` if you want different translation instructions.
5. Start the app:

   ```powershell
   uv run quick-translate
   ```

Press `Enter` in the input box to translate. Use `Shift+Enter` if you want a newline instead.
Use the `x` control in the top-right corner to fully exit the app.
If the app crashes or behaves unexpectedly, check `quick-translate.log` in the project folder.

## Config

`config.toml` supports these sections:

- `[openai]`: `model`
- `[translation]`: `source_language`, `target_language`, `template_path`
- `[storage]`: `database_path`
- `[logging]`: `path`
- `[ui]`: `width`, `height`

Relative paths are resolved from the folder containing `config.toml`.

## Secrets

Place secrets in `.env`, which is ignored by git. The app automatically loads `.env` from the same folder as `config.toml`.

## Prompt Template

`prompt_template.txt` is rendered with:

- `{source_language}`
- `{target_language}`
- `{text}`

If you want literal braces in the template, escape them as `{{` and `}}`.
