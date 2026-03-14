# Signal Dispatch — Fix Prompts

10 sequential prompts for Claude Code to fix and refactor the Signal Dispatch pipeline.

## Quick Start

```bash
# 1. Copy this folder into your repo root
cp -r fix_prompts/ /path/to/signal-dispatch/fix_prompts/

# 2. cd into the repo
cd /path/to/signal-dispatch/

# 3. Run all 10 prompts (each gets a fresh context window)
bash fix_prompts/run_fixes.sh

# Or resume from prompt N after a failure
bash fix_prompts/run_fixes.sh 4

# Or run a specific range
bash fix_prompts/run_fixes.sh 4 6
```

## What Each Prompt Does

| # | File | Summary |
|---|------|---------|
| 1 | `prompt_01.md` | **Critical data integrity** — DB commit, RSS filter inversion, BoC fallback, empty payload guard |
| 2 | `prompt_02.md` | **Configuration hygiene** — model string consolidation, cost cap enforcement, Perplexity removal, sector mapping |
| 3 | `prompt_03.md` | **Error handling** — per-step try/except, orphaned run cleanup, 429 retry (4 retries), bare except removal |
| 4 | `prompt_04.md` | **Circuit breaker + checkpointing** — ServiceHealth, Claude checkpoints table, JSON truncation fix |
| 5 | `prompt_05.md` | **Dead tier cleanup** — GDELT archived, SEDAR+ disabled, Google Alerts placeholder check, municipal health checks |
| 6 | `prompt_06.md` | **File cleanup** — archive 13 legacy files, consolidate URL/missed-project/pipeline-state modules |
| 7 | `prompt_07.md` | **Local LLM** — Qwen 2.5 3B via llama-cpp-python, Gemini becomes fallback-only, CI model caching |
| 8 | `prompt_08.md` | **Phase extraction** — monolith → 9 phase modules, thin orchestrator, all CLI flags preserved |
| 9 | `prompt_09.md` | **Data quality** — dedup key fixes, URL hard gate in DB, cost_unfindable reset, query dedup, phase order verification |
| 10 | `prompt_10.md` | **Frontend + docs** — missing JSON exports, deploy script, briefing CI, meta tags, ARCHITECTURE.md update |

## Fixes Applied vs. Original Document

Two corrections were made to align with CLAUDE.md:

1. **Prompt 3 Fix 4:** Retry count changed from 3 → **4 retries** (CLAUDE.md specifies 4 retry attempts)
2. **Prompt 8:** Phase order corrected — `signals` placed **before** `analysis` (matching CLAUDE.md Phase 4 → Phase 5 order). Also added `--seed-projects` and `--test-feeds` CLI flags that were missing from the original orchestrator.

## Prerequisites

- Claude Code CLI installed and authenticated
- CLAUDE.md in the repo root is current (the version provided with these prompts)
- Working Git repo with clean state (`git status` shows no uncommitted changes)

## Notes

- The runner uses `--dangerously-skip-permissions` so Claude Code won't pause for confirmation on bash commands, file deletions, etc. Every prompt runs fully autonomously.
- Each `claude -p` invocation gets a completely fresh context window — no accumulation, no 50% context wall.
- Logs are saved to `fix_log_prompt_NN.txt` after each prompt for review.
