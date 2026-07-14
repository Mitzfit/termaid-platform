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
