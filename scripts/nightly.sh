#!/bin/bash
# kingstack nightly: roll yesterday's usage and this period's rework into the permanent
# ledgers, because transcripts expire after ~30 days and the history would be lost with them.
# Loaded by launchd as com.hassan.claude-usage-snapshot (00:23).
set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
python3 "$HOME/.claude/scripts/usage-snapshot.py"
python3 "$HOME/.claude/scripts/rework-report.py" --days 14 --snapshot | tail -1
