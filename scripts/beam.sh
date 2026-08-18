#!/bin/bash
# beam: move a live Claude Code session to another working directory or machine, and resume it
# there with its memory intact. The transcript IS the transfer. (Mechanism from heysadie/minions.)
#
#   beam.sh list [--from <cwd>]                       # sessions available for a cwd
#   beam.sh to-dir <dest-dir> [--session <id8>] [--from <cwd>] [--run]
#   beam.sh to-host <user@host> <dest-dir> [--session <id8>] [--from <cwd>]
#   beam.sh fetch <user@host> <remote-cwd> <session-id>   # pull a session back
#
# Local mode (to-dir) needs nothing. Host mode needs ssh access; the remote must have claude
# installed and logged in. Nothing is deleted: beaming copies, so the origin can still resume.
set -euo pipefail
PROJ="$HOME/.claude/projects"
slug(){ printf '%s' "$1" | sed 's|/|-|g'; }

newest_session(){ # <cwd> -> session id
  local d="$PROJ/$(slug "$1")"
  [ -d "$d" ] || { echo "no sessions for $1" >&2; return 1; }
  basename "$(ls -t "$d"/*.jsonl 2>/dev/null | head -1)" .jsonl
}
resolve_session(){ # <cwd> <id-or-prefix-or-empty> -> full id
  local d="$PROJ/$(slug "$1")" want="${2:-}"
  if [ -z "$want" ]; then newest_session "$1"; return; fi
  local hit; hit=$(ls "$d"/*.jsonl 2>/dev/null | xargs -n1 basename 2>/dev/null | sed 's/\.jsonl$//' | grep "^$want" | head -1)
  [ -n "$hit" ] || { echo "no session matching '$want' in $1" >&2; return 1; }
  printf '%s' "$hit"
}
trust_dir(){ # pre-accept the trust dialog for a cwd so a resumed session is not blocked
  python3 - "$1" <<'PY'
import json,os,sys
p=os.path.expanduser("~/.claude.json"); d=os.path.abspath(sys.argv[1])
try: cfg=json.load(open(p))
except Exception: cfg={}
proj=cfg.setdefault("projects",{}); e=proj.setdefault(d,{})
e["hasTrustDialogAccepted"]=True
e.setdefault("allowedTools",[]); e.setdefault("history",[])
json.dump(cfg,open(p,"w"),indent=2)
print("trusted",d)
PY
}

cmd="${1:-}"; shift || true
from="$PWD"; sid=""; run=0
args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --from) from=$(cd "$2" && pwd); shift 2;;
    --session) sid="$2"; shift 2;;
    --run) run=1; shift;;
    *) args+=("$1"); shift;;
  esac
done

case "$cmd" in
  list)
    d="$PROJ/$(slug "$from")"
    echo "sessions for $from:"
    ls -t "$d"/*.jsonl 2>/dev/null | while read -r f; do
      printf '  %s  %s  %sKB  %s turns\n' "$(basename "$f" .jsonl | cut -c1-8)" \
        "$(stat -f %Sm -t '%m-%d %H:%M' "$f")" "$(( $(stat -f %z "$f") / 1024 ))" "$(grep -c '"type":"user"' "$f" 2>/dev/null || echo ?)"
    done
    ;;
  to-dir)
    dest=$(cd "${args[0]}" 2>/dev/null && pwd) || { echo "dest dir does not exist: ${args[0]}" >&2; exit 1; }
    s=$(resolve_session "$from" "$sid")
    dp="$PROJ/$(slug "$dest")"; mkdir -p "$dp"
    cp "$PROJ/$(slug "$from")/$s.jsonl" "$dp/$s.jsonl"
    trust_dir "$dest" >/dev/null
    echo "beamed $(printf %s "$s" | cut -c1-8) -> $dest"
    if [ "$run" = 1 ]; then (cd "$dest" && exec claude --resume "$s"); else
      echo "resume it with:  cd $dest && claude --resume $s"; fi
    ;;
  to-host)
    host="${args[0]}"; dest="${args[1]}"
    s=$(resolve_session "$from" "$sid")
    rslug=$(printf '%s' "$dest" | sed 's|/|-|g')
    ssh "$host" "mkdir -p ~/.claude/projects/$rslug '$dest'"
    scp -q "$PROJ/$(slug "$from")/$s.jsonl" "$host:~/.claude/projects/$rslug/$s.jsonl"
    ssh "$host" "python3 - '$dest' <<'PY'
import json,os,sys
p=os.path.expanduser('~/.claude.json'); d=os.path.abspath(sys.argv[1])
try: cfg=json.load(open(p))
except Exception: cfg={}
e=cfg.setdefault('projects',{}).setdefault(d,{}); e['hasTrustDialogAccepted']=True
json.dump(cfg,open(p,'w'),indent=2)
PY"
    echo "beamed $(printf %s "$s" | cut -c1-8) -> $host:$dest"
    echo "resume it there with:  ssh $host -t 'cd $dest && claude --resume $s'"
    ;;
  fetch)
    host="${args[0]}"; rcwd="${args[1]}"; s="${args[2]}"
    rslug=$(printf '%s' "$rcwd" | sed 's|/|-|g')
    mkdir -p "$PROJ/$(slug "$from")"
    scp -q "$host:~/.claude/projects/$rslug/$s.jsonl" "$PROJ/$(slug "$from")/$s.jsonl"
    echo "fetched $s from $host; resume: cd $from && claude --resume $s"
    ;;
  *) sed -n '2,14p' "$0"; exit 2;;
esac
