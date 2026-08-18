#!/bin/bash
# Biweekly king-mode refresh. Runs headless via launchd (com.hassan.king-mode-refresh).
# Mines transcripts since the last refresh and updates ~/.claude/skills/king-mode/SKILL.md
# via the automate-me procedure. Backs up the previous version first; logs to ~/.claude/logs.
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
# Do NOT set CLAUDE_CONFIG_DIR: the work login lives in ~/.claude.json and the default resolves it.

SKILL="$HOME/.claude/skills/king-mode/SKILL.md"
STAMP="$HOME/.claude/king-mode-last-refresh.txt"
LOG="$HOME/.claude/logs/king-mode-refresh.log"
BACKUP_DIR="$HOME/.claude/skills/king-mode/.history"
mkdir -p "$BACKUP_DIR"

since=$(cat "$STAMP" 2>/dev/null || date -v-14d +%Y-%m-%d)
now=$(date +%Y-%m-%d)
cp "$SKILL" "$BACKUP_DIR/SKILL.$now.md"

{
echo "=== king-mode refresh $now (transcripts since $since) ==="
cd "$HOME"
claude -p --model fable --permission-mode acceptEdits --max-turns 60 \
"You are running the scheduled biweekly refresh of Hassan's personal king-mode skill. Follow the automate-me skill's UPDATE flow (invoke the Skill tool with 'automate-me' first and follow it), in update mode against the existing skill at $SKILL. Do NOT start fresh.

Evidence: mine ONLY Hassan's typed prompts from transcripts modified since $since under $HOME/.claude/projects/*/ (all his projects; he owns them all and asked for cross-project mining). Extract only records with promptSource typed or suggestion_accepted; skip agent-to-agent prompts, skill injections, and anything starting 'You are a'. Split into slices and run parallel miner subagents (model fable) hunting the same signals automate-me lists; keep only patterns seen in 2+ slices or that clearly extend an existing king-mode rule.

Then edit $SKILL in place: preserve sections he has not contradicted, revise ones with new evidence, add sections only for genuinely new recurring rules, remove rules the new evidence contradicts. Keep it operational and dense. Apply the unslop skill to every changed line. Never duplicate anything already in $HOME/.claude/CLAUDE.md (read it). Never echo any secret from transcripts into the file. Preserve the frontmatter (name king-mode, description a single YAML scalar).

There is no human to ask, so skip automate-me's AskQuestion step and proceed on evidence alone. When done, print a short changelog: rules added / revised / removed with the session evidence behind each. If the evidence since $since is too thin to justify any change, say so and leave the file untouched." 2>&1
rc=$?
echo "=== exit $rc ==="
} >> "$LOG" 2>&1

if [ "$rc" = "0" ]; then
  echo "$now" > "$STAMP"
  # Sanity: frontmatter still valid, file non-empty; else roll back.
  if ! head -1 "$SKILL" | grep -q '^---$' || [ "$(wc -l < "$SKILL")" -lt 20 ]; then
    cp "$BACKUP_DIR/SKILL.$now.md" "$SKILL"
    echo "ROLLED BACK: refresh produced an invalid file" >> "$LOG"
  fi
fi
