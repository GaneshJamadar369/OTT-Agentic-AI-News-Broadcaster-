"""
Provider-agnostic LLM chat completions with layered fallbacks:
Groq (Multi-Org Rotation) -> Gemini -> Sarvam AI -> Fail
"""
from __future__ import annotations

import json
import os
import re
import time
import requests
from typing import Any, List, Dict, Optional

# Global state to remember last working Groq key index and provider health
_GLOBAL_STATE = {
    "idx": 0,
    "groq_exhausted": False,
    "gemini_exhausted": False,
}

def _extract_json(text: str) -> str:
    """Cleans LLM output of markdown blocks or leading/trailing garbage."""
    if not text or not isinstance(text, str):
        return "{}"
    text = text.strip()
    # Try to find content between ```json and ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.I)
    if match:
        return match.group(1).strip()
    # Or just find the first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1].strip()
    # If no brackets found, return as is (could be raw JSON)
    return text

def _is_rate_limit_error(exc: BaseException) -> bool:
    code = getattr(exc, "status_code", None)
    if code in (429, 401, 403, 500, 503):
        return True
    name = type(exc).__name__.lower()
    if any(k in name for k in ["ratelimit", "rate_limit", "auth", "exhausted", "quota"]):
        return True
    s = str(exc).lower()
    return any(k in s for k in ["429", "rate limit", "too many requests", "quota", "exhausted"])

class _OpenAICompatResponse:
    """Minimal shape expected by agents: response.choices[0].message.content."""
    def __init__(self, content: str, model: str, provider: str, is_json: bool = False):
        if is_json:
            content = _extract_json(content)
        self.choices = [_Choice(content)]
        self.model = model
        self.provider = provider

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
    """Gemini fallback using Google AI SDK."""
    if _GLOBAL_STATE["gemini_exhausted"]:
        return None

    try:
        import google.generativeai as genai
    except ImportError:
        print("[LLM] Gemini SDK not installed. Skipping.")
        return None

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    model_name = kwargs.get("model") if "gemini" in str(kwargs.get("model", "")).lower() else os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    genai.configure(api_key=api_key)
    
    messages = kwargs.get("messages") or []
    prompt = _messages_to_prompt(messages)
    temperature = float(kwargs.get("temperature", 0.0))
    want_json = kwargs.get("response_format") == {"type": "json_object"}

    model = genai.GenerativeModel(model_name)
    gen_cfg: dict[str, Any] = {"temperature": temperature}
    if want_json:
        gen_cfg["response_mime_type"] = "application/json"

    print(f"[LLM] Falling back to Gemini ({model_name})...")
    start = time.time()
    try:
        r = model.generate_content(prompt, generation_config=gen_cfg)
        latency = time.time() - start
        text = (r.text or "").strip()
        print(f"[LLM] Gemini SUCCESS | Latency: {latency:.2f}s")
        return _OpenAICompatResponse(text, model_name, "gemini", is_json=want_json)
    except Exception as e:
        if _is_rate_limit_error(e):
            print(f"[LLM] Gemini Exhausted. Short-circuiting for this session.")
            _GLOBAL_STATE["gemini_exhausted"] = True
        else:
            print(f"[LLM] Gemini FAIL: {e}")
        return None

def _sarvam_fallback_create(**kwargs: Any) -> Any:
    """Sarvam AI fallback via REST API."""
    api_key = os.getenv("SARVAM_API_KEY", "").strip()
    if not api_key:
        return None

    url = "https://api.sarvam.ai/v1/chat/completions"
    
    # Intelligent steering: If requested model was 8b-class, use the faster 30b model
    requested_model = str(kwargs.get("model", "")).lower()
    default_sarvam = os.getenv("SARVAM_MODEL", "sarvam-30b")
    
    if "8b" in requested_model or "instant" in requested_model:
        model_name = "sarvam-30b"
    else:
        model_name = default_sarvam
    
    headers = {
        "Content-Type": "application/json",
        "api-subscription-key": api_key,
        "Authorization": f"Bearer {api_key}"
    }
    
    want_json = kwargs.get("response_format") == {"type": "json_object"}
    
    # Payload adaptation
    payload = {
        "model": model_name,
        "messages": kwargs.get("messages", []),
        "temperature": kwargs.get("temperature", 0),
        "max_tokens": kwargs.get("max_tokens"),
        "stream": False
    }
    
    if want_json:
        payload["response_format"] = {"type": "json_object"}

    print(f"[LLM] Falling back to Sarvam AI ({model_name})...")
    start = time.time()
    
    # Retry logic for Sarvam specific errors
    for attempt in range(2):
        try:
            # Increase timeout to 180s for large context/heavy generation
            resp = requests.post(url, headers=headers, json=payload, timeout=180)
            latency = time.time() - start
            
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                print(f"[LLM] Sarvam SUCCESS | Latency: {latency:.2f}s")
                return _OpenAICompatResponse(content, model_name, "sarvam", is_json=want_json)
            
            error_data = resp.text
            try:
                error_data = resp.json()
            except:
                pass
                
            print(f"[LLM] Sarvam HTTP {resp.status_code} Error: {error_data}")
            
            # Handle specific retryable errors
            if resp.status_code in (429, 500, 503):
                time.sleep(2)
                continue
            break
        except Exception as e:
            print(f"[LLM] Sarvam Connection Error: {e}")
            if attempt == 0:
                time.sleep(1)
                continue
            raise

    return None

def llm_chat_create(client: Any = None, **kwargs: Any) -> Any:
    """
    Primary entry point for LLM calls.
    Layers: Groq (Multi-Key) -> Gemini -> Sarvam AI
    """
    # 1. GROQ LAYER
    if not _GLOBAL_STATE["groq_exhausted"]:
        keys_str = os.getenv("GROQ_API_KEY", "").strip()
        groq_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        
        if groq_keys:
            from groq import Groq
            total_keys = len(groq_keys)
            attempts = int(os.getenv("GROQ_CHAT_MAX_ATTEMPTS", "10"))
            
            last_err = None
            for i in range(attempts):
                idx = (_GLOBAL_STATE["idx"] + i) % total_keys
                curr_key = groq_keys[idx]
                
                try:
                    # We use a fresh client per key if rotating
                    g_client = Groq(api_key=curr_key)
                    start = time.time()
                    res = g_client.chat.completions.create(**kwargs)
                    latency = time.time() - start
                    
                    # Remember working key
                    _GLOBAL_STATE["idx"] = idx
                    
                    # Log success
                    model = kwargs.get("model", "unknown")
                    print(f"[LLM] Groq SUCCESS | Key {idx+1}/{total_keys} | Model: {model} | Latency: {latency:.2f}s")
                    
                    # Tag response with metadata
                    res.provider = "groq"
                    return res
                except Exception as e:
                    last_err = e
                    if not _is_rate_limit_error(e):
                        print(f"[LLM] Groq FATAL Error (Key {idx+1}): {e}")
                        raise
                    
                    # Check for Organization Quota Exhausted specifically
                    err_msg = str(e).lower()
                    org_match = re.search(r"organization (org_[a-z0-9]+)", err_msg)
                    org_id = org_match.group(1) if org_match else "unknown"
                    
                    print(f"[LLM] Groq Rate Limit (Key {idx+1}, Org {org_id}). Rotating...")
                    
                    # If we've tried all keys, break to next provider and mark group exhausted
                    if i >= total_keys - 1:
                        print("[LLM] All Groq keys/orgs exhausted. Short-circuiting for this session.")
                        _GLOBAL_STATE["groq_exhausted"] = True
                        break

    # 2. GEMINI FALLBACK
    try:
        gemini_res = _gemini_fallback_create(**kwargs)
        if gemini_res:
            return gemini_res
    except Exception as e:
        print(f"[LLM] Gemini Fallback failed critical: {e}")

    # 3. SARVAM FALLBACK
    try:
        sarvam_res = _sarvam_fallback_create(**kwargs)
        if sarvam_res:
            return sarvam_res
    except Exception as e:
        print(f"[LLM] Sarvam Fallback failed critical: {e}")

    raise RuntimeError("All LLM providers (Groq, Gemini, Sarvam) failed or are unconfigured.")

# Backward compatibility alias
def groq_chat_create(client: Any, **kwargs: Any) -> Any:
    return llm_chat_create(client, **kwargs)
