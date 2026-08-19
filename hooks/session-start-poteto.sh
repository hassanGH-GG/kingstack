#!/bin/bash
# SessionStart hook: inject the routing contract into every session, plus a memory-inbox
# nudge when candidates are waiting. Edit poteto-mode-context.md to change the contract.
ctx=$(cat "$HOME/.claude/hooks/poteto-mode-context.md")
inbox="$HOME/.claude/memory-review.md"
if [ -f "$inbox" ]; then
  # `grep -c` prints 0 AND exits 1 when nothing matches, so a `|| echo 0` fallback yields
  # "0\n0" and every later numeric test errors. Take the first line and default it instead.
  pending=$(grep -c '^- \[ \]' "$inbox" 2>/dev/null | head -1); pending=${pending:-0}
  if [ "${pending:-0}" -gt 0 ]; then
    last=$(stat -f %Sm -t %Y-%m-%d "$inbox")
    ctx="$ctx

<memory_inbox>$pending memory candidate(s) are waiting in ~/.claude/memory-review.md (last change $last). If Hassan is not mid-task, mention it once in your first reply and offer /memory-review; never run it unasked.</memory_inbox>"
  fi
fi
# Usage awareness: one line of yesterday's shape so the session regulates itself.
ledger="$HOME/.claude/usage-ledger.csv"
if [ -f "$ledger" ]; then
  uline=$(tail -n +2 "$ledger" | awk -F, -v d="$(date -v-1d +%Y-%m-%d)" '$1==d {t+=$4; c+=$5+$6+$7; usd+=$9} END {if (t>0) printf "yesterday: %d turns, %dk ctx/turn, ~$%.0f list-equivalent", t, c/t/1000, usd}')
  [ -n "$uline" ] && ctx="$ctx

<usage>$uline. The ruler's session-weight rule applies: past ~150k context, propose /clear; bulk to subagents; polling is never an LLM turn.</usage>"
fi
jq -n --arg ctx "$ctx" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$ctx}}'
