"""
ai_stream.py — Async, token-by-token streaming for every provider TermAId
already supports.

Your `termaid/providers/AIClient.chat()` is a blocking single-shot call — great
for module commands that need one final string. For the chat experience in the
web/mobile UI we want tokens to appear as they're generated, so this module adds
an async generator that yields text chunks over the provider's SSE / streaming
API. It reuses your existing `PROVIDER_SPECS` so there's one source of truth for
endpoints, models, and auth.

    async for chunk in stream_chat("gemini-flash", "explain TCP handshake"):
        await ws.send_json({"type": "chat_delta", "text": chunk})
"""

from __future__ import annotations

import json
from typing import AsyncIterator


def _provider_specs() -> dict:
    from termaid.providers import PROVIDER_SPECS  # type: ignore
    return PROVIDER_SPECS


def _api_key(spec: dict) -> str | None:
    from .secrets import get_secret
    for k in spec.get("env_keys", []):
        v = (get_secret(k) or "").strip()
        if v:
            return v
    return None


async def stream_chat(
        provider: str,
        message: str,
        system: str = "") -> AsyncIterator[str]:
    """Yield text chunks from the model as they arrive."""
    import httpx

    specs = _provider_specs()
    spec = specs.get(provider)
    if not spec:
        yield f"[unknown provider: {provider}]"
        return

    fmt = spec["format"]
    key = _api_key(spec)
    if spec.get("env_keys") and not key:
        yield f"[no API key for {provider}]"
        return

    headers = {"Content-Type": "application/json"}

    # ---- build per-format request ----
    if fmt == "gemini":
        model = spec["model"]
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:streamGenerateContent?alt=sse"
        )
        headers[spec["auth_header"]] = key
        payload = {"contents": [{"parts": [{"text": message}]}]}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

    elif fmt == "anthropic":
        url = spec["endpoint"]
        headers[spec["auth_header"]] = key
        headers["anthropic-version"] = "2023-06-01"
        payload = {
            "model": spec["model"], "max_tokens": 4096, "stream": True,
            "messages": [{"role": "user", "content": message}],
        }
        if system:
            payload["system"] = system

    elif fmt == "openai":
        url = spec["endpoint"]
        headers[spec["auth_header"]] = spec.get(
            "auth_prefix", "") + (key or "")
        msgs = ([{"role": "system", "content": system}] if system else []) + \
            [{"role": "user", "content": message}]
        payload = {"model": spec["model"], "messages": msgs, "stream": True}

    elif fmt == "ollama":
        url = spec["endpoint"]
        msgs = ([{"role": "system", "content": system}] if system else []) + \
            [{"role": "user", "content": message}]
        payload = {"model": spec["model"], "messages": msgs, "stream": True}

    else:
        yield f"[unsupported format: {fmt}]"
        return

    # ---- stream + parse ----
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", "replace")
                    yield f"[API error {resp.status_code}: {body[:200]}]"
                    return

                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    for chunk in _parse_line(line, fmt):
                        yield chunk
    except Exception as e:
        yield f"[stream error: {e}]"


def _parse_line(line: str, fmt: str) -> list[str]:
    """Turn one streamed line into zero or more text chunks."""
    out: list[str] = []

    if fmt == "ollama":
        # newline-delimited JSON, not SSE
        try:
            data = json.loads(line)
            piece = data.get("message", {}).get("content", "")
            if piece:
                out.append(piece)
        except Exception:
            pass
        return out

    # SSE: lines look like "data: {...}" or "data: [DONE]"
    if not line.startswith("data:"):
        return out
    data_str = line[5:].strip()
    if data_str in ("[DONE]", ""):
        return out

    try:
        data = json.loads(data_str)
    except Exception:
        return out

    if fmt == "gemini":
        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                if part.get("text"):
                    out.append(part["text"])

    elif fmt == "anthropic":
        if data.get("type") == "content_block_delta":
            piece = data.get("delta", {}).get("text", "")
            if piece:
                out.append(piece)

    elif fmt == "openai":
        for choice in data.get("choices", []):
            piece = choice.get("delta", {}).get("content", "")
            if piece:
                out.append(piece)

    return out
