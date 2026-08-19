#!/bin/bash
# PostToolUse hook: flag any tool result big enough to matter, the moment it enters the
# main thread. Everything in history is re-read every later turn, so one 80KB read costs
# on every turn until compaction. The ruler says bulk goes to a haiku subagent; this makes
# a violation visible at the instant it happens instead of in tomorrow's ledger.
in=$(cat)
size=$(printf '%s' "$in" | jq -r '(.tool_response | tostring | length) // 0' 2>/dev/null)
[ "${size:-0}" -lt 30000 ] && { echo '{}'; exit 0; }
tool=$(printf '%s' "$in" | jq -r '.tool_name // "tool"' 2>/dev/null)
jq -n --arg m "⚠ $tool result ~$((size/1024))KB entered the main thread; it will be re-read every turn until compaction. Ruler: bulk over ~200 lines goes to a haiku subagent that returns a summary." '{systemMessage:$m}'
