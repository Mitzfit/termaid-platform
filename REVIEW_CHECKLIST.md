# Hand-back Review Checklist (Master Agent QC gate)

Run BEFORE accepting any sub-agent hand-back or showing it to the Director. If any
item fails, REJECT: tell the agent exactly what to fix, don't integrate, don't
forward. (Per Chief-of-Staff SOP, Protocol A.)

## Boundaries
- [ ] Touched ONLY its owned files? (No edits to another window's files.)
- [ ] Cross-window effects are in `main.py`/other windows flagged, not silently edited?

## Hand-back completeness
- [ ] HANDOFF present with **Cross-Window Impact** filled in (not blank).
- [ ] BREAKDOWN.md present; HEALTH report scored vs baseline; HISTORY line appended.
- [ ] Version bumped; INDEX entry updated.

## Rules & quality
- [ ] Universal rules followed — esp. **"Termaid"** spelling in prose/comments
      (stylized "TermAId" is a typo); structured-error contract on stream surfaces.
- [ ] Code documented to CODE_STYLE, attributed to Misfit.
- [ ] Tests added for behavior changes (or a clear reason why not).

## Independent verification (don't just trust the report)
- [ ] Re-run any pure/stdlib logic live where possible (parsers, policy, config).
- [ ] Reconstruct PDF-delivered code to clean text and `py_compile` it.
- [ ] Sanity-check claimed health deltas against what actually changed.

## On accept (Protocol C — global state ownership)
- [ ] Update MASTER_INDEX.md (version, files, health, cross-window TODOs).
- [ ] Update ARCHITECTURE.md "Platform state".
- [ ] Append LESSONS + HISTORY; regenerate the source bundle.
