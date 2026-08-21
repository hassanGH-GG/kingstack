#!/bin/bash
# Biweekly king-mode refresh. Runs headless via launchd (com.hassan.king-mode-refresh) on the
# 1st and 15th. Mines transcripts since the last refresh and revises ~/.claude/skills/king-mode
# through the automate-me update flow. Backs up first and rolls back an invalid result.
#
#   refresh-king-mode.sh              # mine and write
#   refresh-king-mode.sh --dry-run    # mine and print the changelog, write nothing
#
# Model: the synthesis session does judgment work, so it runs on KINGSTACK_REFRESH_MODEL
# (default opus). Its miner subagents do bulk extraction, which is haiku work per
# ~/.claude/model-routing.md. Do not hardcode a model here: an unattended job must not die
# because one tier ran out of credits.
set -uo pipefail
KINGSTACK_ROOT="${KINGSTACK_ROOT:-$HOME/Desktop/Work/kingstack}"
if ! PYTHONPATH="$KINGSTACK_ROOT/lib" python3 -c "from kingstack.schedule_lock import claim; claim('com.hassan.king-mode-refresh', 'launchd')"; then
  echo "duplicate prevented"
  exit 0
fi
# PATH (including node for plugin hooks) and claude_retry come from the shared library.
# Do NOT set CLAUDE_CONFIG_DIR: the login lives in ~/.claude.json and the default resolves it.
. "$KINGSTACK_ROOT/scripts/lib-headless.sh"

SKILL="$HOME/.claude/skills/king-mode/SKILL.md"
STAMP="$HOME/.claude/king-mode-last-refresh.txt"
LOG="$HOME/.claude/logs/king-mode-refresh.log"
BACKUP_DIR="$HOME/.claude/skills/king-mode/.history"
MODEL="${KINGSTACK_REFRESH_MODEL:-opus}"
dry=0
[ "${1:-}" = "--dry-run" ] && dry=1
mkdir -p "$BACKUP_DIR" "$(dirname "$LOG")"

since=$(cat "$STAMP" 2>/dev/null || date -v-14d +%Y-%m-%d)
now=$(date +%Y-%m-%d)

if [ "$dry" = 0 ]; then
  cp "$SKILL" "$BACKUP_DIR/SKILL.$now.md"
  write_clause="Then edit $SKILL in place: preserve sections he has not contradicted, revise ones with new evidence, add a section only for a genuinely new recurring rule, and remove a rule the new evidence contradicts. Apply the unslop skill to every line you change. Preserve the frontmatter exactly (name king-mode, description as a single YAML scalar)."
else
  write_clause="Do NOT edit any file. This is a dry run: report only."
fi

{
echo "=== king-mode refresh $now (transcripts since $since, model $MODEL, dry=$dry) ==="
cd "$HOME"
claude_retry 4 30 -- -p --model "$MODEL" --permission-mode acceptEdits --max-turns 60 \
"You are running the scheduled refresh of Hassan's personal king-mode skill. Follow the automate-me skill's UPDATE flow (invoke the Skill tool with 'automate-me' first and follow it) against the existing skill at $SKILL. Do NOT start fresh.

Evidence: mine ONLY Hassan's own typed prompts from transcripts modified since $since under $HOME/.claude/projects/*/ (he owns every project there and asked for cross-project mining). Take only records whose promptSource is typed or suggestion_accepted; skip agent-to-agent prompts, skill injections, and any prompt that opens by assigning a role. Split the transcripts into slices and run parallel miner subagents on model haiku, since extraction is mechanical work; keep only patterns that appear in two or more slices or that clearly extend a rule king-mode already has.

Weight recent evidence by what it says about how he works, not what he happened to be working on. A fortnight spent on one subject is not a preference.

$write_clause

Never duplicate anything already in $HOME/.claude/CLAUDE.md; read it first. Never copy a secret out of a transcript. There is no human to ask, so skip automate-me's question step and proceed on the evidence. Finish by printing a changelog: rules added, revised and removed, each with the sessions behind it. If the evidence since $since is too thin to justify a change, say exactly that and change nothing." 2>&1
rc=$?
echo "=== exit $rc ==="
} >> "$LOG" 2>&1

if [ "$dry" = 1 ]; then
  echo "dry run complete; changelog in $LOG (nothing written)"
  exit ${rc:-0}
fi

if [ "${rc:-1}" = "0" ]; then
  echo "$now" > "$STAMP"
  # Roll back anything that is not a valid skill: missing frontmatter fence, no name or
  # description key, or implausibly short. A bad refresh must never survive to a session.
  bad=""
  head -1 "$SKILL" | grep -q '^---$' || bad="no opening frontmatter fence"
  grep -q '^name: king-mode' "$SKILL" || bad="${bad:-missing name key}"
  grep -q '^description:' "$SKILL" || bad="${bad:-missing description key}"
  [ "$(wc -l < "$SKILL")" -ge 20 ] || bad="${bad:-file too short}"
  if [ -n "$bad" ]; then
    cp "$BACKUP_DIR/SKILL.$now.md" "$SKILL"
    echo "ROLLED BACK ($bad); restored $BACKUP_DIR/SKILL.$now.md" | tee -a "$LOG"
    exit 4
  fi
  echo "refresh applied; diff with: git -C $HOME/.claude diff skills/king-mode"
fi
