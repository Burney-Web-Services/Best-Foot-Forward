# resume-tailor

## Purpose
Tailor a resume and cover letter to a specific job description through a guided conversation, then export formatted .docx files.

## Inputs
- job_description (string): Full job description text, pasted into the chat — or a path on disk to the job description.
- source_resume (string): Selected from saved resume files in the project folder. Do not ask the user to paste a resume.
- source_letter (string): Selected from saved letter files in the project folder. Do not ask the user to paste a letter.
- company (string): Target company name.
- role (string): Target job title.

## Workflow
0. **Precondition — the job must already have a `jds` row.** Look it up by URL, then `file_path`, then company + role (normalizing the company with `canonical_company()` from `best_foot_forward.utils.company_normalize`). If there is no row, **stop and route per `CLAUDE.md` → Natural language routing**: ask whether to skip evaluation, and either create the row (write the JD file, run `scan_jds.py`) or run evaluate-job first. Tailoring a job with no `jds` row produces an application with `jd_id` NULL, orphaned from every report that joins through `jds`.

   **Path handshake.** When evaluate-job has already inserted a stub for a pasted/URL JD, its **absolute** `file_path` must be exactly the path this workflow later writes the JD file to:
   `data/BestFootForward/assets/{Company}/{Role_Slug}/{Company}_{Role_Slug}JobDesc.md`.
   Compute `{Role_Slug}` with the slugify command in `CLAUDE.md` → JD file conventions rather than deriving it by hand. A mismatch creates a second `jds` row and orphans the scored one — this recurred three times (Teaching Strategies 2026-07-01, Beacon Biosignals 2026-07-02, Pfizer 2026-07-14).
1. Read `memory/user_profile.md`, `memory/project_jobsearch.md`, `memory/feedback_style.md`, and `memory/voice_guide.md` for career context, process rules, and voice guidance. Do this before generating any prose.
2. Once the JD's company/role are known, use `python3 src/best_foot_forward/utils/suggest_tailoring_source.py` (or call `suggest_tailoring_source(company, role)` if in a Python context) to identify a smart default suggestion. This utility returns:
   - Same company, any prior role (highest-score) — if found
   - Else, highest-score application with fuzzy domain/role overlap
   - Else, None
   
   If a suggestion is found, present it first as a **Recommended** option with the track label and key angle from its tailoring_notes (e.g., "Recommended: Previous: Chandrila Systems — Senior Engineering Manager (score 82, manager track, platform domain — reused framing likely fits)"). 
   
   Also list all previously tailored applications from the asset directories (e.g., `data/BestFootForward/assets/Chandrila_Systems/Senior_Engineering_Manager/*.txt` — organized by company/role) so the user can override the recommendation.

   Ask for the job description (pasted text or URL). If a URL is provided, fetch it with WebFetch and extract the job description text. Note: LinkedIn URLs often block scraping — if a fetch fails, ask the user to paste the text instead.
   
   - If the user picks a prior application, resolve its application DB id for later use:
     ```sql
     SELECT a.id FROM applications a JOIN jds j ON a.jd_id = j.id
     WHERE j.company = ? AND j.role = ? ORDER BY a.id DESC LIMIT 1
     ```
     Hold this as `source_application_id` (integer). If the suggestion is used and it includes source track/angle, record that for step 9's tailoring_notes.
3. Analyze the fit between the resume and the job description. Identify gaps and areas to reframe.
4. Generate 3-5 targeted clarifying questions based on the specific gaps identified — not a generic checklist.
5. Collect answers. Also ask: "Anything else you'd like to add or emphasize?"
6. Produce a tailored resume draft using all gathered context. Rules:
   - Do not fabricate experience. Only use what is in the resume and the candidate's answers.
   - Reframe existing experience to highlight skills relevant to this role.
   - Use language from the job description where it accurately reflects the candidate's experience.
   - Keep bullet points concise and impact-focused.
   - Preserve the candidate's voice.
7. Show the draft and ask if the user wants any changes. Iterate until satisfied.
8. Produce a tailored letter draft using all gathered context. Rules:
   - Do not fabricate experience. Only use what is in the letter, the resume, and the candidate's answers.
   - Reframe existing experience to highlight skills relevant to this role.
   - Use language from the job description where it accurately reflects the candidate's experience.
   - Preserve the candidate's voice.
9. Show the draft and ask if the user wants any changes. Iterate until satisfied.
   After both drafts are approved, synthesize `tailoring_notes` — a short structured block capturing the session decisions:
   ```
   Track: manager
   Source: Chandrila Systems SEM (app id=155)  # or just the track label if no prior source
   Key angle: QE transformation as headline; Harmonization platform as centerpiece
   Gaps acknowledged: Go (honest, letter para 3)
   Salary: $175K–$225K remote
   ```
   Keep it to 4–6 lines. This goes into the DB and becomes the basis for future "start from" recommendations.
10. Write the finalized resume content to `data/session/resume_data.py`. Must include `COMPANY`, `ROLE`, `JD_FILE_PATH` (the path to the source JD file), `RESUME`, and the two new tracking fields:
    ```python
    SOURCE_APPLICATION_ID = 155   # integer app id, or None if starting from scratch
    TAILORING_NOTES = """
    Track: manager
    Source: Chandrila Systems SEM (app id=155)
    Key angle: ...
    """
    ```
11. Write the finalized letter content to `data/session/letter_data.py`. Must include `COMPANY`, `ROLE`, `JD_FILE_PATH`, and `LETTER`.
    - `LETTER['closing']` should be **the valediction only** (`"Sincerely,"`). Do not append the signer's name: `generate_letter.py` adds it from the contact record, so it stays correct for any user without being retyped each session. Including the name anyway is harmless (`compose_signoff` in `docx_helpers.py` detects it and will not duplicate it), but the bare form is the convention.
12. Ask: "Ready to generate the .docx?" and if the user confirms, run `python3 src/best_foot_forward/utils/generate_resume.py` and `python3 src/best_foot_forward/utils/generate_letter.py` directly using Bash. The generators automatically:
    - Write the .docx files to the same directory as the source JD
    - Also write plain-text .txt versions of both files to the same directory (for future reuse)
    - Register both in the file_registry
    - A PostToolUse hook runs `track_application.py` after `generate_resume.py` completes, so the `applications` row is recorded automatically — **but only on harnesses that define the hook.** Antigravity (`.agents/hooks.json`) and Codex (`.codex/hooks.json`) do; `.claude/settings.json` has no `hooks` block, so under Claude Code run `python3 src/best_foot_forward/utils/track_application.py` manually and confirm the row.
    - **Skills-frequency and salary registration is usually already done — check before scanning.** `save_lead_jd` owns extraction at evaluation time, so any job that came through evaluate-job, or through the CLAUDE.md "tailor a job with no `jds` row" route, already has its salary and `jd_required_skills` indexed. Only run a scan when the JD has no `jd_required_skills` rows — the fallback case is a JD file that was already sitting in the asset tree, which evaluate-job step 1 explicitly skips. Check, then scan only if the count is 0:
      ```
      python3 src/best_foot_forward/utils/db_query.py "SELECT COUNT(*) FROM jd_required_skills WHERE jd_id=<jd_id>"
      python3 src/best_foot_forward/utils/scan_jds.py data/BestFootForward/assets/{Company}/{Role_Slug} --rescan
      ```
      (`--rescan` is required, or a file that already has a `jds` row is skipped entirely. No harness runs `scan_jds.py` for you — this step is always manual when it is needed at all.)
13. Verify the JD role in the DB. If the row was created by `scan_jds.py`, the role came from the folder slug and has lost any punctuation (`Software Engineer II, Backend (Test Infra)` → `Software Engineer II Backend Test Infra`); restore the real title with `UPDATE jds SET role='<actual role>' WHERE file_path='<path>'`. If the row was created by evaluate-job, `track_application.py`, or an explicit `INSERT` (step 0), the role is already correct and no change is needed. Getting this right matters because step 14's `export_graph.py` computes Logseq page filenames fresh from the role text.
14. **Write the Logseq page(s)** for this application (the DB is now final): `python3 -m best_foot_forward.utils.export_graph --only '<Company>'`. This creates/refreshes the company's entity + `<Company>/<Role>/Application` (+ Prep/Notes) pages in the bff graph. Run this last so the role name and application row are already correct.

## Outputs
- Updated `data/session/resume_data.py` with the tailored resume content.
- Updated `data/session/letter_data.py` with the tailored letter content.
- `.docx` files saved to the same directory as the source JD file.

## Output format defaults
- Font: Calibri 11pt
- Margins: 0.75 inches
- Target length: 2 pages

## Notes
- `generate_resume.py` reads from `data/session/resume_data.py` and SQLite (contact, education) — handles all .docx formatting and also writes a plain-text .txt version to the same directory.
- `generate_letter.py` reads from `data/session/letter_data.py` and SQLite (contact) — handles all .docx formatting and also writes a plain-text .txt version to the same directory.
- Both generators automatically register the .txt and .docx files in file_registry, making them visible to future `resume-tailor` and `interview-prep` workflows.
- The Anthropic API is not used. Tailoring happens through conversation in Claude Code.
- After adding new bullets or skills during tailoring, insert them into SQLite as well as `data/_bullets.json` / `data/_skills.json`, then run `python3 src/best_foot_forward/utils/export_cache.py` to sync.
- **Out-of-metro roles**: when the role's city differs from your home city and you want both shown, add `LOCATION_OVERRIDE = "Target City, ST / Home City, ST"` to `resume_data.py`. Omit for all other locations.
- **New company directories**: create at `data/BestFootForward/assets/{Company}/{Role_Slug}/`. OUTPUT_DIR is always `dirname(file_path)` from the `jds` table, never hardcoded.
