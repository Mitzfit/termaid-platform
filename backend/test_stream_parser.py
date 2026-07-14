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
