from functools import lru_cache

from groq import Groq

from app.config import get_settings


class LLMNotConfiguredError(Exception):
    pass


@lru_cache
def _client() -> Groq:
    settings = get_settings()
    if not settings.groq_api_key:
        raise LLMNotConfiguredError("Falta GROQ_API_KEY en backend/.env")
    return Groq(api_key=settings.groq_api_key)


def chat(messages: list[dict[str, str]]) -> str:
    settings = get_settings()
    response = _client().chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        temperature=settings.llm_temperature,
    )
    return response.choices[0].message.content or ""
