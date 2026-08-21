#!/bin/bash
# Sync pstack (+ its cursor-team-kit deps and the adopted extras) from the cursor/plugins
# checkout into ~/.claude, reapplying the Cursor -> Claude Code adaptations. Idempotent.
# king-mode and memory-review are never touched.
#
#   sync-pstack.sh              # pull upstream + sync
#   sync-pstack.sh --no-pull    # sync from the current checkout
#   sync-pstack.sh --force      # overwrite even skills that were edited by hand
#
# CLOBBER GUARD: every file this script installs is recorded in pstack-manifest.sha256.
# On the next run, any installed file whose hash no longer matches (edited, or deleted)
# marks its whole skill as hand-edited; that skill is SKIPPED, never overwritten, and the
# run exits 3 so it is visible. Use --force to discard the edits deliberately.
set -euo pipefail

REPO="${PSTACK_REPO:-$HOME/Desktop/Work/plugins}"
SRC="$REPO/pstack"
TK="$REPO/cursor-team-kit/skills"
DST="$HOME/.claude/skills"
AGENTS="$HOME/.claude/agents"
STAMP="$HOME/.claude/pstack-upstream.txt"
MANIFEST="$HOME/.claude/pstack-manifest.sha256"

pull=1; force=0
for a in "$@"; do case "$a" in --no-pull) pull=0;; --force) force=1;; esac; done

[ -d "$SRC" ] || { echo "no pstack at $SRC" >&2; exit 1; }
[ "$pull" = 1 ] && git -C "$REPO" pull --ff-only --quiet

before=$(head -1 "$STAMP" 2>/dev/null || echo none)
after=$(git -C "$REPO" log -1 --format=%h -- pstack/)

DEPS="deslop control-cli control-ui"
EXTRAS="verify-this=$TK/verify-this
make-pr-easy-to-review=$TK/make-pr-easy-to-review
cli-for-agents=$REPO/cli-for-agent/skills/cli-for-agents
thermo-nuclear-review=$REPO/thermos/skills/thermo-nuclear-review
thermo-nuclear-code-quality-review=$REPO/thermos/skills/thermo-nuclear-code-quality-review"

# Install plan: "<name>\t<source dir>", one per line, across all three tiers.
plan=$(
  for d in "$SRC"/skills/*/; do n=$(basename "$d"); [ "$n" = "setup-pstack" ] && continue; printf '%s\t%s\n' "$n" "${d%/}"; done
  for dep in $DEPS; do printf '%s\t%s\n' "$dep" "$TK/$dep"; done
  printf '%s\n' "$EXTRAS" | while IFS='=' read -r n s; do [ -n "$n" ] && printf '%s\t%s\n' "$n" "$s"; done
)
names=$(printf '%s\n' "$plan" | cut -f1)

# --- clobber guard: hash what is on disk now, compare against what we installed last time
cur=$(mktemp); trap 'rm -f "$cur"' EXIT
( cd "$DST" && printf '%s\n' $names | while read -r n; do [ -d "$n" ] && find "$n" -type f; done \
  | tr '\n' '\0' | xargs -0 shasum -a 256 2>/dev/null ) | sort > "$cur" || true

protected=""
if [ -s "$MANIFEST" ] && [ "$force" = 0 ]; then
  for n in $names; do
    [ -d "$DST/$n" ] || continue
    a=$(grep -E "^[0-9a-f]{64}  $n/" "$cur" 2>/dev/null | sort || true)
    b=$(grep -E "^[0-9a-f]{64}  $n/" "$MANIFEST" 2>/dev/null | sort || true)
    [ -z "$b" ] && continue                 # never installed by us: nothing to protect
    [ "$a" = "$b" ] || protected="$protected $n"
  done
fi
is_protected(){ case " $protected " in *" $1 "*) return 0;; *) return 1;; esac; }

# --- install
synced=0; nextras=0; ndeps=0
while IFS=$'\t' read -r n src; do
  [ -z "$n" ] && continue
  [ -d "$src" ] || { echo "missing source for $n: $src" >&2; exit 1; }
  is_protected "$n" && continue
  rm -rf "$DST/$n"; cp -R "$src" "$DST/$n"
  case " $DEPS " in *" $n "*) ndeps=$((ndeps+1));; *) if printf '%s\n' "$EXTRAS" | grep -q "^$n="; then nextras=$((nextras+1)); else synced=$((synced+1)); fi;; esac
done <<< "$plan"
cp "$SRC"/agents/*.md "$AGENTS"/

# --- prune skills upstream deleted (never touch deps, extras, or anything of mine)
if [ -f "$STAMP" ]; then
  while IFS= read -r old || [ -n "$old" ]; do
    [ -z "$old" ] && continue
    printf '%s\n' "$names" | grep -qx "$old" && continue
    [ -d "$SRC/skills/$old" ] || { rm -rf "$DST/$old"; echo "removed upstream-deleted skill: $old"; }
  done < <(tail -n +2 "$STAMP")
fi

# --- adaptations over every installed dir (skills, deps AND extras)
targets=()
for n in $names; do is_protected "$n" || targets+=("$DST/$n"); done
if [ ${#targets[@]} -gt 0 ]; then
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
fi
# Per-skill adaptations: scratch dir for verify-this, Hassan's 500-line threshold.
is_protected verify-this || perl -pi -e 's{/tmp/verify-this/}{\$TMPDIR/verify-this/}g' "$DST/verify-this/SKILL.md"
is_protected thermo-nuclear-code-quality-review || perl -pi -e 's/\b1k lines\b/500 lines/g; s/\b1,?000 lines\b/500 lines/g; s/past 1k lines/past 500 lines/g; s/from under 1k/from under 500/g; s/over 1k lines/over 500 lines/g; s/below 1000 lines to above 1000 lines/below 500 lines to above 500 lines/g' "$DST/thermo-nuclear-code-quality-review/SKILL.md"
is_protected automate-me || perl -pi -e 's/- Frontmatter `disable-model-invocation: true` by default\. Mode skills are heavy and opinionated; they should only apply when the user explicitly invokes them \(by name or slash command\), not auto-trigger on description matching\./- Mode skills are heavy and opinionated; write the description so they only apply when the user explicitly invokes them (by name or slash command), e.g. "Use only for \/<name>-mode", not on loose description matching./' "$DST/automate-me/SKILL.md" 2>/dev/null || true

# --- Local edits (mine, never upstream's). Two kinds, both idempotent by a grep guard.
# 1. Section appends: one snippet per file in scripts/pstack-local-edits/, named
#    <target-key>--<slug>.md, whose FIRST line is an HTML comment marker. The case statement
#    below maps <target-key> to the file it lands in. Appended only when the marker is absent,
#    so a second sync is a no-op. New local edit = new snippet + new case arm.
# 2. Description tunes: guarded perl rewrites of a `description:` frontmatter line, so the
#    skill also fires on triggers upstream's wording misses.
LOCAL_EDITS="$HOME/.claude/scripts/pstack-local-edits"
for snip in "$LOCAL_EDITS"/*.md; do
  [ -f "$snip" ] || continue
  key=${snip##*/}; key=${key%%--*}
  case "$key" in
    control-cli)              skill=control-cli;              target="$DST/control-cli/SKILL.md";;
    principle-prove-it-works) skill=principle-prove-it-works; target="$DST/principle-prove-it-works/SKILL.md";;
    runtime-forensics)        skill=poteto-mode;              target="$DST/poteto-mode/playbooks/runtime-forensics.md";;
    *) echo "local edit snippet has no target mapping: $snip" >&2; exit 1;;
  esac
  is_protected "$skill" && continue
  [ -f "$target" ] || { echo "local edit target missing: $target" >&2; exit 1; }
  marker=$(head -1 "$snip")
  grep -qF "$marker" "$target" || { printf '\n'; cat "$snip"; } >> "$target"
done

# Description tunes, one per line, each a no-op once its distinctive phrase is present.
is_protected control-cli || grep -q 'feels laggy or clunky' "$DST/control-cli/SKILL.md" || perl -pi -e 's/(terminal demos\.)/$1 Also use when a TUI feels laggy or clunky, when a key does not work in the user\x27s terminal, when something works in tests but not in their terminal, or when asked to UI test the terminal./ if /^description:/' "$DST/control-cli/SKILL.md"
is_protected create-verification-skill || grep -q 'hand-rolled a PTY or browser harness twice' "$DST/create-verification-skill/SKILL.md" || perl -pi -e 's/(behavior\.)"/$1 Also use when the session has already hand-rolled a PTY or browser harness twice for the same app."/ if /^description:/' "$DST/create-verification-skill/SKILL.md"
is_protected blast-radius || grep -q 'shared namespace' "$DST/blast-radius/SKILL.md" || perl -pi -e 's/(trust\.)"/$1 Also use when adding a name to a shared namespace (slash command, keybinding, route, CLI flag), where the check is prefix, abbreviation, and ranking collisions against existing siblings rather than the new entry in isolation."/ if /^description:/' "$DST/blast-radius/SKILL.md"
is_protected reflect || grep -q 'not able to nail this down' "$DST/reflect/SKILL.md" || perl -pi -e 's/(says reflect\.)/$1 Also fires on "we need to reflect", "let\x27s reflect on why we keep missing this", or "we\x27re not able to nail this down" after repeated fix waves, not only the bare \/reflect command./ if /^description:/' "$DST/reflect/SKILL.md"

# --- verify no Cursor-isms survive
left=0
[ ${#targets[@]} -gt 0 ] && left=$(grep -rl "disable-model-invocation: true\|~/\.cursor\|generalPurpose\|sol-max\|grok-4\.[0-9]-fast" "${targets[@]}" 2>/dev/null | wc -l | tr -d ' ' || true)

# --- record what we installed (post-adaptation) so the next run can detect hand edits.
# For a protected dir we keep the PREVIOUS entries, never the edited ones, so the edit stays
# protected on every later run instead of being adopted into the manifest and clobbered next time.
newman=$(mktemp)
( cd "$DST" && printf '%s\n' $names | while read -r n; do [ -d "$n" ] && find "$n" -type f; done \
  | tr '\n' '\0' | xargs -0 shasum -a 256 2>/dev/null ) | sort > "$newman" || true
if [ -n "$protected" ] && [ -s "$MANIFEST" ]; then
  for n in $protected; do
    grep -vE "^[0-9a-f]{64}  $n/" "$newman" > "$newman.keep" 2>/dev/null || true
    mv "$newman.keep" "$newman"
    grep -E "^[0-9a-f]{64}  $n/" "$MANIFEST" >> "$newman" 2>/dev/null || true
  done
  sort -o "$newman" "$newman"
fi
mv "$newman" "$MANIFEST"

{ echo "$after"; printf '%s\n' "$names"; } > "$STAMP"

echo "pstack synced: $synced skills + $ndeps deps + $nextras extras + 2 agents | upstream $before -> $after | cursor-isms: $left"
rc=0
if [ -n "$protected" ]; then
  echo "PROTECTED (hand-edited, not overwritten):$protected" >&2
  echo "  inspect with: git -C $REPO diff --no-index $SRC/skills/<name> $DST/<name>" >&2
  echo "  discard your edits and take upstream: sync-pstack.sh --force" >&2
  rc=3
fi
[ "$left" = "0" ] || { echo "WARNING: adaptations incomplete" >&2; rc=2; }
exit $rc
