# START HERE — TermAId project setup

## 1. Project Knowledge — upload these files (all accepted formats)
MASTER_INDEX.md · ARCHITECTURE.md · SETUP.md · CODE_STYLE.md · WINDOW_DIRECTIVES.md ·
RULES.md · BRAINSTORM_TEMPLATE.md · HEALTH_REPORT_TEMPLATE.md · HANDOFF_TEMPLATE.md ·
LESSONS.md · GLOSSARY.md · CLAUDE_TOOLS.md · PLATFORM_HEALTH_BASELINE.md ·
IDEAS_BACKLOG.md · HISTORY.md · GAME_PLAN.md · TermAId_Orchestration_Playbook.pdf

(These are the shared library every agent reads. `.tar.gz` is NOT accepted — use
these individual files.)

## 2. Custom Instructions — paste the contents of CUSTOM_INSTRUCTIONS.txt
Settings → Project → custom instructions. This is the standing behavior every
agent window inherits.

## 3. Launch an agent (e.g. Database)
- Open a new chat in the project.
- Attach **Database_Agent_Kit.md** (brief + baseline + start prompt + its code in one file).
- Paste the START PROMPT from that kit and set the day's task in the brainstorm.

## 4. The loop
Agent works → produces a hand-back (HANDOFF + files + INDEX + BREAKDOWN + health +
HISTORY) → you bring it to the main thread → I integrate, bump the version, update
the master index → you push to GitHub.

## Format note
Agents/knowledge accept: PDF, MD, TXT, DOCX, CSV, code files. They do not accept
archives. Everything here is already in an accepted format.
