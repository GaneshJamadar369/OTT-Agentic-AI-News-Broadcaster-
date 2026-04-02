"""Sarvam-first LLM client helpers (OpenAI-compatible API)."""
from __future__ import annotations

import os
import time
import json
import re
from typing import Any


def _sarvam_api_key() -> str:
    # Backward-compatible fallback: older local envs may still use SARVAM_API.
    return (os.getenv("SARVAM_API_KEY") or os.getenv("SARVAM_API") or "").strip()


def _is_retryable_error(exc: BaseException) -> bool:
    markers = (
        "429",
        "rate limit",
        "too many requests",
        "resourceexhausted",
        "quota",
        "temporarily unavailable",
        "connection error",
        "timed out",
        "timeout",
    )
    s = str(exc).lower()
    return any(m in s for m in markers)


def _create_client():
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError("OpenAI Python SDK is missing. Install `openai`.") from e

    key = _sarvam_api_key()
    if not key:
        raise RuntimeError(
            "CRITICAL: SARVAM_API_KEY NOT FOUND. Set SARVAM_API_KEY in your .env."
        )
    base_url = (os.getenv("SARVAM_BASE_URL") or "https://api.sarvam.ai/v1").strip()
    return OpenAI(api_key=key, base_url=base_url)


def sarvam_chat_create(client: Any, *, max_attempts: int | None = None, **kwargs: Any):
    """
    OpenAI-compatible chat completion call routed to Sarvam.
    The first `client` arg is kept for backward compatibility with existing callsites.
    """
    k = dict(kwargs)
    req_model = str(k.get("model") or "").strip()
    model_name = req_model or (os.getenv("SARVAM_MODEL") or "sarvam-105b").strip()
    k["model"] = model_name

    sdk_client = client or _create_client()
    attempts = max_attempts or int(os.getenv("SARVAM_MAX_ATTEMPTS", "3"))
    attempts = max(1, attempts)
    base_delay = float(os.getenv("SARVAM_RETRY_BASE_DELAY_SEC", "2"))

    for attempt in range(attempts):
        try:
            print(f"[LLM] Sarvam AI ({model_name}) attempt {attempt + 1}/{attempts}")
            return sdk_client.chat.completions.create(**k)
        except BaseException as e:
            is_retry = _is_retryable_error(e)
            if attempt >= attempts - 1 or not is_retry:
                print(f"[LLM] Sarvam critical error: {e}")
                raise
            delay = base_delay * (attempt + 1)
            print(f"[LLM] Sarvam transient error; sleeping {delay:.1f}s...")
            time.sleep(delay)

    raise RuntimeError("Sarvam chat completion failed after max attempts.")


def groq_chat_create(client: Any, *, max_attempts: int | None = None, **kwargs: Any):
    """Backward-compat alias. Prefer `sarvam_chat_create`."""
    return sarvam_chat_create(client, max_attempts=max_attempts, **kwargs)


def parse_json_completion(response: Any, default: Any):
    """
    Parse a JSON object/array from a completion response.
    Falls back to `default` if content is empty or non-JSON.
    """
    raw = (
        (response.choices[0].message.content or "")
        if getattr(response, "choices", None)
        else ""
    ).strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        obj_match = re.search(r"\{[\s\S]*\}", raw)
        if obj_match:
            try:
                return json.loads(obj_match.group(0))
            except Exception:
                return default
        arr_match = re.search(r"\[[\s\S]*\]", raw)
        if arr_match:
            try:
                return json.loads(arr_match.group(0))
            except Exception:
                return default
        return default
