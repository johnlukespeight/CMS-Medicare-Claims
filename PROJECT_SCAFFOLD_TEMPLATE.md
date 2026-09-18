# Project Scaffold Template

**Purpose:** a copy-and-fill template for bootstrapping a new spec-driven,
agent-governed software project. This captures the scaffolding pattern used
by this repository — generalized and stripped of anything VitruCore-specific
— so it can be dropped into a new, unrelated project.

**How to use this file:** copy the sections below into a new repository as
separate files (the path is given in each section header), replacing every
`[BRACKETED]` placeholder. Delete any section that doesn't apply. This
document itself is not meant to live in the new project — it's the mold, not
the part.

---

## 0. What this pattern is

The pattern separates four concerns that normally get tangled together when
an AI coding agent builds a product with real constraints (safety, legal,
compliance, correctness-critical logic):

1. **A master engineering spec** (`docs/IMPLEMENTATION_SPEC.md`) — the single
   source of truth for architecture, data model, APIs, and milestones. Long,
   detailed, changes rarely.
2. **Agent entrypoint docs** (`CLAUDE.md`, `AGENTS.md`) — short files the
   coding agent reads first, every session. They state hard constraints and
   point to the spec; they don't duplicate it.
3. **Standalone policy docs** (`docs/ARCHITECTURE_DECISIONS.md`,
   `docs/GOVERNANCE.md`, `docs/SAFETY_POLICY.md` or equivalents) — narrow,
   living documents for concerns that change independently of the spec and
   need to be checked against on every change.
4. **A cold-context reviewer subagent + skills** — automation that reads the
   above docs fresh (not biased by having written the code) and checks a diff
   against them before it's committed.

The unifying rule: **anything that must never be violated is deterministic
code and/or a checked document, never something an LLM is trusted to
remember or infer.** Use this pattern when the project has real hard
constraints (safety, legal, financial, data-rights, correctness-critical) and
will be built incrementally by a coding agent across many sessions. Skip it
for small or short-lived projects — the overhead isn't worth it below a
certain size.

---

## 1. File manifest

| File | Purpose | Who reads it |
|---|---|---|
| `CLAUDE.md` | Claude Code entrypoint: objective, milestone order, hard constraints, pointer to spec | Claude Code, every session |
| `AGENTS.md` | Generic coding-agent entrypoint (Codex, other tools): same content, tool-agnostic framing | Any coding agent |
| `docs/IMPLEMENTATION_SPEC.md` | Master spec: product definition, architecture, data model, APIs, milestones, coding standards, ADR log, definition of done | Coding agent, before implementing anything |
| `docs/ARCHITECTURE_DECISIONS.md` | Standalone running ADR log (may duplicate the spec's embedded copy) | Anyone proposing an architecture change |
| `docs/GOVERNANCE.md` | Data rights, retention, consent, third-party content rules | Anyone touching data ingestion, storage, or retention |
| `docs/SAFETY_POLICY.md` | Domain behavior policy: allowed/out-of-scope behavior, risk handling, language rules | Anyone touching user-facing AI output |
| `.claude/agents/[domain]-reviewer.md` | Cold-context subagent that checks a diff against the docs above | Invoked before commit |
| `.claude/skills/[policy-name]/SKILL.md` | Packaged policy loaded contextually when relevant work is detected | Claude Code, contextually |
| `PRODUCT_SPEC.md` (repo root, optional) | Upstream business/product spec: market, users, success criteria, build plan | Humans + agent, upstream of the implementation spec |

Only `CLAUDE.md` and `docs/IMPLEMENTATION_SPEC.md` are load-bearing. Add the
rest as the project's real constraints justify them — don't create a
`GOVERNANCE.md` for a project with no data-rights questions.

---

## 2. Template: `CLAUDE.md`

```markdown
# CLAUDE.md — [PROJECT_NAME]

Before implementing changes, read `docs/IMPLEMENTATION_SPEC.md`.

## Project objective

[PROJECT_NAME] is a [ONE-LINE PROJECT DESCRIPTION]. The core vertical slice is:

**[STEP 1] → [STEP 2] → [STEP 3] → ... → [FINAL OUTCOME]**

## Implementation order

Follow the milestones in `docs/IMPLEMENTATION_SPEC.md`. Do not skip ahead to
[LIST OF DEFERRED CONCERNS, e.g. advanced AI, infrastructure, mobile, analytics, multi-tenant support].

## Hard constraints

1. [ARCHITECTURE STYLE, e.g. modular monolith first].
2. [BACKEND FRAMEWORK/LANGUAGE].
3. [FRONTEND FRAMEWORK/LANGUAGE].
4. [DATABASE / STORAGE CHOICE].
5. Deterministic code controls [LIST WHAT MUST NEVER BE LEFT TO AN LLM, e.g. permissions, safety gates, business-rule constraints, retention].
6. LLMs may [WHAT THEY'RE ALLOWED TO DO] only where allowed; they cannot override hard constraints.
7. All AI artifacts are auditable through [AUDIT MECHANISM, e.g. model-run records].
8. [ANY USER-FACING CLAIM RULE, e.g. RAG claims require source-backed citations].
9. Do not ingest [ANYTHING RIGHTS-RESTRICTED].
10. Do not [ANY IMPERSONATION / ENDORSEMENT PROHIBITION].
11. [ANY DOMAIN-SPECIFIC OUTPUT-LANGUAGE RULE, e.g. feedback must be observational, never diagnostic].
12. [ANY DATA RETENTION RULE].
13. Do not introduce [SPECIFIC OVER-ENGINEERED INFRASTRUCTURE TO AVOID, e.g. Kubernetes, a dedicated vector DB] for the initial [POC/MVP] without an explicit architecture change.
14. Add tests with each feature.
15. Stop at a milestone boundary unless asked to continue.

## When uncertain

Prefer:

- explicit rules over opaque AI behavior;
- fewer features over shallow scope;
- provider abstractions over vendor coupling;
- auditable outputs over hidden reasoning;
- abstention over invented certainty;
- synthetic or project-owned test data over real sensitive data.

See `docs/IMPLEMENTATION_SPEC.md` for schemas, APIs, directory layout,
milestones, acceptance criteria, coding standards, evaluation requirements,
and the exact first tasks.
```

---

## 3. Template: `AGENTS.md`

```markdown
# AGENTS.md — [PROJECT_NAME]

Read `docs/IMPLEMENTATION_SPEC.md` before making architectural or feature changes.

## Mission

Build [PROJECT_NAME]: [ONE-SENTENCE MISSION RESTATEMENT].

## Current priority

Implement milestones in the exact order defined in `docs/IMPLEMENTATION_SPEC.md`.

If starting from an empty repository, begin with **Milestone 0 — Repository
Foundation**. Do not scaffold the full future system before the foundation
is runnable and tested.

## Non-negotiable rules

- [MIRROR THE HARD CONSTRAINTS FROM CLAUDE.md, RESTATED AS SHORT IMPERATIVES]
- Do not commit secrets, unlicensed source content, or real sensitive user data.

## Engineering behavior

- Make the smallest coherent change that advances the current milestone.
- Add/update tests with each change.
- Keep provider SDKs behind adapters.
- Do not silently modify API contracts or database schemas.
- Record durable architecture changes in `docs/ARCHITECTURE_DECISIONS.md`.
- Keep README developer commands accurate.
- Stop at milestone boundaries unless instructed to continue.

## Required source of truth

See:

- `docs/IMPLEMENTATION_SPEC.md`
- `docs/ARCHITECTURE_DECISIONS.md`
- [OTHER POLICY DOCS, e.g. `docs/SAFETY_POLICY.md`, `docs/GOVERNANCE.md`]

If these conflict, prefer the most recent explicit human decision and update
the documents so the repository has one coherent source of truth.
```

> `CLAUDE.md` and `AGENTS.md` intentionally overlap. `CLAUDE.md` is read by
> Claude Code specifically; `AGENTS.md` is the tool-agnostic version other
> coding agents (Codex, etc.) pick up. Keep them in sync by hand — don't
> generate one from the other, or drift will go unnoticed.

---

## 4. Template: `docs/IMPLEMENTATION_SPEC.md`

This is the master spec. Keep the numbered-section skeleton even if some
sections are one line ("N/A for this project") — a stable table of contents
is what lets the agent and the reviewer subagent cite it by section number.

```markdown
# [PROJECT_NAME] — Coding Agent Implementation Specification

**Document purpose:** Source-of-truth implementation brief for [AGENT TOOLING]
**Project:** [PROJECT_NAME]
**Stage:** [POC / MVP / production]
**Primary language(s):** [LANGUAGES]
**Architecture style:** [e.g. modular monolith first; service boundaries in code, not premature microservices]
**Deployment target:** [LOCAL DEV TARGET] → [PRODUCTION TARGET]
**Guiding principle:** Prefer the simplest design that preserves [YOUR TOP 3–4 PRIORITIES, e.g. safety, auditability, testability, extensibility].

---

# 0. Instructions to the Coding Agent

Treat this document as the primary engineering specification unless a newer
human-authored decision explicitly overrides it.

## Working rules

[NUMBERED LIST — MIRROR CLAUDE.md's HARD CONSTRAINTS, EXPANDED WITH RATIONALE WHERE USEFUL]

## Definition of a good implementation

[WHAT "DONE AND CORRECT" LOOKS LIKE FOR THIS PROJECT]

# 1. Product Definition

[WHAT IS BEING BUILT AND FOR WHOM, ONE OR TWO PARAGRAPHS]

# 2. [POC/MVP] User Story

[END-TO-END NARRATIVE OF THE CORE VERTICAL SLICE]

# 3. Explicit Non-Goals

[WHAT IS DELIBERATELY OUT OF SCOPE, AND UNTIL WHEN]

# 4. Architecture Decision Summary

## Initial stack

[STACK CHOICES]

## Why not [MORE COMPLEX ALTERNATIVE] now?

[RATIONALE FOR DEFERRING COMPLEXITY]

# 5. Repository Layout

[DIRECTORY TREE — SEE SECTION 11 BELOW FOR A GENERIC STARTING POINT]

# 6. [Backend] Module Boundaries

[ONE SUBSECTION PER MODULE — NAME + ONE-LINE RESPONSIBILITY + WHAT IT MUST NOT DO]

## `[module_1]`
## `[module_2]`
## `[module_n]`

# 7. Database Model

[ONE SUBSECTION PER TABLE GROUP, THEN PER TABLE — NAME + PURPOSE + KEY FIELDS + OWNING MODULE]

## 7.1 [Table group]
### `[table_name]`

# 8. [Domain-Specific Data Model, if any — e.g. knowledge/rights model, inventory model]

[ONLY IF THE PROJECT HAS A NON-OBVIOUS DOMAIN DATA MODEL BEYOND STANDARD CRUD]

# 9. AI Governance Model (if the project uses AI/LLM components)

[MODEL REGISTRY, PROMPT VERSIONING, RUN RECORDS, CITATION TRACKING — WHATEVER MAKES AI OUTPUT AUDITABLE]

# 10. [Sensitive Data Handling, if any — e.g. consent, uploads, biometric data]

[ONLY IF THE PROJECT HANDLES DATA THAT NEEDS EXPLICIT CONSENT/RETENTION RULES]

# 11. API Contract

[GROUPED BY RESOURCE/FEATURE AREA — METHOD, PATH, REQUEST/RESPONSE SHAPE, AUTH REQUIREMENT]

# 12. [Core Pipeline(s), if any — e.g. RAG pipeline, ETL pipeline, ML pipeline]

[STAGE-BY-STAGE BREAKDOWN OF THE PROJECT'S CENTRAL PROCESSING PIPELINE]

# 13. [Risk/Safety Routing, if applicable]

[HOW THE SYSTEM DETECTS AND HANDLES HIGH-RISK INPUT/OUTPUT]

# 14. [Core Business-Logic Engine, e.g. recommendation engine, pricing engine, matching engine]

## Hard constraints
## Candidate scoring / ranking
## [LLM role, if any — explicitly bounded]

# 15. [Second Domain-Specific Subsystem, if any]

# 16. Frontend Requirements

[PAGES/VIEWS BY USER ROLE, KEY SHARED COMPONENTS]

# 17. Internal Interfaces

[PROVIDER ABSTRACTIONS — e.g. embeddings, generation, storage, payments — so vendors stay swappable]

# 18. Configuration

[ENV VARS, SECRETS MANAGEMENT APPROACH]

# 19. Local Development

[HOW TO RUN THE PROJECT LOCALLY, STEP BY STEP]

# 20. Testing Strategy

## Unit tests
## Integration tests
## End-to-end test
## Test data

[REQUIRE SYNTHETIC/PROJECT-OWNED DATA, NEVER REAL SENSITIVE DATA]

# 21. Evaluation Harness (if the project has AI/ML components with measurable quality)

[WHAT GETS MEASURED, HOW OFTEN, WHAT THE PASS BAR IS]

# 22. Observability and Auditability

[LOGGING, TRACING, AUDIT TRAIL REQUIREMENTS]

# 23. Privacy and Retention Requirements

# 24. Security Requirements

# 25. [Product Safety / Compliance Language, if applicable]

# 26. [Third-Party / Public-Figure / Brand Content Rules, if applicable]

# 27. [Analytics, if applicable]

# 28. Implementation Milestones

[ONE SUBSECTION PER MILESTONE, IN BUILD ORDER — EACH WITH DELIVERABLES AND ACCEPTANCE CRITERIA]

## Milestone 0 — Repository Foundation
### Deliverables
### Acceptance criteria

## Milestone 1 — [NEXT SLICE]
### Deliverables
### Acceptance criteria

[... REPEAT UNTIL THE FULL VERTICAL SLICE IS COVERED ...]

## Milestone N — Integrated Demo
### Deliverables
### Acceptance criteria

## Milestone N+1 — Evaluation and Hardening
### Deliverables
### Acceptance criteria

# 29. First Tasks for the Coding Agent

[NUMBERED, CONCRETE, IN ORDER — WHAT TO DO IN THE VERY FIRST SESSION]

## Task 1
## Task 2
## ...

# 30. Coding Standards

## [Language 1]
## [Language 2]
## [SQL / other]

# 31. Git and Change Discipline

[COMMIT CONVENTIONS, BRANCHING, WHAT REQUIRES HUMAN REVIEW]

# 32. Architecture Decision Records

[EMBEDDED COPY OF docs/ARCHITECTURE_DECISIONS.md, OR A POINTER TO IT — PICK ONE, DON'T MAINTAIN BOTH INDEPENDENTLY]

## ADR-001 — [TITLE]

# 33. Definition of Done

[PROJECT-WIDE, NOT PER-MILESTONE — WHAT MAKES THE WHOLE THING SHIPPABLE]

# 34. [POC/MVP] Completion Criteria

# 35. Future Work — Do Not Implement Yet

[EXPLICITLY DEFERRED FEATURES, SO THE AGENT DOESN'T "HELPFULLY" BUILD THEM EARLY]

# 36. Final Agent Directive

[ONE CLOSING PARAGRAPH RESTATING THE PRIME DIRECTIVE — SCOPE DISCIPLINE, CONSTRAINT PRECEDENCE, STOP-AT-MILESTONE-BOUNDARIES]
```

---

## 5. Template: `docs/ARCHITECTURE_DECISIONS.md`

```markdown
# [PROJECT_NAME] Architecture Decisions

## ADR-001 — [DECISION TITLE]

**Status:** [Accepted / Superseded by ADR-00X]
**Context:** [WHAT PROBLEM FORCED THIS DECISION]
**Decision:** [WHAT WAS DECIDED]
**Consequences:** [WHAT THIS RULES OUT OR COMMITS TO]

## ADR-002 — [DECISION TITLE]

[REPEAT PER DECISION, APPEND-ONLY — SUPERSEDE, DON'T DELETE]
```

---

## 6. Template: `docs/GOVERNANCE.md`

Only needed if the project ingests third-party content, handles user data
with rights/consent implications, or has retention requirements.

```markdown
# [PROJECT_NAME] Data Governance — [STAGE]

## Principles

[TOP-LEVEL STANCE, e.g. "no unapproved content in production retrieval/serving paths"]

## Source data

[WHERE INPUT DATA COMES FROM, HOW RIGHTS/LICENSING ARE TRACKED]

## [Sensitive data category, e.g. video / biometrics / PII]

[STORAGE, RETENTION WINDOW, ACCESS CONTROLS]

## Model improvement

[WHETHER/HOW USER DATA MAY BE USED TO IMPROVE MODELS — DEFAULT TO OPT-IN, NEVER SILENT]

## Development data

[RULE: SYNTHETIC OR PROJECT-OWNED DATA ONLY IN DEV/TEST, NEVER REAL SENSITIVE DATA]
```

---

## 7. Template: `docs/SAFETY_POLICY.md`

Only needed if the project has user-facing AI output where wrong or
overconfident language is a real risk (health, legal, financial, safety
domains).

```markdown
# [PROJECT_NAME] Safety Policy — [STAGE]

## Purpose

[WHY THIS POLICY EXISTS]

## Allowed scope

[WHAT THE SYSTEM IS PERMITTED TO DO/SAY]

## Out of scope

[WHAT IT MUST REFUSE OR DEFER, e.g. diagnosis, legal advice, guaranteed outcomes]

## Risk behavior

[HOW HIGH-RISK INPUT IS DETECTED AND ROUTED — e.g. escalate to a human, abstain, show a disclaimer]

## [Domain] language

[SPECIFIC WORDING RULES — e.g. observational not diagnostic, probabilistic not certain]

## Constraint precedence

[WHICH RULE WINS WHEN POLICIES CONFLICT — USUALLY: SAFETY > CORRECTNESS > FEATURE COMPLETENESS]
```

---

## 8. Template: `.claude/agents/[domain]-reviewer.md`

A subagent that reviews a diff cold — it did not write the code, so it isn't
anchored to the implementer's assumptions.

```markdown
---
name: [domain]-reviewer
description: Use after implementing a change (before commit) to check a diff against [PROJECT_NAME]'s hard constraints, [policy areas], and current milestone scope. Give it the diff and, if one exists, the spec for the change — not a summary of what you did. Runs in a clean context so it isn't biased by having written the code.
tools: Read, Grep, Glob, Bash
model: inherit
---

You are reviewing a code change for the [PROJECT_NAME] project, [ONE-LINE PROJECT DESCRIPTION]. You did not write this change — review it cold.

Before judging anything, read:

- `CLAUDE.md` and `AGENTS.md` for hard constraints and current milestone scope
- `docs/IMPLEMENTATION_SPEC.md` for the module boundaries, schemas, and milestone this change should belong to
- `docs/ARCHITECTURE_DECISIONS.md` for accepted ADRs the change must not contradict
- [OTHER POLICY DOCS] for anything touching [RELEVANT CONCERNS]

Check the diff for:

1. **Constraint violations** — does an LLM path override a deterministic hard constraint? Deterministic logic must remain in code, never delegated to a model.
2. **[Domain]-language drift** — [WHATEVER LANGUAGE/OUTPUT RULE MATTERS FOR THIS PROJECT]
3. **Rights/consent gaps** — [IF APPLICABLE]
4. **Auditability gaps** — do new AI-generated artifacts lack the audit record the spec requires?
5. **Scope creep** — does the change reach past the current milestone, or introduce [SPECIFIC OVER-ENGINEERING TO WATCH FOR]?
6. **Coding standards** — conventions from `docs/IMPLEMENTATION_SPEC.md` §[N], and whether tests were added or updated alongside the change.

Report findings as a short list ordered by severity: constraint/safety
violations first, then governance gaps, then scope/style issues. For each,
cite the file and line, state the concrete failure it causes, and say which
rule it breaks. If the diff is clean, say so plainly — do not invent issues
to fill space.
```

---

## 9. Template: `.claude/skills/[policy-name]/SKILL.md`

Package each standalone policy doc as a skill so it's loaded automatically
when relevant work is detected, instead of relying on the agent to remember
to open the doc.

```markdown
---
name: [policy-name]
description: [PROJECT_NAME]'s [policy area] rules — [ONE-LINE SUMMARY OF WHAT IT COVERS]. Load when implementing or reviewing [TRIGGERING WORK, e.g. "data ingestion, retention, or consent flows"].
---

[BODY: THE OPERATIVE RULES FROM THE CORRESPONDING docs/*.md FILE, RESTATED
FOR AN AGENT ABOUT TO WRITE CODE RATHER THAN A HUMAN READING POLICY. KEEP IT
SHORT — THIS IS A WORKING CHECKLIST, NOT THE POLICY DOCUMENT ITSELF.]
```

---

## 10. Template: `PRODUCT_SPEC.md` (repo root, optional)

An upstream, human-oriented business/product document. Not read by the
coding agent every session — it's the source `docs/IMPLEMENTATION_SPEC.md`
was derived from, kept around for context on *why*, not *what to build next*.

```markdown
# [PROJECT_NAME] [Proof-of-Concept/Product] Specification

## 1. Executive Summary
## 2. Market Reality
## 3. Target Users and Jobs to Be Done
## 4. [Stage] Objective
## 5. [Stage] Non-Goals
## 6. [Stage] Success Criteria
## 7. Product Architecture
## 8. [Core Domain Subsystem 1]
## 9. [Core Domain Subsystem 2]
## 10. Data Model
## 11. Recommended Technology Stack
## 12. Privacy, Security, and Data Retention
## 13. [Regulatory/Compliance Boundary, if applicable]
## 14. Model and Dataset Governance
## 15. Evaluation Plan
## 16. Build Plan (by week or phase)
## 17. Main Risks
## 18. Recommended First Demo
## 19. Go/No-Go Decision After [Stage]
## 20. Research and Regulatory Basis
```

---

## 11. Generic repo layout

Adapt paths to the actual stack; the shape (frontend / backend / data /
docs / agent config as top-level siblings) is what matters.

```
[project-root]/
├── CLAUDE.md
├── AGENTS.md
├── PRODUCT_SPEC.md              # optional
├── README.md
├── Makefile
├── docker-compose.yml
├── .env.example
├── .claude/
│   ├── agents/
│   │   └── [domain]-reviewer.md
│   └── skills/
│       └── [policy-name]/
│           └── SKILL.md
├── docs/
│   ├── IMPLEMENTATION_SPEC.md
│   ├── ARCHITECTURE_DECISIONS.md
│   ├── GOVERNANCE.md            # if applicable
│   └── SAFETY_POLICY.md         # if applicable
├── apps/
│   └── web/                     # frontend app
├── services/
│   └── api/                     # backend service
│       ├── src/
│       └── tests/
└── db/
    ├── migrations/
    └── seeds/
```

---

## 12. Instantiation checklist

Order of operations when starting a new project from this template:

1. Write `PRODUCT_SPEC.md` first if the project needs a business case — this
   is where "why" and "for whom" get decided before any code exists.
2. Derive `docs/IMPLEMENTATION_SPEC.md` from it: fill every numbered section,
   deleting ones marked N/A. This is the expensive step — don't skip to code
   before it's coherent.
3. Extract the hard constraints into `CLAUDE.md`, restate them tool-agnostic
   in `AGENTS.md`.
4. Split out `docs/ARCHITECTURE_DECISIONS.md`, `docs/GOVERNANCE.md`,
   `docs/SAFETY_POLICY.md` only for the concerns that are real for this
   project — an empty policy doc is worse than no policy doc.
5. Write the `[domain]-reviewer` subagent once there's at least one hard
   constraint worth checking on every diff.
6. Package each standalone policy doc as a `.claude/skills/` entry so it
   loads contextually instead of relying on memory.
7. Scaffold the repo layout, get Milestone 0 (repo foundation, health check,
   CI, empty-but-runnable app) green before writing any feature code.
8. From then on: implement milestones in order, run the reviewer subagent
   before each commit, update the ADR log whenever an architecture decision
   changes, and stop at milestone boundaries.
