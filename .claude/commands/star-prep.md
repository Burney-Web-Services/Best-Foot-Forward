# star-prep

## Purpose
Generate a STAR-format interview prep document for a specific company and role. Produces flash-card style S/T/A/R stories organized by likely interview questions, cross-indexed to the company's stated values or operating principles, and exports a formatted .docx to the company's output directory.

## Input
The user provides a company name (e.g., `/star-prep Kuat Design Systems`). Optionally: interviewer name, interview date, and a path or pasted text for the company's values/operating principles document.

## Workflow

1. Look up the company in the `jds` table by matching `company` (case-insensitive, partial match OK). Retrieve `file_path`, `output_dir` (or derive from `dirname(file_path)`), and `jd_id`. If multiple JD records match, list them and ask the user to pick.
2. Read the JD file from `file_path`. If it's an `.odt` file, convert first:
   `libreoffice --headless --convert-to txt --outdir /tmp <file_path>`
3. Find and read the tailored resume (.txt file) from the JD's asset directory — search `{output_dir}/*.txt` for files named like `{Company} Resume*.txt`. If found, read it; if not, work from JD and career context alone.
4. Read `data/_bullets.json` for the full bullet inventory.
5. Read `memory/user_profile.md` and `memory/project_jobsearch.md` for career context.
6. If the user hasn't provided a values/OPs document, check the company's output directory for any attached PDF or document (e.g., `*OPs.pdf`, `*Values.pdf`, `*Principles*`). If found, read it. If not found, ask the user whether to proceed without one or provide it.
7. Check if a previous screen prep or interview prep exists in the output directory — if so, read it to understand what was already probed.
8. Identify 8–10 stories from the seeker's background that map to the JD's stated requirements. Prioritize:
   - Architecture/system design decisions
   - Leading through adversity or setbacks
   - Building and developing a high-performing team
   - Cross-functional collaboration (Product, QA, ops stakeholders)
   - Operational excellence / observability
   - AI integration or tooling adoption
   - Scale / performance engineering
   - Scope negotiation under pressure
   - Non-STAR items as needed: "Why did you leave?", known gaps (acknowledge + bridge)
9. For each story, write terse STAR flash-card bullets — a few words or phrases per point, not full sentences. The goal is memory-jogging, not scripting.
10. Cross-index each story to the company's values/OPs: note which principle(s) each story demonstrates, using the full principle name (not an abbreviation).
11. Write `data/star_data.py` with this structure:
    ```python
    COMPANY = "Temporal"
    ROLE = "Senior Engineering Manager"
    OUTPUT_DIR = "/path/to/applications/Temporal/Senior_Engineering_Manager"  # dirname(file_path) from jds table
    INTERVIEWER = "Jane Smith"   # empty string if unknown
    DATE = "2026-05-29"

    OPS_KEY = [
        ("CF", "Customers First"),
        ("DR", "Deliver Results"),
        # ... one tuple per principle
    ]

    STARS = [
        {
            "title": "STORY 1: MONOLITH EXTRACTION / ARCHITECTURAL DECISION",
            "triggers": ["Complex architectural decision", "THINK BIG / KS example"],
            "S": ["auth/rostering baked into core monolith", "6-team deploy coordination required"],
            "T": ["decompose to own quality + delivery independently"],
            "A": ["architected SQS event-driven extraction", "shifted QA left into CI"],
            "R": ["independent sprint-cadence releases", "test coverage 30% → 65%"],
            "ops": "TB (bold architectural vision) | KS (eliminated deployment complexity)",
            # optional: "note": "Direct answer — not a STAR story"
            # optional: "note2": "Callout text in amber (e.g. pharmacy angle)"
        },
    ]

    OPS_CROSSREF = [
        ("Customers First (CF)", "Stories 4, 5, 8"),
        # ... one tuple per principle
    ]
    ```
    - T and A may be empty lists `[]` for non-STAR items (Why did you leave, gap bridges).
    - The `ops` string uses abbreviations from `OPS_KEY` — the generator expands them to full names automatically.
    - Use `note` for a label shown in amber above the STAR blocks (e.g., "Direct answer — not a STAR story").
    - Use any additional lowercase string key (e.g., `note2`) for amber callout text rendered after the R block (e.g., pharmacy angle suggestions).

12. Run `python3 src/best_foot_forward/utils/generate_star_prep.py` via Bash. It saves to `{output_dir}/{Company}STARPrep.docx`.
13. Register the saved file in `file_registry` so it's picked up by the graph:
    ```
    PYTHONPATH=src python3 -c "
    from best_foot_forward.db import register_file
    register_file('{output_dir}/{Company}STARPrep.docx', 'star_prep',
                   'STAR prep — {Company} {Role}', jd_id=<jd_id>)
    "
    ```
    Use the `jd_id` found in step 1.
14. Scan and execute any post-prep hooks (see "Post-prep hooks" in CLAUDE.md) — this refreshes the BFF graph's Prep page and the Home dashboard.
15. Report the save path and flag any stories that feel thin or any JD requirements that don't have a good story mapped to them.

## Document layout (produced by generator)
- **Page 1**: Title block (company, role, interviewer, date) → OPs key table → Cross-reference table
- **Page 2+**: One story per page (page break before each), with:
  - Story title as teal section header
  - Q triggers in italic
  - Amber NOTE line if present
  - S / T / A / R flash-card blocks with bold hanging labels
  - Amber callout line if present (e.g. `note2`)
  - OPs footer line in teal italic with full principle names

## Notes
- STAR bullets should be terse phrase fragments — 3–8 words each. The goal is a memory jog during final prep review, not a script.
- For "Why did you leave?" and gap acknowledgment stories: set `T: []` and `A: []` as needed; mark with `"note": "Direct answer — not a STAR story"`.
- If no company values/OPs document exists, omit the cross-indexing and leave `OPS_KEY`, `OPS_CROSSREF`, and `ops` fields empty. The generator handles empty gracefully.
- OUTPUT_DIR is always `dirname(file_path)` from the `jds` table — never hardcoded. Pre-existing companies stay in their current directory, wherever `file_path` already points.
- Do not ask the user to confirm before writing — write and report.
