# HANDBACK_TEXT_PROTOCOL.md — how every Termaid sub-agent returns work (TEXT only)

Deliver the entire hand-back as PLAIN TEXT in the chat. Full file contents, not
diffs. No file attachments. No PDF (it mangles code). If too long for one message,
split across messages but keep every marker intact and write "(continued)".

Output in exactly this order, with these literal markers:

=== HAND-BACK · <agent name> · v<in> -> v<out> ===

## 1. HANDOFF
Window:
Changed:        (file -> one-line what & why)
Added:
Removed:
Decisions:
Cross-Window Impact:   REQUIRED — never blank. Name the other window + the exact
                       change they must make, or write "none".
New TODOs:
Tests:          (count + which ran live vs CI-only)

## 2. FILES  (full text of EVERY changed/added file)
For each file:

----- FILE: <relative/path/from/repo/root> -----
```<lang>
<COMPLETE file contents>
```
----- END FILE -----

(Repeat per file. If a file contains ``` , use four backticks for the outer fence.)

## 3. BREAKDOWN
Prose explanation of each component: what it is, how it works, why. The slice must
be understandable from this section alone.

## 4. HEALTH REPORT
Table: Category | Score (0-10) | Trend | Note — for Correctness, Security,
Performance, Architecture, Test coverage, Documentation, Cross-window cohesion, and
Overall. Then Top 3 risks, and What changed vs baseline.

## 5. INDEX ENTRY
Table: file | owns — for every owned file (mark NEW where added).

## 6. HISTORY LINE
YYYY-MM-DD · <window> · <what changed; health x.x->y.y; version a.b.c->a.b.d>

## 7. SELF-CHECK (yes/no before sending — the gate the Master Agent applies)
- Stayed strictly inside owned files?
- Cross-Window Impact filled in (not blank)?
- Universal rules followed (Termaid spelling in prose/UI; structured-error contract)?
- Code documented to CODE_STYLE, attributed to Misfit?
- Tests added for behavior changes?
- Version bumped + INDEX + HISTORY updated above?

=== END HAND-BACK ===
