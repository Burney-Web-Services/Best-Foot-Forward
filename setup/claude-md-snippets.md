# ~/.claude/CLAUDE.md Snippets

Blocks to add to `~/.claude/CLAUDE.md` when setting up a new machine. Each block registers a global skill so Claude picks it up across all projects.

See `docs/machine-setup.md` for the full setup procedure.

---

## cleanup skill

Paste this into `~/.claude/CLAUDE.md`:

```
# cleanup
- **cleanup** (`~/.claude/skills/cleanup/SKILL.md`) - universal session wrap-up before /compact. Saves artifacts, checks git, surfaces outstanding items. Trigger: `/cleanup`, "cleanup", "wrap up", "session cleanup".
When the user types `/cleanup` or says "wrap up" / "session cleanup", invoke the Skill tool with `skill: "cleanup"` before doing anything else. Projects with `.claude/commands/cleanup.md` extend this with project-specific steps.
```

After pasting: copy `setup/claude-skills/cleanup/SKILL.md` to `~/.claude/skills/cleanup/SKILL.md`.

---

## Adding more global skills

When a new global skill is created, add its snippet here and a matching entry under `Machine status` in `docs/machine-setup.md`.
