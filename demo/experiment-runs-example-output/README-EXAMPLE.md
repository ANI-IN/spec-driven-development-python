# experiment-runs-example-output: the full worked example

This folder holds the **complete artifact set** that the Spec Kit pipeline
produces for the prompts in the [demo README](../README.md): constitution,
spec, clarifications, plan, research, data model, contract, tasks, and a
working, tested implementation. Use it as a known-good baseline to compare
your own run against, phase by phase.

Your run will not match it word for word. The agent words things differently
each time, and it may ask different clarifying questions. Compare the
**structure and the decisions**, not the prose. The artifacts here were also
edited after generation: for clarity, to apply the analyze remediations
(which you ask Claude to make after `/speckit-analyze` reports them), and to
fold in fixes from a code review of the generated service.

Checked on 2026-10-10 against Spec Kit v1.1.2 with Python 3.12: all pytest
tests pass, `mypy --strict` is clean, and `ruff check` and `ruff format
--check` are clean.

## What's in here

| Path | What it is | Produced by |
|---|---|---|
| `.specify/memory/constitution.md` | The five-principle project constitution | `/speckit-constitution` |
| `specs/001-experiment-runs/spec.md` | User stories, functional requirements, success criteria, edge cases, assumptions, and the Clarifications session | `/speckit-specify` + `/speckit-clarify` |
| `specs/001-experiment-runs/checklists/requirements.md` | Spec quality checklist | `/speckit-specify` |
| `specs/001-experiment-runs/plan.md` | Implementation plan with the Constitution Check gate | `/speckit-plan` |
| `specs/001-experiment-runs/research.md` | Seven technical decisions with rationale and rejected alternatives | `/speckit-plan` (Phase 0) |
| `specs/001-experiment-runs/data-model.md` | Entities, invariants, state transitions, validation rules | `/speckit-plan` (Phase 1) |
| `specs/001-experiment-runs/contracts/openapi.yaml` | OpenAPI 3.1 contract for the four endpoints | `/speckit-plan` (Phase 1) |
| `specs/001-experiment-runs/quickstart.md` | Manual QA scenarios with curl | `/speckit-plan` (Phase 1) |
| `specs/001-experiment-runs/tasks.md` | 37 tasks across 7 phases, with `[P]` markers, story tags, and the analyze remediations | `/speckit-tasks`, then edits after `/speckit-analyze` |
| `src/experiment_runs/` | The service: 13 modules plus `__init__.py` | `/speckit-implement` |
| `tests/` | pytest modules for each layer, plus crash, restart, real-process, and latency tests | `/speckit-implement` |
| `pyproject.toml` | Packaging, dependencies, and Ruff, mypy, and pytest settings | `/speckit-implement` |
| `README.md` | Project README for the generated service | `/speckit-implement` |

## What is NOT in here (deliberately)

- **`.claude/skills/`, `.specify/templates/`, `.specify/scripts/`,
  `.specify/workflows/`, and the integration manifests**: they are identical to the untouched scaffold in
  [../experiment-runs-reference/](../experiment-runs-reference/), so they are
  not duplicated here.
- **`.specify/feature.json`**: Spec Kit's own `.specify/.gitignore` marks it
  as per-checkout state.
- **`.venv/`**: create it with the setup steps in [README.md](README.md).
- **`data/`**: created at runtime by the store.

## Run it yourself

```bash
cd demo/experiment-runs-example-output
python3 -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
```

To try the API by hand, follow
[specs/001-experiment-runs/quickstart.md](specs/001-experiment-runs/quickstart.md).

## Do NOT run Spec Kit skills against this folder

Running `/speckit-specify`, `/speckit-plan`, and so on here would overwrite the
reference artifacts. To try the pipeline, work in a scratch directory outside
this repo (see the [demo README](../README.md)).

## Provenance

The prompts are in the [demo README](../README.md):

- **Constitution**: the five-principle block from *Phase 0: Constitution*.
- **Specify**: the Experiment Runs description from *Phase 1: Specify*.
- **Clarify**: five questions (list ordering, identifier format,
  observability, corrupted-store recovery, finishing a finished run), each
  answered with the recommended option.
- **Plan**: the Python, FastAPI, Pydantic, and pytest stack from
  *Phase 2: Plan*.
- **Tasks**: 37 tasks across 7 phases after remediation.
- **Analyze remediations applied**: G1 (latency test for SC-004), G2
  (automated restart-cycle test for SC-006), G3 (request-log assertions for
  FR-016), G4 (startup-log assertions for FR-018), U1 (`schema_version`
  invariant), A1 (tighter SC-003 wording).
