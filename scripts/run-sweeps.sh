#!/bin/bash
# Run every enabled sweep in ~/.claude/sweeps/*.md, one headless session each, isolated.
# Usage: run-sweeps.sh [--only <name>] [--dry-run]
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
S="$HOME/.claude/sweeps"; LOG="$HOME/.claude/logs/sweeps.log"; mkdir -p "$HOME/.claude/logs"
only=""; dry=0
while [ $# -gt 0 ]; do case "$1" in --only) only="$2"; shift 2;; --dry-run) dry=1; shift;; *) shift;; esac; done
fm(){ awk -v k="$2" 'NR==1&&$0!="---"{exit} NR>1&&$0=="---"{exit} NR>1{split($0,a,": "); if(a[1]==k){sub(/^[^:]*: */,""); print; exit}}' "$1"; }
body(){ awk 'NR==1{next} f{print} $0=="---"&&NR>1{f=1}' "$1"; }
dow=$(date +%u)
for f in "$S"/*.md; do
  n=$(basename "$f" .md); [ "$n" = "README" ] && continue; [ "$n" = "_template" ] && continue
  [ -n "$only" ] && [ "$n" != "$only" ] && continue
  en=$(fm "$f" enabled); sched=$(fm "$f" schedule); cwd=$(fm "$f" cwd); model=$(fm "$f" model); mt=$(fm "$f" max_turns); rep=$(fm "$f" report)
  [ "$(fm "$f" name)" = "$n" ] || { echo "SKIP $n: frontmatter name != filename"; continue; }
  [ "$en" = "true" ] || { echo "skip $n (disabled)"; continue; }
  [ "$sched" = "weekly" ] && [ "$dow" != "1" ] && [ -z "$only" ] && { echo "skip $n (weekly, not Monday)"; continue; }
  [ -n "$mt" ] || { echo "SKIP $n: max_turns required"; continue; }
  cwd="${cwd/#\~/$HOME}"
  echo "=== sweep $n [$model, max_turns $mt, cwd $cwd] $(date '+%F %T') ==="
  [ $dry = 1 ] && { echo "(dry-run) would run"; continue; }
  # Unattended: allow read-only tools + the sweep's own declared commands; never bypassPermissions.
  allow=$(fm "$f" allow); allow_flags=(--allowedTools "Read" "Glob" "Grep" "Bash(cat *)" "Bash(ls *)" "Bash(git status*)" "Bash(git log*)")
  [ -n "$allow" ] && IFS=',' read -ra extra <<< "$allow" && for a in "${extra[@]}"; do allow_flags+=("$(echo "$a" | xargs)"); done
  out=$(cd "$cwd" && body "$f" | claude -p --model "${model:-haiku}" --max-turns "$mt" "${allow_flags[@]}" 2>&1); rc=$?
  echo "$out"; echo "=== exit $rc ==="
  case "$rep" in
    memory-inbox) echo "- [ ] $(date '+%F %H:%M') | sweep:$n | $(echo "$out" | head -1 | cut -c1-200)" >> "$HOME/.claude/memory-review.md";;
    file:*) echo "$out" > "${rep#file:}";;
  esac
done 2>&1 | tee -a "$LOG"
