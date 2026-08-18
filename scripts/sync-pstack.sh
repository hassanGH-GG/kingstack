#!/bin/bash
# Sync pstack from the cursor/plugins checkout into ~/.claude, reapplying the
# Cursor -> Claude Code adaptations. Idempotent. king-mode is never touched.
#
#   ~/.claude/scripts/sync-pstack.sh            # pull upstream + sync
#   ~/.claude/scripts/sync-pstack.sh --no-pull  # sync from current checkout
set -euo pipefail

REPO="${PSTACK_REPO:-$HOME/Desktop/Work/plugins}"
SRC="$REPO/pstack"
DST="$HOME/.claude/skills"
AGENTS="$HOME/.claude/agents"
STAMP="$HOME/.claude/pstack-upstream.txt"

[ -d "$SRC" ] || { echo "no pstack at $SRC" >&2; exit 1; }

if [ "${1:-}" != "--no-pull" ]; then
  git -C "$REPO" pull --ff-only --quiet
fi

before=$(cat "$STAMP" 2>/dev/null | head -1 || echo none)
after=$(git -C "$REPO" log -1 --format=%h -- pstack/)

# Skills: mirror every upstream skill except Cursor-only setup-pstack.
synced=0
for d in "$SRC"/skills/*/; do
  n=$(basename "$d")
  [ "$n" = "setup-pstack" ] && continue
  rm -rf "$DST/$n"
  cp -R "$d" "$DST/$n"
  synced=$((synced+1))
done
cp "$SRC"/agents/*.md "$AGENTS"/

# pstack's declared cross-plugin dependencies: poteto-mode invokes these cursor-team-kit
# skills by name (deslop before commit, control-cli/control-ui for verification).
TK="$REPO/cursor-team-kit/skills"
for dep in deslop control-cli control-ui; do
  [ -d "$TK/$dep" ] || { echo "missing pstack dependency $TK/$dep" >&2; exit 1; }
  rm -rf "$DST/$dep"; cp -R "$TK/$dep" "$DST/$dep"
done

# Prune skills that upstream removed (only ones we own: those present in a prior stamp list).
if [ -f "$STAMP" ]; then
  while IFS= read -r old || [ -n "$old" ]; do
    [ -z "$old" ] && continue
    case "$old" in deslop|control-cli|control-ui|verify-this|make-pr-easy-to-review|cli-for-agents|thermo-nuclear-review|thermo-nuclear-code-quality-review) continue;; esac
    if [ ! -d "$SRC/skills/$old" ]; then rm -rf "$DST/$old"; echo "removed upstream-deleted skill: $old"; fi
  done < <(tail -n +2 "$STAMP")
fi

# Adopted extras from sibling packs (Hassan's picks, 2026-08-18): verification protocol,
# reviewer rubrics, agent-CLI checklist, PR reviewability. Same rerunnable path as pstack.
EXTRAS="verify-this=$REPO/cursor-team-kit/skills/verify-this
make-pr-easy-to-review=$REPO/cursor-team-kit/skills/make-pr-easy-to-review
cli-for-agents=$REPO/cli-for-agent/skills/cli-for-agents
thermo-nuclear-review=$REPO/thermos/skills/thermo-nuclear-review
thermo-nuclear-code-quality-review=$REPO/thermos/skills/thermo-nuclear-code-quality-review"
nextras=0
while IFS='=' read -r name src; do
  [ -z "$name" ] && continue
  [ -d "$src" ] || { echo "missing adopted extra $src" >&2; exit 1; }
  rm -rf "$DST/$name"; cp -R "$src" "$DST/$name"; targets+=("$DST/$name"); nextras=$((nextras+1))
done <<< "$EXTRAS"
# Extra-specific adaptations: scratch dir, and Hassan's 500-line decomposition threshold.
perl -pi -e 's{/tmp/verify-this/}{\$TMPDIR/verify-this/}g' "$DST/verify-this/SKILL.md"
perl -pi -e 's/\b1k lines\b/500 lines/g; s/\b1,?000 lines\b/500 lines/g; s/past 1k lines/past 500 lines/g; s/from under 1k/from under 500/g; s/over 1k lines/over 500 lines/g; s/below 1000 lines to above 1000 lines/below 500 lines to above 500 lines/g' "$DST/thermo-nuclear-code-quality-review/SKILL.md"

# Adaptations. Every rule here is a Cursor-ism with a Claude Code equivalent.
targets=()
for d in "$SRC"/skills/*/; do n=$(basename "$d"); [ "$n" = "setup-pstack" ] && continue; targets+=("$DST/$n"); done
for dep in deslop control-cli control-ui; do targets+=("$DST/$dep"); done
find "${targets[@]}" "$AGENTS/poteto-agent.md" "$AGENTS/comment-sicko.md" \
  -type f \( -name "*.md" -o -name "*.ts" -o -name "*.sh" \) -exec perl -pi -e '
    s/^disable-model-invocation: true\n//;
    s/^is_background: true\n//;
    s/claude-fable-5-thinking-max/fable/g;
    s/grok-4\.\d+-fast-xhigh/haiku/g;
    s/gpt-5\.\d+-sol-max/opus/g;
    s/claude-opus-5-thinking-xhigh/opus/g;
    s/generalPurpose/general-purpose/g;
    s{~/\.cursor/rules/pstack-models\.mdc}{~/.claude/pstack-models.md}g;
    s{\$HOME/\.cursor/projects/\$slug/agent-transcripts}{\$HOME/.claude/projects/\$slug}g;
    s{~/\.cursor/projects}{~/.claude/projects}g;
    s{~/\.cursor/skills}{~/.claude/skills}g;
    s{~/\.cursor/plugins}{~/.claude/plugins}g;
    s{\.cursor/worktrees}{.claude/worktrees}g;
    s{\.cursor/skills}{.claude/skills}g;
    s/\bCursor\b/Claude Code/g;
  ' {} +
# automate-me documents the Cursor-only frontmatter flag in prose; rephrase.
perl -pi -e 's/- Frontmatter `disable-model-invocation: true` by default\. Mode skills are heavy and opinionated; they should only apply when the user explicitly invokes them \(by name or slash command\), not auto-trigger on description matching\./- Mode skills are heavy and opinionated; write the description so they only apply when the user explicitly invokes them (by name or slash command), e.g. "Use only for \/<name>-mode", not on loose description matching./' "$DST/automate-me/SKILL.md" 2>/dev/null || true

# Verify: no Cursor-isms survive.
left=$(grep -rl "disable-model-invocation: true\|~/\.cursor\|generalPurpose\|sol-max\|grok-4\.[0-9]-fast" "${targets[@]}" 2>/dev/null | wc -l | tr -d ' ' || true)

# Stamp: first line = upstream commit, rest = synced skill names (for future prune).
{ echo "$after"; for t in "${targets[@]}"; do basename "$t"; done; } > "$STAMP"

echo "pstack synced: $synced skills + 3 team-kit deps + $nextras adopted extras + 2 agents | upstream $before -> $after | leftover cursor-isms: $left"
[ "$left" = "0" ] || { echo "WARNING: adaptations incomplete, inspect the files above" >&2; exit 2; }
