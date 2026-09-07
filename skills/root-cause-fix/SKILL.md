---
name: root-cause-fix
description: This skill should be used when the user asks to "investigate and fix this bug", "dig into this issue and fix it", "find and fix this problem", "debug and fix this", or reports something broken (an error, a regression, unexpected behavior in production or dev) and wants the root cause diagnosed AND a fix implemented — not just a diagnosis, and not just a guess-and-patch. Runs a mandatory upfront intake interview, parallel evidence-confirmed investigation, a fix plan, implementation, and verification, then stops before any git commit/push so the user can test the fix themselves first. Triggers on /root-cause-fix, /fix-it.
---

# Root Cause Fix

Diagnose a reported bug down to a confirmed root cause, implement the minimal correct fix, and verify it — without ever committing or pushing. Use this when the user wants a bug genuinely root-caused and fixed, not just patched or diagnosed.

**Do not use this skill** for a one-line typo/config fix the user has already fully diagnosed themselves (just make the edit), for a request to diagnose without fixing (skip straight to Phase 2's investigation methodology instead), or for building new, non-broken functionality (use `fullstack-feature`, `nextjs-frontend`, or `fastapi-backend` for that).

**Prerequisites**: a working directory the user wants investigated (a git repo is not strictly required, but `git log`/`git status` are used opportunistically for timeline context in Phase 1 when present). `.memory/`, and the `project-memory`, `architecture-analysis`, and `logic-lens` skills, are all used opportunistically when present/available — none of them block this skill if missing; skip the step and continue.

## Phase 0 — Load Project Memory (if it exists)

Check whether `.memory/INDEX.md` exists in the project root.
- If it exists, call the Skill tool with "project-memory" and retrieve the `gotchas` and `architecture` topics (and `domain` if the bug looks domain-related) before doing anything else. A prior session may have already hit this exact trap.
- If `.memory/` does not exist and the codebase is unfamiliar, call the Skill tool with "architecture-analysis" to build a working mental model of the stack, module boundaries, and data flow before interviewing the user — this produces sharper intake questions instead of generic ones.
- If neither applies (familiar codebase, no memory system), skip straight to Phase 1.

## Phase 1 — Adaptive Intake Interview (mandatory, before any exploration)

Always interview the user first, even when the symptom looks self-explanatory. This is a **relentless, multi-round interview, not a single batch of questions** — do not stop after one round of `AskUserQuestion` and proceed to Phase 2 until every open thread below is concrete and falsifiable. Never answer on the user's behalf and never assume an answer to save a round — an interview where the agent fills in its own guesses has failed at this phase.

**Round 1 — breadth-first.** Use `AskUserQuestion` to cover the full open surface in one pass:
- **Symptom**: exactly what happens vs. what should happen. Ask for a screenshot, error message, stack trace, or exact copy-pasted output rather than a paraphrase.
- **Reproduction**: exact steps, and whether it reproduces every time or intermittently.
- **Scope**: which environment (local/staging/production), which page/feature/endpoint/service.
- **Timeline**: when it started, and anything that changed around that time (a deploy, a dependency bump, a config change, a recent PR) — check `git log` yourself for this rather than relying purely on the user's memory, and bring what you find back into a later round instead of asking the user to recall it blind.
- **Urgency/blast radius**: is this affecting live users right now, is a stopgap needed before the real fix.

**Round 2+ — depth-first, on demand.** For every answer from Round 1 (or any later round) that is vague, hedged, or opens a new question, run another `AskUserQuestion` round narrowing that specific thread — do not let a vague answer pass through unresolved just because a round of questions already happened. Examples of answers that demand a follow-up round: "it's broken sometimes" (needs a concrete trigger/threshold), "I think it started recently" (pin down a date/commit/deploy), "just fix it everywhere it happens" (needs the actual list of affected areas confirmed, not assumed). Keep digging on one thread at a time (depth-first) until it resolves, rather than fanning out across everything at once.

Only proceed to Phase 2 once the problem statement is concrete and falsifiable end-to-end — a vague symptom like "it's slow sometimes" is not actionable without a threshold and a repro.

**Cross-check against prior fixes throughout.** Weave whatever `gotchas`/`architecture` content Phase 0 already loaded (or, if Phase 0 was skipped, retrieve it now via the Skill tool with "project-memory") into the interview itself — don't just load it once and set it aside. If the reported symptom matches or resembles a previously-documented trap or fix, say so explicitly to the user during the interview ("this looks like it might be the same [X] issue documented on [date] — does that match?") and use targeted follow-up questions to confirm whether this is a recurrence, a regression of that old fix, or a genuinely new variant, rather than re-investigating from a blank slate. Carry that prior understanding — what the root cause was, what the fix was, why it was fixed that way — into Phase 2 as a starting hypothesis to confirm or rule out first.

## Phase 2 — Parallel Investigation

From the intake, identify the 2–3 candidate layers most likely involved (e.g., frontend data flow, backend logic, infra/deployment config, a specific third-party integration). For each, launch an Explore or general-purpose agent in parallel with a specific, self-contained question — never a vague "look into this." Each agent must trace actual code paths and report file:line evidence, not speculation.

Call the Skill tool with "systematic-debugging" to run its feedback-loop, reproduce-and-minimize, and ranked-hypothesis phases as the rigor backbone for this investigation — use its falsifiable-hypothesis format ("If [Cause X] is true, then [Y] will make the symptom disappear") rather than accepting the first plausible-sounding explanation.

In parallel with reading code, gather live evidence wherever possible: curl the real endpoint, run the actual build, reproduce locally, inspect real response shapes. Code that "looks correct" is not evidence — a passing static read can hide an infra-level cause (a proxy, a WAF rule, a cache) that only live reproduction reveals.

## Phase 3 — Confirm Root Cause With Direct Evidence

Do not declare a root cause confirmed until it's been verified against real behavior — a reproduced failure that disappears when the hypothesized cause is removed/patched, a direct API call showing the actual response, an actual build run. "The code looks like it should be the problem" is a hypothesis, not a confirmation.

If the confirmed cause turns out not to be fixable in this repo (a third-party dashboard setting, DNS/CDN config, a paid-plan limitation, a platform-level policy), say so plainly. Separate what you can fix in code from what the user must change elsewhere — never paper over an infra-level cause with a code workaround that just hides the symptom without addressing it.

## Phase 4 — Plan the Fix

With root cause confirmed, decide fix scope. Prefer the smallest correct fix: reuse existing utilities/patterns already in the codebase, avoid new abstractions, don't expand scope beyond what the confirmed root cause actually requires. If there's a genuine fork in approach — e.g., a sibling feature shares the identical bug pattern and could reasonably be included or excluded — ask the user via AskUserQuestion. Do not ask about anything the codebase itself already answers.

If running under formal plan mode, write the plan (context, confirmed root cause, fix approach, files, verification) before touching code.

## Phase 5 — Implement

Make the minimal, targeted change. Preserve existing APIs/contracts unless the confirmed root cause requires changing them.

**Never run `git add`, `git commit`, `git push`, or open a PR as part of this skill.** The user tests the fix themselves before deciding to commit. Read-only git commands (`status`, `log`, `diff`) are fine and encouraged for context throughout every phase above.

## Phase 6 — Verify

Run the project's real build/lint/test commands (check CLAUDE.md or the README for the actual commands — don't guess). Re-run the same live reproduction/evidence check from Phase 3 to confirm the fix resolves the real symptom, not just that the code compiles.

Deliberately stress the failure path, not only the happy path — re-simulate the original failure condition (the unreachable dependency, the bad input, the edge case that started this) to confirm the fix degrades gracefully now, rather than merely dodging the one exact trigger that was reported.

Optionally, call the Skill tool with "logic-lens" for a focused review of the changed files before declaring done — it targets null handling, boundary conditions, concurrency, and security issues the debugging loop above doesn't specifically aim at.

## Phase 7 — Document & Hand Off

If `.memory/` exists, call the Skill tool with "project-memory" to record the confirmed root cause and fix pattern as a durable `gotchas` entry, so no future session re-diagnoses the same issue from scratch. Include: what broke, why, the fix, and anything not fixable in code that still needs manual action outside the repo.

Summarize for the user: confirmed root cause, exactly what changed (files), anything requiring manual action outside the repo (infra settings, dashboard changes), and how to test it themselves. State plainly that nothing has been committed or pushed — that's next, on their side.

## Output Format

The final hand-off to the user (Phase 7) is always a short summary containing, in order:
1. **Confirmed root cause** — one or two sentences, stated as a fact backed by the Phase 3 evidence, not a hedge.
2. **What changed** — the specific files touched and, in one line each, why.
3. **Manual action still needed outside the repo**, if any (a dashboard setting, a DNS/CDN change, a config only a human can apply) — omit this line entirely if there is none.
4. **How to test it** — the concrete steps or command to verify the fix locally.
5. An explicit statement that nothing has been committed or pushed.

## Example

A user reports: "the /blog page shows no articles in production." Phase 1 Round 1 asks (via `AskUserQuestion`) for the exact symptom/screenshot, whether it reproduces locally too, which environment, and when it started. The answer "started sometime after our last deploy, not sure exactly when" is vague, so Round 2 follows up narrowing it to a specific commit via `git log` correlated with the user's rough timeframe, before Phase 2 investigation begins.
