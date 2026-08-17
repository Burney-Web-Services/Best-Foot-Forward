# BFF Commands — Reference

Every slash command below is a full workflow definition in `.claude/commands/<name>.md` — this page is the human-readable index: what each one is for, when to reach for it, and what it produces. For the exact step-by-step logic Claude follows, open the linked source file.

Natural-language triggers (phrases that fire a workflow without typing the `/command`) are listed where one exists — otherwise just say the company name or paste the input directly.

## Note on flexibility

These workflows are templates, not iron rails. You can:
- Run `/resume-tailor` once but ask for two parallel drafts with different framing angles before picking a direction
- Skip a step if you've already done the work (e.g., if you're prepping for a second-round interview with someone you've already met, skip the "who are they" research)
- Combine workflows (e.g., run `/interview-debrief` immediately after a call to capture what happened, then feed that into `/interview-prep` for the next round)
- Interrupt mid-workflow and restart with a different approach if something isn't landing

The system is yours to adapt. Tell Claude directly what you want to change or try differently, and the workflow adjusts.

---

## Core workflow

### [`/onboard`](../.claude/commands/onboard.md)
Builds your profile from whatever you bring — a current resume, an outdated one, or nothing at all — and ends with a populated bullet/skills library plus a base resume. Run once at the start; safe to re-run later to add more history. First-time users can also ask to explore a sample profile before committing their own data.

### [`/evaluate-job`](../.claude/commands/evaluate-job.md)
Scores a job description 0–100 across five dimensions (technical match, role/level, domain fit, experience depth, gap risk) against your actual bullet and skills library — so you can triage before investing time in a tailor. Accepts pasted text, a file path, or a URL.
*Triggers on: pasting a job description or JD file path.*

### [`/resume-tailor`](../.claude/commands/resume-tailor.md)
Tailors a resume and cover letter to a specific role through a short guided conversation — a handful of targeted questions about gaps, then a draft you review and iterate on — and exports formatted `.docx` files.
*Triggers on: "tailor", "tailor for [X]", "let's tailor".*

### [`/screening-prep`](../.claude/commands/screening-prep.md)
Preps you for a recruiter or early hiring-manager screen: a spoken "tell me about yourself," likely questions with brief responses, and questions to ask back — saved to the company's folder.
*Triggers on: "screen", "screen prep", "screening for [X]".*

### [`/interview-prep`](../.claude/commands/interview-prep.md)
The deeper version of screening-prep for a hiring-manager or technical round: a fuller value proposition, 5–10 anticipated questions with bullet-referenced responses, and genuine questions to ask the interviewer.
*Triggers on: "prep", "interview prep", "prep for [X]".*

### [`/star-prep`](../.claude/commands/star-prep.md)
Generates flash-card style STAR stories for a specific company, cross-indexed to that company's stated values or operating principles — built for quick review right before the interview, not for reading in full.

### [`/star-story`](../.claude/commands/star-story.md)
A conversational debrief that captures one work situation as a structured STAR story, tags it with themes, and links it to existing resume bullets. This is how the STAR corpus that feeds interview prep and future bullets actually gets built.
*Triggers on: "capture a story", "add a story", "record a situation", "star story".*

### [`/capture-voice`](../.claude/commands/capture-voice.md)
Derives a voice guide from 2–3 samples of your own writing so cover letters and interview answers sound like you, not a template. Optional and non-blocking — skip it and tone gets inferred from accumulated STAR stories instead.
*Triggers on: "capture my voice", "voice guide", "learn how I write", "sound like me".*

### [`/practice-interview`](../.claude/commands/practice-interview.md)
Runs a simulated interview — 10 questions in a chosen persona (gentle, neutral, or harsh) followed by two candidate questions — then breaks character for a rubric-scored analysis of what worked and what to fix before the real thing.
*Triggers on: "practice", "practice interview", "mock interview", "drill questions for [X]", "let's practice for [X]".*

### [`/interview-debrief`](../.claude/commands/interview-debrief.md)
Captures what actually happened after a real interview — questions asked, what landed, what didn't — and feeds it back into the application record so the next round of prep is sharper. This is the feedback loop the other prep commands draw on.

### [`/write-thank-you`](../.claude/commands/write-thank-you.md)
Drafts a thank-you email after an interview, pulling the interviewer's name, title, and the interview date from the `contacts` record so the note references what you actually discussed rather than generic gratitude. Works out relative timing on its own ("earlier this week"). Triggered by `/write-thank-you <Company>` or naturally ("thank you for X", "send thank you to X").

### [`/accept-offer`](../.claude/commands/accept-offer.md)
Records an accepted job offer — terms, start date, deadline — and concludes the application. Also closes out the rest of the pipeline in three questions regardless of size (withdraw from applications with real momentum, mark the rest not-pursued, decline open leads). Triggered by `/accept-offer <Company>` or naturally ("I accepted the offer from X"). An offer that's arrived but not yet decided is a lighter-weight natural-language trigger, not this command — see `CLAUDE.md`.

### [`/intake-artifacts`](../.claude/commands/intake-artifacts.md)
Bulk-adds bullets and skills from artifacts of ongoing work — git logs, PR descriptions, architecture docs, performance reviews — for enriching the library between onboarding and your next tailor. Distinct from `/onboard`, which builds from scratch.

### [`/web`](../.claude/commands/web.md)
Launches a local, read-only web UI for browsing your live BFF database and chatting with the embedded assistant — no manual setup, safe to run repeatedly.

---

## Secondary-machine sourcing

For a two-machine setup where a collaborator (e.g. a recruiter or sourcer) evaluates leads on their own machine and sends them back for review. See [README.md → "Secondary mode"](README.md#secondary-mode--sourcing-leads-with-a-collaborator) for the full setup.

### [`/secondary`](../.claude/commands/secondary.md)
Opens a sourcing session: pulls a grounding snapshot of the primary's bullet/skills library over MCP so scoring stays calibrated (and keeps working offline). Run once at the start of each sourcing session.

### [`/push-leads`](../.claude/commands/push-leads.md)
Drains any leads that were queued locally while offline up to the primary's database. Runs automatically as part of `/cleanup` on a secondary machine, or run it manually once back online.

---

## Session hygiene

### [`/cleanup`](../.claude/commands/cleanup.md)
End-of-session wrap-up: verifies application materials were saved, checks recent DB writes look right, refreshes derived exports, and updates project memory — so nothing from the conversation evaporates when context compacts.
*Triggers on: "cleanup", "wrap up", "session cleanup".*
