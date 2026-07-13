# Agent 04 — AI & The Brain (complete kit)

Attach this single file to the AI & Brain agent window (or add to project knowledge). Contains the brief, baseline, start prompt, and all owned source.

---

# Agent 04 — AI & The Brain

**Role:** AI engineer. The model layer — providers, token streaming, and the
reasoning modules. Where Termaid actually "thinks".
**Baseline health:** 5.9 / 10 (set 2026-06-13).

## Owns
- `backend/ai_stream.py` — async token-by-token streaming for every provider.
- `backend/providers_extra.py` — adds xai/together/fireworks/deepinfra at runtime
  without forking the CLI's provider source.
- `backend/tests/test_stream_parser.py` — stream-parser tests (maintain + extend).
- Governs (CLI side, read the contract; don't fork blindly):
  `termaid/providers/__init__.py` (PROVIDER_SPECS + AIClient) — shipped here as
  `cli_providers__init__.py` for reference.
- Reasoning modules (CLI): brain, cognition, cortex, smart, agent, chain.

## Depends on / feeds
- Reads: Secrets & Config (Agent 11) for API keys (keychain/.env).
- Feeds: Backend Core (main.py streaming chat route).

## Standing job (WINDOW_DIRECTIVES)
Brainstorm → Document → Break down → Harden → Health report. Obey RULES.md
(incl. Termaid spelling). Never touch another window's files.


---

# Health Report — AI & The Brain  (BASELINE, v2.3.1, 2026-06-13)

| Category | Score | Notes |
|---|---|---|
| Correctness / reliability | 6 | Stream parsing for 5 provider formats works (test_stream_parser in CI). providers_extra adds 4 providers at runtime. |
| Security | 6 | Keys sourced from secrets/keychain (Agent 11). Prompt-injection surface in agent/chain modules; error leakage to check. |
| Performance | 7 | Async streaming is sound; throughput bounded by provider latency. |
| Architecture / maintainability | 7 | Clean provider abstraction; runtime extension avoids forking the CLI. |
| Test coverage | 4 | Parser covered; providers_extra registration + error/timeout paths untested. |
| Documentation | 4 | Headers present; per-function why-docs thin. |
| Cross-window cohesion | 6 | Feeds main.py chat; depends on secrets contract. |
| **Overall** | **5.9** | Capable model layer; needs error-path tests + documentation. |

## Top 3 risks
1. Provider error/timeout/cancel handling — a hung or failing stream shouldn't wedge a request.
2. Key handling — confirm keys only come from secrets/keychain, never logged.
3. Reasoning-module prompt-injection surface (agent/chain) — input boundaries.

## Highest-value next action
Directive 1 (document ai_stream.py + providers_extra.py to CODE_STYLE, Misfit) +
add tests for provider registration and stream error/timeout/cancel paths →
Documentation 4→8, Tests 4→7.


---

## START PROMPT (paste into the new agent window)

```
This is the AI & THE BRAIN agent.

Your role: AI engineer. You own backend/ai_stream.py (async token streaming for all
providers), backend/providers_extra.py (adds xai/together/fireworks/deepinfra at
runtime), and backend/tests/test_stream_parser.py. You govern the CLI provider
contract (termaid/providers/__init__.py — PROVIDER_SPECS + AIClient) and the
reasoning modules (brain, cognition, cortex, smart, agent, chain) — read the
contract; don't fork it blindly. Work ONLY on your files.

Read from project knowledge first: MASTER_INDEX.md, ARCHITECTURE.md, CODE_STYLE.md,
WINDOW_DIRECTIVES.md, RULES.md (Termaid spelling), LESSONS.md, BASELINE_HEALTH.md.

Run the kickoff brainstorm, then the four directives: 1) Document (what/does/why,
Misfit), 2) Break down (BREAKDOWN.md), 3) Harden, 4) Health report.

Watch-items this session:
- Stream error/timeout/cancel handling — a failing stream must not wedge a request.
- API keys come only from secrets/keychain (Agent 11); never log a key.
- Reasoning modules (agent/chain) input boundaries — prompt-injection surface.

Hand back with HANDOFF_TEMPLATE.md + updated files (as .py text, not PDF) + INDEX +
BREAKDOWN + health report + appended HISTORY. Bump the version.

Your files are attached. Today's task: <I will set this in the brainstorm>.

```

---

## OWNED SOURCE CODE

### `backend/ai_stream.py`

```python
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
import os
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


async def stream_chat(provider: str, message: str, system: str = "") -> AsyncIterator[str]:
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
        headers[spec["auth_header"]] = spec.get("auth_prefix", "") + (key or "")
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

```

### `backend/providers_extra.py`

```python
"""
providers_extra.py — add providers WITHOUT editing your CLI's source.

Your `termaid/providers/__init__.py` defines PROVIDER_SPECS. Because that's a
plain module-level dict shared by both the streaming path (ai_stream.py) and the
CLI's own provider code, we can extend it in place at startup. Anything added
here becomes selectable via AI_PROVIDER and usable by every AI module — no fork.

All of these speak the OpenAI chat format, which ai_stream already streams, so
they work out of the box once you add the matching key to .env.
"""

from __future__ import annotations

EXTRA_SPECS: dict[str, dict] = {
    # xAI Grok — the actual "Grok" (distinct from Groq).
    "xai": {
        "name": "xAI Grok",
        "model": "grok-2-latest",
        "endpoint": "https://api.x.ai/v1/chat/completions",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "env_keys": ["XAI_API_KEY"],
        "tier": "complex",
        "format": "openai",
    },
    # Together AI — large catalogue of hosted open-source models.
    "together": {
        "name": "Together AI",
        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "endpoint": "https://api.together.xyz/v1/chat/completions",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "env_keys": ["TOGETHER_API_KEY"],
        "tier": "simple",
        "format": "openai",
    },
    # Fireworks AI — fast hosted open-source inference.
    "fireworks": {
        "name": "Fireworks AI",
        "model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "endpoint": "https://api.fireworks.ai/inference/v1/chat/completions",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "env_keys": ["FIREWORKS_API_KEY"],
        "tier": "simple",
        "format": "openai",
    },
    # DeepInfra — cheap hosted open-source models.
    "deepinfra": {
        "name": "DeepInfra",
        "model": "meta-llama/Llama-3.3-70B-Instruct",
        "endpoint": "https://api.deepinfra.com/v1/openai/chat/completions",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "env_keys": ["DEEPINFRA_API_KEY"],
        "tier": "simple",
        "format": "openai",
    },
}


def merge_into_cli_specs() -> int:
    """Merge EXTRA_SPECS into the CLI's PROVIDER_SPECS (no overwrite). Returns
    how many new providers were added. Safe no-op if the CLI isn't importable."""
    try:
        from termaid.providers import PROVIDER_SPECS  # type: ignore
    except Exception:
        return 0
    added = 0
    for name, spec in EXTRA_SPECS.items():
        if name not in PROVIDER_SPECS:
            PROVIDER_SPECS[name] = spec
            added += 1
    return added

```

### `backend/tests/test_stream_parser.py`

```python
"""Streaming parser unit tests — pure, no network."""
from backend.ai_stream import _parse_line


def test_openai_delta():
    line = 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
    assert _parse_line(line, "openai") == ["Hello"]


def test_anthropic_delta():
    line = 'data: {"type":"content_block_delta","delta":{"text":" world"}}'
    assert _parse_line(line, "anthropic") == [" world"]


def test_gemini_parts():
    line = 'data: {"candidates":[{"content":{"parts":[{"text":"hi"}]}}]}'
    assert _parse_line(line, "gemini") == ["hi"]


def test_ollama_ndjson():
    assert _parse_line('{"message":{"content":"tok"}}', "ollama") == ["tok"]


def test_done_sentinel_ignored():
    assert _parse_line("data: [DONE]", "openai") == []


def test_malformed_line_is_safe():
    assert _parse_line("data: not-json", "openai") == []
    assert _parse_line("", "openai") == []

```

### `termaid/providers/__init__.py  (REFERENCE — CLI contract, do not fork blindly)`

```python
"""Unified AI provider clients.

Uses httpx directly (no SDKs) so it works on Termux without Rust.
Supports: Gemini, Groq, Cerebras, OpenAI, Anthropic, OpenRouter, Ollama.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional


PROVIDER_SPECS = {
    "gemini": {
        "name": "Gemini 2.5 Pro",
        "model": "gemini-2.5-pro",
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "auth_header": "x-goog-api-key",
        "env_keys": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        "tier": "complex",
        "format": "gemini",
    },
    "gemini-flash": {
        "name": "Gemini 2.5 Flash",
        "model": "gemini-2.5-flash",
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "auth_header": "x-goog-api-key",
        "env_keys": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        "tier": "simple",
        "format": "gemini",
    },
    "groq": {
        "name": "Groq (Llama 3.3)",
        "model": "llama-3.3-70b-versatile",
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "env_keys": ["GROQ_API_KEY"],
        "tier": "simple",
        "format": "openai",
    },
    "cerebras": {
        "name": "Cerebras",
        "model": "llama-3.3-70b",
        "endpoint": "https://api.cerebras.ai/v1/chat/completions",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "env_keys": ["CEREBRAS_API_KEY"],
        "tier": "simple",
        "format": "openai",
    },
    "openai": {
        "name": "OpenAI GPT-4o",
        "model": "gpt-4o",
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "env_keys": ["OPENAI_API_KEY"],
        "tier": "complex",
        "format": "openai",
    },
    "anthropic": {
        "name": "Claude",
        "model": "claude-sonnet-4-5",
        "endpoint": "https://api.anthropic.com/v1/messages",
        "auth_header": "x-api-key",
        "env_keys": ["ANTHROPIC_API_KEY"],
        "tier": "complex",
        "format": "anthropic",
    },
    "openrouter": {
        "name": "OpenRouter",
        "model": "meta-llama/llama-3.1-70b-instruct:free",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "env_keys": ["OPENROUTER_API_KEY"],
        "tier": "simple",
        "format": "openai",
    },
    "ollama": {
        "name": "Ollama (local)",
        "model": "llama3.2",
        "endpoint": "http://localhost:11434/api/chat",
        "auth_header": None,
        "env_keys": [],
        "tier": "simple",
        "format": "ollama",
    },
}


@dataclass
class ChatResponse:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class AIClient:
    """Unified client for all AI providers."""

    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.spec = PROVIDER_SPECS.get(provider_name)
        if not self.spec:
            raise ValueError(f"Unknown provider: {provider_name}")
        self.name = provider_name
        self.display_name = self.spec["name"]
        self.model = self.spec["model"]

    def _get_key(self) -> Optional[str]:
        for k in self.spec["env_keys"]:
            val = os.environ.get(k, "").strip()
            if val:
                return val
        return None

    def chat(self, message: str, system: str = "") -> ChatResponse:
        """Send a chat message, return the response."""
        import httpx

        fmt = self.spec["format"]
        key = self._get_key()

        if self.spec["env_keys"] and not key:
            return ChatResponse(
                text=f"[Error: No API key for {self.provider_name}. Use /router.addkey {self.provider_name} <key>]",
                provider=self.provider_name, model=self.model,
            )

        headers = {"Content-Type": "application/json"}

        # Build request per format
        if fmt == "gemini":
            url = self.spec["endpoint"].format(model=self.model)
            headers[self.spec["auth_header"]] = key
            contents = [{"parts": [{"text": message}]}]
            payload = {"contents": contents}
            if system:
                payload["systemInstruction"] = {"parts": [{"text": system}]}

        elif fmt == "anthropic":
            url = self.spec["endpoint"]
            headers[self.spec["auth_header"]] = key
            headers["anthropic-version"] = "2023-06-01"
            payload = {
                "model": self.model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": message}],
            }
            if system:
                payload["system"] = system

        elif fmt == "openai":
            url = self.spec["endpoint"]
            headers[self.spec["auth_header"]] = self.spec.get("auth_prefix", "") + key
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": message})
            payload = {"model": self.model, "messages": messages}

        elif fmt == "ollama":
            url = self.spec["endpoint"]
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": message})
            payload = {"model": self.model, "messages": messages, "stream": False}

        else:
            return ChatResponse(f"[Unknown format: {fmt}]", self.provider_name, self.model)

        try:
            with httpx.Client(timeout=90.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code != 200:
                    return ChatResponse(
                        text=f"[API error {resp.status_code}: {resp.text[:300]}]",
                        provider=self.provider_name, model=self.model,
                    )
                return self._parse_response(resp.json(), fmt)
        except Exception as e:
            return ChatResponse(
                text=f"[Connection error: {e}]",
                provider=self.provider_name, model=self.model,
            )

    def _parse_response(self, data: dict, fmt: str) -> ChatResponse:
        text = ""
        in_tok = 0
        out_tok = 0

        try:
            if fmt == "gemini":
                cands = data.get("candidates", [])
                if cands:
                    parts = cands[0].get("content", {}).get("parts", [])
                    text = "".join(p.get("text", "") for p in parts)
                usage = data.get("usageMetadata", {})
                in_tok = usage.get("promptTokenCount", 0)
                out_tok = usage.get("candidatesTokenCount", 0)

            elif fmt == "anthropic":
                content = data.get("content", [])
                if content:
                    text = content[0].get("text", "")
                usage = data.get("usage", {})
                in_tok = usage.get("input_tokens", 0)
                out_tok = usage.get("output_tokens", 0)

            elif fmt == "openai":
                choices = data.get("choices", [])
                if choices:
                    text = choices[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})
                in_tok = usage.get("prompt_tokens", 0)
                out_tok = usage.get("completion_tokens", 0)

            elif fmt == "ollama":
                text = data.get("message", {}).get("content", "")

        except Exception as e:
            text = f"[Parse error: {e}]"

        return ChatResponse(
            text=text, provider=self.provider_name, model=self.model,
            input_tokens=in_tok, output_tokens=out_tok,
        )


def get_provider(name: str) -> AIClient:
    return AIClient(name)

```


---
## HISTORY (append each session)

- 2026-06-13 · main · Kit created (baseline 5.9). Awaiting first session.
