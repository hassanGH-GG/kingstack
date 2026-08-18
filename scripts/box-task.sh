#!/bin/bash
# box-task: fire-and-forget an unattended Claude run. Completion is an exit FILE, never process
# presence, so a dropped terminal or a closed lid cannot be mistaken for "finished".
# (Mechanism from heysadie/minions box-task.sh.)
#
#   echo "<brief>" | box-task.sh run <name> [--cwd <dir>] [--model haiku] [--max-turns 30]
#   box-task.sh status <name>            # queued | running | done <code>
#   box-task.sh wait <name> [--timeout 900]
#   box-task.sh result <name>            # the run's output
#   box-task.sh list
#
# Runs survive this shell. They do NOT survive a reboot or sleep: that is what a real always-on
# host buys. Model defaults to haiku per ~/.claude/model-routing.md; raise it for judgment work.
set -euo pipefail
ROOT="$HOME/.claude/box-tasks"
cmd="${1:-}"; name="${2:-}"; shift 2 2>/dev/null || true
cwd="$PWD"; model="haiku"; maxturns="30"; timeout="900"
while [ $# -gt 0 ]; do
  case "$1" in
    --cwd) cwd=$(cd "$2" && pwd); shift 2;;
    --model) model="$2"; shift 2;;
    --max-turns) maxturns="$2"; shift 2;;
    --timeout) timeout="$2"; shift 2;;
    *) shift;;
  esac
done
d="$ROOT/$name"

case "$cmd" in
  run)
    [ -n "$name" ] || { echo "name required" >&2; exit 2; }
    [ -e "$d/exit" ] && rm -rf "$d"
    [ -d "$d" ] && { echo "task '$name' already running (status: $("$0" status "$name"))" >&2; exit 1; }
    mkdir -p "$d"
    { echo "You are running unattended. Nobody will answer a question, so never ask one: decide,"
      echo "act, and report. If you are truly blocked, stop and write why in one paragraph."
      echo "Do not wait or poll; if something is not ready, say so and exit."
      echo; cat; } > "$d/brief.md"
    printf '{"name":"%s","cwd":"%s","model":"%s","max_turns":"%s","started":"%s"}\n' \
      "$name" "$cwd" "$model" "$maxturns" "$(date '+%F %T')" > "$d/meta.json"
    nohup bash -c "cd '$cwd' && claude -p --model '$model' --max-turns '$maxturns' \
      < '$d/brief.md' > '$d/out.log' 2>&1; echo \$? > '$d/exit'" >/dev/null 2>&1 &
    echo "started $name (pid $!, cwd $cwd, model $model) -> $d"
    ;;
  status)
    [ -d "$d" ] || { echo "unknown"; exit 1; }
    if [ -f "$d/exit" ]; then echo "done $(cat "$d/exit")"; else echo "running"; fi
    ;;
  wait)
    [ -d "$d" ] || { echo "unknown task '$name'" >&2; exit 1; }
    n=0
    until [ -f "$d/exit" ]; do
      n=$((n+2)); [ "$n" -ge "$timeout" ] && { echo "timeout after ${timeout}s (still running)" >&2; exit 2; }
      sleep 2
    done
    echo "done $(cat "$d/exit") after ~${n}s"
    ;;
  result)
    [ -f "$d/out.log" ] || { echo "no output for '$name'" >&2; exit 1; }
    cat "$d/out.log"
    ;;
  list)
    [ -d "$ROOT" ] || { echo "no tasks"; exit 0; }
    for t in "$ROOT"/*/; do
      [ -d "$t" ] || continue; b=$(basename "$t")
      printf '  %-22s %s\n' "$b" "$([ -f "$t/exit" ] && echo "done $(cat "$t/exit")" || echo running)"
    done
    ;;
  *) sed -n '2,16p' "$0"; exit 2;;
esac
