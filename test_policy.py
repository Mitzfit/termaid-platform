"""Policy unit tests — no termaid package required."""
from backend.policy import allowed_modules, SAFE_MODULES, DANGEROUS_MODULES

DISCOVERED = ["calc", "text", "privesc", "git", "assistant", "fwown", "weather"]


def test_server_mode_allows_only_safe_and_ai():
    allowed, blocked = allowed_modules(DISCOVERED, "server")
    assert "calc" in allowed and "weather" in allowed       # safe
    assert "assistant" in allowed                           # ai
    assert "privesc" in blocked and "fwown" in blocked      # dangerous
    assert "git" in blocked                                 # system → blocked on server


def test_local_mode_allows_system_but_not_dangerous():
    allowed, blocked = allowed_modules(DISCOVERED, "local")
    assert "git" in allowed                                 # system ok locally
    assert "calc" in allowed
    assert "privesc" in blocked and "fwown" in blocked      # still blocked


def test_dangerous_never_leaks_in_either_mode():
    for mode in ("server", "local"):
        allowed, _ = allowed_modules(list(DANGEROUS_MODULES), mode)
        assert not (allowed & DANGEROUS_MODULES)


def test_operator_overrides():
    allowed, blocked = allowed_modules(
        ["git", "weather"], "server",
        extra_allow={"git"}, extra_deny={"weather"},
    )
    assert "git" in allowed         # force-allowed
    assert "weather" in blocked     # force-denied
