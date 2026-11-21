from collections.abc import Iterator
from functools import lru_cache
from typing import Literal

from groq import Groq

from app.config import get_settings

ReasoningEffort = Literal["low", "medium", "high"]


class LLMNotConfiguredError(Exception):
    pass


def ensure_configured() -> None:
    if not get_settings().groq_api_key:
        raise LLMNotConfiguredError("Falta GROQ_API_KEY en backend/.env")


@lru_cache
def _client() -> Groq:
    ensure_configured()
    return Groq(api_key=get_settings().groq_api_key)


def _params(reasoning_effort: ReasoningEffort | None) -> dict:
    settings = get_settings()
    return {
        "model": settings.groq_model,
        "temperature": settings.llm_temperature,
        # gpt-oss es un modelo de razonamiento: no necesitamos que Groq nos devuelva el razonamiento interno.
        "include_reasoning": False,
        "reasoning_effort": reasoning_effort or settings.llm_reasoning_effort,
    }


def complete(messages: list[dict[str, str]], reasoning_effort: ReasoningEffort | None = None) -> str:
    response = _client().chat.completions.create(messages=messages, **_params(reasoning_effort))
    return (response.choices[0].message.content or "").strip()


def stream(messages: list[dict[str, str]], reasoning_effort: ReasoningEffort | None = None) -> Iterator[str]:
    """Devuelve el texto de la respuesta de a pedacitos, a medida que el modelo lo genera."""
    response = _client().chat.completions.create(messages=messages, stream=True, **_params(reasoning_effort))
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
