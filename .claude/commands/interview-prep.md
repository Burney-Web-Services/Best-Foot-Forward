# interview-prep

## Purpose
Prepare the seeker for a hiring manager or technical interview for a specific company. Produces a spoken "tell me about yourself" value proposition, 5–10 anticipated interview questions with concise bullet-referenced responses, and 2–3 genuine questions to ask the interviewer — then saves everything as a formatted .docx to the company's output directory.

## Input
The user provides a company name (e.g., `/interview-prep Kuat Design Systems`) and optionally: interviewer name, interviewer title/role, and any context the company provided about the interview format or focus areas. If not provided upfront, ask for this context before generating.

## Workflow

1. Look up the company in the `jds` table by matching `company` (case-insensitive, partial match OK). Retrieve `file_path`, `output_dir` (or derive from `file_path`), and `jd_id`. If multiple JD records match, list them and ask the user to pick.
2. Find the matching application in the `applications` table via `jd_id`. Note the `stage` — update it to `interview_1` if it's currently `application` or `screen`, or `interview_2` if already `interview_1`, etc. Run the UPDATE via Bash. Also read the `notes` field: if non-empty, it contains debrief notes from prior rounds (questions asked, how they landed, gaps flagged). Use this to inform Section 2 and to avoid re-preparing for things that already went well.
3. Read the JD file from `file_path`. If it's an `.odt` file, convert to text first:
   `libreoffice --headless --convert-to txt --outdir /tmp <file_path>`
   then read the `/tmp/<filename>.txt` output.
4. Find and read the tailored resume (.txt file) from the JD's asset directory — search `{output_dir}/*.txt` for files named like `{Company} Resume*.txt` or similar. If found, read it; if not, note that the tailored version doesn't exist yet.
5. Find and read the tailored letter (.txt file) from the JD's asset directory — search `{output_dir}/*.txt` for files named like `{Company} Cover Letter*.txt` or similar. If found, read it; if not, note that the tailored version doesn't exist yet.
6. Read `data/_bullets.json` — this is the current bullet inventory. Note any bullets that appear stronger or more complete than what's in the tailored resume, and draw on them for Q&A responses.
7. Read `memory/user_profile.md`, `memory/project_jobsearch.md`, `memory/feedback_style.md`, and `memory/voice_guide.md` for career context and voice guidance. The voice guide has patterns extracted directly from the seeker's writing — use it when drafting the tell-me-about-yourself and all prose responses.
8. If the user hasn't already provided the following, ask before generating:
   - Interviewer name and title (if known)
   - What the company told you about this interview's focus or format
   - Anything you learned during the recruiter screen that's relevant (e.g., a gap they probed, a specific project they asked about)
9. Produce the prep document with three sections:

   **Section 1 — Personal Value Proposition / Tell Me About Yourself**
   A 2–3 minute spoken narrative (~300–350 words, first person, conversational). Structure:
   - Current situation (your most recent employer, what you're looking for and why)
   - Most relevant experience thread for this role — lead with the strongest match, name specific accomplishments
   - Earlier career context that connects (prior employers, education thread, as relevant)
   - Why this company and this role specifically — be concrete, not generic
   This should feel like the seeker talking, not a resume recitation. Reference `memory/feedback_style.md` for voice.

   **Section 2 — Anticipated Questions + Concise Responses** (5–10 questions)
   Weight toward the JD's specific requirements and the focus areas the company described. For each question:
   - **Question**: written in all-caps, as the interviewer would ask it
   - **Response**: 3–6 sentences. Tie each response to a specific bullet or accomplishment from the tailored resume or `_bullets.json`. Reference the employer and the outcome. Not a script — prep notes.
   Cover: why leaving the most recent role, technical depth (architecture decisions, distributed systems, scale), team building and management philosophy, cross-functional collaboration, AI/tooling experience, and any gaps or probes that came up in earlier screens.

   **Section 3 — Questions to Ask** (2–3 questions)
   Genuine, specific questions. Always include a version of: "What do you love most about working at [Company]?" — this should be the last question. The other 1–2 should draw from the JD and the interview context: team structure, what success looks like, current state of a specific initiative mentioned in the JD. Avoid generic questions.

10. Write `data/session/prep_data.py` with this structure:
    ```python
    COMPANY = "Temporal"
    ROLE = "Senior Engineering Manager"
    OUTPUT_DIR = "/path/to/applications/Temporal/Senior_Engineering_Manager"  # dirname(file_path) from jds table
    RECRUITER = "Jane Smith"   # interviewer name — empty string if unknown
    SCREEN_DATE = "2026-05-29"

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
    Use `RECRUITER` to hold the interviewer name — `generate_interview_prep.py` reads this field.

11. Run `python3 src/best_foot_forward/utils/generate_interview_prep.py` via Bash. It saves to `{output_dir}/{Company}InterviewPrep.docx`.
12. Register the saved file in `file_registry` so it's picked up by the graph:
    ```
    PYTHONPATH=src python3 -c "
    from best_foot_forward.db import register_file
    register_file('{output_dir}/{Company}InterviewPrep.docx', 'interview_prep',
                   'Interview prep — {Company} {Role}', jd_id=<jd_id>, application_id=<application_id>)
    "
    ```
    Use the `jd_id` and `application_id` found in step 2.
13. Scan and execute any post-prep hooks (see "Post-prep hooks" in CLAUDE.md) — this refreshes the BFF graph's Prep page and the Home dashboard.
14. Report the save path, stage update made, and any key gaps or talking points worth flagging.

## Notes
- Compare what was on the tailored resume against the current `_bullets.json` — if the bullet inventory has been strengthened since the resume was sent, note it and draw on the stronger framing in Q&A responses, but don't contradict what's on the resume.
- If the recruiter screen prep exists (e.g., `{Company}ScreenPrep.txt` or `.docx`), read it — what was probed there will likely come up again in the hiring manager screen.
- If no tailored resume or letter exists, note that and work from JD and career context alone.
- Do not ask the user to confirm before writing the files — write and report.
- The "tell me about yourself" should be the seeker's voice — warm, direct, confident. Not a list of credentials.
