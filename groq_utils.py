"""Shared Groq chat completions with retries on 429; optional Gemini (Google AI) fallback."""
from __future__ import annotations

import os
import re
import time
from typing import Any


def _is_rate_limit_error(exc: BaseException) -> bool:
    code = getattr(exc, "status_code", None)
    if code == 429:
        return True
    name = type(exc).__name__.lower()
    if "ratelimit" in name or "rate_limit" in name:
        return True
    s = str(exc).lower()
    return "429" in s or "rate limit" in s or "too many requests" in s


class _OpenAICompatResponse:
    """Minimal shape expected by agents: response.choices[0].message.content."""

    def __init__(self, content: str):
        self.choices = [_Choice(content)]


class _Choice:
    def __init__(self, content: str):
        self.message = _Message(content)


class _Message:
    def __init__(self, content: str):
        self.content = content


def _messages_to_prompt(messages: list) -> str:
    parts = []
    for m in messages or []:
        role = m.get("role", "user")
        c = m.get("content", "")
        parts.append(f"[{role}]\n{c}")
    return "\n\n".join(parts)


def _gemini_fallback_create(**kwargs: Any) -> Any:
    """Google AI Studio — set GEMINI_API_KEY in .env (never commit keys)."""
    try:
        import google.generativeai as genai
    except ImportError as e:
        raise RuntimeError(
            "GEMINI_API_KEY is set but google-generativeai is not installed. "
            "Run: pip install google-generativeai"
        ) from e

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    genai.configure(api_key=api_key)
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    messages = kwargs.get("messages") or []
    prompt = _messages_to_prompt(messages)
    temperature = float(kwargs.get("temperature", 0.2))
    want_json = kwargs.get("response_format") == {"type": "json_object"}

    model = genai.GenerativeModel(model_name)
    gen_cfg: dict[str, Any] = {"temperature": temperature}
    if want_json:
        gen_cfg["response_mime_type"] = "application/json"

    print(f"[LLM] Groq rate limit exhausted — fallback to Gemini ({model_name})")
    r = model.generate_content(prompt, generation_config=gen_cfg)
    text = (r.text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned empty text")
    return _OpenAICompatResponse(text)


def groq_chat_create(client: Any, *, max_attempts: int | None = None, **kwargs: Any):
    """
    Wrap client.chat.completions.create with retries on 429 (TPM / rate limit).
    If all attempts fail and GEMINI_API_KEY is set, one Gemini call is attempted.
    """
    attempts = max_attempts
    if attempts is None:
        attempts = int(os.getenv("GROQ_CHAT_MAX_ATTEMPTS", "15"))
    last: BaseException | None = None
    fallback_ok = os.getenv("GROQ_GEMINI_FALLBACK", "true").lower() in ("1", "true", "yes")

    for i in range(attempts):
        try:
            return client.chat.completions.create(**kwargs)
        except BaseException as e:
            last = e
            if not _is_rate_limit_error(e):
                raise
            err = str(e)
            m = re.search(r"try again in ([0-9.]+)\s*ms", err, re.I)
            if m:
                delay = float(m.group(1)) / 1000.0 + 0.35
            else:
                delay = min(1.5**i, 120.0)
            delay = max(delay, 0.5)
            print(
                f"[Groq] Rate limit (429); sleeping {delay:.2f}s then retry "
                f"{i + 1}/{attempts}…"
            )
            time.sleep(delay)

    if fallback_ok and os.getenv("GEMINI_API_KEY", "").strip():
        try:
            return _gemini_fallback_create(**kwargs)
        except Exception as gem_e:
            print(f"[LLM] Gemini fallback failed: {gem_e}")
            if last is not None:
                raise last from gem_e
            raise

    if last is not None:
        raise last
    raise RuntimeError("groq_chat_create: no attempts and no exception")
