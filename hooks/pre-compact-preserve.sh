#!/bin/bash
# PreCompact hook: minimize what compaction loses, two ways at once.
# 1. Steer the summarizer: tell it which facts are load-bearing and must survive.
# 2. Checkpoint mechanically: before the summary replaces history, write the session's
#    last human prompts and live git state to a durable file no summarizer can eat.
in=$(cat)
sid=$(printf '%s' "$in" | jq -r '.session_id // "unknown"' 2>/dev/null)
tp=$(printf '%s' "$in" | jq -r '.transcript_path // ""' 2>/dev/null)
cwd=$(printf '%s' "$in" | jq -r '.cwd // ""' 2>/dev/null)

ck="$HOME/.claude/logs/compaction-checkpoints"; mkdir -p "$ck"
{
  echo "# compaction checkpoint $(date '+%F %T') session ${sid:0:8} cwd $cwd"
  if [ -n "$cwd" ] && git -C "$cwd" rev-parse --git-dir >/dev/null 2>&1; then
    echo "## git state at compaction"
    git -C "$cwd" status --short 2>/dev/null | head -20
    echo "unpushed: $(git -C "$cwd" log --oneline @{u}..HEAD 2>/dev/null | wc -l | tr -d ' ') commit(s)"
  fi
  if [ -f "$tp" ]; then
    echo "## last human prompts before compaction"
    python3 - "$tp" <<'PY' 2>/dev/null
import json,sys
rows=[]
for line in open(sys.argv[1],errors="ignore"):
    if '"type":"user"' not in line: continue
    try: r=json.loads(line)
    except: continue
    if r.get("type")!="user" or r.get("promptSource") not in ("typed","suggestion_accepted"): continue
    c=(r.get("message") or {}).get("content")
    t=c if isinstance(c,str) else " ".join(b.get("text","") for b in c or [] if isinstance(b,dict) and b.get("type")=="text")
    t=(t or "").strip()
    if t and not t.startswith("<"): rows.append(t.replace("\n"," ")[:200])
for t in rows[-6:]: print("-", t)
PY
  fi
} > "$ck/${sid:0:8}.md" 2>/dev/null

jq -n '{hookSpecificOutput:{hookEventName:"PreCompact",additionalContext:"PRESERVE VERBATIM in the summary, these outrank narrative: (1) the current finish condition, done means, exactly as last stated; (2) every file path edited or created this session and whether it is committed and pushed; (3) open decisions and anything Hassan corrected, in his words; (4) any command or step that was about to run next; (5) unpushed or uncommitted state named in the transcript. Drop pleasantries and process narration first, never these."}}'
