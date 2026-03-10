# SKILL.md — Obsidian Second Brain

## When to Use
Activate when you need to persist context across sessions, record architectural decisions, log debugging sessions, capture session summaries, or reference knowledge from previous work. Also activate when the user mentions "second brain", "obsidian", "remember this", or "context".

## Vault Location
`C:/Users/walte/OneDrive/SecondBrain/`
Access via: `--add-dir "C:/Users/walte/OneDrive/SecondBrain"`

## Vault Structure
```
SecondBrain/
├── 00-inbox/           # Quick captures, braindumps, unprocessed notes
├── 01-projects/        # Per-project context, decisions, session logs
│   └── can-macro-dashboard/  # This project's context
├── 02-knowledge/       # Consolidated learnings, patterns, reference
├── 03-decisions/       # ADRs (architectural decision records)
├── 04-debug-journal/   # Debugging sessions, root causes, fixes
└── 05-templates/       # Note templates (decision, debug-session, session-log)
```

## How to Use from Claude Code

### Reading context at session start
Read `01-projects/can-macro-dashboard/context.md` for project state and recent session log.

### Logging a session
After significant work, write a session log to `01-projects/can-macro-dashboard/YYYY-MM-DD.md` using the session-log template.

### Recording a decision
When an architectural choice is made, write to `03-decisions/YYYY-MM-DD-short-title.md` using the decision template.

### Logging a debug session
After resolving a tricky bug, write to `04-debug-journal/YYYY-MM-DD-short-title.md` using the debug-session template.

### Capturing knowledge
When discovering reusable patterns/insights, write to `02-knowledge/topic-name.md`.

### Quick capture
Dump anything unprocessed to `00-inbox/` for later sorting.

## Rules
- Use plain markdown — Obsidian renders it, Claude reads/writes it
- Use `[[wikilinks]]` for cross-references between notes (Obsidian auto-links)
- Keep notes concise — this is a reference system, not a transcript
- Update `01-projects/can-macro-dashboard/context.md` session log after each session
- Templates are in `05-templates/` — copy the structure, don't modify templates
