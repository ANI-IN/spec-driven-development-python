# Spec-Driven Development with Spec Kit

**Executable specs · `/speckit-*` pipeline · Constitution-enforced · Python end to end**

Spec-Driven Development treats the specification as **executable intent**.
Instead of coding first and writing docs later, you start with a spec, and the
agent generates the plan, the tasks, the code, and the tests from it.
[Spec Kit](https://github.com/github/spec-kit) is GitHub's open-source toolkit
for this. It installs a chain of skills into your coding agent, which you run
in order, with a checkpoint between each one.

---

## 01. The Problem It Solves

Vague prompting works for prototypes and breaks for anything that matters.
"Build me an experiment tracker" forces the agent to guess at dozens of
unstated requirements: what a run is, what happens to results on a crash, what
"stalled" means. Usually you only find out which guesses were wrong deep into
the implementation.

Spec-driven development flips that failure mode. Every ambiguity is **surfaced
as a question before code exists**. Every architectural decision goes into a
plan the agent must respect. Every requirement is traced to at least one task
before the agent writes anything.

## 02. The Pipeline

Spec Kit installs ten skills. In Claude Code they are named with hyphens
(`/speckit-specify`); other agents use dots (`/speckit.specify`). The
skills underneath are the same.

| Order | Skill | Job | Output |
|---|---|---|---|
| 0 | `/speckit-constitution` | Set the project's non-negotiable rules | `.specify/memory/constitution.md` |
| 1 | `/speckit-specify` | Turn a description into a spec: what and why, no tech | `specs/<nnn>-<slug>/spec.md` with user stories, functional requirements, success criteria, edge cases, assumptions |
| 1a | `/speckit-clarify` *(optional, recommended)* | Ask up to 5 targeted questions, one at a time, to remove ambiguity | A `Clarifications` section in `spec.md`, plus edits to every section an answer affects |
| 2 | `/speckit-plan` | Add the tech direction and produce a design | `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`, with Constitution Check gates |
| 2a | `/speckit-checklist` *(optional)* | Generate a requirements-quality checklist | `checklists/*.md` |
| 3 | `/speckit-tasks` | Break spec and plan into small, dependency-ordered tasks | `tasks.md` with `[P]` parallel markers and `[USn]` story tags |
| 3a | `/speckit-analyze` *(optional, highest leverage)* | Read-only consistency check across spec, plan, and tasks | A findings report and an offer to suggest fixes |
| 4 | `/speckit-implement` | Work through the tasks, writing tests and code, checking each phase | The source tree, with tests green between phases |
| 4a | `/speckit-converge` *(optional)* | Compare the code with the spec and append any unbuilt work as new tasks | New tasks in `tasks.md` |
| – | `/speckit-taskstoissues` *(optional)* | Turn `tasks.md` into GitHub issues | Issues in your repository |

Your job at each phase is to **steer and verify**. The agent writes; you own
the checkpoint.

## 03. What Makes a Spec Executable

Spec Kit's spec is not prose. It is a structured contract:

- **Prioritized user stories** (P1, P2, ...) with acceptance scenarios.
- **Numbered functional requirements** (`FR-001`, `FR-002`, ...), each one
  testable.
- **Measurable success criteria** (`SC-001`, ...) with numbers, not
  adjectives.
- An **edge cases** section that describes the failure paths.
- **Assumptions**: every silent decision made explicit.

If a "should" in the spec has no testable condition, the spec has a gap.
`/speckit-clarify` and `/speckit-analyze` are where those gaps get closed.

## 04. How the Constitution Flows Downstream

The constitution holds the project's non-negotiable principles, and the
later skills read it and check against it:

- **`/speckit-plan`** runs a **Constitution Check** gate before and after
  design. If a principle is violated, the plan does not advance until the
  violation is fixed or justified.
- **`/speckit-tasks`** reads the constitution when it builds the task list.
  Test tasks are optional by default, so a test-first principle (and a
  one-line reminder in the prompt) is what makes it generate a test task and
  order it before each implementation task. Check the result: the agent can
  still miss one.
- **`/speckit-analyze`** treats any conflict with a constitution MUST as a
  CRITICAL finding, to be fixed in the spec, plan, or tasks, never by
  weakening the principle.
- **`/speckit-implement`** follows the task order and checks each phase before
  moving on.

This is the most under-appreciated feature. Team conventions stop being
reminders you retype into every prompt and become **rules that every later
phase is checked against**. You still verify each checkpoint.

## 05. How It Fits with Plan Mode and CLAUDE.md

- **Plan Mode** applies to a single change; **Spec Kit** applies to a whole
  feature. Plan Mode is the atom, a spec is the molecule. To review risky work
  one step at a time, pass `/speckit-implement` a task filter (for example
  `/speckit-implement only T020`) and check the diff before you continue.
- **CLAUDE.md** and the constitution overlap. Use the constitution for hard
  rules the spec pipeline should enforce, and CLAUDE.md for softer defaults
  every session picks up.

## 06. When to Use It, and When to Skip It

**Use it when:**

- **Greenfield**: a new project or subsystem.
- **A feature in an existing system** where the "what" is not yet agreed.
- **Modernizing legacy code**: the intent is known but the current code is
  not the target.
- **Several engineers** will work on the same feature and need one source of
  truth.

**Skip it when:**

- It is a single-file bug fix.
- The change is small enough that Plan Mode alone is proportionate.
- The "what" is not decided yet. Spec Kit generates *from* a description; if
  you cannot describe it, do not run it.

## 07. Version Drift Warning

GitHub's announcement post (September 2025) used unprefixed commands such as
`/specify`, `/plan`, and `/tasks`, and an `--ai` CLI flag. The **current
release, v1.1.2 (checked 2026-10-10)**, is different:

- Commands are skills with a `speckit-` prefix (`/speckit-specify`).
- The flag is `--integration claude`, not `--ai claude`.
- `--script py` installs Python helper scripts, which the skills run with
  `python3`, so the same scaffold works on macOS, Linux, and Windows as long
  as `python3` runs in your shell.
- Creating a git branch per feature is no longer built in. It is an optional
  extension (`--extension git`). Without it no branch is created: the skills
  find the current feature through `.specify/feature.json`, and you create a
  branch yourself if you want one.

This demo pins `@v1.1.2` so the commands and flags below match. The agent's
own output still varies from run to run. If you follow an older blog post and
get flag errors, this is why.

## 08. Recap

- Spec Kit chains **constitution → specify → clarify → plan → tasks →
  analyze → implement**.
- Constitution principles are checked at every later phase: plan gates,
  task ordering, and analyze findings. You still verify each checkpoint.
- Every phase has a checkpoint. You steer; the agent writes.
- `/speckit-analyze` is the highest-leverage step. It turns silent
  inconsistencies into fixable findings before any code exists.
- Defects usually trace back to a spec or plan gap. Fix upstream, then re-run.
- The constitution, spec, plan, tasks, and code live under `.specify/`,
  `specs/`, `src/`, and `tests/`. Commit them together.

---

# Demo: Build an Experiment Runs API with Spec Kit

**Full pipeline · Python, FastAPI, Pydantic, pytest · about 75 to 90 minutes**

You will take a plain-language description of an **Experiment Runs API**, a
small service where an ML engineer logs training runs, and drive it through
the pipeline: constitution → specify → clarify → plan → tasks → analyze →
implement. At the end you will have about 35 generated tasks and a working,
tested service, none of which you wrote by hand. The per-phase times below
add up to about 75 minutes; allow longer for implement on a slow machine.

## 01. Why This Demo

In the [lab](../lab/README.md) you write a spec **by hand** with a one-page
template. This demo shows the tool-driven form of the same idea. Same mental
model, different packaging. Run it before or after the lab.

A complete set of artifacts for these exact prompts is checked in at
[experiment-runs-example-output/](experiment-runs-example-output/), so you can
compare your run with a known-good baseline at every phase.

## 02. Prerequisites

- Claude Code installed and signed in. Inside Claude Code, `/status` should
  show an account with API credit or a Claude subscription.
- Python 3.10 or newer, and `python3 --version` must work in your shell,
  because the Spec Kit skills call `python3`. (On Windows, install Python from
  python.org or the Microsoft Store and check that `python3` runs; if only
  `python` or `py` works, add a `python3` alias.)
- `uv`:
  - macOS or Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows PowerShell: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - Fallback anywhere: `python -m pip install uv`
  - Check: `uv --version`
- `git` on `PATH`.
- An **empty working directory** outside this repo, where Spec Kit will
  scaffold the project.

Project folders: [experiment-runs-reference/](experiment-runs-reference/)
(the raw scaffold) and
[experiment-runs-example-output/](experiment-runs-example-output/) (the
complete worked example).

## 03. Initialize the Project

*(about 5 min)*

In an empty directory:

```bash
uvx --from git+https://github.com/github/spec-kit.git@v1.1.2 \
  specify init experiment-runs --integration claude --script py
cd experiment-runs
git init
git switch -c 001-experiment-runs
```

The same command works in PowerShell (put it on one line, or replace each
`\` with a backtick). `specify init` ends with a **Project ready** banner and a
**Next Steps** panel listing the `/speckit-*` skills.

Look at the layout:

```bash
ls -a
find .claude .specify -type f | sort
# PowerShell: Get-ChildItem -Force; Get-ChildItem -Recurse -File .claude, .specify
```

Notice:

- **`.claude/skills/speckit-*/SKILL.md`**: ten Spec Kit skills registered with
  Claude Code. You use seven in this demo; `/speckit-checklist`,
  `/speckit-converge`, and `/speckit-taskstoissues` are optional extras.
- **`.specify/memory/`, `.specify/templates/`, `.specify/scripts/python/`**:
  the toolkit's working area.
- **No application code yet.** The toolkit installed a *workflow*, not a
  project.

Compare with [experiment-runs-reference/](experiment-runs-reference/).

The CLI also prints an **Agent Folder Security** note: agents can keep local
state in `.claude/`, so before you push, check that only the skill files are
committed (`.claude/settings.local.json` should stay out of git).

## 04. Open Claude Code

*(about 2 min)*

```bash
claude
```

Type `/speckit` and confirm the `speckit-*` skills appear in the autocomplete
menu.

If they are missing, exit and start Claude Code again from the project root.
Skills are loaded from `.claude/skills/*/SKILL.md` when the session starts.

## 05. Phase 0: Constitution

*(about 5 min)*

Paste exactly:

```text
/speckit-constitution The project follows five principles:
1. Tests before implementation (NON-NEGOTIABLE): every feature ships with a
   failing test first.
2. Fully type-hinted code: mypy --strict passes; no Any without a comment.
3. Typed exceptions, never strings: raise subclasses of a shared AppError and
   handle errors by class, never by message text.
4. One responsibility per module: a route module has no business logic; a
   service module has no HTTP.
5. Data safety over convenience: persistence must be crash-safe (atomic
   writes, no partial states).
```

Expect:

- `.specify/memory/constitution.md` filled in with the five principles,
  rationale for each, quality gates, and governance rules.
- A **Sync Impact Report** at the top of the file summarizing what changed
  and flagging placeholders such as `TODO(RATIFICATION_DATE)`.
- A suggested commit message.

Compare with
[the example constitution](experiment-runs-example-output/.specify/memory/constitution.md).

Why this matters:

> Every later phase is checked against this file. If `/speckit-plan` ignores
> principle 5, you catch the violation before any code exists.

Commit: `git add -A && git commit -m "Add project constitution"`.

## 06. Phase 1: Specify

*(about 10 min)*

```text
/speckit-specify Build a small Experiment Runs API that lets a single ML
engineer log model training runs. A run has a name, a model type, a set of
hyperparameters, and an optional time budget in minutes. The engineer can
list their runs, finish a run by recording its final metrics, and delete a
run. They need to see stalled runs, ones still running past their time
budget, at a glance, and must never lose data on a crash. There is no
authentication in this release: one user, one process.
```

Expect `specs/001-<short-name>/spec.md`, where the agent picks the short name
(the worked example uses `specs/001-experiment-runs/`), with:

- **About four prioritized user stories** (P1 and P2) with acceptance
  scenarios: log and list, survive crashes, finish and delete, see stalled
  runs.
- **About 15 to 20 functional requirements** (`FR-001`, ...).
- **About six measurable success criteria** (`SC-001`, ...).
- An **edge cases** section.
- **Several explicit assumptions**: single user, single process, no auth,
  local file storage, runs are logged rather than executed, no pagination.
- `checklists/requirements.md`: the spec-quality checklist that
  `/speckit-specify` writes and checks the spec against.
- A **readiness note**: ready for `/speckit-plan`, or run `/speckit-clarify`
  first.

Read the readiness note. Even if it says clarify is optional, run it anyway:
the questions it asks show you which silent decisions it made.

## 07. Phase 1a: Clarify

*(about 10 min)*

```text
/speckit-clarify
```

The skill asks up to five questions **one at a time**, either as **multiple
choice with a recommended option** or as a short answer with a suggested
answer. For this API, expect questions such as:

1. List ordering: stalled first, newest first, or start-time order?
2. Run identifier format: UUID v4, counter, ULID, or slug?
3. Observability: logs only, logs plus metrics, or logs plus a health
   endpoint?
4. Corrupted-store recovery: quarantine and exit, rebuild empty, or abort?
5. Finishing a run that is already finished: reject, overwrite, or ignore?

Answer each one. **Accepting the recommended option is a valid strategy**:
the skill picks it as the best-practice, lowest-risk choice. Reply with the option letter or
`yes` to accept the recommendation. To match the worked example, choose the
answers recorded in its
[Clarifications section](experiment-runs-example-output/specs/001-experiment-runs/spec.md#clarifications).

At the end, expect a completion report: how many questions were asked, which
spec sections changed, and a coverage table marking each ambiguity category
as Resolved, Deferred, Clear, or Outstanding.

## 08. Phase 2: Plan

*(about 10 min)*

```text
/speckit-plan Use Python 3.10+ with FastAPI for HTTP and Pydantic v2 for
input validation. Persist runs to a single JSON file with an atomic write
(write a temp file, fsync it, os.replace it over the target, then fsync the
directory) so a crash mid-write cannot corrupt the store. Put tests in a
tests/ folder using pytest and FastAPI's TestClient. Check types with mypy
--strict and lint with Ruff. No database, no ORM, no auth middleware.
```

Expect five artifacts under `specs/001-experiment-runs/`:

- `plan.md`: technical context, project structure, and the **Constitution
  Check** section.
- `research.md`: decisions with rationale and rejected alternatives.
- `data-model.md`: entities, invariants, state transitions.
- `contracts/openapi.yaml`: the HTTP contract.
- `quickstart.md`: manual QA steps.

Look for explicit gate results in `plan.md`: an initial Constitution Check of
PASS, and a post-design re-check of PASS.

If the plan adds dependencies you did not ask for, correct it with a targeted
re-prompt, for example:
`/speckit-plan remove SQLAlchemy; use the json module and the atomic write described above`.

## 09. Phase 3: Tasks

*(about 5 min)*

```text
/speckit-tasks Follow the constitution's test-first principle: put a failing
test task before every implementation task.
```

Test tasks are optional in Spec Kit by default, so say it in the prompt as
well as in the constitution. Expect:

- **About 35 tasks across about 7 phases**: Setup, Foundational, one
  phase per user story, and Polish.
- Each task in the strict format `- [ ] Txxx [P?] [Story?] Description with file path`.
- `[P]` markers on tasks whose files are independent.
- `[USn]` tags tying tasks to user stories.
- A **suggested MVP scope**.
- **Test-first ordering**: every implementation task depends on a test task
  that comes before it. Check this yourself; it is the rule agents most often
  bend for "plumbing" tasks such as wiring up the app.

Apply one filter: *"When I finish this task, can I commit and still have a
working repo?"* If a task fails that test, re-prompt:
`/speckit-tasks refine: split any task that leaves the repo broken`.

## 10. Phase 3a: Analyze

*(about 10 min)*

```text
/speckit-analyze
```

Analyze is **read-only**. Expect a **Specification Analysis Report** with:

- A **findings table**: each finding has an ID, category, severity
  (CRITICAL, HIGH, MEDIUM, LOW), location, summary, and recommendation.
- A **coverage summary** listing every requirement with the tasks that cover
  it.
- **Constitution alignment** issues, if any.
- **Metrics**: total requirements, total tasks, coverage percentage, and
  counts of ambiguities, duplications, and critical issues.
- An offer: *would you like concrete remediation edits for the top issues?*

A typical first pass on this API reports coverage below 100%: success
criteria such as the latency target (SC-004) or the 100-restart test (SC-006)
have no task that actually measures them. Say yes, review the suggested
edits, then ask Claude to apply the ones you agree with (analyze itself never
edits files). The worked example's
[tasks.md](experiment-runs-example-output/specs/001-experiment-runs/tasks.md#notes)
lists the six remediations it applied.

This is the highest-leverage step. On a real feature, these findings could
have become production bugs.

## 11. Phase 4: Implement

*(about 15 min)*

```text
/speckit-implement
```

The agent works through the tasks phase by phase, writing each failing test
before the code that makes it pass, and runs the checks between phases as
its own feedback loop:

```bash
pytest
mypy
ruff check .
ruff format --check .
```

Watch the pytest count climb as each phase completes. The exact numbers
depend on your run. If any checklist under `checklists/` still has unchecked
items, `/speckit-implement` stops and asks before it starts.

What to watch for:

- Each phase should end green before the next one starts. That is the
  test-first principle at work.
- When a test fails, the fix belongs upstream: trace it to a spec or plan gap
  first.

If a test fails mid-run, **do not let the agent chase it blindly**. Ask:

```text
Which line of the spec (or plan) does this failure trace to? If the spec is
silent on it, propose the spec amendment first; do not patch the code without
patching the spec.
```

## 12. Verify From a Fresh Shell

*(about 3 min)*

Exit Claude Code and open a new terminal in the project folder. Use the
setup and run commands from your generated `README.md` or `quickstart.md`;
for the worked example they are:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
```

You should see the same pass count Claude reported. If you don't, a leftover
`data/` file or a difference between environments is hiding a problem that
only shows up in a fresh shell.

Then start the service and, in a second terminal, try a scenario from the
generated `quickstart.md`:

```bash
python -m experiment_runs
```

Finally, list the generated artifacts:

```bash
find .specify/memory specs -type f | sort
```

## 13. Summary

- `specify init --integration claude --script py` scaffolds the workflow; it
  writes no application code.
- Walk the pipeline in order: constitution → specify → clarify → plan →
  tasks → analyze → implement.
- Non-negotiable principles are enforced automatically in plan and tasks.
- Clarify asks multiple-choice questions with a recommended option.
- `/speckit-analyze` finds the last gaps between requirements and tasks, and
  offers fixes you approve.
- `/speckit-implement` runs the tests between phases as its own feedback
  loop.
- Commit the constitution, spec, plan, tasks, code, and tests together.

**Design decision:** *the spec is the source of truth; the code is a build
artifact of the spec.*

## 14. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `uvx: command not found` | `uv` is not on `PATH` after install | Open a new shell, use the full path, or run `python -m uv tool run ...` |
| `specify init` rejects `--ai` | Following the 2025 blog post | Use `--integration claude` |
| `No such option` on another flag | Running a different Spec Kit version | Keep the `@v1.1.2` pin from this guide |
| `/speckit-*` missing in Claude Code | Session started before the scaffold existed | Exit and re-open `claude` from the project root |
| No feature branch was created | Branching is an optional extension in v1.x | `git switch -c 001-experiment-runs`, or init with `--extension git` |
| Claude Code reports an invalid API key or an authentication error | Claude Code auth issue | Inside Claude Code run `/logout`, then `/login`; or unset a stale `ANTHROPIC_API_KEY` |
| `/speckit-plan` invents dependencies | Prompt too permissive | Re-run with an explicit "use only these libraries" constraint |
| `/speckit-implement` skips tasks | Task descriptions too vague | Re-run `/speckit-tasks` with the "working repo after every task" rule, then `/speckit-analyze` |
| Tests fail during implement | A spec or plan gap, not an agent error | Trace it to the spec first; patch the spec, then re-run |
| Old blog commands (`/specify`) do nothing | The blog predates v1.x | Use the `speckit-` prefix on every command |

## 15. Next Steps

- Browse [experiment-runs-example-output/](experiment-runs-example-output/),
  the full artifact set, and diff it against your run.
- Do the [lab](../lab/README.md) by hand on the early-stopping PRD. Notice
  which part of the one-page template maps to which Spec Kit skill.
- To use another agent, scaffold with a different integration (for example
  `--integration copilot`) and use dot syntax (`/speckit.constitution`). The
  artifacts it produces have the same structure.
- Optional: run Spec Kit on one small feature idea in one of your own repos,
  and compare the generated spec with what you would have written by hand.

---

Based on the [GitHub Spec Kit repository](https://github.com/github/spec-kit)
(v1.1.2, checked 2026-10-10) and GitHub's blog post
[Spec-driven development with AI: Get started with a new open source toolkit](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/)
(September 2025).
