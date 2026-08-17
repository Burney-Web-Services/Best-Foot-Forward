# Security Policy

## Reporting a vulnerability

**Do not open a public issue.** Report privately, either way works:

- GitHub's [private vulnerability reporting](https://github.com/Burney-Web-Services/Best-Foot-Forward/security/advisories/new) on this repository, or
- email [pburney@gmail.com](mailto:pburney@gmail.com) with `SECURITY` in the subject line.

Expect an acknowledgement within a few days. This is a small project — there is no on-call
rotation — but a real vulnerability report gets looked at ahead of anything else.

If you've found something and aren't sure whether it counts, report it. A false alarm costs
a few minutes; the other mistake is worse.

## Supported versions

There is one supported version: current `main`. There are no backported fixes and no
long-term support branches.

## What this project's threat model actually is

Best Foot Forward is **local-first**. There is no hosted service, no account, no telemetry, and
no server holding anyone's data. That removes most of the usual categories — and concentrates
the risk somewhere unusual, so it's worth naming plainly.

**The database is the crown jewel.** `data/best_foot_forward.db` accumulates a complete
professional and job-search history: employers, compensation, contacts, the reasons someone
passed on a role, the reasons a company passed on them. That's more sensitive than a resume,
and it lives in a plain SQLite file with no encryption at rest. Disk-level encryption is the
user's responsibility and is a genuinely good idea here.

Things that **are** in scope and worth reporting:

- Anything that causes `data/`, `memory/`, or generated documents to be written outside their
  intended location, committed to git, or transmitted anywhere.
- A gap in `.gitignore` coverage that would let personal data or credentials become tracked.
- Command injection or path traversal through a job description, URL, company name, or filename —
  these are all attacker-influenced strings that reach the filesystem and the shell.
- SQL injection in any query path. Ad-hoc writes are supposed to go through `db_query.py`'s
  `--params-json` bound parameters; a place that doesn't is a bug.
- Anything in the optional MCP server (`/secondary`, `/push-leads`) that exposes the database
  beyond its intended reach. This is the one component that listens on a network.
- Anything in the optional local web UI (`/web`) that escapes its read-only intent.
- A dependency with a known advisory that we're pinned to.

Things that are **not** in scope:

- The AI agent producing wrong, unflattering, or badly-worded resume content. That's a quality
  bug — file it as a normal issue.
- Sensitive data appearing in your *own* agent's conversation history or your terminal
  scrollback. That's how coding agents work; treat those transcripts as sensitive.
- Prompt injection embedded in a job description you deliberately fed to the tool. It's a real
  risk and worth reporting if you find a *novel* consequence of it, but "a JD can influence what
  the agent says" is understood and unavoidable given what this does.

## For contributors

`data/`, `memory/`, and `.claude/settings.local.json` are gitignored. That is a load-bearing
line of defense, not a convenience — this repo's history had to be rewritten once with
`git filter-repo` because real PII and a live API token had been committed before those rules
existed. Before you commit, check what you're staging.

If you find you've committed a credential, rotate it first and clean history second. Rotation
is the fix; history rewriting is cleanup.
