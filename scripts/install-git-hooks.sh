#!/bin/bash
# Install kingstack's tracked git hooks into .git/hooks (which git never tracks itself).
set -euo pipefail
SRC="$HOME/.claude/scripts/git-hooks"; DST="$HOME/.claude/.git/hooks"
for h in "$SRC"/*; do cp "$h" "$DST/$(basename "$h")"; chmod +x "$DST/$(basename "$h")"; echo "installed $(basename "$h")"; done
