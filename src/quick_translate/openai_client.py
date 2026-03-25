from __future__ import annotations

from quick_translate.config import AppConfig
from quick_translate.logging_utils import get_logger
from quick_translate.prompting import render_prompt

from openai import OpenAI


class TranslationError(RuntimeError):
    """Raised when translation fails."""


logger = get_logger(__name__)


class TranslationService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._client = OpenAI(api_key=config.openai_api_key)

    def translate(self, text: str) -> str:
        logger.info(
            "Sending translation request using model %s for %s characters",
            self._config.model,
            len(text),
        )
        prompt = render_prompt(
            template_path=self._config.prompt_template_path,
            text=text,
            source_language=self._config.source_language,
            target_language=self._config.target_language,
        )

        response = self._client.responses.create(
            model=self._config.model,
            input=prompt,
        )
        translated_text = self._extract_text(response).strip()
        if not translated_text:
            raise TranslationError("OpenAI returned an empty translation.")
        logger.info("Received translation with %s characters", len(translated_text))
        return translated_text

    @staticmethod
    def _extract_text(response: object) -> str:
        output_text = getattr(response, "output_text", "")
        if output_text:
            return str(output_text)

        chunks: list[str] = []
        for item in getattr(response, "output", []):
            for content in getattr(item, "content", []):
                if getattr(content, "type", "") == "output_text":
                    text = getattr(content, "text", "")
                    if text:
                        chunks.append(str(text))
        return "".join(chunks)
