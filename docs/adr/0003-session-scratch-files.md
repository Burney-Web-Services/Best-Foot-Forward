# ADR-0003: Session scratch files as generator inputs

**Status:** Accepted  
**Date:** 2026-05-15

## Context

`generate_resume.py` and `generate_letter.py` need to receive tailored content — the specific bullets, summary, skills, and letter paragraphs that Claude assembled during the session. Options for passing this content:

- CLI arguments
- Stdin / pipe
- Write to a table in SQLite and have the generator read it
- Write to a Python file that the generator imports

## Decision

Claude writes `data/resume_data.py` and `data/letter_data.py` during the tailoring session. These are Python files containing dict literals. The generators import them directly.

Both files are gitignored. Both are overwritten at the start of every new tailoring session. Neither is a source of truth for anything permanent — the canonical tailored content is saved to `data/resumes/tailored/` and `data/letters/tailored/` as plain text before generation.

`data/prep_data.py` follows the same pattern for interview and screening prep.

## Consequences

- **Easy to inspect**: A human (or Claude in a follow-up session) can read the scratch file and see exactly what was generated, in what structure, without querying a DB.
- **Easy to re-run**: Calling `generate_resume.py` again after fixing a typo in the scratch file regenerates the `.docx` without re-running the whole tailoring session.
- **Overwrite semantics**: Each session starts fresh. There's no history of what was in the scratch file last time. The `tailored/` plain text files serve as the human-readable record; the DB serves as the structured record.
- **Not source of truth**: Anything worth keeping permanently goes into SQLite (new bullets, new skills) and the `tailored/` directory. The scratch file is ephemeral by design.
