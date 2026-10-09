# Spec Quality Checklist

Run through this before you commit a spec. If any item is unchecked, the spec
is not yet executable.

## Structure

- [ ] The spec fits on one page (two at the absolute most).
- [ ] All six required sections are present: context, scope, acceptance
      criteria, constraints, non-goals, definition of done.
- [ ] It links to the PRD and any existing design notes instead of restating
      them.

## Acceptance criteria

- [ ] Each AC is testable. A reader can picture the test without asking.
- [ ] Each AC describes **observable behavior** (return values, raised
      errors, log lines, files), not internal implementation.
- [ ] No AC contains the word "should" without a follow-on condition.
- [ ] At least one AC covers the **failure path**: what happens when something
      goes wrong (bad input, bad data, a metric that is `nan`).

## Constraints

- [ ] Constraints that are not obvious from the PRD are stated explicitly.
- [ ] Numeric constraints are quantified (numbers and units, not adjectives).
- [ ] Defaults are named, not assumed: seeds, thresholds, margins, limits,
      and what happens when the caller passes nothing.

## Non-goals

- [ ] At least two non-goals are listed. (If you cannot think of any, your
      scope is unclear.)
- [ ] The non-goals include anything a reasonable reader might assume is in.

## Definition of done

- [ ] It lists every gate: tests, lint, format, type check, docs,
      observability.
- [ ] Each gate is one that CI or a human reviewer can check mechanically.

## The "agent test"

Re-read the spec as if you were the agent.

- [ ] Could you build this without asking a single clarifying question?
- [ ] If you generated something wrong, would the spec tell you it was wrong?

If either answer is no, the spec has a gap.
