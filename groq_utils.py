"""Shared Groq chat completions with retries on 429; optional Gemini (Google AI) fallback."""
from __future__ import annotations

import os
import re
import time
from typing import Any


_GLOBAL_KEY_STATE = {"idx": 0}


def _is_rate_limit_error(exc: BaseException) -> bool:
    code = getattr(exc, "status_code", None)
    if code == 429:
        return True
    # We also rotate on 401 if multiple keys are provided, handled inside the main loop
    if code == 401:
        return True
    name = type(exc).__name__.lower()
    if "ratelimit" in name or "rate_limit" in name or "auth" in name:
        return True
    s = str(exc).lower()
    return "429" in s or "rate limit" in s or "too many requests" in s or "401" in s or "invalid api key" in s


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
    Supports multiple keys via GROQ_API_KEY env var (comma-separated).
    If a key hits 429, it switches to the next one.
    If all attempts/keys fail and GEMINI_API_KEY is set, one Gemini call is attempted.
    """
    # 1. Gather all available Groq keys
    keys_str = os.getenv("GROQ_API_KEY", "").strip()
    if keys_str:
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
    else:
        # Fallback to single GROQ_API_KEY if present
        k1 = os.getenv("GROQ_API_KEY", "").strip()
        keys = [k1] if k1 else []

    # 2. Prepare clients
    from groq import Groq
    
    unique_keys = []
    seen = set()
    for k in keys:
        if k not in seen:
            unique_keys.append(k)
            seen.add(k)
    
    all_clients = [Groq(api_key=k) for k in unique_keys]
    if not all_clients:
        all_clients = [client]
    
    total_keys = len(all_clients)
    attempts = max_attempts or int(os.getenv("GROQ_CHAT_MAX_ATTEMPTS", "15"))
    last: BaseException | None = None
    fallback_ok = os.getenv("GROQ_GEMINI_FALLBACK", "true").lower() in ("1", "true", "yes")

    for i in range(attempts):
        idx = (_GLOBAL_KEY_STATE["idx"] + i) % total_keys
        curr = all_clients[idx]
        try:
            res = curr.chat.completions.create(**kwargs)
            _GLOBAL_KEY_STATE["idx"] = idx
            return res
        except BaseException as e:
            last = e
            if not _is_rate_limit_error(e):
                raise
            
            err = str(e)
            from groq import AuthenticationError
            is_401 = isinstance(e, AuthenticationError) or getattr(e, "status_code", None) == 401
            
            if is_401:
                if total_keys > 1:
                    _GLOBAL_KEY_STATE["idx"] = (idx + 1) % total_keys
                    print(
                        f"[Groq] Key {idx + 1} failed (401 unauthorized). "
                        "Remove or replace this key in GROQ_API_KEY. Trying next key..."
                    )
                    continue
                print("[Groq] Single API key failed (401). Check GROQ_API_KEY is valid.")
                raise
            
            if (i + 1) % total_keys == 0:
                m = re.search(r"try again in ([0-9.]+)\s*ms", err, re.I)
                delay = float(m.group(1))/1000.0 + 0.35 if m else min(1.5**(i//total_keys), 60.0)
                print(f"[Groq] Rate limited. Sleeping {delay:.2f}s...")
                time.sleep(max(delay, 0.5))

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
