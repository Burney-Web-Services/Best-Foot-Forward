# Contributing to Best Foot Forward

Best Foot Forward is a template you fork and personalize — not a service you subscribe to. The code is the workflow; your career data is the content. This guide explains how to set up your own instance and adapt the project to your background.

---

## What "contributing" means here

There are two kinds of contributors:

1. **You're setting up your own instance** — fork the repo, replace the sample data with your career history, and run it. This is the primary use case.
2. **You're improving the shared tooling** — bug fixes, new utilities, improved skill workflows, or better documentation that benefits everyone. PRs welcome.

---

## Prerequisites

- [Claude Code](https://claude.ai/code) with a paid Claude plan (the agent workflows run inside Claude Code)
- Python 3.11+
- [uv](https://astral.sh/uv) for dependency management
- `ffmpeg` (only required for the audio transcription feature)

---

## Setting up your own instance

### 1. Fork and clone

```bash
git clone https://github.com/your-username/best-foot-forward.git
cd best-foot-forward
uv sync
```

For audio transcription support:
```bash
uv sync --group audio
```

### 2. Initialize the database

```bash
python3 src/best_foot_forward/utils/migrate.py
python3 src/best_foot_forward/utils/export_cache.py
```

`migrate.py` contains sample data for demonstration. Before running it, open the file and replace the `EMPLOYERS`, `CONTACT`, and `EDUCATION` blocks with your own career history. The format is straightforward Python dicts — employer names, dates, and locations.

### 3. Add your resume tracks

Create plain-text versions of your resume in `data/resumes/`:
- `data/resumes/general.txt` — a general-purpose version
- Additional tracks as needed (`engineer.txt`, `manager.txt`, etc.)

These are the source documents Claude uses when tailoring for a specific role.

### 4. Open in Claude Code and tailor your first role

```bash
claude
```

Paste in a job description and run `/resume-tailor`. Claude will ask a few targeted questions and produce a tailored resume and cover letter.

---

## The data model

Understanding the data model helps when you want to add bullets, adjust skills, or query your application history.

**Key tables:**

| Table | Purpose |
|-------|---------|
| `employers` | Career history — name, location, dates |
| `bullets` | Achievement statements with track/theme tags |
| `skills` | Skill groups with track/theme tags |
| `jds` | Job descriptions with fit scores |
| `applications` | Application tracking with stage/status |
| `stories` | STAR-format interview stories |
| `file_registry` | Every file BFF creates or discovers, linked to the jd/application that generated it |

**Tracks** — every bullet and skill group belongs to one or more tracks:
- `engineer` — individual contributor / technical
- `manager` — people management / team leadership
- `executive` — org-level / strategic
- `general` — applicable everywhere

**Themes** — finer-grained tags within a track. Examples: `infrastructure`, `ai-tooling`, `cross-functional`, `org-building`. Use the same vocabulary consistently — Claude uses themes to select the most relevant bullets for a given role.

---

## Adding new bullets and skills

When you tailor a resume and want to add a new bullet permanently:

```bash
# 1. Insert via the query tool
python3 src/best_foot_forward/utils/db_query.py

# 2. After any DB change, regenerate the JSON caches
python3 src/best_foot_forward/utils/export_cache.py
```

Or just tell Claude "add this bullet to the library" during a tailoring session and it will handle the INSERT and cache regeneration.

---

## Syncing the file registry (existing installs)

If you're upgrading from a version before file_registry was added, run:

```bash
python3 src/best_foot_forward/utils/sync_files.py --dry-run   # preview first
python3 src/best_foot_forward/utils/sync_files.py             # register all existing files
```

The table is created automatically on fresh installs (`/onboard` calls `init_db()`).
For existing installs, any script that calls `init_db()` will add the table safely.
Going forward, resumes, letters, JD files, and transcripts are registered automatically
as they're generated. Run `sync_files.py --check-orphans` periodically to surface drift.

---

## Running reports

```bash
python3 src/best_foot_forward/cli.py
```

Interactive menu: weekly activity, rejection patterns, skill frequency, salary data.

---

## Running tests

```bash
uv run pytest
```

Tests cover schema initialization, cache export structure, and pure utility functions. They use an in-memory SQLite database — no data directory needed.

The same suite runs in CI on every pull request, against Python 3.11, 3.12, and 3.13 — see [`.github/workflows/tests.yml`](.github/workflows/tests.yml). CI installs only the `dev` dependency group: `tests/conftest.py` stubs the heavy audio/ML imports, so the `audio` group isn't needed to run tests.

---

## Architecture notes

See [docs/README.md](docs/README.md) for the full architecture overview and [docs/adr/](docs/adr/) for the decision records behind key design choices.

The short version:
- **SQLite** is the source of truth. JSON files in `data/` are generated read caches — edit via SQL, not JSON.
- **Claude Code is the UI.** The Python scripts handle data transformation and document generation; Claude handles conversation, reasoning, and workflow.
- **Session scratch files** (`data/session/*.py`) are temporary. They're written by Claude during a session and read by the generator scripts. They're not source of truth for anything.
- **Everything in `data/` is gitignored.** Your resume, bullets, applications, and generated files never leave your machine.

---

## Pull requests

For improvements to the shared tooling:
- Keep changes focused — one thing per PR
- If you're adding a new skill workflow, follow the structure of the existing ones in `.claude/commands/`
- If you're adding a utility script, keep it under 200 lines and make it idempotent where possible
- Tests for pure functions are appreciated

Opening a PR fills in a checklist from [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md). The one item on it worth reading twice is the personal-data check: this project's normal working state involves real employers, salaries, and contacts sitting in gitignored directories, so it's unusually easy to paste something real into a test fixture or a doc example.

Open an issue first for anything that touches the schema or the core skill workflows.

---

## Code of conduct and security

Participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md). Vulnerabilities go through [SECURITY.md](SECURITY.md), privately — not a public issue.
