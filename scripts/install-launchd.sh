#!/bin/bash
# Install (or reload) kingstack's launchd schedules from the repo copies, and list any
# com.hassan.* plist in ~/Library/LaunchAgents that the repo does NOT track (a stray job
# that came back to life is a real incident; only tracked units get loaded).
set -euo pipefail
REPO="${KINGSTACK_ROOT:-$HOME/Desktop/Work/kingstack}/launchd"; LA="$HOME/Library/LaunchAgents"
for p in "$REPO"/*.plist; do
  label=$(basename "$p" .plist)
  cp "$p" "$LA/$label.plist"
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$LA/$label.plist"
  echo "loaded $label"
done
for p in "$LA"/com.hassan.*.plist; do
  [ -f "$REPO/$(basename "$p")" ] || echo "STRAY (not in repo, not loaded by this script): $p"
done
