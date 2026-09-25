# Phase execution template

Copy this prompt into Codex, Claude Code or Antigravity.

Read AGENTS.md and the relevant phase in docs/PHASES.md.

Current phase: `<PHASE>`

Do the following:
1. Inspect repository state and relevant skill.
2. Identify inputs and expected outputs.
3. Implement only this phase.
4. Add tests and test fixtures.
5. Run all relevant checks.
6. Inspect representative output.
7. Record provenance and limitations.
8. Update docs.
9. Return PASS or BLOCKED.

Do not guess missing data.
Do not claim unsupported accuracy.
Do not advance if verification fails.

Return:
- Phase
- What it means
- Why it is needed
- Implementation
- Files changed
- Tests
- Verification
- Limitations
- Stop conditions encountered
- Next phase
