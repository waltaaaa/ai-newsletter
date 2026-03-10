# SKILL.md — Ralph Loop (Iterative AI Development)

## When to Use
Activate when the user wants to run an iterative development loop — large refactors, batch operations, greenfield builds, test coverage campaigns, or any task with clear completion criteria that benefits from persistent retry.

## How Ralph Loop Works
The Ralph Wiggum technique uses a Stop hook to create a self-referential loop:
1. User runs `/ralph-loop "<prompt>" --max-iterations N --completion-promise "DONE"`
2. Claude works on the task, tries to exit
3. Stop hook blocks exit and re-feeds the same prompt
4. Each iteration sees previous file changes and git history
5. Loop continues until completion promise is detected or max iterations hit

## Plugin Status
- **Installed:** ralph-loop@claude-plugins-official (enabled in settings.json)
- **Commands:** `/ralph-loop`, `/cancel-ralph`
- **Project PROMPT.md:** Template at project root for CLI-based loops

## Usage from CLI (Terminal)
```bash
# Using the plugin (recommended):
claude
/ralph-loop "Your task here" --max-iterations 20 --completion-promise "DONE"

# Simple bash loop (no plugin needed):
while :; do cat PROMPT.md | claude --print; done

# With iteration limit:
for i in $(seq 1 10); do cat PROMPT.md | claude --print; done
```

## Usage from VSCode
The plugin works in VSCode terminal sessions. Open a terminal, run `claude`, then use `/ralph-loop`.

## Writing Good Ralph Prompts
- Include clear completion criteria (tests passing, all endpoints working, etc.)
- Use phased/incremental goals
- Include TDD/self-verification steps
- Add escape hatch instructions for when stuck
- Always use `--max-iterations` as safety net
- Use `--completion-promise` with exact match string

## When NOT to Use Ralph
- Tasks requiring human judgment or design decisions
- One-shot operations
- Tasks with unclear success criteria
- Production debugging (use /gsd:debug instead)

## Project PROMPT.md
Edit `PROMPT.md` in project root before running CLI-based loops. Replace the "Current Task" section with the actual work.
