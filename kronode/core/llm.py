"""Unified LLM helper.

Routes calls to the right provider:
- cheap() → tries providers cheapest-first, auto-failover on error
- quality() → always Anthropic Sonnet

Failover order (cheapest to most expensive):
  1. Gemini Flash    (free tier / $0.10 per MTok)
  2. DeepSeek V3     ($0.27/$1.10 per MTok)
  3. GPT-4.1 nano    ($0.10/$0.40 per MTok)
  4. Haiku           ($0.80/$4.00 per MTok)  ← always available as final fallback

Only providers with API keys set are attempted.
"""
import logging

from kronode.core.config import settings

logger = logging.getLogger(__name__)

# OpenAI first — reliable JSON mode, then cheapest to most expensive
_PROVIDER_ORDER = [
    ("openai", lambda: settings.openai_api_key),
    ("gemini", lambda: settings.gemini_api_key),
    ("deepseek", lambda: settings.deepseek_api_key),
    ("haiku", lambda: settings.anthropic_api_key),
]


async def cheap(system: str, user_message: str, max_tokens: int = 1024) -> str:
    """Call the cheapest available model, failover to next on error."""
    errors = []

    for provider, key_fn in _PROVIDER_ORDER:
        if not key_fn():
            continue
        try:
            result = await _call_provider(provider, system, user_message, max_tokens)
            return result
        except Exception as exc:
            logger.warning(f"[LLM] {provider} failed: {exc} — trying next provider")
            errors.append(f"{provider}: {exc}")

    raise RuntimeError(f"All cheap LLM providers failed: {'; '.join(errors)}")


async def quality(system: str, user_message: str, max_tokens: int = 2048) -> str:
    """Call the quality model. Tries OpenAI GPT-4.1 first (free credits), falls back to Sonnet."""
    # Try GPT-4.1 first if OpenAI key is available
    if settings.openai_api_key:
        try:
            return await _openai_compat(system, user_message, max_tokens,
                                         api_key=settings.openai_api_key,
                                         base_url=None,
                                         model="gpt-4.1")
        except Exception as exc:
            logger.warning(f"[LLM] quality: GPT-4.1 failed: {exc} — falling back to Sonnet")

    return await _sonnet(system, user_message, max_tokens)


async def _call_provider(provider: str, system: str, user_message: str, max_tokens: int) -> str:
    """Route to the right provider."""
    if provider == "gemini":
        return await _gemini(system, user_message, max_tokens)
    elif provider == "deepseek":
        return await _openai_compat(system, user_message, max_tokens,
                                     api_key=settings.deepseek_api_key,
                                     base_url="https://api.deepseek.com",
                                     model="deepseek-chat")
    elif provider == "openai":
        return await _openai_compat(system, user_message, max_tokens,
                                     api_key=settings.openai_api_key,
                                     base_url=None,
                                     model="gpt-4.1-nano")
    else:
        return await _haiku(system, user_message, max_tokens)


async def _openai_compat(system: str, user_message: str, max_tokens: int,
                          api_key: str, base_url: str | None, model: str) -> str:
    """Call any OpenAI-compatible API (OpenAI, DeepSeek, Together, Groq, etc.)."""
    from openai import AsyncOpenAI

    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url

    client = AsyncOpenAI(**kwargs)

    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError(f"{model} returned empty content (finish_reason={response.choices[0].finish_reason})")
    return content.strip()


async def _gemini(system: str, user_message: str, max_tokens: int) -> str:
    """Call Gemini Flash via the Google GenAI SDK."""
    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_message,
        config={
            "system_instruction": system,
            "max_output_tokens": max_tokens,
            "response_mime_type": "application/json",
        },
    )
    return response.text


async def _haiku(system: str, user_message: str, max_tokens: int) -> str:
    """Call Anthropic Haiku — final fallback, always works if Anthropic key is set."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    message = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text.strip()


async def _sonnet(system: str, user_message: str, max_tokens: int) -> str:
    """Call Anthropic Sonnet."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text.strip()
