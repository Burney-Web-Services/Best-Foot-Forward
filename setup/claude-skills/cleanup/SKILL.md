---
name: cleanup
description: "Universal session wrap-up before /compact. Saves artifacts, checks git, surfaces outstanding items. Run before context compression. Projects can extend this with a .claude/commands/cleanup.md that adds project-specific steps."
---

# /cleanup

Universal session wrap-up. Run before `/compact` to make sure nothing gets lost when context compresses.

## Trigger
User says "cleanup", "wrap up", "session cleanup", or invokes `/cleanup`. Also appropriate when the user says they're done for the session.

## Authorship convention

When saving session artifacts, be explicit about who produced what:

| Source | Convention |
|--------|-----------|
| User's own words / raw notes | `{Topic}Notes.md` |
| Claude's analysis / synthesis | `{Topic}ClaudeNotes.md` |
| Mixed (both voices) | explicit section headers: `## Your Notes` / `## Claude's Analysis` |

Never blend the two silently. If the user shared raw observations and Claude also analyzed them, keep them in separate sections or separate files.

## Workflow

### Step 1 — Session inventory

Ask yourself (do not ask the user): what happened this session? Build a mental list:
- Decisions made or conclusions reached
- Analysis Claude produced (strategy, assessment, critique, synthesis)
- New information the user shared (context, preferences, domain knowledge, constraints)
- Files created or changed
- Anything flagged as TODO, "follow up", "check later", or "remind me"

If the session was light (one quick question, no significant output), say so and skip to Step 4.

### Step 2 — Artifact capture

Scan the conversation for anything that:
- Represents Claude's analysis, synthesis, or strategic assessment
- Was produced verbally and never written to a file
- Would be worth having in a future conversation, cold

Write these to files in the appropriate project location. **Do not ask permission — if it's worth saving, save it.** The whole point of cleanup is to catch what falls through the cracks before context compresses.

If the project has its own naming conventions for session artifacts, follow those. Otherwise, default to placing `ClaudeNotes.md` files alongside the relevant work, and `Notes.md` for the user's raw observations.

### Step 3 — Memory check

If this project has a memory system (e.g., a `memory/` directory with a `MEMORY.md` index):
- Did anything this session change what a future conversation should know?
- Is any existing memory now stale?
- Did the user share preferences, corrections, or context that should survive a reset?

Update or create memory files as needed. The test: "would future-me benefit from knowing this cold, in a new conversation?" If no, don't save it. Save signal, not session noise.

### Step 4 — Git status

Run `git status`. If there are uncommitted changes to code or config files (not just gitignored data/generated files):
- List them
- Ask if the user wants to commit before compacting

### Step 5 — Outstanding items

Scan the session for anything flagged as TODO, "follow up", "check later", or "remind me":
- List them explicitly
- Ask if any should be persisted (memory, notes file, task tracker)

### Step 6 — Report

```
Session cleanup complete.

SAVED:
- [files written or updated, or "nothing to save"]

MEMORY:
- [memory files updated, or "no changes needed"]

GIT:
- [uncommitted changes listed, or "clean"]

OUTSTANDING:
- [carry-forward items, or "none"]
```

Then suggest: "Ready for `/compact`."

## Notes
- The memory check is a judgment call, not a checklist — ask: "would future-me benefit from knowing this?"
- If the user is in a hurry, prioritize Steps 2 and 3 — those are the highest-value, hardest-to-recover steps.
- If the project has a `.claude/commands/cleanup.md`, that file extends this skill with project-specific steps. The project command should instruct Claude to run this global workflow first, then its additions.
