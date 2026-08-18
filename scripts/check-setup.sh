#!/bin/bash
# check-setup: 2-second health check of the whole Claude setup. Exit 0 = healthy, 1 = drift.
# Run after any hook/skill/profile change, or whenever a session behaves oddly.
set -uo pipefail
C="$HOME/.claude"; P="$HOME/.claude-personal"; fail=0
ok(){ printf "✓ %s\n" "$1"; }
bad(){ printf "✗ %s\n" "$1"; fail=1; }

# 1. Profile symlinks: every shared layer resolves to the work profile.
links_ok=1
for f in CLAUDE.md skills agents settings.json projects plugins history.jsonl; do
  if [ -L "$P/$f" ] && [ "$(readlink "$P/$f")" = "$C/$f" ] && [ -e "$P/$f" ]; then :; else bad "personal/$f not a symlink to work profile"; links_ok=0; fi
done
[ "$links_ok" = 1 ] && ok "personal profile: 7 layers symlinked to ~/.claude"

# 2. No stray config in the work dir (a headless run with CLAUDE_CONFIG_DIR set creates it → 'not logged in').
[ -e "$C/.claude.json" ] && bad "stray $C/.claude.json exists (breaks headless login) → rm it" || ok "no stray ~/.claude/.claude.json"

# 3. settings.json valid, both hooks present, superpowers off.
if jq -e . "$C/settings.json" >/dev/null 2>&1; then
  jq -e '.hooks.SessionStart[0].hooks[0].command' "$C/settings.json" >/dev/null 2>&1 && ok "SessionStart hook registered" || bad "SessionStart hook missing"
  jq -e '.hooks.Stop[0].hooks[0].command' "$C/settings.json" >/dev/null 2>&1 && ok "Stop hook registered" || bad "Stop hook missing"
  [ "$(jq -r '.enabledPlugins["superpowers@claude-plugins-official"]' "$C/settings.json")" = "false" ] && ok "superpowers disabled (one front door)" || bad "superpowers enabled: conflicts with pstack"
else bad "settings.json is not valid JSON (ALL settings silently disabled)"; fi

# 4. SessionStart hook actually emits the routing contract naming both modes.
out=$(echo '{}' | bash "$C/hooks/session-start-poteto.sh" 2>/dev/null)
echo "$out" | jq -e '.hookSpecificOutput.additionalContext' >/dev/null 2>&1 && echo "$out" | grep -q poteto-mode && echo "$out" | grep -q king-mode \
  && ok "SessionStart contract emits poteto-mode + king-mode" || bad "SessionStart hook output invalid or missing a mode"

# 4b. Routing ruler present and injected; effort default medium.
[ -f "$C/model-routing.md" ] && echo "$out" | grep -q model-routing && ok "model-routing ruler present and in SessionStart contract" || bad "model-routing ruler missing or not injected"
[ "$(jq -r '.effortLevel // empty' "$C/settings.json")" = "medium" ] && ok "effortLevel medium (main thread)" || bad "effortLevel not medium"

# 5. Critical skills present with frontmatter.
missing=""; for s in poteto-mode king-mode memory-review deslop control-cli control-ui verify-this unslop; do
  head -3 "$C/skills/$s/SKILL.md" 2>/dev/null | grep -q '^name:' || missing="$missing $s"; done
[ -z "$missing" ] && ok "critical skills present ($(ls "$C/skills" | wc -l | tr -d ' ') total)" || bad "missing skills:$missing"

# 5b. No hand-edited generated skills (the next sync would skip them and exit 3).
if [ -s "$C/pstack-manifest.sha256" ]; then
  edited=$( (cd "$C/skills" && shasum -a 256 -c "$C/pstack-manifest.sha256" 2>/dev/null || true) | grep -c "FAILED" || true )
  [ "${edited:-0}" = "0" ] && ok "no hand-edited pstack skills (manifest clean)" || bad "$edited generated file(s) hand-edited → they are protected but drifting; sync-pstack.sh reports which, --force discards"
else bad "pstack manifest missing → run sync-pstack.sh --no-pull to create the clobber guard"; fi

# 5c. node reachable by plugin hooks (they get a minimal PATH; ~/.claude/bin is injected via settings env.PATH).
if [ -x "$C/bin/node" ] && "$C/bin/node" --version >/dev/null 2>&1; then
  case "$(jq -r '.env.PATH // ""' "$C/settings.json")" in *"$C/bin"*) ok "node linked for hooks ($("$C/bin/node" --version)) and on session PATH";; *) bad "~/.claude/bin exists but is not in settings env.PATH";; esac
else bad "node not linked for plugin hooks → scripts/link-node.sh"; fi

# 6. Agents present.
[ -f "$C/agents/poteto-agent.md" ] && [ -f "$C/agents/comment-sicko.md" ] && ok "pstack agents present" || bad "pstack agents missing"

# 7. pstack in sync with upstream checkout; no Cursor-isms leaked.
repo="$HOME/Desktop/Work/plugins"
if [ -d "$repo/pstack" ]; then
  want=$(git -C "$repo" log -1 --format=%h -- pstack/ 2>/dev/null); have=$(head -1 "$C/pstack-upstream.txt" 2>/dev/null)
  [ "$want" = "$have" ] && ok "pstack synced at $have (= upstream checkout)" || bad "pstack stale: installed $have, checkout $want → run sync-pstack.sh"
  leak=$(grep -rl "disable-model-invocation: true\|~/\.cursor\|generalPurpose" "$C/skills/poteto-mode" "$C/skills/unslop" 2>/dev/null | wc -l | tr -d ' ')
  [ "$leak" = "0" ] && ok "no Cursor-isms in pstack skills" || bad "$leak pstack files contain Cursor-isms"
else bad "plugins checkout missing at $repo"; fi

# 8. Memory system: distiller + inbox module + tests green.
[ -x "$C/hooks/session-memory-distiller.py" ] || [ -f "$C/hooks/session-memory-distiller.py" ] && ok "memory distiller present" || bad "memory distiller missing"
t=$(python3 "$C/hooks/test_memory_inbox.py" 2>&1 | tail -1); echo "$t" | grep -q "0 failed" && ok "memory inbox tests: $t" || bad "memory inbox tests failing: $t"

# 9. Biweekly king-mode refresh scheduled.
launchctl print "gui/$(id -u)/com.hassan.king-mode-refresh" >/dev/null 2>&1 && ok "launchd king-mode refresh loaded" || bad "launchd king-mode refresh not loaded"

# 9b. Nightly usage snapshot scheduled and ledger fresh (within 2 days).
launchctl print "gui/$(id -u)/com.hassan.claude-usage-snapshot" >/dev/null 2>&1 && ok "launchd usage snapshot loaded" || bad "launchd usage snapshot not loaded"
if [ -f "$C/usage-ledger.csv" ]; then
  last=$(tail -1 "$C/usage-ledger.csv" | cut -d, -f1); cutoff=$(date -v-2d +%Y-%m-%d)
  [ "$last" \> "$cutoff" ] || [ "$last" = "$cutoff" ] && ok "usage ledger fresh (last day $last)" || bad "usage ledger stale (last day $last)"
else bad "usage ledger missing"; fi
if [ -f "$C/rework-ledger.csv" ]; then ok "rework ledger present ($(( $(wc -l < "$C/rework-ledger.csv") - 1 )) rows)"; else bad "rework ledger missing → scripts/rework-report.py --snapshot"; fi

# 9c. kingstack repo: is a git repo, no untracked-but-allowlisted files, no secrets tracked.
if git -C "$C" rev-parse --git-dir >/dev/null 2>&1; then
  dirty=$(git -C "$C" status --short | wc -l | tr -d ' ')
  [ "$dirty" = "0" ] && ok "kingstack repo clean" || bad "kingstack repo has $dirty uncommitted change(s): commit them"
  git -C "$C" ls-files | grep -qE "credentials|\.claude\.json|history\.jsonl|usage\.db|/projects/" && bad "SECRET/RUNTIME FILE TRACKED IN GIT" || ok "no secrets or runtime state tracked"
else bad "~/.claude is not a git repo"; fi

# 9d. kingstack behind its own remote? (verify.sh pattern from minions: check installed vs git ls-remote)
if git -C "$C" rev-parse --git-dir >/dev/null 2>&1; then
  local_head=$(git -C "$C" rev-parse HEAD 2>/dev/null); remote_head=$(git -C "$C" ls-remote origin main 2>/dev/null | cut -f1)
  if [ -n "$remote_head" ]; then
    [ "$local_head" = "$remote_head" ] && ok "kingstack in sync with origin/main" || bad "kingstack differs from origin/main → git -C ~/.claude pull (or push)"
  fi
fi

# 10. Scripts executable.
exec_ok=1
for s in sync-pstack.sh refresh-king-mode.sh measure.ts usage-report.py usage-snapshot.py \
         rework-report.py nightly.sh run-sweeps.sh beam.sh box-task.sh install-launchd.sh link-node.sh; do
  [ -x "$C/scripts/$s" ] || { bad "$C/scripts/$s not executable"; exec_ok=0; }
done
[ "$exec_ok" = 1 ] && ok "all 12 helper scripts executable"

# 11. Pending memory review nudge (informational, never fails).
pend=$(grep -c '^- \[ \]' "$C/memory-review.md" 2>/dev/null | head -1 || true); pend=${pend:-0}
[ "$pend" -gt 0 ] && printf "ℹ %s pending memory candidate(s): run /memory-review\n" "$pend"

[ $fail = 0 ] && echo "SETUP HEALTHY" || echo "SETUP DRIFT DETECTED"
exit $fail
