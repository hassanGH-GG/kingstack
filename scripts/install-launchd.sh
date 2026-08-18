#!/bin/bash
# Install (or reload) kingstack's launchd schedules from the repo copies.
set -euo pipefail
for p in "$HOME/.claude/launchd/"*.plist; do
  label=$(basename "$p" .plist)
  cp "$p" "$HOME/Library/LaunchAgents/$label.plist"
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/$label.plist"
  echo "loaded $label"
done
