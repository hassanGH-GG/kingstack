#!/bin/bash
# Give scheduled jobs and plugin hooks a stable path to node.
#
# Hooks are spawned with a minimal environment whose PATH is roughly
# /usr/gnu/bin:/usr/local/bin:/bin:/usr/bin, none of which contains an nvm node, so any plugin
# hook that shells out to node fails with "node: command not found" on every unattended run.
# System directories need sudo, so kingstack owns ~/.claude/bin instead and injects it through
# settings.json env.PATH. Re-run this after switching node versions with nvm.
set -euo pipefail
BIN="$HOME/.claude/bin"; mkdir -p "$BIN"
# Prefer nvm's default alias, then whatever is on the interactive PATH, then the newest install.
ver=$(cat "$HOME/.nvm/alias/default" 2>/dev/null || true)
src=""
[ -n "$ver" ] && [ -x "$HOME/.nvm/versions/node/v$ver/bin/node" ] && src="$HOME/.nvm/versions/node/v$ver/bin"
[ -z "$src" ] && [ -n "$ver" ] && [ -x "$HOME/.nvm/versions/node/$ver/bin/node" ] && src="$HOME/.nvm/versions/node/$ver/bin"
[ -z "$src" ] && command -v node >/dev/null 2>&1 && src=$(dirname "$(command -v node)")
[ -z "$src" ] && src=$(ls -td "$HOME"/.nvm/versions/node/*/bin 2>/dev/null | head -1)
[ -n "$src" ] && [ -x "$src/node" ] || { echo "no node found to link" >&2; exit 1; }
for b in node npm npx; do [ -x "$src/$b" ] && ln -sf "$src/$b" "$BIN/$b"; done
echo "linked $BIN -> $src ($("$BIN/node" --version))"
