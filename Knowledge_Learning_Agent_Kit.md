# Agent 05 — Knowledge & Learning (kit)

Attach BOTH this file and `Knowledge_Learning_Code.md` to the agent window. This file = brief/baseline/start; the code file = the 6 owned modules.

---

# Agent 05 — Knowledge & Learning

**Role:** Knowledge engineer. The platform's memory: facts, notes, lessons, the
learned environment, and the module catalog — the context that makes the brain
personal and informed.
**Baseline health:** 5.0 / 10 (set 2026-06-14).

## Owns (CLI modules, modules/<name>/__init__.py)
- `memory` — long-term FACTS injected into the brain's system prompt.
- `learn` — knowledge base with examples.
- `learner` — detects the user's hardware/environment (NOT model training).
- `lessons` — recorded lessons/tips.
- `notes` — personal notes.
- `catalog` — the module catalog/registry.

## Depends on / feeds
- Feeds: AI & The Brain — `memory` facts flow into the system prompt that
  `brain_config.compile()` now builds. Coordinate so memory routes through the
  brain's context cleanly (and untrusted/stored text gets `wrap_untrusted` where
  it isn't authored by the user).
- Reads/writes: a local store (verify the persistence path + privacy of stored
  personal facts).

## Inherited consideration (routed from AI v2.3.2)
- Decide the LEARNING architecture: near-term realistic = memory/retrieval/feedback
  logging (RAG-style), NOT weight training. If genuine weight-level learning
  (fine-tune/LoRA/datasets) is wanted, spec the dataset + eval loop here as a
  written proposal before any code.

## Scope guard
6 modules (~3,500 lines) is too much for one session. Pick a SUBSET per session
(suggest memory + notes + lessons first — smaller, highest leverage).

## Standing job (WINDOW_DIRECTIVES)
Brainstorm → Document → Break down → Harden → Health report. Obey RULES.md
(incl. Termaid spelling + structured-error rule). Never touch another window's files.


---

# Health Report — Knowledge & Learning  (BASELINE, v2.3.2, 2026-06-14)

| Category | Score | Notes |
|---|---|---|
| Correctness / reliability | 6 | Working shipped CLI modules; behavior unverified by tests. |
| Security | 5 | memory/notes store personal facts that get injected into the model's system prompt — privacy + injection surface; persistence path needs review. |
| Performance | 6 | Fine for CLI use; no profiling. |
| Architecture / maintainability | 5 | Large modules (learn ~33KB, learner ~36KB); likely mixed concerns. |
| Test coverage | 2 | No tests for any of the 6 modules. |
| Documentation | 4 | Module docstrings exist (memory's is good); per-function/why docs thin. |
| Cross-window cohesion | 5 | memory → brain system prompt (AI) is informal; storage contract undocumented. |
| **Overall** | **5.0** | Functional knowledge layer, undocumented and untested; the personal-data-into-prompt path needs care. |

## Top 3 risks
1. Zero tests across 6 modules — behavior and regressions unverified.
2. Personal facts flow into the model's system prompt — privacy + prompt-injection
   surface; should route through brain_config guardrails / wrap_untrusted.
3. Large modules are hard to reason about until documented + broken down.

## Highest-value next action
Pick memory + notes + lessons. Directive 1 (document to CODE_STYLE, Misfit) +
Directive 2 (breakdown) to understand them, add tests for memory/notes →
Documentation 4→7, Tests 2→5. Write the memory↔brain_config integration note.


---

## START PROMPT (paste into the new agent window)

```
This is the KNOWLEDGE & LEARNING agent.

Your role: knowledge engineer. You own the CLI knowledge modules (modules/<name>/
__init__.py): memory, learn, learner, lessons, notes, catalog — the context that
makes the brain personal and informed. Work ONLY on these; never touch another
window's files.

Read from project knowledge first: MASTER_INDEX.md, ARCHITECTURE.md, CODE_STYLE.md,
WINDOW_DIRECTIVES.md, RULES.md (Termaid spelling + structured-error rule),
LESSONS.md, BASELINE_HEALTH.md.

SCOPE GUARD: 6 modules is too much for one session. In the brainstorm, pick a
SUBSET (suggest memory + notes + lessons first). Then run the four directives:
1) Document (what/does/why, Misfit), 2) Break down (BREAKDOWN.md), 3) Harden,
4) Health report.

Key considerations:
- `memory` facts get injected into the brain's system prompt — coordinate with the
  AI window: route memory through the context cleanly and wrap any stored/untrusted
  text with brain_config.wrap_untrusted where it isn't user-authored.
- LEARNING architecture: near-term realistic is memory/retrieval/feedback logging
  (RAG-style), NOT weight training. If weight-level learning is genuinely wanted,
  write a dataset + eval spec FIRST — don't fabricate a training pipeline.

Hand back with HANDOFF_TEMPLATE.md + updated files (as .py text, not PDF) + INDEX +
BREAKDOWN + health report + appended HISTORY. Bump the version.

Your files are attached. Today's task: <I will set this in the brainstorm>.

```


---
## HISTORY (append each session)

- 2026-06-14 · main · Kit created (baseline 5.0). Awaiting first session.
