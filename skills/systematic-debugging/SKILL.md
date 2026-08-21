---
name: systematic-debugging
description: Comprehensive 6-phase debugging loop for resolving difficult bugs, unexpected errors, and regressions. Traces root cause using fast, deterministic feedback loops. Triggers on /debug, /bug-hunter, /diagnose.
---

# Systematic Root-Cause Debugging

A disciplined, evidence-based debugging playbook. Never guess—construct a deterministic feedback loop, test falsifiable hypotheses, and fix the root cause.

## Phase 1 — Build a Feedback Loop
Construct a fast, red-capable reproduction command before writing any fix:
- Failing unit/integration test.
- Deterministic curl script or CLI command.
- Minimal reproduction script isolating the failing code path.

*Rule*: Phase 1 is complete only when you have a single command that runs in seconds and reliably fails (goes red) on the bug.

## Phase 2 — Reproduce & Minimize
- Confirm the loop catches the exact symptom reported by the user.
- Cut away non-essential inputs, configs, and code lines until every remaining piece is load-bearing for the failure.

## Phase 3 — Generate Ranked Hypotheses
Formulate 3–5 falsifiable hypotheses in this format:
> *"If [Cause X] is true, then [Changing Y] will make the bug disappear / [Changing Z] will alter the error."*

## Phase 4 — Targeted Instrumentation
- Insert tagged debug probes (`[DEBUG-probe-id]`) at the boundaries separating your hypotheses.
- Step through logic with a debugger or inspect exact runtime state.
- Change one variable at a time.

## Phase 5 — Root-Cause Fix & Regression Test
- Fix the underlying root cause, not the symptom (e.g. do not just add optional chaining `?.` if data was supposed to be initialized).
- Add an automated regression test at the real seam to prevent future recurrence.
- Watch the test go green.

## Phase 6 — Cleanup & Post-Mortem
- Delete all `[DEBUG-...]` probes and temporary scripts.
- Document the root cause, the fix, and any architectural safeguards needed.
