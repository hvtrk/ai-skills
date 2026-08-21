---
trigger: always_on
---

# Decision-Gate Protocol — Mandatory

The human project owner is the final decision-maker for WorkQuant product and implementation decisions.

The AI agent must NOT silently resolve meaningful ambiguity when multiple reasonable solutions exist.

## 1. When to Stop and Ask

Immediately stop the current task and ask the project owner a question when you encounter any of the following:

### Ambiguous Requirement

The available documentation does not clearly determine the intended behavior.

Example:

```text
Should a task belong directly to a Project,
or should every task belong to a Board within a Project?
```

### Multiple Valid Solutions

There are two or more technically or product-wise reasonable approaches.

Example:

```text
Should Tasks support one assignee or multiple assignees?
```

### Significant Product Decision

The decision affects how users experience WorkQuant.

Example:

```text
Should completed tasks remain visible on the board
or automatically disappear from active views?
```

### Significant Domain Decision

The decision affects relationships between domain entities.

Example:

```text
Should a Subtask be a full Task,
or should it be a separate lightweight entity?
```

### Significant Architecture Decision

The decision could materially affect future implementation.

Example:

```text
Should task relationships be modeled as a generic relationship
with a type, or as separate dependency/reference concepts?
```

### Irreversible or Expensive Decision

The decision could result in substantial future migration or rework.

Example:

```text
Should organization membership be maintained entirely by Clerk
or partially represented in the application database?
```

### Product-Simplicity Trade-off

There is a conflict between feature richness and WorkQuant's simplicity principle.

Example:

```text
Should WorkQuant support multiple assignees because it is powerful,
or enforce a single primary assignee to keep the product simple?
```

---

# 2. When NOT to Stop

Do NOT interrupt the project owner for trivial implementation details.

The agent may make reasonable decisions for:

* formatting
* wording
* Markdown structure
* section ordering
* obvious documentation improvements
* naming that is already established by `TERMINOLOGY.md`
* implementation details explicitly determined by existing architecture
* decisions that have only one reasonable interpretation
* low-impact choices that can easily be changed later

The purpose of this protocol is NOT to make the agent ask questions constantly.

It is specifically for **meaningful decisions where the project owner's intent matters**.

---

# 3. Decision Priority

When determining whether to ask a question, classify the decision:

### Level 1 — Cosmetic

No need to ask.

Example:

```text
Should this section use a table or bullets?
```

Proceed.

### Level 2 — Low Impact

Usually proceed using established conventions.

Example:

```text
Should this filename use singular or plural?
```

Proceed unless terminology conflicts with an existing decision.

### Level 3 — Product / Domain

STOP and ask.

Example:

```text
Can a task have multiple assignees?
```

### Level 4 — Architecture / Data

STOP and ask.

Example:

```text
Should Project own Boards, or should Boards exist independently?
```

### Level 5 — Irreversible / High Impact

STOP and ask before continuing.

Example:

```text
Should task deletion be hard deletion or permanent archival?
```

---

# 4. Required Question Format

When a decision gate is triggered, do NOT continue generating the document.

Instead, provide:

## Decision Required

### Context

Briefly explain what was discovered.

### Decision

Clearly state the exact question that needs an answer.

### Why It Matters

Explain what parts of the product/document will be affected.

### Options

Provide the viable options.

For each option include:

* description
* advantages
* disadvantages
* impact on WorkQuant
* implications for future development

### Recommendation

You MAY provide a recommendation.

However, the recommendation is advisory only.

Do NOT automatically select it.

### Your Decision

Wait for the project owner's answer.

Do not continue until the answer is provided.

---

# 5. Example

If the agent discovers that both of these are viable:

```text
Option A:
A Task can have exactly one assignee.

Option B:
A Task can have multiple assignees.
```

The agent should stop and ask:

```text
## Decision Required

### Context

The current product model does not definitively establish whether
a task can have one or multiple assignees.

### Decision

Should WorkQuant support multiple assignees per task?

### Option A — Single Assignee

Advantages:
- Simpler UX
- Clear ownership
- Easier workload reporting
- Lower conceptual complexity

Disadvantages:
- Less suitable for collaborative tasks
- May require workarounds for shared ownership

### Option B — Multiple Assignees

Advantages:
- Supports collaborative ownership
- More flexible

Disadvantages:
- More complex task UX
- More complicated workload reporting
- Less clear individual accountability

### Recommendation

I recommend Option A because WorkQuant prioritizes simplicity and
clear ownership.

However, this is a product decision.

### Your Decision

Please choose A or B, or provide another direction.
```

Then STOP.

Do not continue generating the remaining PRD.

---

# 6. Multiple Questions

If multiple independent decisions are discovered, do NOT dump a large questionnaire on the project owner.

Ask the **highest-impact decision first**.

After receiving the answer:

1. Apply the decision.
2. Continue analysis.
3. Ask the next decision only if necessary.
4. Continue until all meaningful ambiguities are resolved.
5. Then complete the document.

The conversation should therefore behave like:

```text
AI analyzes
    ↓
Decision required?
    ↓
YES
    ↓
Ask owner
    ↓
STOP
    ↓
Owner answers
    ↓
Apply decision
    ↓
Continue analysis
    ↓
Another decision?
    ↓
YES → Ask again
    ↓
NO
    ↓
Complete document
```

---

# 7. Do Not Hide Assumptions

The agent must never silently convert a significant assumption into a requirement.

If the agent must make an assumption for a low-impact decision, explicitly record it in the document as:

```text
ASSUMPTION
```

For example:

```text
ASSUMPTION:
The initial product will use a single primary assignee because no
requirement for multi-assignee tasks has been established.
```

However, if the decision is significant enough to affect the domain,
product behavior, database model, API design, or future architecture,
the agent must STOP and ask the project owner instead.

---

# 8. Decision Log

When the project owner answers a decision question, record the decision in the document where appropriate.

Use:

```text
## Decision Log

| ID | Decision | Chosen Option | Reason | Date |
|---|---|---|---|---|
```

Do not repeatedly ask the same question in later sections.

Once the project owner has explicitly decided something, treat that decision as authoritative unless new evidence creates a genuine contradiction.

If new evidence contradicts an earlier decision, STOP and ask whether the previous decision should be changed.

---

# 9. Conflict With Existing Documentation

If the agent discovers:

```text
Current Code
     ≠
Existing Documentation
```

do not silently choose one.

Determine whether the discrepancy materially affects the current task.

If it does, STOP and ask the project owner which should be treated as authoritative.

If it does not materially affect the current task, document the discrepancy and continue.

---

# 10. Conflict With Previous Human Decisions

Human decisions always take precedence over the AI's recommendations.

If an existing documented decision says:

```text
Decision: Tasks have one primary assignee.
```

the agent must not later change it to:

```text
Tasks support multiple assignees.
```

because it believes that is architecturally better.

Instead:

```text
Previous decision conflicts with the newly identified requirement.

Decision required:
Should the existing decision be retained or changed?
```

Then stop.

---

# 11. Recommendation vs Decision

The AI is encouraged to challenge assumptions and provide strong recommendations.

However:

```text
Recommendation ≠ Decision
```

The AI should be willing to say:

> "I recommend Option B because of X, Y, and Z."

But it must not say:

> "I chose Option B and continued."

for Level 3–5 decisions unless the project owner has explicitly delegated that decision.

---

# 12. Final Authority

The project owner has final authority over:

* product behavior
* domain semantics
* UX behavior
* feature scope
* business rules
* architecture trade-offs
* data-model trade-offs
* technology choices
* implementation strategy

The AI's role is to:

1. Analyze.
2. Identify ambiguity.
3. Explain alternatives.
4. Challenge weak assumptions.
5. Recommend an option when appropriate.
6. Ask the project owner to decide.
7. Apply the decision.
8. Continue.

Never silently make a material decision simply to keep the task moving.
