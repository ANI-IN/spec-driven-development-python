# Worksheet: Spec-Driven Development

Fill this in during the lab. Keep it open in a split editor, or print it and
write on it.

## Exercise 1: Read the PRD

Open [prd-early-stopping.md](prd-early-stopping.md) and run
`python -m minitrain` to see the problem for yourself.

List three things the PRD does **not** answer:

1.
2.
3.

## Exercise 2: Write the spec

Use [spec-template.md](spec-template.md). Commit it as `spec.md` at the repo
root on your `feature/early-stopping-<initials>` branch.

Check off the items in
[spec-quality-checklist.md](spec-quality-checklist.md).

## Exercise 3: Implement, then iterate the spec once

Run the agent against the spec. As gaps surface, **patch the spec first, then
re-run.** Do not patch the code without patching the spec.

| Spec gap | Defect that surfaced | Fix in spec |
|---|---|---|
| | | |
| | | |
| | | |

For each row, be ready to say in one sentence: *"This defect traces to this
spec gap."*

## Exercise 4: Lock the build

- [ ] `spec.md` committed before any implementation code
- [ ] Implementation committed on `feature/early-stopping-<initials>`
- [ ] At least one acceptance test passing
- [ ] `pytest`, `ruff check .`, `ruff format --check .`, and `mypy` all pass
- [ ] Branch pushed
