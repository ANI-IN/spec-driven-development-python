# experiment-runs-reference: the Spec Kit reference scaffold

This folder is the **untouched output** of:

```bash
uvx --from git+https://github.com/github/spec-kit.git@v1.1.2 \
  specify init experiment-runs-reference --integration claude --script py
```

generated on 2026-10-10 with Spec Kit v1.1.2.

It is committed so learners doing the [Spec Kit demo](../README.md) can
compare their own scaffold with a known-good one. **Do not run Spec Kit skills
(`/speckit-specify` and the rest) against this folder.** They would change it
and destroy its value as a reference.

## What's in here

| Path | Purpose |
|---|---|
| `.claude/skills/speckit-*/SKILL.md` | The ten Spec Kit skills registered with Claude Code |
| `.specify/memory/constitution.md` | The constitution template; `/speckit-constitution` fills it in |
| `.specify/templates/` | The spec, plan, tasks, checklist, and constitution templates the skills expand |
| `.specify/scripts/python/` | The Python helper scripts the skills call (chosen with `--script py`) |
| `.specify/scripts/bash/` | Shell equivalents that Spec Kit installs alongside them |
| `.specify/workflows/`, `.specify/integrations/` | Toolkit metadata; you never edit these by hand |
| `.specify/init-options.json` | The options this scaffold was created with |
| `.specify/.gitignore` | Spec Kit's own list of per-checkout files to keep out of git |

The files under `.claude/` and `.specify/` are Spec Kit's own. They are
generic and cover many languages, which is why some of them mention tools
this project does not use.

## When to regenerate this reference

Only when a new Spec Kit release changes the scaffold layout. To regenerate:

```bash
rm -rf demo/experiment-runs-reference
cd demo
uvx --from git+https://github.com/github/spec-kit.git@<new-tag> \
  specify init experiment-runs-reference --integration claude --script py \
  --ignore-agent-tools
```

`rm -rf` also deletes this file, so restore it with
`git checkout -- demo/experiment-runs-reference/README-REFERENCE.md`, update
the version line at the top, and update the [demo README](../README.md).
