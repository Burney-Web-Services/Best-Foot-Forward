## What this changes

<!-- One or two sentences. What was wrong or missing, and what does this do about it? -->

## Why

<!-- The reasoning. If this fixes a bug, what was the root cause? Link an issue if there is one. -->

## How to verify

<!-- The commands or steps a reviewer can run. "uv run pytest -q" is the baseline; say what
     else you did if the change touches a workflow, a generated file, or the database. -->

## Checklist

- [ ] `uv run pytest -q` passes
- [ ] New or changed logic has a test (see [CONTRIBUTING.md](../CONTRIBUTING.md))
- [ ] No personal data — this repo's `data/` and `memory/` are gitignored for a reason; check that
      nothing real (names, employers, salaries, contact details, file paths from your own machine)
      leaked into tracked files, docs, or test fixtures
- [ ] Docs updated if behavior changed (`README.md`, `docs/`, or the relevant command file)
- [ ] If this changes a documented decision, there's an ADR in `docs/adr/`
