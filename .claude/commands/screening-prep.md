# screening-prep

## Purpose
Prepare the seeker for a recruiter or hiring manager screen for a specific company. Produces a spoken "tell me about yourself" summary, likely questions with brief responses, and questions to ask — then saves everything to the company's output directory.

## Input
The user provides a company name (e.g., `/screening-prep Kuat Design Systems`). The company name is used to look up the JD, tailored resume, and tailored letter from the database and filesystem.

## Workflow

1. Look up the company in the `jds` table by matching `company` (case-insensitive, partial match OK). Retrieve `file_path`, `output_dir`, and `jd_id`.
2. Find the matching application in the `applications` table via `jd_id`. Update `applications.stage` to `'screen'` if it's currently `'application'`; leave it unchanged if already at `screen` or later. Run the UPDATE via Bash (use `python3 src/best_foot_forward/utils/db_query.py`).
3. If the user's request (or recent conversation) includes a specific date/time and recruiter/interviewer name for the screen, insert a row into `contacts` so it surfaces in the `upcoming` report — this is the *only* place that report reads from, so skipping this step means the screen won't show up anywhere:
   ```sql
   INSERT INTO contacts (jd_id, name, title, role, interview_date, interview_time, interview_stage, notes)
   VALUES (<jd_id>, '<recruiter name>', '<title if known>', 'recruiter', '<YYYY-MM-DD>', '<time with timezone>', 'screen', '<meeting link/ID/platform notes>')
   ```
   If no date/time was given yet, skip this step — don't guess a date.
4. Read the JD file from `file_path`. If it's an `.odt` file, convert to text first:
   `libreoffice --headless --convert-to txt --outdir /tmp <file_path>`
   then read the `/tmp/<filename>.txt` output.
5. Find and read the tailored resume (.txt file) from the JD's asset directory — search `{output_dir}/*.txt` for files named like `{Company} Resume*.txt`. If found, read it; if not, note that the tailored version doesn't exist yet.
6. Find and read the tailored letter (.txt file) from the JD's asset directory — search `{output_dir}/*.txt` for files named like `{Company} Cover Letter*.txt`. If found, read it; if not, note that the tailored version doesn't exist yet.
7. Read `memory/user_profile.md`, `memory/project_jobsearch.md`, `memory/feedback_style.md`, and `memory/voice_guide.md` for full career context and voice guidance. The voice guide has patterns extracted directly from the seeker's writing — use it when drafting the tell-me-about-yourself and all prose responses.
8. Produce the prep document with three sections:

   **Section 1 — Tell Me About Yourself**
   A 2-minute spoken narrative (~250–300 words, first person, conversational). Structure:
   - Current situation (your most recent employer, what you're looking for)
   - Most relevant experience thread for this role (lead with the strongest match)
   - Earlier career context that connects (prior employers, etc. as relevant)
   - Why this company / this role specifically

   **Section 2 — Likely Questions + Brief Responses** (up to 5)
   Tailor to the specific role and what a recruiter at this company would focus on. For recruiter screens, weight toward: why leaving, why this company, compensation expectations, team leadership experience, regulated/domain experience. For hiring manager screens, weight toward: technical depth, architecture decisions, team-building stories, specific JD callouts. Keep responses concise — these are prep notes, not scripts.

   **Section 3 — Questions to Ask** (3 questions)
   Genuine, specific questions about the role, team, or company. Avoid generic questions. Draw from the JD to ask about things that actually matter — current state of the team, what success looks like, specific initiatives mentioned.

9. Write `data/session/prep_data.py` with this structure:
   ```python
   COMPANY = "Temporal"
   ROLE = "Senior Engineering Manager"
   OUTPUT_DIR = "/path/to/applications/Temporal/Senior_Engineering_Manager"  # dirname(file_path) from jds table
   RECRUITER = "Peter Jakola"   # empty string if unknown
   SCREEN_DATE = "2026-05-20"

   PREP = {
       'tell_me_about_yourself': """...""",
       'questions': [
           {'question': 'WHY DID YOU LEAVE YOUR LAST ROLE?', 'response': """..."""},
       ],
       'questions_to_ask': [
           "What does the team structure look like today...",
       ],
   }
   ```
   Use triple-quoted strings for all multi-sentence text to avoid escaping issues.
10. Run `python3 src/best_foot_forward/utils/generate_prep.py` via Bash. It saves to `{output_dir}/{Company}ScreenPrep.docx`.
11. Register the saved file in `file_registry` so it's picked up by the graph:
    ```
    PYTHONPATH=src python3 -c "
    from best_foot_forward.db import register_file
    register_file('{output_dir}/{Company}ScreenPrep.docx', 'screen_prep',
                   'Screening prep — {Company} {Role}', jd_id=<jd_id>, application_id=<application_id>)
    "
    ```
    Use the `jd_id` and `application_id` found in step 2.
12. Scan and execute any post-prep hooks (see "Post-prep hooks" in CLAUDE.md) — this refreshes the BFF graph's Prep page and the Home dashboard.
13. Report the save path and any key context worth flagging (e.g., known gap to watch for, stage already reached, compensation range from JD, and whether the screen was added to `contacts` for the `upcoming` report).

## Notes
- If multiple JD records match the company name, list them and ask the user to pick one.
- If no tailored resume or letter is found, note that and work from the JD and career context alone.
- If the JD file is missing or unreadable, ask the user to paste the JD text.
- The "tell me about yourself" should be the seeker's voice — warm, direct, confident. Not a resume recitation. Reference `memory/feedback_style.md` for voice guidance.
- Do not ask the user to confirm before writing the file — just write it and report the path.
