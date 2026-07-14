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
