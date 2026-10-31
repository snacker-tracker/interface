# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`GLOSSARY-MAP.md`** at the repo root, then the glossary of each context you're working in.
- **The ADRs of that context**: read the ones that touch the area you're about to work in.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

This repo has two contexts, listed in `GLOSSARY-MAP.md`: Snacker Tracker, and stepdag, a separate workflow framework developed here. stepdag's docs live in its own directory, so they move with it if it's extracted.

```
/
├── GLOSSARY-MAP.md
├── GLOSSARY.md                 ← Snacker Tracker
├── docs/adr/                   ← Snacker Tracker
│   └── 0001-<decision>.md
├── backend/
├── frontend/
└── stepdag/
    ├── GLOSSARY.md             ← stepdag
    └── docs/adr/               ← stepdag
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in that context's glossary. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders), but worth reopening because…_
