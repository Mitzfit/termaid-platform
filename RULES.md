# RULES — Universal & Local

Two layers so you can tune how any window behaves without rewriting everything.

- **Universal rules** — permanent. Every window obeys them no matter what,
  every session. Read first, always.
- **Local (session) rules** — temporary, scoped to one session. Use them to steer
  a window for the task at hand. If a local rule proves its worth, promote it to
  Universal (see protocol below).

The hierarchy, top to bottom: Custom Instructions → Window Directives →
**Universal Rules** → **Local Rules**. Lower layers refine, never override safety
or the directives.

---

## UNIVERSAL RULES (permanent — applies to every window)

1. Never hardcode secrets, keys, or credentials. Use the keychain / `.env`.
2. Never modify files another window owns. Flag cross-window needs in the hand-back.
3. Don't break CI or change behavior silently. Tests accompany behavior changes.
4. Comment to `CODE_STYLE.md`, attributed to `Misfit`. WHY over WHAT.
5. "No change needed" is a valid, honest result. Don't churn to look busy.
6. Every session ends with a health report + hand-back. Append reusable lessons.
7. Stay inside this window's slice. Surface, don't silently absorb, scope creep.
8. **Termaid spelling.** Spell the project name "Termaid" in all human-readable
   text (prose, comments, docstrings, headers, docs, UI). The stylized "TermAId"
   is a typo. EXCEPTION: never rewrite all-caps identifiers (TERMAID_ROOT,
   TERMAID_SCAN_BIN) or crate/module names (termaid_scan, termaid_web.db) —
   those are code contracts; renaming them is a separate deliberate refactor.
9. **Structured error contract.** Any streaming/generator surface must signal
   errors/control state as a typed event (e.g. {kind:"error"}), never smuggled
   inside content. Callers branch on kind, never sniff text. (Promoted from AI v2.3.2.)
10. **NEVER delete anything without explicit approval from the user. ALWAYS ask first, no exceptions.**
11. **Always double check for typos, and syntax errors before running any code. ALWAYS ensure that you have the correct permissions to access the files you need to access.**
12. **NEVER EDIT MASTER_INDEX.md unless explicitely told to do so. I will ask you to do this as needed.**

---

_(Add new universal rules here as we promote them. Bump the platform version when you do.)_

---

## LOCAL RULES (this session only — fill in per task)

> Example slots — replace each session:

- [ ] e.g. "Today: documentation + breakdown only, no hardening yet."
- [ ] e.g. "Refactor for readability; do not change public function signatures."
- [ ] e.g. "Target test coverage 3 → 6 for this slice this session."

## Promotion protocol (Local → Universal)

At session end, if a local rule worked well and should always apply, note it in
the hand-back under Decisions: "Promote rule: <text>". The main thread moves it
into UNIVERSAL RULES above and bumps the version. That's how the rulebook learns.
