# star-story

## Purpose
Conduct a conversational STAR debrief to capture a work situation as a structured story, then store it in the DB with theme tags and bullet links. Builds the STAR corpus that feeds interview prep, bullet provenance, and voice pattern analysis.

## Input
The user invokes `/star-story` optionally with a topic hint (e.g., `/star-story Kuat Drive Yards integration rewrite`). If no topic is given, ask. The user may also trigger this naturally by saying "let's capture a story", "add a story", or "record a situation".

## Workflow

### 1. Identify the situation
If the user provided a topic hint, confirm it and ask a quick opening question to start the conversation. Otherwise ask: "What situation do you want to capture? A few words is fine — we'll dig in together."

### 2. Identify the employer
Ask which job/company this was at if not obvious from the topic. Look up the employer in the `employers` table:
```sql
SELECT id, name FROM employers ORDER BY end_date DESC
```
Use the matched `employer_id` when writing to DB.

### 3. Conduct the STAR interview
Ask one component at a time. Don't rush — stay on each section until you have enough detail. The Action section deserves the most attention.

**Situation**
- "Set the scene. What was the context — what was the state of things before this started?"
- Follow-up on: timeframe, team/org structure, what was broken or missing, what was at stake

**Task**
- "What was your specific responsibility here? Was this handed to you or something you identified yourself?"
- Follow-up on: constraints, competing priorities, what success looked like, who else was involved

**Action** *(spend the most time here)*
- "Walk me through what you actually did — take me through the key decisions and steps."
- Follow-ups: "You mentioned X — how did you approach that specifically?", "What was the hardest part?", "What would have happened if you'd gone a different direction?", "Who pushed back and how did you handle it?"

**Result**
- "What changed because of what you did? Numbers, timelines, reactions from stakeholders?"
- Follow-up: "Was there anything unexpected?", "How do you know it worked?", "What would you do differently?"

### 4. Synthesize and show the draft
Present the structured story for review:
```
TITLE: [short label — 4-8 words]
EMPLOYER: [company name]
TIMEFRAME: [period, e.g. "2022 Q3" or "Kuat Drive Yards 2020-2021"]

S: [2-4 sentences setting context]
T: [1-2 sentences on responsibility/goal]
A: [3-6 sentences on specific actions and decisions — the richest section]
R: [2-3 sentences on outcomes, metrics, impact]
```
Ask: "Does this capture it accurately? Anything to add or change?" Iterate until approved.

### 5. Tag themes
Read `data/_bullets.json` and extract the existing theme vocabulary. Suggest 3-6 themes that fit this story. Show them and ask the user to confirm, add, or remove. Use existing theme names — only propose a new theme name if the situation clearly doesn't fit any existing ones.

### 6. Link to existing bullets
Scan `data/_bullets.json` for bullets that this story could be the source for — match by employer, role, and content overlap. Show the matches:
- "These existing bullets appear to come from this story — confirm links?"
If the story surfaces framings not yet in the bullet library, draft candidate bullets and ask: "This story supports a framing we don't have yet — want to add it?"

### 7. Write to DB
Insert the story:
```sql
INSERT INTO stories (title, situation, task, action, result, employer_id, timeframe, raw_transcript, source_type, notes)
VALUES ('...', '...', '...', '...', '...', N, '...', '...', 'conversation', '...')
```
Insert theme rows:
```sql
INSERT INTO story_themes (story_id, theme) VALUES (last_insert_rowid(), '...')
```
Insert bullet links:
```sql
INSERT INTO story_bullets (story_id, bullet_id) VALUES (last_insert_rowid(), '...')
```
If new bullets were approved: insert into `bullets`, `bullet_tracks`, `bullet_themes`, then run:
```
python3 src/best_foot_forward/utils/export_cache.py
```

Log the capture: `python3 -m best_foot_forward.utils.log_action --actor star-story --action capture --entity-type story --entity-id <story_id> --details '{"title": "<title>", "employer_id": <employer_id>}'`

### 8. Report
Confirm what was saved: story title, story ID, themes tagged, bullets linked, any new bullets created. Flag if the Result section feels thin — it's the most common weakness and worth flagging for the seeker to revisit.

## Notes
- `raw_transcript` should capture the key exchanges from this conversation in the seeker's own words — not a verbatim chat log, but enough to reconstruct how the story was told. It is the voice corpus source.
- Themes must come from the existing vocabulary unless a genuinely new one is needed. Consistency is what makes theme-based retrieval work.
- The Action section is the most important. Vague actions produce vague bullets. Push for specifics: decisions made, tradeoffs weighed, people convinced, things that were hard.
- A 10-exchange interview that produces a rich story beats a 3-exchange one that produces a thin one. Don't rush to synthesis.
- Don't fabricate. Only write what the user describes. If a detail seems important but wasn't mentioned, ask — don't infer.
