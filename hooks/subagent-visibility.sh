#!/bin/bash
# SubagentStart hook: every spawn reports its model and effort to the parent transcript,
# so routing is visible at the moment it happens instead of being asserted afterwards.
# "inherit" means the spawn call set nothing and the parent's model/effort leaked through,
# which the routing ruler treats as a smell for routed work.
in=$(cat)
d=$(printf '%s' "$in" | jq -r '.tool_input.description // .tool_input.prompt // "agent" | .[0:60]' 2>/dev/null)
m=$(printf '%s' "$in" | jq -r '.tool_input.model // "inherit"' 2>/dev/null)
e=$(printf '%s' "$in" | jq -r '.tool_input.effort // "inherit"' 2>/dev/null)
t=$(printf '%s' "$in" | jq -r '.tool_input.subagent_type // "default"' 2>/dev/null)
flag=""; [ "$m" = "inherit" ] && flag=" ⚠ no model set"
jq -n --arg msg "↳ spawn [$t] $d · model=$m effort=$e$flag" '{systemMessage:$msg}'
