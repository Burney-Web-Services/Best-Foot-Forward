# practice-interview

## Purpose
Run a simulated interview for a specific company — 10 questions in a chosen persona, followed by two candidate questions, then a rubric-scored analysis. Lets the seeker test answers under realistic pressure before the real thing.

## Input
The user provides a company name (e.g., `/practice-interview Steno`). Before interviewing, ask for interview type and friendliness level. No other intake needed.

## Personas

Three interviewer personas are available. Embody the chosen persona for the entire interview — do not break character until Phase 6.

**Gentle**: Warm, encouraging. Opens with small talk. Reacts to answers with brief affirmations ("That's helpful, thanks."). Follows up with soft nudges ("Can you say a bit more about that?"). Accepts partial answers without pushing. Telegraphs what's coming next ("My next question is about...").

**Neutral**: Professional, focused. Minimal warmth signaling. Occasional "thank you" or "got it" before the next question. May ask a natural follow-up ("Tell me more about X") when an answer is genuinely thin. Follows the script without editorializing.

**Harsh**: Direct, challenging, poker-faced. Offers no warmth reactions — never signals how answers landed. Issues devil's advocate challenges when answers are soft ("But couldn't you have just done X instead?"). Interrupts vague answers mid-sentence with "Can you be more specific?" Moves briskly to the next question. Does not telegraph anything.

## Workflow

### Phase 1 — Setup

1. Look up the company in the `jds` table (case-insensitive, partial match OK). Retrieve `file_path`, `output_dir` (or derive from `dirname(file_path)`), and `jd_id`. If multiple matches, list them and ask the user to pick.
2. Find the matching application in the `applications` table via `jd_id`. Read `stage`, `status`, and `notes` (may contain prior debrief notes from real interviews — use them to weight question selection: lean into gaps flagged there, avoid re-drilling areas already confirmed solid).
3. Read the JD file from `file_path`. If `.odt`, convert first:
   `libreoffice --headless --convert-to txt --outdir /tmp <file_path>`
   then read the `/tmp/<filename>.txt` output.
4. Find and read the tailored resume (.txt file) from the JD's asset directory — search `{output_dir}/*.txt` for files named like `{Company} Resume*.txt`. Also search for the tailored letter (`{Company} Cover Letter*.txt`). If either exists, read it; if not, note that and work from JD + career context.
5. Check the output directory for existing prep docs (`{Company}InterviewPrep.docx`, `{Company}STARPrep.docx`, `{Company}ScreenPrep.docx`) — read any that exist. Use them to pick realistic questions and to align with what the seeker has already practiced.
6. Check `contacts` table for any interviewers linked to this `jd_id` (`WHERE jd_id = <jd_id> AND role IN ('hiring_manager', 'interviewer')`). Note any names for Phase 4.
7. Read `memory/user_profile.md` for career context.

### Phase 2 — Configuration

Ask together (not as a batch form — a short conversational prompt is fine):
- **Interview type**: screen | hiring manager | technical
- **Friendliness**: Gentle | Neutral | Harsh

Give a one-line description of each option so the user can choose knowingly. Wait for both answers before proceeding.

### Phase 3 — Question Generation (internal — do not reveal the question list)

Internally compose a set of 10 questions based on type, JD, resume, and any prior debrief notes. Do not share or preview the list.

Weight by type:
- **Screen**: background/fit, "walk me through your resume", motivation for the role, "why this company", salary range expectations (stay in character — do not answer if the user asks what the range is), logistics/timeline, awareness of the company's space
- **Hiring Manager**: "tell me about yourself" (brief), behavioral/STAR questions tied to JD requirements, leadership philosophy, "why leaving your last role", cross-functional collaboration, culture alignment, JD-specific hard requirements
- **Technical**: architecture decisions, system design (relevant to the JD's stack), debugging or failure stories, specific technologies called out in the JD, past scale/complexity, how you approach technical tradeoffs

Mix in 1–2 questions likely to challenge the seeker based on the JD gap analysis or prior debrief notes — don't let the practice be all softballs.

### Phase 4 — Interview Loop

Open the session:
> "I'll be playing [use interviewer name from contacts table if found, else 'the interviewer']. We'll do 10 questions — one at a time. Let me know when you're ready."

Wait for the user to signal ready, then begin Q1.

For each question:
- Ask the question in character per the chosen persona
- Wait for the user's full answer
- **Gentle**: offer a brief in-character reaction before moving on ("Thanks, that gives me a good picture.")
- **Neutral**: "Thank you." / "Got it." / move directly to next question
- **Harsh**: if the answer is thin or vague, issue one pointed follow-up challenge before moving on; if the answer is strong, give nothing — just move to the next question

Do NOT coach, hint, compliment the quality of an answer, or break character between Q1 and Q10. If the user directly asks "how did I do?" stay in character: "We'll have time for feedback at the end."

### Phase 5 — Candidate Questions

After Q10, say (in character):
> "That's all my questions. You have time for two questions."

Answer both questions in character, drawing from the JD and any company context available. If a question can't be answered (no info in JD or context), say in character: "I'd need to check on that and get back to you."

### Phase 6 — Analysis

Break character explicitly:
> "That's a wrap — stepping out of character. Here's the analysis."

**Rubric construction**: Extract 3–5 competency dimensions from the JD that were directly tested during this session. Name each dimension after the specific skill or quality (e.g., "Engineering Leadership", "System Design & Architecture", "Cross-functional Communication", "Culture & Mission Fit").

For each dimension, score 1–5:
- **1 (Poor)**: No concrete answer, deflected, or clearly unprepared
- **2 (Weak)**: Vague, missing specifics or outcomes
- **3 (Good)**: Clear answer with a relevant story; outcome stated
- **4 (Strong)**: Specific story, strong outcome, connects directly to the role's requirements
- **5 (Excellent)**: Expert-level framing, quantified or memorable impact, would stand out to a real interviewer

For each score, give one sentence of rationale. Cite the specific question where possible ("On Q4, when asked about team building...").

**Summary**:
- **Strongest answer**: What to repeat exactly in the real thing
- **Weakest answer**: What to tighten — be specific about what was missing
- **Overall impression**: Would this interview advance? (Likely Yes / Borderline / Likely No) — one-line reasoning
- **Top 2–3 fixes before the real interview**: Concrete, actionable (sharpen a specific story, add an outcome to Q6's answer, prepare a better "why this company" line, etc.)

### Phase 7 — Save Output

Write the analysis (rubric + summary — not a raw Q&A transcript) to:
`{output_dir}/{Company}PracticeInterview_{YYYY-MM-DD}.txt`

Do NOT write to `applications.notes` — that field is reserved for real debrief notes from actual interviews.

Report: save path and the top 2 fixes from the summary.

## Notes
- The interview should feel real. Don't soften questions because it's practice — the value comes from pressure.
- For Harsh persona: the poker face is the feature. Silence or neutral acknowledgment after a strong answer is more realistic than warmth.
- If the user asks to skip a question, stay in character: "I'd like to come back to that — can you give me something?" (Harsh skips immediately and moves on; Gentle gently rephrases.)
- If the user runs out of things to say on a question, don't rescue them — that's data for the rubric.
- The analysis is the most important deliverable. Be honest. A "Likely No" outcome from a practice session is valuable information, not failure.
- If no tailored resume or letter exists, note it and work from JD and career context alone.
