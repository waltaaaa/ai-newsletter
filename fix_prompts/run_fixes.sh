#!/usr/bin/env bash
# run_fixes.sh — Execute Signal Dispatch fix prompts sequentially
# Each `claude -p` invocation gets a fresh context window (no accumulation).
#
# Usage: 
#   cd into your repo root
#   cp -r /path/to/fix_prompts ./fix_prompts
#   bash run_fixes.sh           # run all 10
#   bash run_fixes.sh 4         # resume from prompt 4
#   bash run_fixes.sh 4 6       # run prompts 4 through 6 only

set -euo pipefail

PROMPTS_DIR="./fix_prompts"
START_FROM="${1:-1}"
END_AT="${2:-10}"

# Pre-flight checks
if [ ! -d "$PROMPTS_DIR" ]; then
    echo "ERROR: $PROMPTS_DIR not found."
    echo "Copy the fix_prompts/ directory into your repo root first."
    exit 1
fi

if ! command -v claude &> /dev/null; then
    echo "ERROR: 'claude' CLI not found. Install Claude Code first."
    exit 1
fi

echo "═══════════════════════════════════════════════════"
echo "  Signal Dispatch — Fix Prompts Runner"
echo "  Running prompts $START_FROM through $END_AT"
echo "  Mode: FULLY AUTONOMOUS (all permissions granted)"
echo "═══════════════════════════════════════════════════"
echo ""

for i in $(seq "$START_FROM" "$END_AT"); do
    PROMPT_FILE="$PROMPTS_DIR/prompt_$(printf '%02d' $i).md"

    if [ ! -f "$PROMPT_FILE" ]; then
        echo "⚠️  Skipping prompt $i — file not found: $PROMPT_FILE"
        continue
    fi

    echo ""
    echo "───────────────────────────────────────────────────"
    echo "  PROMPT $i of 10"
    echo "───────────────────────────────────────────────────"
    echo ""

    # --dangerously-skip-permissions: auto-approve ALL tool use (bash, file edits, etc.)
    # --max-turns 50: generous turn limit for complex prompts
    # --verbose: full logging
    # Each invocation = fresh context window, no accumulation
    claude -p "$(cat "$PROMPT_FILE")" \
        --dangerously-skip-permissions \
        --max-turns 50 \
        --verbose \
        2>&1 | tee "fix_log_prompt_$(printf '%02d' $i).txt"

    EXIT_CODE=${PIPESTATUS[0]}

    if [ "$EXIT_CODE" -ne 0 ]; then
        echo ""
        echo "❌ Prompt $i exited with code $EXIT_CODE"
        echo "   Review fix_log_prompt_$(printf '%02d' $i).txt"
        echo "   Fix any issues, then resume:"
        echo "   bash run_fixes.sh $i"
        exit 1
    fi

    echo ""
    echo "✅ Prompt $i complete. Committing..."

    git add -A
    git commit -m "fix(signal-dispatch): prompt $i of 10 — $(head -1 "$PROMPT_FILE" | sed 's/^I need you to //' | sed 's/\. .*//' | cut -c1-60)" --allow-empty

    echo "   Committed. Moving to next prompt..."
    sleep 2
done

echo ""
echo "═══════════════════════════════════════════════════"
echo "  🎉 All done (prompts $START_FROM–$END_AT)."
echo ""
echo "  Post-completion checklist:"
echo "  [ ] python update_dashboard.py --indicators-only"
echo "  [ ] Verify imports: grep -rn 'from perplexity' *.py"
echo "  [ ] Verify circuit breaker: temporarily set threshold=1"
echo "  [ ] Verify claude_checkpoints table created"
echo "  [ ] Review updated ARCHITECTURE.md"
echo "═══════════════════════════════════════════════════"
