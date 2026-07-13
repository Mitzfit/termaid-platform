# TermAId — Code Style & Commenting Conventions

Production-readiness rule: a new developer should understand any file from its
header and any function from its docstring, without reading the whole codebase.

## Universal
- File header first: purpose, what it owns, how it fits the system, and
  `Author: Misfit`.
- Every documented block is attributed to Misfit (the project author).
- Comment the WHY (intent, trade-offs, gotchas), not the WHAT (the code shows that).
- Small, single-purpose functions. Clear names over clever ones.
- Public behavior gets a test.

## Python
```python
"""
models.py — ORM tables for the web layer.

Owns: User, CommandHistory, RefreshSession. Read by the Backend and AI windows
via the schema, so changes here ripple — flag them in the hand-back.

Author: Misfit
"""

def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt.

    Args:
        plain: the user-supplied password.
    Returns:
        A bcrypt hash safe to store. Never store or log `plain`.
    """
    ...
```
- Full type hints. Module docstring + function docstrings (Google or NumPy style).
- `# why-comment` inline only where the reason isn't obvious.

## TypeScript
```ts
/**
 * Typed REST client. Handles auth + token storage + auto-refresh.
 * Mirrors backend/schemas.py — keep the two in sync (cross-window).
 */
export async function login(username: string, password: string): Promise<TokenPair> {
  // OAuth2 password flow expects form-encoded, not JSON.
  ...
}
```
- JSDoc on exported functions/types. Explain non-obvious control flow inline.

## Rust
```rust
/// Scan `host` over an inclusive port range with a per-port connect timeout.
/// Uses a bounded thread pool so even a large range stays fast and predictable.
pub fn scan(host: &str, start: u16, end: u16, timeout_ms: u64) -> ScanResult {
    // 128 workers balances throughput against fd/thread limits on phones.
    ...
}
```
- `///` doc-comments on public items; `//` inline for intent. `cargo clippy` clean.

## Commenting cadence (don't boil the ocean)
Comment each window's files as we work that window — not all 120 modules at once.
Each window's hand-back should leave its files fully documented to this standard.
