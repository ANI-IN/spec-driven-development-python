<!--
SYNC IMPACT REPORT
==================
Version change: (unversioned template) → 1.0.0
Bump rationale: Initial ratification. All five core principles are newly
defined; no earlier versioned constitution existed.

Modified principles:
  - [PRINCIPLE_1_NAME] → I. Tests Before Implementation (NON-NEGOTIABLE)
  - [PRINCIPLE_2_NAME] → II. Fully Type-Hinted Code
  - [PRINCIPLE_3_NAME] → III. Typed Exceptions, Never Strings
  - [PRINCIPLE_4_NAME] → IV. One Responsibility Per Module
  - [PRINCIPLE_5_NAME] → V. Data Safety Over Convenience

Added sections:
  - Core Principles (I–V)
  - Additional Constraints (Python and runtime rules derived from the principles)
  - Development Workflow & Quality Gates
  - Governance

Removed sections: None (template placeholders replaced in place).

Templates requiring updates:
  - .specify/templates/plan-template.md       ✅ compatible (Constitution Check
     section is filled per feature; no principle-specific gates hard-coded)
  - .specify/templates/spec-template.md       ✅ compatible (no changes needed)
  - .specify/templates/tasks-template.md      ✅ compatible (test-first ordering
     is enforced through principle I during /speckit-tasks)
  - .specify/templates/checklist-template.md  ✅ compatible

Follow-up TODOs:
  - TODO(RATIFICATION_DATE): 2026-10-10 reflects adoption in this session.
    Adjust it if the project ratified the constitution on another date.
-->

# Experiment Runs API Constitution

## Core Principles

### I. Tests Before Implementation (NON-NEGOTIABLE)

Every feature MUST ship with a failing test written first. The workflow is:
write the test, run it and watch it fail for the intended reason, then write
the implementation that makes it pass. A change that adds or alters behavior
without a preceding failing test MUST be rejected.

**Rationale**: Tests written after the code tend to describe the
implementation instead of the requirement. Writing the test first states the
requirement in executable form and proves the test can fail.

### II. Fully Type-Hinted Code

Every function, method, and module-level value in `src/` and `tests/` MUST
carry type hints, and `mypy --strict` MUST report zero errors. `typing.Any`
and `# type: ignore` MUST NOT appear unless the same or the previous line
carries a comment explaining why a precise type is impossible.

**Rationale**: Untyped escape hatches spread silently. Requiring a comment
turns each one into a reviewable decision instead of a habit.

### III. Typed Exceptions, Never Strings

Code MUST raise subclasses of a shared `AppError` base class (for example
`class NotFoundError(AppError)`). Raising bare `Exception`, `ValueError` with
only a message, or any non-exception value is prohibited on production code
paths. Callers that handle errors MUST branch on the exception class
(`except NotFoundError` or `isinstance`), never on message text.

**Rationale**: Exception classes make failure modes part of the API, let one
place map them to responses, and survive rewording of messages.

### IV. One Responsibility Per Module

Each source module MUST have exactly one responsibility:

- Route modules MUST only parse requests, call the service, and shape
  responses. They MUST NOT contain business rules or touch storage.
- Service modules MUST only contain domain logic. They MUST NOT import HTTP
  framework types (requests, responses, status codes, routers).
- Repository modules MUST only contain storage concerns. They MUST NOT contain
  HTTP or business rules.

**Rationale**: Mixing layers in one module couples transport, domain, and
storage, makes each impossible to test alone, and turns small changes into
cascading edits.

### V. Data Safety Over Convenience

Every persistence operation MUST be crash-safe. Writes MUST be atomic: for a
file this means write to a temp file, fsync, and rename over the target; for a
database it means one transaction per logical change. A crash at any point
MUST leave the store in either its pre-write or its post-write state, never a
partial one. Shortcuts such as writing the target file in place, or
multi-step writes without a transaction, are prohibited.

**Rationale**: Partial-write states are the hardest production bugs to detect
and the most damaging to recover from. Paying for atomicity at write time is
always cheaper than debugging corrupted state later.

## Additional Constraints

- **Language**: Python 3.10 or newer. Every module in `src/` is type-checked
  with `mypy --strict`.
- **Error hierarchy**: All domain errors derive from `AppError`, so the HTTP
  boundary can map them in one place.
- **Layer boundaries**: Dependencies point `routes → service → repository`.
  Reverse imports are prohibited.
- **Atomic write utility**: One reviewed helper performs every write of
  persisted state. Ad-hoc `open(..., "w")` on the store is not permitted.

## Development Workflow & Quality Gates

- **Pre-merge gates** (all MUST pass):
  1. New or changed behavior has a test that failed before the implementation
     commit and passes after it.
  2. `mypy --strict` reports zero errors, and every `Any` or `type: ignore`
     has a justifying comment.
  3. `ruff check .` and `ruff format --check .` pass.
  4. No route module imports the repository; no service module imports HTTP
     framework types.
  5. Every persistence write path either goes through the atomic-write helper
     or is covered by a test that simulates a crash mid-write.

- **Review discipline**: Reviewers MUST cite the specific principle (I–V) when
  asking for changes over a constitutional violation, and MUST NOT approve
  exceptions without an amendment recorded under Governance.

## Governance

- **Authority**: This constitution overrides ad-hoc conventions and individual
  preference. Where another document conflicts with it, this one wins until it
  is formally amended.

- **Amendment procedure**: An amendment needs (a) a written proposal with the
  change and its rationale, (b) an updated Sync Impact Report in this file,
  and (c) approval from at least one maintainer other than the proposer. Every
  amendment bumps the version in the same change.

- **Versioning policy** (semantic versioning of this document):
  - **MAJOR**: a principle is removed or redefined incompatibly, or governance
    changes in a backward-incompatible way.
  - **MINOR**: a principle or a materially expanded section is added.
  - **PATCH**: wording, typo, or other non-semantic fixes.

- **Compliance review**: Every pull request is checked against the Core
  Principles. Complexity or exceptions are justified in writing in the pull
  request and, if they recur, turned into an amendment rather than tolerated
  as precedent.

**Version**: 1.0.0 | **Ratified**: 2026-10-10 | **Last Amended**: 2026-10-10
