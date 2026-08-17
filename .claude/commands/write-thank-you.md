# write-thank-you

Draft and save a thank you email for a recent interview.

## Workflow

1. **Look up company** (case-insensitive match in `jds` table)
   - If multiple matches: list them and ask the user to clarify
   - If no match: ask the user to provide the company name as it appears in the database

2. **Find application and contacts**
   - Query `applications` via `jd_id` to get application stage/status
   - Query `contacts` via `jd_id` to find the interviewer record
   - Extract: `name`, `title`, `interview_date`, `interview_time`
   - If no contacts record: ask the user for interviewer name and interview date

3. **Calculate relative timing** from today's date (e.g., "Monday", "earlier this week")
   - If `interview_date` is NULL: ask the user
   - Python code to compute day-of-week from ISO date:
     ```python
     from datetime import datetime
     interview = datetime.fromisoformat('2026-08-03').date()
     today = datetime.now().date()
     days_ago = (today - interview).days
     if days_ago == 1:
         timing = "yesterday"
     elif days_ago <= 7:
         timing = interview.strftime("%A")  # "Monday", etc.
     else:
         timing = "earlier this week"
     ```

4. **Read memory files** for tone and voice guidance
   - `memory/user_profile.md` — career context
   - `memory/voice_guide.md` — prose patterns, identity phrases, signature style
   - `memory/feedback_style.md` — email preferences
   - Key guidance: warm, direct, no corporate filler; reference something specific from the interview

5. **Collect context** (ask the user)
   - "What's one specific moment from the interview you want to reference?"
   - "What about this role/company excites you most?"
   - Optional: read the JD file if it exists to pull specific details

6. **Draft the email**
   - Structure:
     - Opening: "Hi [RecipientName],"
     - Paragraph 1: Thank them + reference the specific moment from conversation
     - Paragraph 2: Why you're interested (mission, team, specific problem mentioned)
     - Closing: "Looking forward to next steps" / "I'd love to talk more..." / similar warm close
     - Signature: single hyphen + the seeker's first name from `contact.name` (e.g. "-Alex") — see `memory/voice_guide.md` if it documents a different preferred signoff
   - Use the voice guide to match the seeker's tone (warm, no jargon, "I'd love to", team-centered framing — adjust to whatever `memory/voice_guide.md` actually says)
   - Keep it conversational, not a form letter

7. **Show the draft to the user**
   - Ask: "Does this capture it? Any edits before we save?"
   - Iterate if needed

8. **Approve and write session file**
   - Write `data/session/thankyou_data.py`:
     ```python
     COMPANY = "Kuat Design Systems"
     ROLE = "Senior Engineering Manager"
     JD_FILE_PATH = "/absolute/path/to/jd/file"
     RECIPIENT_NAME = "Danny Garcia-Huang"
     RECIPIENT_TITLE = "VP of Engineering"
     INTERVIEW_DATE = "2026-08-03"
     EMAIL_BODY = """[full email text here]"""
     ```

9. **Call generator**
   - Run: `python3 src/best_foot_forward/utils/generate_thankyou.py`
   - Verify output: file saved to `{output_dir}/{Company}_{Role}ThankYou.txt`
   - Confirm: "Thank you email saved."

10. **Optional: Regenerate graph** (Phase 3, if implemented)
    - Run: `python3 -m best_foot_forward.utils.export_graph --only '{COMPANY}'`
    - Refreshes the BFF graph with the #ThankYouNote page

## Database Queries

**Look up company:**
```bash
python3 src/best_foot_forward/utils/db_query.py "SELECT id, company, role, file_path, output_dir FROM jds WHERE company LIKE '%{search}%'"
```

**Find application and contacts:**
```bash
python3 src/best_foot_forward/utils/db_query.py "SELECT a.id, a.stage, a.status, c.name, c.title, c.interview_date, c.interview_time FROM applications a LEFT JOIN contacts c ON a.jd_id = c.jd_id WHERE a.jd_id = {jd_id}"
```

## Notes

- **Timing calculation:** ISO date format (YYYY-MM-DD). Use Python's `datetime` module to compute relative timing.
- **Edge cases:**
  - No contacts record: ask user for interviewer name and date
  - Multiple contacts for same jd_id: list them and ask which one
  - interview_date is NULL: ask the user
  - Company name ambiguous: list matches, ask for clarification
- **Warmth matters:** Reference something specific they said. Show genuine interest. Avoid generic thank-yous.
- **Idempotency:** Calling this workflow twice for the same company/role updates the existing thank you note (same file path, upsert in file_registry).

