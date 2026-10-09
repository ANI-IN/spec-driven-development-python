# Spec Template

> Keep it short. One page is a good target; two pages is the upper bound for
> one feature. If you need more, the feature should be split.

## 1. Context

- One paragraph: what is being built and why.
- Link to the PRD and any existing design notes.

## 2. Scope

- A bulleted list of what is in scope, written as behavior a user or a
  calling program can observe.

## 3. Acceptance criteria

> Each criterion must be testable. If you cannot imagine the test, the
> criterion is not specific enough.

- [ ] AC1: `<observable behavior>`
- [ ] AC2: `<observable behavior>`
- [ ] AC3: `<observable behavior>`

## 4. Constraints

- Technical, performance, reproducibility, or compatibility constraints.
- Anything the agent must obey that a reader of the PRD would not know.

## 5. Non-goals

- Things explicitly out of scope.
- Things a reasonable reader might assume are included but you are not
  building.

## 6. Definition of done

- All acceptance criteria pass automated tests (`pytest`).
- `<other gates: ruff check, ruff format --check, mypy --strict, review>`
- Documentation: `<what is updated and where>`
- Observability: `<new log events or result fields>`

## Optional sections (use sparingly)

### 7. Interfaces

- Public classes, function signatures, dataclass fields, CLI flags, or log
  event shapes the rest of the system will see. Treat this as a contract.

### 8. Open questions

- Anything you want to flag rather than guess. The agent may not see these.
