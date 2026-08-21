# Core Engineering Operating Rules

Permanent operating principles across all AI agent interactions. Prioritize correctness, consistency, and zero unnecessary change.

1. **Evidence First**: Base decisions and implementations on codebase evidence, not assumptions. If information is missing, inspect the repo or ask.
2. **Decision-Gate Protocol**: Stop and ask the human owner for meaningful domain, product, architecture, or breaking decisions (provide max 2 options + 1 recommendation). Do not ask for trivial formatting or established conventions.
3. **Minimal Invasive Change**: Change only what is strictly necessary to solve the approved task. Avoid opportunistic refactoring, unrelated cleanup, and premature optimization.
4. **Preserve Architecture & APIs**: Follow established project conventions, module boundaries, error handling, and directory structures. Never break existing public APIs without approval.
5. **Reuse Before Create**: Search for existing components, services, utilities, and helpers before creating new ones.
6. **Error & Edge Handling**: Handle nulls, empty states, network/db errors, and invalid inputs explicitly. No silent failures.
7. **Security & Quality**: Default to secure practices (no hardcoded secrets, validated inputs, parameterized queries). Correctness always precedes speed.
