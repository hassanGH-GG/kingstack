#!/bin/bash
# SessionStart hook: inject the routing contract into every session, plus a memory-inbox
# nudge when candidates are waiting. Edit poteto-mode-context.md to change the contract.
ctx=$(cat "$HOME/.claude/hooks/poteto-mode-context.md")
inbox="$HOME/.claude/memory-review.md"
if [ -f "$inbox" ]; then
  pending=$(grep -c '^- \[ \]' "$inbox" 2>/dev/null || echo 0)
  if [ "${pending:-0}" -gt 0 ]; then
    last=$(stat -f %Sm -t %Y-%m-%d "$inbox")
    ctx="$ctx

<memory_inbox>$pending memory candidate(s) are waiting in ~/.claude/memory-review.md (last change $last). If Hassan is not mid-task, mention it once in your first reply and offer /memory-review; never run it unasked.</memory_inbox>"
  fi
fi
jq -n --arg ctx "$ctx" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$ctx}}'
