# README-YOUR-ANSWER-HERE.md — Main/Architecture agent (The Brain)

Understood T.M. I will read README-COMMUNICATION.md first, every conversation.

## Your goal: make the Brain faster + present the right info

A focused plan to cut response time and tighten how we work.

### What slows us down (and the fix)

1. **Reconstructing code from PDFs.** Agents on mobile hand back code as PDFs;
   I must rebuild clean source before integrating — slow + error-prone.
   → Fix: when possible, hand back code as .py/.md/.txt (not PDF). PDFs are fine
   for the human-readable reports (HANDOFF, BREAKDOWN, HEALTH); code as text.
2. **Re-deriving context each turn.** → Fix: keep MASTER_INDEX + this file current;
   I read them first and skip re-explaining. You already built this — it works.
3. **Doing too much per turn.** → Fix: one clear objective per message. I lead with
   the answer, keep it scannable, and park side-ideas in IDEAS_BACKLOG.

### How I'll present info (to save your time/API)

- Lead with the result, then a short "what changed / what to do" list.
- Status line up top: version, health trend, what's ready to push.
- Detail lives in files (backlog, breakdown), not the chat.

### Your "Projects module with Rules" idea — strong, and we're already prototyping it

What we've built for orchestration (Custom Instructions + Universal/Local RULES +
per-window directives + brainstorm + health) is _exactly_ a Projects-with-Rules
system. Proposal: turn it into a user-facing **Projects module** in Termaid —
users create a project, attach knowledge files, set rules, and run scoped
sessions. We'd be shipping the very workflow we use to build the app. Noted in the
backlog; high-value and dogfooded.

### My one ask back

Hand code back as text files where you can; keep PDFs for the reports. That single
change is the biggest speed-up available to us right now.
