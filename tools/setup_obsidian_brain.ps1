<#
.SYNOPSIS
    Bootstraps a new Obsidian second-brain vault at C:\Obsidian Brain.

.DESCRIPTION
    Creates the same folder structure as the existing SecondBrain vault
    (C:/Users/walte/OneDrive/SecondBrain), seeds the note templates, a Home
    note, and a per-project context file. Idempotent: existing files are
    never overwritten, so it is safe to re-run.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File setup_obsidian_brain.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File setup_obsidian_brain.ps1 -ProjectName "my-new-project"
#>
param(
    [string]$VaultPath = "C:\Obsidian Brain",
    [string]$ProjectName = "new-project"
)

$ErrorActionPreference = "Stop"

function New-VaultFile {
    param([string]$Path, [string]$Content)
    if (Test-Path $Path) {
        Write-Host "  skip (exists): $Path"
    } else {
        Set-Content -Path $Path -Value $Content -Encoding UTF8
        Write-Host "  created:       $Path"
    }
}

Write-Host "Creating vault at `"$VaultPath`" ..."

$folders = @(
    "00-inbox",
    "01-projects",
    "01-projects\$ProjectName",
    "02-knowledge",
    "03-decisions",
    "04-debug-journal",
    "05-templates"
)
foreach ($f in $folders) {
    $full = Join-Path $VaultPath $f
    if (-not (Test-Path $full)) {
        New-Item -ItemType Directory -Path $full -Force | Out-Null
        Write-Host "  created:       $full"
    } else {
        Write-Host "  skip (exists): $full"
    }
}

# ---------------------------------------------------------------- Home note
New-VaultFile (Join-Path $VaultPath "Home.md") @'
# Obsidian Brain

## Structure
- [[00-inbox]] — quick captures, braindumps, unprocessed notes
- [[01-projects]] — per-project context, decisions, session logs
- [[02-knowledge]] — consolidated learnings, patterns, reference
- [[03-decisions]] — ADRs (architectural decision records)
- [[04-debug-journal]] — debugging sessions, root causes, fixes
- [[05-templates]] — note templates (copy structure, do not modify)

## Conventions
- Plain markdown, `[[wikilinks]]` for cross-references
- Keep notes concise — reference system, not a transcript
- Session logs: `01-projects/<project>/YYYY-MM-DD.md`
- Decisions: `03-decisions/YYYY-MM-DD-short-title.md`
- Debug logs: `04-debug-journal/YYYY-MM-DD-short-title.md`
- Update each project's `context.md` after every working session
'@

# ------------------------------------------------------- Project context
New-VaultFile (Join-Path $VaultPath "01-projects\$ProjectName\context.md") @'
# Project Context

## What this project is
(One-paragraph description — what it does, who it is for.)

## Current state
(Where things stand right now. Update every session.)

## Key decisions
(Link ADRs as they are written, e.g. [[2026-06-12-example-decision]].)

## Open questions / next steps
-

## Session log
| Date | Summary |
|------|---------|
'@

# ------------------------------------------------------------- Templates
New-VaultFile (Join-Path $VaultPath "05-templates\session-log.md") @'
# Session Log — YYYY-MM-DD

## What was done
-

## Decisions made
-

## Problems hit / solved
-

## Next steps
-
'@

New-VaultFile (Join-Path $VaultPath "05-templates\decision.md") @'
# Decision — (short title)

**Date:** YYYY-MM-DD
**Status:** proposed | accepted | superseded by [[...]]

## Context
(What situation forced a choice.)

## Decision
(What was chosen.)

## Alternatives considered
-

## Consequences
(What this makes easier / harder.)
'@

New-VaultFile (Join-Path $VaultPath "05-templates\debug-session.md") @'
# Debug — (short title)

**Date:** YYYY-MM-DD

## Symptom
(What was observed.)

## Root cause
(What was actually wrong.)

## Fix
(What changed, with file/line references.)

## Prevention
(Test, guard, or convention added so it cannot recur.)
'@

New-VaultFile (Join-Path $VaultPath "05-templates\knowledge.md") @'
# (Topic name)

## Summary
(The reusable insight in 2-3 sentences.)

## Details
-

## Related
- [[...]]
'@

# ------------------------------------------------- Mind map (Canvas)
# Obsidian Canvas is a core feature (no plugin). This seeds a starter mind
# map: central project node with six branches and a link to context.md.
New-VaultFile (Join-Path $VaultPath "Mind Map.canvas") @"
{
	"nodes": [
		{"id":"center","type":"text","text":"# $ProjectName","x":-150,"y":-50,"width":300,"height":100,"color":"4"},
		{"id":"goals","type":"text","text":"**Goals & Scope**\n- What done looks like\n- In / out of scope","x":420,"y":-320,"width":300,"height":140,"color":"5"},
		{"id":"arch","type":"text","text":"**Architecture**\n- Components\n- Data flow\n- Tech choices","x":420,"y":-70,"width":300,"height":140,"color":"5"},
		{"id":"risks","type":"text","text":"**Risks & Open Questions**\n- Unknowns\n- Blockers","x":420,"y":180,"width":300,"height":140,"color":"2"},
		{"id":"ideas","type":"text","text":"**Ideas**\n- Braindump here, sort to [[00-inbox]] later","x":-870,"y":-320,"width":300,"height":140,"color":"6"},
		{"id":"decisions","type":"text","text":"**Decisions**\n- Link ADRs from 03-decisions as they land","x":-870,"y":-70,"width":300,"height":140,"color":"3"},
		{"id":"knowledge","type":"text","text":"**Knowledge & Resources**\n- Docs, references, 02-knowledge notes","x":-870,"y":180,"width":300,"height":140,"color":"1"},
		{"id":"context","type":"file","file":"01-projects/$ProjectName/context.md","x":-150,"y":220,"width":300,"height":180}
	],
	"edges": [
		{"id":"e-goals","fromNode":"center","fromSide":"right","toNode":"goals","toSide":"left"},
		{"id":"e-arch","fromNode":"center","fromSide":"right","toNode":"arch","toSide":"left"},
		{"id":"e-risks","fromNode":"center","fromSide":"right","toNode":"risks","toSide":"left"},
		{"id":"e-ideas","fromNode":"center","fromSide":"left","toNode":"ideas","toSide":"right"},
		{"id":"e-decisions","fromNode":"center","fromSide":"left","toNode":"decisions","toSide":"right"},
		{"id":"e-knowledge","fromNode":"center","fromSide":"left","toNode":"knowledge","toSide":"right"},
		{"id":"e-context","fromNode":"center","fromSide":"bottom","toNode":"context","toSide":"top"}
	]
}
"@

New-VaultFile (Join-Path $VaultPath "05-templates\mind-map-outline.md") @'
# (Topic) — Mind Map Outline

<!--
Alternative to Canvas: install the community plugin "Mind map" (markmap)
and open this note with "Mind map: Preview" — headings and bullets render
as an auto-laid-out mind map. Pure markdown, so it stays readable without
the plugin too.
-->

## Branch one
- point
  - sub-point

## Branch two
- point

## Branch three
- point
'@

# ------------------------------------- Claude Code skill file (template)
New-VaultFile (Join-Path $VaultPath "05-templates\claude-skill-template.md") @'
<!--
Copy this file into the new project repo as
.claude/skills/second-brain/SKILL.md and fill in the project name.
-->
# SKILL.md — Obsidian Second Brain

## When to Use
Activate when you need to persist context across sessions, record
architectural decisions, log debugging sessions, capture session summaries,
or reference knowledge from previous work. Also activate when the user
mentions "second brain", "obsidian", "remember this", or "context".

## Vault Location
`C:/Obsidian Brain/`
Access via: `--add-dir "C:/Obsidian Brain"`

## Vault Structure
00-inbox / 01-projects / 02-knowledge / 03-decisions / 04-debug-journal / 05-templates

## How to Use from Claude Code
- Session start: read `01-projects/<project>/context.md`
- After significant work: session log to `01-projects/<project>/YYYY-MM-DD.md`
- Architectural choice: ADR to `03-decisions/YYYY-MM-DD-short-title.md`
- Tricky bug resolved: `04-debug-journal/YYYY-MM-DD-short-title.md`
- Reusable pattern: `02-knowledge/topic-name.md`
- Anything unprocessed: `00-inbox/`

## Rules
- Plain markdown, `[[wikilinks]]` for cross-references
- Keep notes concise — reference system, not a transcript
- Update `01-projects/<project>/context.md` session log after each session
- Templates are in `05-templates/` — copy the structure, do not modify them
'@

Write-Host ""
Write-Host "Done. Next steps:"
Write-Host "  1. Open Obsidian -> 'Open folder as vault' -> `"$VaultPath`""
Write-Host "  2. Rename 01-projects\$ProjectName to the real project name (if needed)"
Write-Host "     and open 'Mind Map.canvas' to start mapping the project"
Write-Host "  3. In the new project's repo, copy 05-templates\claude-skill-template.md"
Write-Host "     to .claude/skills/second-brain/SKILL.md so Claude Code uses the vault"
Write-Host "  4. Launch Claude Code with: claude --add-dir `"$VaultPath`""
Write-Host ""
Write-Host "Note: unlike the existing SecondBrain vault, this path is NOT inside"
Write-Host "OneDrive, so it will not sync across machines unless you add it to a"
Write-Host "sync/backup tool yourself."
