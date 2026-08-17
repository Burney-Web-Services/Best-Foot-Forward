# BFF Machine Setup — Claude Code Configuration

> **Claude Code users** (Linux/Mac): Clone the repo locally. All configuration
> travels with it. See the setup section below.

> **Codex / Gemini / Antigravity users**: After cloning and running `uv sync`,
> open the repository in your agent, mark it trusted, and use `/mcp` and `/hooks`
> to review the project-local `bff` MCP server and application-tracking hook.
> Workflow skills are discovered automatically from `.agents/skills/`; use
> `$onboard` to begin. No additional setup needed — all three agents share the
> same `.agents/skills/` layer.

Configuration guide for running BFF across Claude Code (Linux/Mac), Codex, Gemini, and Antigravity.

The BFF project files (`.claude/commands/`, `CLAUDE.md`) travel with the repo. Claude Code users must set up global machine-level configuration in `~/.claude/`; Codex/Gemini/Antigravity users don't need this step — the agent discovers `.agents/skills/` automatically and uses the shared workflow layer.

## What lives where

| Location | Travels with | Notes |
|----------|-------------|-------|
| `.claude/commands/cleanup.md` | BFF repo ✓ | Project-level cleanup — gets it on clone |
| `CLAUDE.md` (BFF project root) | BFF repo ✓ | Project instructions |
| `~/.claude/skills/cleanup/SKILL.md` | **Manual deploy** | Global skill — must copy to each machine |
| `~/.claude/CLAUDE.md` entries | **Manual deploy** | Global config — must update on each machine |

---

## One-time machine setup (Claude Code users only)

Codex, Gemini, and Antigravity users can skip this section — the agents discover `.agents/skills/` automatically.

### 1. Deploy the global cleanup skill

Run from the repo root (where you `cd`'d after cloning):

```bash
mkdir -p ~/.claude/skills/cleanup
cp setup/claude-skills/cleanup/SKILL.md ~/.claude/skills/cleanup/SKILL.md
```

(The canonical source of this file is `BFF/setup/claude-skills/cleanup/SKILL.md` — update there first if you revise it, then redeploy to each machine.)

### 2. Add the cleanup entry to `~/.claude/CLAUDE.md`

Add this block to `~/.claude/CLAUDE.md` (see `setup/claude-md-snippets.md` for the full text to paste):

```
# cleanup
- **cleanup** (`~/.claude/skills/cleanup/SKILL.md`) - universal session wrap-up before /compact.
  Trigger: `/cleanup`, "cleanup", "wrap up", "session cleanup".
  When triggered, invoke the Skill tool with `skill: "cleanup"` before doing anything else.
  Projects with `.claude/commands/cleanup.md` extend this with project-specific steps.
```

### 3. Verify

Start a new Claude Code session and run `/cleanup`. You should see the cleanup workflow fire. In a BFF session, the project-level `.claude/commands/cleanup.md` takes over and adds BFF-specific steps (DB check, application dir, memory files).

---

## For future BFF users

The setup files are in `setup/` at the BFF project root:
- `setup/claude-skills/cleanup/SKILL.md` — copy to `~/.claude/skills/cleanup/`
- `setup/claude-md-snippets.md` — paste the relevant block into `~/.claude/CLAUDE.md`

The BFF `onboard` command (`.claude/commands/onboard.md`) should eventually walk through this automatically. For now, do it manually per the steps above.

---

## How the global skill gets shared

Right now: manually, via the `setup/` directory in this repo. Each machine is an independent `~/.claude/` installation.

Long-term options (when there are more machines/users):
- A dotfiles repo synced across machines (symlink `~/.claude/skills/` to a shared location)
- The BFF `onboard` command installs the global skills automatically
- BFF-Next handles this as part of user account setup (web-based, no local install)
