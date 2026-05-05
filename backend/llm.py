"""Unified LLM client — supports Groq (cloud, free) and Ollama (local).

Priority order:
  1. Groq  — if GROQ_API_KEY is set (fast cloud inference, free tier)
  2. Ollama — if reachable on OLLAMA_URL (local Docker / desktop)
  3. Rule-based fallback — if neither is available

Every module calls `get_llm()` — it returns the right backend automatically.
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from backend.config import settings

_TIMEOUT = httpx.Timeout(180.0, connect=10.0)


# ── Groq client (OpenAI-compatible) ───────────────────────────────────────────

class GroqClient:
    """Calls Groq's OpenAI-compatible API. Free tier: 14,400 req/day."""

    GROQ_BASE = "https://api.groq.com/openai/v1"
    # Fast, capable model available on free tier
    DEFAULT_MODEL = "llama-3.3-70b-versatile"

    def __init__(self, api_key: str, model: str | None = None):
        self.api_key = api_key
        self.model_name = model or self.DEFAULT_MODEL

    def _chat(self, messages: list[dict], max_tokens: int = 4096) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(f"{self.GROQ_BASE}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def generate(self, prompt: str, *, max_tokens: int = 4096, system: str | None = None) -> str:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self._chat(messages, max_tokens)

    def generate_json(self, prompt: str, *, max_tokens: int = 4096, system: str | None = None) -> dict | list:
        json_prompt = (
            prompt + "\n\nIMPORTANT: Respond with valid JSON only. "
            "No explanation, no markdown fences, no extra text — just the JSON."
        )
        raw = self.generate(json_prompt, max_tokens=max_tokens, system=system)
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
        raw = raw.strip()
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw)
        if match:
            raw = match.group(1)
        return json.loads(raw)

    async def generate_json_async(self, prompt: str, *, max_tokens: int = 4096, system: str | None = None) -> dict | list:
        import asyncio
        from functools import partial
        return await asyncio.to_thread(
            partial(self.generate_json, prompt, max_tokens=max_tokens, system=system)
        )

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=5.0) as client:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                resp = client.get(f"{self.GROQ_BASE}/models", headers=headers)
                return resp.status_code == 200
        except Exception:
            return False


# ── Ollama client (local) ─────────────────────────────────────────────────────

class LLMClient:
    """Thin wrapper around Ollama that exposes a simple generate interface."""

    def __init__(self, model: str | None = None):
        self.model_name = model or settings.ollama_model
        self.base_url = settings.ollama_url.rstrip("/")

    def generate(self, prompt: str, *, max_tokens: int = 4096, system: str | None = None) -> str:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": max_tokens},
        }
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
        return resp.json()["message"]["content"].strip()

    async def generate_json_async(self, prompt: str, *, max_tokens: int = 4096, system: str | None = None) -> dict | list:
        import asyncio
        from functools import partial
        return await asyncio.to_thread(
            partial(self.generate_json, prompt, max_tokens=max_tokens, system=system)
        )

    def generate_json(self, prompt: str, *, max_tokens: int = 4096, system: str | None = None) -> dict | list:
        json_prompt = (
            prompt + "\n\nIMPORTANT: Respond with valid JSON only. "
            "No explanation, no markdown fences, no extra text — just the JSON."
        )
        raw = self.generate(json_prompt, max_tokens=max_tokens, system=system)
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
        raw = raw.strip()
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw)
        if match:
            raw = match.group(1)
        return json.loads(raw)

    def generate_with_tools(self, messages: list[dict], tools: list[dict], system: str | None = None, max_tokens: int = 4096) -> dict:
        chat_messages: list[dict] = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        for msg in messages:
            role = msg.get("role", "user")
            if role == "model":
                role = "assistant"
            parts = msg.get("parts", msg.get("content", ""))
            if isinstance(parts, list):
                content = " ".join(p if isinstance(p, str) else str(p) for p in parts)
            else:
                content = str(parts)
            chat_messages.append({"role": role, "content": content})

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": chat_messages,
            "tools": tools,
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": max_tokens},
        }
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(f"{self.base_url}/v1/chat/completions", json=payload)
            resp.raise_for_status()

        data = resp.json()
        choice = data["choices"][0]
        message = choice["message"]
        finish_reason = choice.get("finish_reason", "stop")

        result: dict[str, Any] = {
            "text": message.get("content") or None,
            "function_calls": None,
            "finish_reason": finish_reason,
        }
        raw_tool_calls = message.get("tool_calls")
        if raw_tool_calls:
            parsed = []
            for i, tc in enumerate(raw_tool_calls):
                args = tc["function"].get("arguments", "{}")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                parsed.append({"id": tc.get("id", f"call_{i}"), "name": tc["function"]["name"], "args": args})
            result["function_calls"] = parsed
            result["finish_reason"] = "tool_use"
        return result


# ── Factory ───────────────────────────────────────────────────────────────────

def get_llm(model: str | None = None) -> LLMClient | GroqClient:
    """
    Returns the best available LLM client:
      1. Groq  — if GROQ_API_KEY is configured
      2. Ollama — fallback (local Docker)
    """
    if settings.groq_api_key:
        return GroqClient(api_key=settings.groq_api_key, model=model)
    return LLMClient(model=model)


def ollama_is_available() -> bool:
    """True if Ollama is reachable (local mode)."""
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{settings.ollama_url.rstrip('/')}/api/version")
            return resp.status_code == 200
    except Exception:
        return False


def llm_is_available() -> bool:
    """True if ANY LLM backend is reachable (Groq or Ollama)."""
    if settings.groq_api_key:
        return True   # Groq is always up if key is set; avoid extra HTTP call
    return ollama_is_available()
